"""Invariante en dos fases (BR-U0-01..08, P-U0-03, AUTONOMIA-06)."""

import math
from datetime import datetime
from decimal import Decimal, localcontext
from types import UnionType
from typing import Annotated, Any, Literal, Self, Union, get_args, get_origin
from uuid import UUID

from pydantic import BaseModel, Field, PrivateAttr, RootModel, ValidationInfo, model_validator

from vectra_contracts.catalog import (
    ExplainerError,
    FailClosedCause,
    Outcome,
    ReasonCode,
    RegistryError,
    ServingState,
)
from vectra_contracts.decimal_ctx import VECTRA_DECIMAL_CTX
from vectra_contracts.dictionary import covers
from vectra_contracts.errors import ContractViolation
from vectra_contracts.models.base import Sha256Hex, StrictModel, Timestamp, UnitDecimal4
from vectra_contracts.models.explanation import (
    Explanation,
    FailClosed,
    PolicyResult,
    Prediction,
    RegistryAck,
)
from vectra_contracts.models.features import FeatureDictionary
from vectra_contracts.outcome import _internal

# `_internal` se importa como modulo, no el simbolo: `outcome` no debe dejar `CONSTRUCTION_TOKEN` como atributo publico (R2-01).
_QUANT = Decimal("0.0001")


def _has_token(info: ValidationInfo) -> bool:
    return isinstance(info.context, dict) and info.context.get("token") is _internal.CONSTRUCTION_TOKEN


def _context() -> dict[str, Any]:
    return {"token": _internal.CONSTRUCTION_TOKEN}


class _Guarded(StrictModel):
    """Exige el token privado para construir desde datos; una instancia ya construida se anida sin token (U00-T03)."""

    # La instancia recuerda que nacio con el token (fabricas o `read_wire`): al anidarla en otro modelo no se vuelve a exigir. Se usa
    # un atributo privado y un validador `after` porque un validador `before` o `wrap` hace que pydantic valide el JSON en modo python
    # y rompe `StrictModel` (fechas y UUID como cadena). `model_construct` esta prohibido, asi que no hay otra forma de tener el sello.
    _born_with_token: bool = PrivateAttr(default=False)

    @model_validator(mode="after")
    def _require_token(self, info: ValidationInfo) -> Self:
        if _has_token(info):
            self._born_with_token = True
        elif not self._born_with_token:
            raise ContractViolation(f"{type(self).__name__} solo se construye con las fabricas de outcome")
        return self

    @classmethod
    def model_construct(cls, _fields_set: set[str] | None = None, **values: Any) -> Self:  # type: ignore[override]
        raise ContractViolation(f"{cls.__name__} no admite model_construct")


class Ready(_Guarded):
    case_id: UUID
    prediction: Prediction
    policy_result: PolicyResult
    explanation: Explanation
    feature_vector_hash: Sha256Hex
    evaluated_at: Timestamp


class Recommendation(_Guarded):
    kind: Literal["recommendation"] = "recommendation"
    case_id: UUID
    score: UnitDecimal4
    confidence: UnitDecimal4
    outcome: Outcome
    reasons: list[ReasonCode]
    model_version_id: str
    policy_version_id: str
    explanation: Explanation
    registry_entry_id: Annotated[str, Field(min_length=1)]
    evaluated_at: Timestamp
    feature_vector_hash: Sha256Hex

    @model_validator(mode="after")
    def _structural(self) -> Self:
        if self.explanation.model_version_id != self.model_version_id:
            raise ValueError("version_mismatch")
        return self


_RecommendResultRoot = Annotated[Recommendation | FailClosed, Field(discriminator="kind")]


class RecommendResult(RootModel[_RecommendResultRoot]):
    """Cuerpo de la respuesta 200 de `POST /v1/recommendations` (BR-U0-06)."""

    @classmethod
    def from_wire(cls, data: str | bytes) -> Recommendation | FailClosed:
        """Aplica la capa estructural al leer una `Recommendation` o un `FailClosed` de la red (BR-U0-06)."""
        return read_wire(cls, data).root


def _contains(tp: Any, target: type, seen: set[Any]) -> bool:
    if tp in seen:
        return False
    seen.add(tp)
    if isinstance(tp, type) and issubclass(tp, target):
        return True
    if isinstance(tp, type) and issubclass(tp, BaseModel):
        return any(_contains(f.annotation, target, seen) for f in tp.model_fields.values())
    if get_origin(tp) in (Union, UnionType, Annotated) or get_args(tp):
        return any(_contains(a, target, seen) for a in get_args(tp))
    return False


def read_wire[M: BaseModel](model: type[M], data: str | bytes) -> M:
    """Lectura publica de JSON de un modelo que contiene `Recommendation` (p. ej. `CaseDetail`); aplica la capa estructural.

    Rechaza `Ready` y todo modelo que lo contenga con `ContractViolation`: `Ready` solo sale de `check_preconditions`.
    """
    if _contains(model, Ready, set()):
        raise ContractViolation(f"{model.__name__} contiene Ready: solo se construye con las fabricas de outcome")
    return model.model_validate_json(data, context=_context())


class InvalidModelOutput(StrictModel):
    """Salida de KServe no finita o fuera de [0, 1] (BR-U0-07): lleva a `model_output_invalid`."""

    model_version_id: str


def quantize_probability(value: float) -> str | None:
    """Unico punto donde existe un `float` (BR-U0-07). Nunca recorta en silencio."""
    if not math.isfinite(value) or not 0.0 <= value <= 1.0:
        return None
    with localcontext(VECTRA_DECIMAL_CTX) as ctx:
        quantized = ctx.quantize(Decimal(value), _QUANT)
    # `str` y `copy_abs` no dependen del contexto global (P-U0-10); `format` y `abs` si.
    return str(quantized.copy_abs())


def quantize_prediction(
    model_version_id: str, score: float, confidence: float
) -> Prediction | InvalidModelOutput:
    quantized_score = quantize_probability(score)
    quantized_confidence = quantize_probability(confidence)
    if quantized_score is None or quantized_confidence is None:
        return InvalidModelOutput(model_version_id=model_version_id)
    return Prediction(
        model_version_id=model_version_id, score=quantized_score, confidence=quantized_confidence
    )


def _fail(case_id: UUID, cause: FailClosedCause, now: datetime) -> FailClosed:
    frozen = cause is FailClosedCause.MODEL_FROZEN
    return FailClosed(
        case_id=case_id,
        status="modelo_congelado" if frozen else "en_sincronizacion",
        cause=cause,
        retryable=not frozen,
        occurred_at=now,
    )


def _first_cause(
    serving_state: ServingState,
    requested_model_version_id: str,
    serving_model_version_id: str | None,
    prediction: Prediction | InvalidModelOutput | None,
    policy_result: PolicyResult | None,
    explainer: Explanation | ExplainerError | None,
    dictionary: FeatureDictionary | None,
) -> FailClosedCause | None:
    """Tabla de BR-U0-02. Cada bloque es una fila, en orden de precedencia (BR-U0-03)."""
    # Discrepancia de version pedida: scoring no invoca nada y esas ausencias son validas (S2).
    discrepancy = (
        serving_state is ServingState.ACTIVO and requested_model_version_id != serving_model_version_id
    )
    invalid_output = isinstance(prediction, InvalidModelOutput)
    if serving_state is ServingState.CONGELADO:
        return FailClosedCause.MODEL_FROZEN
    if serving_state is ServingState.NO_DISPONIBLE or (
        not discrepancy and (prediction is None or (policy_result is None and not invalid_output))
    ):
        return FailClosedCause.SERVING_CONFIG_UNAVAILABLE
    if invalid_output:
        return FailClosedCause.MODEL_OUTPUT_INVALID
    if explainer is ExplainerError.TIMEOUT:
        return FailClosedCause.TIMEOUT
    if explainer is ExplainerError.UNAVAILABLE or (explainer is None and not discrepancy):
        return FailClosedCause.EXPLAINER_UNAVAILABLE
    if explainer is ExplainerError.ERROR:
        return FailClosedCause.EXPLAINER_ERROR
    explanation = explainer if isinstance(explainer, Explanation) else None
    version = prediction.model_version_id if isinstance(prediction, Prediction) else None
    if (
        discrepancy
        or explainer is ExplainerError.VERSION_MISMATCH
        or (explanation is not None and explanation.model_version_id != version)
        or (dictionary is not None and dictionary.model_version_id != version)
    ):
        return FailClosedCause.VERSION_MISMATCH
    if (
        explainer is ExplainerError.FEATURE_DICTIONARY_INCOMPLETE
        or dictionary is None
        or (explanation is not None and not covers(dictionary, explanation.shap_vector))
    ):
        return FailClosedCause.FEATURE_DICTIONARY_INCOMPLETE
    if explainer is ExplainerError.FACTUALITY_FAILED:
        return FailClosedCause.FACTUALITY_FAILED
    return None


def check_preconditions(
    case_id: UUID,
    serving_state: ServingState,
    requested_model_version_id: str,
    serving_model_version_id: str | None,
    prediction: Prediction | InvalidModelOutput | None,
    policy_result: PolicyResult | None,
    explainer: Explanation | ExplainerError | None,
    dictionary: FeatureDictionary | None,
    feature_vector_hash: str,
    now: datetime,
) -> Ready | FailClosed:
    """Causas 1-9 de BR-U0-02. Es la unica que construye `Ready`."""
    cause = _first_cause(
        serving_state,
        requested_model_version_id,
        serving_model_version_id,
        prediction,
        policy_result,
        explainer,
        dictionary,
    )
    if cause is not None:
        return _fail(case_id, cause, now)
    return Ready.model_validate(
        {
            "case_id": case_id,
            "prediction": prediction,
            "policy_result": policy_result,
            "explanation": explainer,
            "feature_vector_hash": feature_vector_hash,
            "evaluated_at": now,
        },
        context=_context(),
    )


def build_outcome(
    ready: Ready, registry: RegistryAck | RegistryError | None, now: datetime
) -> Recommendation | FailClosed:
    """Causa 10 de BR-U0-02. Es la unica que construye `Recommendation`."""
    if not isinstance(registry, RegistryAck):
        return _fail(ready.case_id, FailClosedCause.REGISTRY_UNAVAILABLE, now)
    return Recommendation.model_validate(
        {
            "case_id": ready.case_id,
            "score": ready.prediction.score,
            "confidence": ready.prediction.confidence,
            "outcome": ready.policy_result.outcome,
            "reasons": list(ready.policy_result.reasons),
            "model_version_id": ready.prediction.model_version_id,
            "policy_version_id": ready.policy_result.policy_version_id,
            "explanation": ready.explanation,
            "registry_entry_id": registry.registry_entry_id,
            "evaluated_at": ready.evaluated_at,
            "feature_vector_hash": ready.feature_vector_hash,
        },
        context=_context(),
    )


__all__ = [
    "InvalidModelOutput",
    "RecommendResult",
    "Ready",
    "Recommendation",
    "build_outcome",
    "check_preconditions",
    "quantize_prediction",
    "quantize_probability",
    "read_wire",
]
