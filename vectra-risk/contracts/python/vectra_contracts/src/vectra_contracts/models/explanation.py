"""Explicacion, resultado de fail-closed y entradas de las fabricas (domain-entities §3)."""

from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import Field, model_validator

from vectra_contracts.catalog import FailClosedCause, Outcome, ReasonCode
from vectra_contracts.models.base import DecimalStr, StrictModel, Timestamp, UnitDecimal4
from vectra_contracts.models.features import FeatureContribution


class Explanation(StrictModel):
    model_version_id: str
    method: Literal["shap"]
    shap_vector: list[FeatureContribution]
    base_value: DecimalStr
    narrative: Annotated[str, Field(max_length=4000)]
    narrative_generator: str
    feature_dictionary_version: str
    posthoc_notice: str
    factuality_check: Literal["passed"]


class FailClosed(StrictModel):
    kind: Literal["fail_closed"] = "fail_closed"
    case_id: UUID
    status: Literal["en_sincronizacion", "modelo_congelado"]
    cause: FailClosedCause
    retryable: bool
    occurred_at: Timestamp

    @model_validator(mode="after")
    def _coherent(self) -> Self:
        frozen = self.cause is FailClosedCause.MODEL_FROZEN
        if (self.status == "modelo_congelado") != frozen:
            raise ValueError("status_incoherent")
        if self.retryable == frozen:
            raise ValueError("retryable_incoherent")
        return self


class Prediction(StrictModel):
    model_version_id: str
    score: UnitDecimal4
    confidence: UnitDecimal4


class PolicyResult(StrictModel):
    policy_version_id: str
    outcome: Outcome
    reasons: list[ReasonCode]


class RegistryAck(StrictModel):
    registry_entry_id: str
    seq: Annotated[int, Field(ge=0)]
    recorded_at: Timestamp
