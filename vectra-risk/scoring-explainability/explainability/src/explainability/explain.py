"""`POST /v1/explanations` (BR-U7-08 a 11; P-U7-01, 04, 05; US-104, US-105, US-111).

Con la cache fria, el diccionario (F103) y `:explain` (F22) corren a la vez en un `asyncio.TaskGroup`; si uno falla, el otro se
cancela. Despues, en orden: verificacion de version (BR-U7-08), cobertura del diccionario (BR-U7-09), narrativa (BR-U7-10) y
factualidad (BR-U7-11). Todo dentro de `min(deadline - 50 ms, llegada + 700 ms)` (P-U7-01): una cabecera manipulada no extiende
el presupuesto. Los errores son los de domain-entities §5.
"""

import asyncio
import json
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from pydantic import BaseModel, ValidationError
from vectra_common import deps
from vectra_common.deps import DependencyClient
from vectra_common.errors import (
    ConflictState,
    DependencyTimeout,
    DependencyUnavailable,
    UnprocessableExplanation,
    VectraError,
)
from vectra_contracts.catalog import ProblemReason
from vectra_contracts.dictionary import covers
from vectra_contracts.models.api import ExplainRequest
from vectra_contracts.models.explanation import Explanation
from vectra_contracts.models.features import FeatureContribution, FeatureDictionary

from explainability.config import DEADLINE_MARGIN_MS, EXPLAIN_TIMEOUT_MS, OWN_CEILING_MS
from explainability.dictionary_cache import DictionaryCache
from explainability.factuality import FactualityValidator
from explainability.metrics import DEADLINE_EXHAUSTED, EXPLANATIONS, timed
from explainability.narrative import FeatureDictionaryIncomplete, TemplateNarrativeGenerator

OK = 200
SERVER_ERROR = 500
Clock = Callable[[], datetime]


class _Contribution(BaseModel):
    feature_id: str
    contribution: float


class _Explained(BaseModel):
    contributions: list[_Contribution]
    base_value: float
    model_version_id: str


class _Response(BaseModel):
    explanations: list[_Explained]


def _decimal(value: float) -> str:
    """Un `float` de KServe como `DecimalStr`, sin notacion cientifica."""
    return format(Decimal(repr(value)), "f")


def result_of(error: BaseException | None) -> str:
    """La etiqueta `result` de `vectra_explanations_total` (P-U7-08)."""
    if error is None:
        return "ok"
    if isinstance(error, DependencyTimeout):
        return "timeout"
    if isinstance(error, DependencyUnavailable):
        return "unavailable"
    if isinstance(error, VectraError) and error.reason is not None:
        return error.reason.value
    return "error"


def _first_leaf(group: BaseExceptionGroup[BaseException]) -> BaseException:
    leaf = group.exceptions[0]
    return _first_leaf(leaf) if isinstance(leaf, BaseExceptionGroup) else leaf


class Explainer:
    """Un cliente por dependencia (P-U7-04): `explain_client` (F22, pool 20) y el de la cache del diccionario (F103, pool 5).

    `url_template` lleva `{inference_service}`: el `Service` de KServe del `inference_service` que scoring copio de `serving-config`.
    """

    def __init__(
        self,
        explain_client: DependencyClient,
        dictionary_cache: DictionaryCache,
        generator: TemplateNarrativeGenerator,
        validator: FactualityValidator,
        url_template: str,
        clock: Clock = lambda: datetime.now(UTC),
    ) -> None:
        self._client = explain_client
        self._dictionaries = dictionary_cache
        self._generator = generator
        self._validator = validator
        self._url_template = url_template
        self._clock = clock

    def _cutoff(self, arrival: datetime, deadline: datetime | None) -> datetime:
        """`min(deadline - 50 ms, llegada + 700 ms)`; sin cabecera (o mal formada), solo el tope propio."""
        cutoff = arrival + timedelta(milliseconds=OWN_CEILING_MS)
        if deadline is not None:
            cutoff = min(cutoff, deadline - timedelta(milliseconds=DEADLINE_MARGIN_MS))
        return cutoff

    async def _kserve(self, request: ExplainRequest, cutoff: datetime) -> _Explained:
        base = self._url_template.format(inference_service=request.inference_service)
        body = {"instances": [request.features.model_dump(mode="json")]}
        async with timed("explain"):
            response = await deps.call(
                self._client,
                "POST",
                f"{base}/v1/models/{request.inference_service}:explain",
                timeout=EXPLAIN_TIMEOUT_MS / 1000,
                deadline=cutoff,
                headers={"content-type": "application/json"},
                content=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            )
        if response.status_code >= SERVER_ERROR:
            raise DependencyUnavailable()  # 503 por saturacion o rollout de KServe (P-U6-05)
        if response.status_code != OK:
            raise VectraError()  # un 4xx del explicador es un defecto, no una caida
        try:
            parsed = _Response.model_validate_json(response.content)
        except ValidationError as exc:
            raise VectraError() from exc
        if len(parsed.explanations) != 1:
            raise VectraError()
        return parsed.explanations[0]

    async def _gather(
        self, request: ExplainRequest, cutoff: datetime
    ) -> tuple[FeatureDictionary, _Explained]:
        cached = self._dictionaries.cached(request.model_version_id)
        try:
            async with asyncio.TaskGroup() as group:
                explained = group.create_task(self._kserve(request, cutoff))
                dictionary = (
                    None
                    if cached is not None
                    else group.create_task(self._dictionaries.get(request.model_version_id, cutoff))
                )
        except BaseExceptionGroup as failures:
            raise _first_leaf(failures) from None
        if cached is not None:
            return cached, explained.result()
        assert dictionary is not None
        return dictionary.result(), explained.result()

    async def explain(self, request: ExplainRequest, deadline: datetime | None) -> Explanation:
        try:
            explanation = await self._explain(request, deadline)
        except BaseException as error:
            EXPLANATIONS.labels(result=result_of(error)).inc()
            raise
        EXPLANATIONS.labels(result="ok").inc()
        return explanation

    async def _explain(self, request: ExplainRequest, deadline: datetime | None) -> Explanation:
        arrival = self._clock()
        cutoff = self._cutoff(arrival, deadline)
        remaining = (cutoff - arrival).total_seconds()
        if remaining <= 0:
            DEADLINE_EXHAUSTED.labels(stage="explain").inc()
            raise DependencyTimeout()
        try:
            async with asyncio.timeout(remaining):
                dictionary, explained = await self._gather(request, cutoff)
        except TimeoutError:
            DEADLINE_EXHAUSTED.labels(stage="explain").inc()
            raise DependencyTimeout() from None
        if (
            explained.model_version_id != request.model_version_id
        ):  # BR-U7-08: nunca un explicador de otra version
            raise ConflictState(ProblemReason.VERSION_MISMATCH)
        if dictionary.model_version_id != request.model_version_id:  # BR-U0-81
            raise ConflictState(ProblemReason.VERSION_MISMATCH)
        return self._compose(request, dictionary, explained)

    def _compose(
        self, request: ExplainRequest, dictionary: FeatureDictionary, explained: _Explained
    ) -> Explanation:
        incomplete = UnprocessableExplanation(ProblemReason.FEATURE_DICTIONARY_INCOMPLETE)
        values = request.features.features
        if any(item.feature_id not in values for item in explained.contributions):
            raise VectraError()  # el explicador devolvio un factor que no esta en el vector pedido
        shap = [
            FeatureContribution(
                feature_id=item.feature_id,
                value=values[item.feature_id],
                contribution=_decimal(item.contribution),
            )
            for item in explained.contributions
        ]
        if not covers(dictionary, shap):  # BR-U7-09
            raise incomplete
        try:
            narrative = self._generator.generate(shap, dictionary, request.model_version_id)
        except FeatureDictionaryIncomplete as exc:
            raise incomplete from exc
        if not self._validator.validate(narrative, shap, dictionary, request.model_version_id):  # BR-U7-11
            raise UnprocessableExplanation(ProblemReason.FACTUALITY_FAILED)
        return Explanation(
            model_version_id=request.model_version_id,
            method="shap",
            shap_vector=shap,
            base_value=_decimal(explained.base_value),
            narrative=narrative,
            narrative_generator=self._generator.template_id,
            feature_dictionary_version=dictionary.dictionary_version,
            posthoc_notice=self._generator.posthoc_notice,
            factuality_check="passed",
        )
