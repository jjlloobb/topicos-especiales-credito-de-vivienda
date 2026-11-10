"""Orquestador de la recomendacion (BR-U0-08, BR-U7-01, 02, 03, 12, 15, 16; P-U7-01, 02, 03; US-103, 109, 111, 113).

Secuencia: `serving-config` -> (si `activo` y la version pedida es la vigente) `:predict` -> cuantizacion -> politica ->
explainability -> `check_preconditions` -> append de la `recommendation` -> `build_outcome`. Cada `FailClosed` intenta escribir su
entrada `fail_closed` (best effort). Nunca devuelve una decision ni lanza por una dependencia: la respuesta es siempre un
`Recommendation` o un `FailClosed` (PBT-U7-07).

Todo lo anterior al registro cabe en `llegada + 700 ms` (P-U7-01): cada llamada recibe `deadline=` y el timeout efectivo es el menor
entre el propio y lo que queda. El append de la `recommendation` tiene su propio presupuesto (2 x 2,5 s) y reutiliza su
`idempotency_key` (un UUID v4 por solicitud, nunca derivado de `case_id` ni de `attempt`) en el unico reintento.
"""

import asyncio
import random
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from vectra_common import logging as vlog
from vectra_contracts.canonical import sha256_hex
from vectra_contracts.catalog import (
    EntryType,
    ExplainerError,
    LogEvent,
    ServingState,
)
from vectra_contracts.catalog import RegistryError as RegistryFailure
from vectra_contracts.models.api import ExplainRequest, ScoringRequest
from vectra_contracts.models.explanation import (
    Explanation,
    FailClosed,
    PolicyResult,
    Prediction,
    RegistryAck,
)
from vectra_contracts.models.features import FeatureDictionary, FeatureDictionaryEntry
from vectra_contracts.models.governance import ServingConfig
from vectra_contracts.models.registry import Actor, FailClosedPayload, RecommendationPayload, RegistryEntryIn
from vectra_contracts.outcome import (
    InvalidModelOutput,
    Ready,
    Recommendation,
    build_outcome,
    check_preconditions,
)

from scoring.clients import (
    ExplainabilityClient,
    PredictClient,
    RegistryClient,
)
from scoring.config import (
    APPEND_ATTEMPTS,
    APPEND_JITTER_MAX_MS,
    APPEND_JITTER_MIN_MS,
    APPEND_TIMEOUT_MS,
    EXPLAINABILITY_TIMEOUT_MS,
    FAIL_CLOSED_APPEND_TIMEOUT_MS,
    PRE_REGISTRY_BUDGET_MS,
)
from scoring.metrics import (
    FAILCLOSED,
    RECOMMENDATIONS,
    REGISTRY_ABANDONED,
    REGISTRY_ATTEMPTS,
)
from scoring.policy import PolicyEvaluationInput, evaluate
from scoring.serving_config_client import ServingConfigClient

ACTOR = Actor(kind="service", id="scoring-service")
Clock = Callable[[], datetime]


def attested_dictionary(
    explainer: Explanation | ExplainerError | None,
    prediction: Prediction | InvalidModelOutput | None,
    config: ServingConfig | None,
) -> FeatureDictionary | None:
    """El `dictionary` de `check_preconditions` (BR-U0-02, causas 7 a 9), que scoring no tiene: el diccionario (F103) es de explainability.

    - Una `Explanation` entregada ya cubrio todos sus factores: se declara esa cobertura, factor por factor.
    - `factuality_failed` (causa 9) solo se alcanza si `dictionary` no es nulo (la causa 8 lo trata como «falta»): se declara uno
      vacio de la version de la prediccion, que no corresponde a ninguna cobertura.
    - En los demas casos no hace falta: una causa anterior ya aplica, o no hubo explicacion que cubrir.

    Es la unica forma de decirselo a `check_preconditions` sin una llamada que el diseno no preve (candidatas en `CANDIDATAS.md`).
    """
    if isinstance(explainer, Explanation):
        return FeatureDictionary(
            dictionary_version=explainer.feature_dictionary_version,
            model_version_id=explainer.model_version_id,
            entries=[
                FeatureDictionaryEntry(
                    feature_id=item.feature_id,
                    label_es=item.feature_id,
                    increases_risk_phrase_es="",
                    decreases_risk_phrase_es="",
                    applicant_safe=False,
                )
                for item in explainer.shap_vector
            ],
        )
    if (
        explainer is ExplainerError.FACTUALITY_FAILED
        and isinstance(prediction, Prediction)
        and config is not None
    ):
        return FeatureDictionary(
            dictionary_version=config.feature_dictionary_version,
            model_version_id=prediction.model_version_id,
            entries=[],
        )
    return None


def default_jitter() -> float:
    """P-U7-02: el reintento sale de inmediato con un jitter de 0 a 100 ms."""
    return random.uniform(APPEND_JITTER_MIN_MS, APPEND_JITTER_MAX_MS) / 1000  # noqa: S311 - no es criptografia


class Orchestrator:
    def __init__(
        self,
        serving_config: ServingConfigClient,
        predictor: PredictClient,
        explainer: ExplainabilityClient,
        registry: RegistryClient,
        clock: Clock = lambda: datetime.now(UTC),
        uuid_factory: Callable[[], UUID] = uuid4,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        jitter: Callable[[], float] = default_jitter,
    ) -> None:
        self._serving = serving_config
        self._predictor = predictor
        self._explainer = explainer
        self._registry = registry
        self._clock = clock
        self._uuid = uuid_factory
        self._sleep = sleep
        self._jitter = jitter

    async def recommend(self, request: ScoringRequest) -> Recommendation | FailClosed:
        arrival = self._clock()
        pre_deadline = arrival + timedelta(milliseconds=PRE_REGISTRY_BUDGET_MS)
        # BR-U7-15: uno por solicitud, nunca derivado de `case_id` ni de `attempt`.
        idempotency_key = self._uuid()
        config = await self._serving.get(pre_deadline)
        if config is None:
            state = ServingState.NO_DISPONIBLE
        else:
            state = ServingState.CONGELADO if config.state == "congelado" else ServingState.ACTIVO
        prediction: Prediction | InvalidModelOutput | None = None
        policy_result: PolicyResult | None = None
        explainer: Explanation | ExplainerError | None = None
        # BR-U7-01: congelado (aunque la version pedida difiera) y version pedida distinta con `activo` no llaman a nadie.
        if (
            config is not None
            and state is ServingState.ACTIVO
            and request.model_version_id == config.model_version_id
        ):
            prediction = await self._predictor.predict(
                config.inference_service, request.features, pre_deadline
            )
            if isinstance(prediction, Prediction):
                policy_result = self._policy(config, request, prediction)
                if prediction.model_version_id != config.model_version_id:
                    # El predictor del `inference_service` de `serving-config` respondio otra version: desincronia. No se pide
                    # una explicacion que ya no podria coincidir con lo registrado (AUTONOMIA-06).
                    explainer = ExplainerError.VERSION_MISMATCH
                else:
                    explainer = await self._explain(config, request, prediction, pre_deadline)
        checked = check_preconditions(
            request.case_id,
            state,
            request.model_version_id,
            config.model_version_id if config is not None else None,
            prediction,
            policy_result,
            explainer,
            attested_dictionary(explainer, prediction, config),
            sha256_hex(request.features.model_dump(mode="json")),
            self._clock(),
        )
        if isinstance(checked, FailClosed):
            return await self._fail(request, config, checked)
        ack = await self._append_recommendation(request, config, checked, idempotency_key)
        outcome = build_outcome(checked, ack, self._clock())
        if isinstance(outcome, FailClosed):
            return await self._fail(request, config, outcome)
        RECOMMENDATIONS.labels(outcome=outcome.outcome.value).inc()
        return outcome

    def _policy(self, config: ServingConfig, request: ScoringRequest, prediction: Prediction) -> PolicyResult:
        """BR-U7-04: los parametros de la politica salen del mismo `ServingConfig` (misma foto, sin otra llamada; U04-T09)."""
        return evaluate(
            PolicyEvaluationInput(
                policy_version_id=config.policy_version_id,
                score=prediction.score,
                confidence=prediction.confidence,
                property_value=request.policy_inputs.property_value,
                proposed_rate_ea=request.policy_inputs.proposed_rate_ea,
                channel=request.policy_inputs.channel,
                cutoff=config.cutoff,
                low_confidence_threshold=config.low_confidence_threshold,
                channel_rules=config.channel_rules,
                normative=config.normative_current,
            )
        )

    async def _explain(
        self, config: ServingConfig, request: ScoringRequest, prediction: Prediction, pre_deadline: datetime
    ) -> Explanation | ExplainerError:
        # P-U7-01: `min(ahora + 800 ms, pre_deadline)`. El `model_version_id` pedido a explainability es el vigente: si el
        # predictor respondio otra version, la explicacion no coincidira y `check_preconditions` lo cierra como `version_mismatch`.
        deadline = min(self._clock() + timedelta(milliseconds=EXPLAINABILITY_TIMEOUT_MS), pre_deadline)
        return await self._explainer.explain(
            ExplainRequest(
                case_id=request.case_id,
                model_version_id=config.model_version_id,
                inference_service=config.inference_service,
                features=request.features,
                prediction_score=prediction.score,
            ),
            deadline,
        )

    # --- registro ---------------------------------------------------------------------------------------------------------

    def _recommendation_entry(
        self, request: ScoringRequest, config: ServingConfig | None, ready: Ready, key: UUID
    ) -> RegistryEntryIn:
        payload = RecommendationPayload(
            score=ready.prediction.score,
            confidence=ready.prediction.confidence,
            outcome=ready.policy_result.outcome,
            reasons=list(ready.policy_result.reasons),
            feature_vector=request.features,
            feature_vector_hash=ready.feature_vector_hash,
            evaluated_at=ready.evaluated_at,
            monitoring_labels=request.monitoring_labels,
            explanation=ready.explanation,
            # BR-U7-01 paso 7: se copian de la `ScoringRequest`, sin recalcular (los usa U11).
            received_at=request.received_at,
            channel=request.policy_inputs.channel,
            attempt=request.attempt,
            first_evaluation=request.first_evaluation,
        )
        return RegistryEntryIn(
            entry_type=EntryType.RECOMMENDATION,
            case_id=request.case_id,
            model_version_id=ready.prediction.model_version_id,
            policy_version_id=ready.policy_result.policy_version_id,
            actor=ACTOR,
            occurred_at=max(self._clock(), ready.evaluated_at),
            correlation_id=vlog.correlation_id_var.get() or uuid4().hex,
            idempotency_key=key,
            payload=payload,
        )

    async def _append_recommendation(
        self, request: ScoringRequest, config: ServingConfig | None, ready: Ready, key: UUID
    ) -> RegistryAck | RegistryFailure:
        """P-U7-02: 2 intentos con la misma llave, solo ante 503, timeout o error de conexion y sin circuito abierto."""
        entry = self._recommendation_entry(request, config, ready, key)
        for attempt in range(1, APPEND_ATTEMPTS + 1):
            result = await self._registry.append(entry, APPEND_TIMEOUT_MS)
            REGISTRY_ATTEMPTS.labels(attempt=str(attempt), result=result.kind).inc()
            if result.ack is not None:
                return result.ack
            if result.kind == "conflict":  # misma llave y otro contenido: un defecto, no una caida (P-U7-02)
                vlog.log_event(
                    LogEvent.REGISTRY_IDEMPOTENCY_CONFLICT,
                    case_id=str(request.case_id),
                    attempt=request.attempt,
                )
                return RegistryFailure.UNAVAILABLE
            if not result.transient:
                return RegistryFailure.UNAVAILABLE  # un 4xx: un solo intento
            if attempt == APPEND_ATTEMPTS or result.breaker_open:
                REGISTRY_ABANDONED.inc()  # P-U7-03: la entrada puede haberse escrito sin entregarse
                return RegistryFailure.UNAVAILABLE
            await self._sleep(self._jitter())
        raise AssertionError("inalcanzable: el ultimo intento retorna")  # pragma: no cover

    async def _fail(
        self, request: ScoringRequest, config: ServingConfig | None, failed: FailClosed
    ) -> FailClosed:
        """BR-U7-03 y 16: la metrica, el log y la entrada `fail_closed` (best effort, un intento, otro UUID v4, solo `cause`)."""
        FAILCLOSED.labels(cause=failed.cause.value).inc()
        RECOMMENDATIONS.labels(outcome="fail_closed").inc()
        vlog.log_event(
            LogEvent.RECOMMENDATION_FAIL_CLOSED,
            case_id=str(request.case_id),
            fail_closed_cause=failed.cause.value,
            attempt=request.attempt,
        )
        entry = RegistryEntryIn(
            entry_type=EntryType.FAIL_CLOSED,
            case_id=request.case_id,
            model_version_id=config.model_version_id if config is not None else None,
            policy_version_id=config.policy_version_id if config is not None else None,
            actor=ACTOR,
            occurred_at=self._clock(),
            correlation_id=vlog.correlation_id_var.get() or uuid4().hex,
            idempotency_key=self._uuid(),
            payload=FailClosedPayload(
                cause=failed.cause, retryable=failed.retryable, attempt=request.attempt
            ),
        )
        # Un solo intento: si no se escribe, el caso reevalua (BR-U0-08).
        await self._registry.append(entry, FAIL_CLOSED_APPEND_TIMEOUT_MS)
        return failed
