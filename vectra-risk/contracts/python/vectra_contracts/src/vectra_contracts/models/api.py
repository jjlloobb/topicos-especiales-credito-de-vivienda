"""Tipos de API de scoring, casos, consola y seguridad (domain-entities §6, §7, §9)."""

from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import Field, JsonValue, model_validator

from vectra_contracts.catalog import (
    REASON_ALLOWED_CODE,
    CreditStatus,
    Decision,
    FinalOutcome,
    ProblemCode,
    ProblemReason,
    Role,
    Scope,
)
from vectra_contracts.models.application import ApplicationView, CaseIdentifierGroup, CaseSummary
from vectra_contracts.models.base import (
    COP,
    Decimal4,
    InferenceServiceName,
    StrictModel,
    Timestamp,
    UnitDecimal4,
)
from vectra_contracts.models.features import FeatureVector, MonitoringLabels
from vectra_contracts.models.registry import RegistryDossier
from vectra_contracts.validation import check_justification, check_used_factors


class PolicyInputs(StrictModel):
    property_value: COP
    proposed_rate_ea: Decimal4
    channel: Annotated[str, Field(max_length=40)]


class ScoringRequest(StrictModel):
    case_id: UUID
    features: FeatureVector
    monitoring_labels: MonitoringLabels
    policy_inputs: PolicyInputs
    attempt: Annotated[int, Field(ge=1)]
    model_version_id: str
    received_at: Timestamp
    first_evaluation: bool


class ExplainRequest(StrictModel):
    case_id: UUID
    model_version_id: str
    inference_service: InferenceServiceName
    features: FeatureVector
    prediction_score: UnitDecimal4


class ApplicantSummaryRequest(StrictModel):
    case_id: UUID
    recommendation_entry_id: str


class ApplicantFactor(StrictModel):
    label_es: str
    direction: Literal["aumenta", "reduce"]


class ApplicantSummary(StrictModel):
    case_id: UUID
    factors: list[ApplicantFactor]
    posthoc_notice: str
    generated_at: Timestamp


class DecisionIn(StrictModel):
    decision: Decision
    final_outcome: FinalOutcome
    used_factors: list[str]
    justification: Annotated[str, Field(max_length=2000)]

    @model_validator(mode="after")
    def _coherent(self) -> Self:
        check_used_factors(self.used_factors)
        check_justification(self.decision, self.justification)
        return self


class DecisionRef(StrictModel):
    case_id: UUID
    registry_entry_id: str
    recorded_at: Timestamp


class DecisionView(StrictModel):
    decision: Decision
    final_outcome: FinalOutcome
    used_factors: list[str]
    justification: str
    decided_at: Timestamp
    decided_by: str


class CaseDetail(CaseSummary):
    application: ApplicationView
    identifiers: CaseIdentifierGroup | None = None
    recommendation: JsonValue | None = None
    recommendation_entry_id: str | None = None
    credit_status: CreditStatus | None = None
    decision: DecisionView | None = None
    model_frozen_after_recommendation: bool
    anonymized: bool
    attempts: int
    last_cause: str | None = None


class Principal(StrictModel):
    """Domain-entities §7.1. `mfa` se deriva: `acr == "mfa"` (BR-U0-72)."""

    subject: str
    kind: Literal["user", "service"]
    roles: frozenset[Role] = frozenset()
    scopes: frozenset[Scope] = frozenset()
    acr: str | None = None
    auth_time: Timestamp | None = None
    token_expiry: Timestamp


class SessionInfo(StrictModel):
    role: Role
    mfa: bool
    auth_time: Timestamp
    locale: Literal["es-CO"]


class ConsoleDossier(StrictModel):
    dossier: RegistryDossier
    identifiers: CaseIdentifierGroup | None = None
    identifiers_unavailable: bool
    anonymized: bool

    @model_validator(mode="after")
    def _without_identifiers(self) -> Self:
        if (self.anonymized or self.identifiers_unavailable) and self.identifiers is not None:
            raise ValueError("identifiers_not_allowed")
        return self


class ClientErrorReport(StrictModel):
    error_code: Literal[
        "render_error",
        "chunk_load_failed",
        "unhandled_rejection",
        "api_contract_mismatch",
        "stepup_failed",
        "csp_violation",
    ]
    route_template: Annotated[str, Field(max_length=200)]
    app_version: Annotated[str, Field(pattern=r"^\d+\.\d+\.\d+$")]
    correlation_id: Annotated[str, Field(pattern=r"^[0-9a-f]{32}$")] | None = None


class InvalidParam(StrictModel):
    name: str
    reason_code: str


class Problem(StrictModel):
    """RFC 9457; campos cerrados (BR-U0-61) y `reason` de su catalogo (§6)."""

    type: str
    title: str
    status: int
    code: ProblemCode
    correlation_id: str
    reason: ProblemReason | None = None
    invalid_params: list[InvalidParam] | None = None

    @model_validator(mode="after")
    def _closed(self) -> Self:
        if self.reason is not None and REASON_ALLOWED_CODE[self.reason] is not self.code:
            raise ValueError("reason_not_allowed_for_code")
        if self.invalid_params is not None and self.code is not ProblemCode.VALIDATION_ERROR:
            raise ValueError("invalid_params_only_on_validation_error")
        return self


class Page[T](StrictModel):
    items: list[T]
    next_seq_after: int | None = None
    page: int | None = None
    total: int | None = None


class CreditStatusView(StrictModel):
    credit_id: str
    status: CreditStatus


class Empty(StrictModel):
    """Respuesta sin cuerpo util."""
