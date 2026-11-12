"""`POST /v1/applicant-summaries` (BR-U7-13, 14; P-U7-03; US-110).

Lee la entrada `recommendation_entry_id` en la proyeccion `explanation` del registro (F23, por `seq`) y comprueba que es del
`case_id`. Si no existe, no tiene explicacion o es de otro caso: 409 `conflict_state`, sin datos parciales. Emite el log
`applicant_summary.generated` solo con `case_id` y no guarda el resumen. La regla de objeto «decision final desfavorable» es del
BFF (U10), no de aqui.

NFR-U7-03 (p95 <= 500 ms): el resumen sale de una sola lectura al registro (F23) y del diccionario ya cacheado, sin llamar a KServe ni generar texto
libre; no se almacena. Su medicion con carga (k6) esta diferida por la demo (T3, `evidence/cierre-demo.md`).
"""

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID

from vectra_common import deps
from vectra_common import logging as vlog
from vectra_common.deps import DependencyClient
from vectra_common.errors import ConflictState, DependencyUnavailable, VectraError
from vectra_contracts.catalog import LogEvent
from vectra_contracts.models.api import ApplicantSummary, ApplicantSummaryRequest, Page
from vectra_contracts.models.registry import ExplanationProjection

from explainability import applicant
from explainability.config import REGISTRY_TIMEOUT_MS
from explainability.dictionary_cache import DictionaryCache
from explainability.metrics import timed

OK = 200
SERVER_ERROR = 500
Clock = Callable[[], datetime]


class RegistryExplanations:
    """Cliente F23 propio (pool de 5, su circuit breaker): registro caido -> 503 hacia el BFF (P-U7-04)."""

    def __init__(self, client: DependencyClient) -> None:
        self._client = client

    async def explanation_at(self, case_id: UUID, seq: int) -> ExplanationProjection | None:
        """La proyeccion `explanation` de la entrada `seq` del caso; `None` si no hay (el registro devuelve la pagina vacia)."""
        query = f"/v1/entries?projection=explanation&case_id={case_id}&seq={seq}"
        async with timed("registry"):
            response = await deps.call(self._client, "GET", query, timeout=REGISTRY_TIMEOUT_MS / 1000)
        if response.status_code >= SERVER_ERROR:
            raise DependencyUnavailable()
        if response.status_code != OK:
            raise VectraError()  # 403 u otro 4xx: defecto de configuracion, no un caso ajeno
        page = Page[ExplanationProjection].model_validate_json(response.content)
        return page.items[0] if page.items else None


class ApplicantSummaries:
    def __init__(
        self,
        registry: RegistryExplanations,
        dictionaries: DictionaryCache,
        clock: Clock = lambda: datetime.now(UTC),
    ) -> None:
        self._registry = registry
        self._dictionaries = dictionaries
        self._clock = clock

    async def summarize(self, request: ApplicantSummaryRequest) -> ApplicantSummary:
        if not request.recommendation_entry_id.isascii() or not request.recommendation_entry_id.isdigit():
            raise ConflictState()  # el `registry_entry_id` del registro es el `seq`
        found = await self._registry.explanation_at(request.case_id, int(request.recommendation_entry_id))
        if found is None or found.case_id != request.case_id:  # BR-U7-13: de otro caso o sin explicacion
            raise ConflictState()
        explanation = found.payload.explanation
        dictionary = await self._dictionaries.get(explanation.model_version_id)
        summary = applicant.generate(request.case_id, explanation.shap_vector, dictionary, self._clock())
        # BR-U7-14: solo `case_id`, sin contenido del resumen.
        vlog.log_event(LogEvent.APPLICANT_SUMMARY_GENERATED, case_id=str(request.case_id))
        return summary
