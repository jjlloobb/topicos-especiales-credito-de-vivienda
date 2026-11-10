"""Clientes de `scoring-service` (P-U7-04, NFR-U7-11, 43): uno por dependencia, cada uno con su pool y su circuit breaker.

Todos usan `vectra_common.deps.call` (que recorta el timeout al presupuesto restante, propaga `x-vectra-deadline` y reintenta una
vez ante un 401). Ninguno devuelve datos de otra version ni un valor por omision: una falla es `None`, un `ExplainerError` o un
`AppendResult` sin `ack`, y `check_preconditions` decide la causa (BR-U0-02).

Los hosts de KServe no se escriben aqui: el cliente de `:predict` arma la URL con el `inference_service` de `serving-config` y una
plantilla por configuracion (INF-U7-04).
"""

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ValidationError
from vectra_common import deps
from vectra_common.deps import CircuitState, DependencyClient
from vectra_common.errors import DependencyTimeout, DependencyUnavailable
from vectra_contracts.catalog import ExplainerError
from vectra_contracts.models.api import ExplainRequest
from vectra_contracts.models.explanation import Explanation, Prediction, RegistryAck
from vectra_contracts.models.features import FeatureVector
from vectra_contracts.models.registry import RegistryEntryIn
from vectra_contracts.outcome import InvalidModelOutput, quantize_prediction

from scoring.config import EXPLAINABILITY_TIMEOUT_MS, PREDICT_TIMEOUT_MS, REGISTRY_TIMEOUT_MS
from scoring.metrics import DEADLINE_EXHAUSTED, timed

OK = 200
CONFLICT = 409
UNPROCESSABLE = 422
BAD_GATEWAY_TIMEOUT = 504
SERVICE_UNAVAILABLE = 503


class _PredictionOut(BaseModel):
    score: float
    confidence: str
    model_version_id: str


class _PredictResponse(BaseModel):
    predictions: list[_PredictionOut]


class PredictClient:
    """KServe `:predict` (F19, pool de 20): protocolo v1, `{"instances": [FeatureVector]}` -> `{"predictions": [...]}`."""

    def __init__(self, client: DependencyClient, url_template: str) -> None:
        self._client = client
        self._url_template = url_template

    async def predict(
        self, inference_service: str, features: FeatureVector, deadline: datetime
    ) -> Prediction | InvalidModelOutput | None:
        """`None` si no hay prediccion (timeout, caida, circuito abierto o respuesta ilegible)."""
        base = self._url_template.format(inference_service=inference_service)
        body = json.dumps({"instances": [features.model_dump(mode="json")]}, ensure_ascii=False).encode(
            "utf-8"
        )
        try:
            async with timed("predict"):
                response = await deps.call(
                    self._client,
                    "POST",
                    f"{base}/v1/models/{inference_service}:predict",
                    timeout=PREDICT_TIMEOUT_MS / 1000,
                    deadline=deadline,
                    headers={"content-type": "application/json"},
                    content=body,
                )
        except DependencyTimeout:
            DEADLINE_EXHAUSTED.labels(stage="predict").inc()
            return None
        except Exception:  # noqa: BLE001 - circuito abierto, conexion caida o fallo del token de servicio: sin prediccion
            return None
        if response.status_code != OK:
            return None
        try:
            parsed = _PredictResponse.model_validate_json(response.content)
            item = parsed.predictions[0]
            return quantize_prediction(item.model_version_id, item.score, float(item.confidence))
        except (ValidationError, ValueError, IndexError):
            return None


def _reason(content: bytes) -> str | None:
    try:
        body: Any = json.loads(content)
        reason = body.get("reason") if isinstance(body, dict) else None
        return reason if isinstance(reason, str) else None
    except ValueError:
        return None


class ExplainabilityClient:
    """explainability `POST /v1/explanations` (F20, pool de 20) con `x-vectra-deadline`; los errores de domain-entities §5."""

    def __init__(self, client: DependencyClient) -> None:
        self._client = client

    async def explain(self, request: ExplainRequest, deadline: datetime) -> Explanation | ExplainerError:
        try:
            async with timed("explainability"):
                response = await deps.call(
                    self._client,
                    "POST",
                    "/v1/explanations",
                    timeout=EXPLAINABILITY_TIMEOUT_MS / 1000,
                    deadline=deadline,
                    headers={"content-type": "application/json"},
                    content=request.model_dump_json().encode("utf-8"),
                )
        except DependencyTimeout:
            DEADLINE_EXHAUSTED.labels(stage="explain").inc()
            return ExplainerError.TIMEOUT
        except DependencyUnavailable:
            return ExplainerError.UNAVAILABLE  # circuito abierto o conexion caida
        except Exception:  # noqa: BLE001 - una falla inesperada del cliente no puede escapar como un 500 (PBT-U7-07)
            return ExplainerError.ERROR
        return self._translate(response.status_code, response.content)

    @staticmethod
    def _translate(status: int, content: bytes) -> Explanation | ExplainerError:
        if status == OK:
            try:
                return Explanation.model_validate_json(content)
            except ValidationError:
                return ExplainerError.ERROR
        reason = _reason(content)
        if status == CONFLICT and reason == "version_mismatch":
            return ExplainerError.VERSION_MISMATCH
        if status == UNPROCESSABLE and reason == "feature_dictionary_incomplete":
            return ExplainerError.FEATURE_DICTIONARY_INCOMPLETE
        if status == UNPROCESSABLE and reason == "factuality_failed":
            return ExplainerError.FACTUALITY_FAILED
        if status == BAD_GATEWAY_TIMEOUT:
            return ExplainerError.TIMEOUT
        if status == SERVICE_UNAVAILABLE:
            return ExplainerError.UNAVAILABLE
        return ExplainerError.ERROR


AppendKind = Literal["ok", "timeout", "unavailable", "conflict", "rejected"]


@dataclass(frozen=True)
class AppendResult:
    kind: AppendKind
    ack: RegistryAck | None = None
    breaker_open: bool = False

    @property
    def transient(self) -> bool:
        """Reintentable (P-U7-02): 503, timeout o error de conexion. Nunca un 4xx."""
        return self.kind in ("timeout", "unavailable")


class RegistryClient:
    """decision-registry `POST /v1/entries` (F21, pool de 10)."""

    def __init__(self, client: DependencyClient) -> None:
        self._client = client

    def breaker_open(self) -> bool:
        breaker = self._client.breaker
        return breaker is not None and breaker.state is CircuitState.OPEN

    async def append(self, entry: RegistryEntryIn, timeout_ms: int = REGISTRY_TIMEOUT_MS) -> AppendResult:
        try:
            async with timed("registry"):
                response = await deps.call(
                    self._client,
                    "POST",
                    "/v1/entries",
                    timeout=timeout_ms / 1000,
                    headers={"content-type": "application/json"},
                    content=entry.model_dump_json(exclude_none=True).encode("utf-8"),
                )
        except DependencyTimeout:
            return AppendResult("timeout", breaker_open=self.breaker_open())
        except Exception:  # noqa: BLE001 - circuito abierto, conexion caida o falla inesperada: registro no disponible
            return AppendResult("unavailable", breaker_open=self.breaker_open())
        if response.status_code == OK:
            try:
                return AppendResult("ok", RegistryAck.model_validate_json(response.content))
            except ValidationError:
                return AppendResult("rejected")
        if response.status_code == SERVICE_UNAVAILABLE:
            return AppendResult("unavailable", breaker_open=self.breaker_open())
        return AppendResult("conflict" if response.status_code == CONFLICT else "rejected")
