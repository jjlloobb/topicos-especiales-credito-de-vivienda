"""Registro y expediente (domain-entities §5 y §9.6)."""

from typing import Annotated, Any, Literal, Self
from uuid import UUID

from pydantic import Field, JsonValue, ValidationInfo, field_validator, model_validator

from vectra_contracts.catalog import (
    Decision,
    EntryType,
    FailClosedCause,
    FinalOutcome,
    LocalCause,
    Outcome,
    ReasonCode,
    Role,
)
from vectra_contracts.models.base import (
    Sha256Hex,
    StrictModel,
    Timestamp,
    UnitDecimal4,
    validate_nested,
)
from vectra_contracts.models.explanation import Explanation
from vectra_contracts.models.features import FeatureVector, MonitoringLabels
from vectra_contracts.models.monitoring import FreezeContextPackage, PrePostReport
from vectra_contracts.validation import check_fail_closed_payload, check_no_forbidden_keys


class Actor(StrictModel):
    kind: Literal["user", "service", "system"]
    id: str
    role: Role | None = None
    acr: str | None = None
    auth_time: Timestamp | None = None

    @model_validator(mode="after")
    def _auth_evidence(self) -> Self:
        if self.kind == "user":
            if self.acr is None or self.auth_time is None:
                raise ValueError("user_without_auth_evidence")
        elif self.acr is not None or self.auth_time is not None:
            raise ValueError("auth_evidence_on_non_user")
        return self


class RecommendationPayload(StrictModel):
    score: UnitDecimal4
    confidence: UnitDecimal4
    outcome: Outcome
    reasons: list[ReasonCode]
    feature_vector: FeatureVector
    feature_vector_hash: Sha256Hex
    evaluated_at: Timestamp
    monitoring_labels: MonitoringLabels
    explanation: Explanation
    received_at: Timestamp
    channel: Annotated[str, Field(max_length=40)]
    attempt: Annotated[int, Field(ge=1)]
    first_evaluation: bool


class FailClosedPayload(StrictModel):
    cause: FailClosedCause | None = None
    local_cause: LocalCause | None = None
    retryable: bool
    attempt: Annotated[int, Field(ge=1)]
    escalated_at: Timestamp | None = None

    @model_validator(mode="after")
    def _br_u0_38(self) -> Self:
        check_fail_closed_payload(self.cause, self.local_cause, self.retryable, self.escalated_at is not None)
        return self


class HumanDecisionPayload(StrictModel):
    decision: Decision
    final_outcome: FinalOutcome
    used_factors: list[str]
    justification: Annotated[str, Field(max_length=2000)]
    explanation_viewed_before: bool
    decided_at: Timestamp
    recommendation_entry_id: str


class ExplanationViewPayload(StrictModel):
    viewed_at: Timestamp
    recommendation_entry_id: str


class ModelEventPayload(StrictModel):
    event: Literal[
        "registrado",
        "validacion_iniciada",
        "informe_validacion",
        "validacion_fallida",
        "aprobado",
        "rechazado",
        "activado",
        "inactivado",
        "retirado",
        "transicion_descartada",
    ]
    details: dict[str, JsonValue]


class PolicyEventPayload(StrictModel):
    event: Literal["propuesta", "activada", "rechazada", "historica"]
    policy_version_id: str


class DataSourceEventPayload(StrictModel):
    event: Literal["propuesta", "evaluacion_iniciada", "aprobada", "rechazada"]
    source_id: str
    pre_post_report: PrePostReport | None = None


class FreezePayload(StrictModel):
    freeze_id: str
    frozen_at: Timestamp
    context_package: FreezeContextPackage


class FrozenResolutionPayload(StrictModel):
    action: Literal["reactivar", "descartar", "investigar"]
    justification: Annotated[str, Field(max_length=2000)]


class GenesisPayload(StrictModel):
    schema_version: str
    contract_version: str
    checkpoint_key_fingerprint: str


class CheckpointPayload(StrictModel):
    checkpoint_seq: int
    checkpoint_hash: str
    signature: str
    key_fingerprint: str


RegistryPayload = (
    RecommendationPayload
    | FailClosedPayload
    | HumanDecisionPayload
    | ExplanationViewPayload
    | ModelEventPayload
    | PolicyEventPayload
    | DataSourceEventPayload
    | FreezePayload
    | FrozenResolutionPayload
    | GenesisPayload
    | CheckpointPayload
)

PAYLOAD_TYPES: dict[str, type[StrictModel]] = {
    EntryType.RECOMMENDATION: RecommendationPayload,
    EntryType.FAIL_CLOSED: FailClosedPayload,
    EntryType.HUMAN_DECISION: HumanDecisionPayload,
    EntryType.EXPLANATION_VIEW: ExplanationViewPayload,
    EntryType.MODEL_EVENT: ModelEventPayload,
    EntryType.POLICY_EVENT: PolicyEventPayload,
    EntryType.DATA_SOURCE_EVENT: DataSourceEventPayload,
    EntryType.FREEZE: FreezePayload,
    EntryType.FROZEN_RESOLUTION: FrozenResolutionPayload,
    EntryType.GENESIS: GenesisPayload,
    EntryType.CHECKPOINT: CheckpointPayload,
}


class RegistryEntryIn(StrictModel):
    entry_type: EntryType
    case_id: UUID | None = None
    model_version_id: str | None = None
    policy_version_id: str | None = None
    actor: Actor
    occurred_at: Timestamp
    correlation_id: Annotated[str, Field(pattern=r"^[0-9a-f]{32}$")]
    idempotency_key: UUID
    payload: RegistryPayload

    @field_validator("payload", mode="before")
    @classmethod
    def _typed_payload(cls, value: Any, info: ValidationInfo) -> Any:
        """El tipo del payload lo fija `entry_type`; prohibe identificadores en cualquier nivel."""
        entry_type = info.data.get("entry_type")
        if entry_type is None:
            raise ValueError("entry_type_unknown")
        if isinstance(value, StrictModel):
            value = value.model_dump(mode="json")
        check_no_forbidden_keys(value)
        return validate_nested(PAYLOAD_TYPES[entry_type], value)


class RegistryEntry(RegistryEntryIn):
    seq: Annotated[int, Field(ge=0)]
    prev_hash: str
    hash: str
    recorded_at: Timestamp
    contract_version: str


IntegrityReason = Literal[
    "hash", "link", "checkpoint_signature", "checkpoint_mismatch", "seq_gap", "column_mismatch"
]


class IntegrityStatus(StrictModel):
    status: Literal["verified", "not_verified"]
    from_checkpoint_seq: int
    to_checkpoint_seq: int | Literal["head"]
    entries_checked: int
    first_inconsistent_seq: int | None = None
    reason: IntegrityReason | None = None

    @model_validator(mode="after")
    def _coherent(self) -> Self:
        failed = self.status == "not_verified"
        if failed != (self.reason is not None) or failed != (self.first_inconsistent_seq is not None):
            raise ValueError("integrity_status_incoherent")
        return self


class DossierEntry(RegistryEntry):
    canonical: str
    delivery_status: Literal["entregada", "no_entregada", "pendiente_de_decision"] | None = None


class LastFullVerification(StrictModel):
    check_id: str
    finished_at: Timestamp
    result: Literal["integra", "inconsistente"]


class RegistryDossier(StrictModel):
    case_id: UUID
    entries: list[DossierEntry]
    integrity: IntegrityStatus
    last_full_verification: LastFullVerification | None

    @field_validator("entries")
    @classmethod
    def _ordered(cls, value: list[DossierEntry]) -> list[DossierEntry]:
        if [entry.seq for entry in value] != sorted(entry.seq for entry in value):
            raise ValueError("entries_not_ordered")
        return value


class IntegrityCheckRequest(StrictModel):
    mode: Literal["full", "range"]
    from_seq: Annotated[int, Field(ge=0)] | None = None
    to_seq: Annotated[int, Field(ge=0)] | None = None

    @model_validator(mode="after")
    def _coherent(self) -> Self:
        if self.mode == "range":
            if self.from_seq is None or self.to_seq is None or self.from_seq > self.to_seq:
                raise ValueError("range_requires_ordered_seqs")
        elif self.from_seq is not None or self.to_seq is not None:
            raise ValueError("full_forbids_seqs")
        return self


class IntegrityCheckRef(StrictModel):
    check_id: str
    mode: Literal["full", "range"]
    requested_at: Timestamp
    already_active: bool


class IntegrityReport(StrictModel):
    mode: Literal["incremental", "nightly", "full", "range"]
    from_seq: int
    to_seq: int
    entries_checked: int
    checkpoints_checked: int
    result: Literal["integra", "inconsistente", "error"]
    first_inconsistent_seq: int | None = None
    reason: IntegrityReason | None = None
    started_at: Timestamp
    finished_at: Timestamp

    @model_validator(mode="after")
    def _coherent(self) -> Self:
        inconsistent = self.result == "inconsistente"
        if inconsistent != (self.first_inconsistent_seq is not None) or inconsistent != (
            self.reason is not None
        ):
            raise ValueError("integrity_report_incoherent")
        return self


class Progress(StrictModel):
    checked: Annotated[int, Field(ge=0)]
    total: Annotated[int, Field(ge=0)]

    @model_validator(mode="after")
    def _bounded(self) -> Self:
        if self.checked > self.total:
            raise ValueError("progress_exceeds_total")
        return self


class IntegrityCheckStatus(StrictModel):
    check_id: str
    mode: Literal["full", "range"]
    status: Literal["pendiente", "en_curso", "terminada", "fallida"]
    progress: Progress
    report: IntegrityReport | None = None
    reason: Literal["interrumpida", "error_de_ejecucion", "plazo_vencido"] | None = None
    requested_at: Timestamp
    started_at: Timestamp | None = None
    finished_at: Timestamp | None = None

    @model_validator(mode="after")
    def _coherent(self) -> Self:
        finished = (
            self.status == "terminada"
            and self.report is not None
            and self.report.result
            in (
                "integra",
                "inconsistente",
            )
        )
        if (self.status == "terminada") != finished or (
            self.status != "terminada" and self.report is not None
        ):
            raise ValueError("report_incoherent")
        if (self.status == "fallida") != (self.reason is not None):
            raise ValueError("reason_incoherent")
        return self


class EntryFilter(StrictModel):
    case_id: UUID | None = None
    entry_type: list[EntryType] | None = None
    seq: int | None = None
    recorded_from: Timestamp | None = None
    recorded_to: Timestamp | None = None
    seq_after: int | None = None
    limit: Annotated[int, Field(ge=1, le=1000)] = 1000
    projection: Literal["full", "explanation", "metrics", "monitoring_freezes"] | None = None


class _ExplanationOnly(StrictModel):
    explanation: Explanation


class ExplanationProjection(StrictModel):
    """Proyección `explanation` (U3 §3; BR-U7-13)."""

    seq: Annotated[int, Field(ge=0)]
    case_id: UUID
    model_version_id: str
    payload: _ExplanationOnly


class MetricsRecommendationRef(StrictModel):
    seq: Annotated[int, Field(ge=0)]
    outcome: Outcome
    model_version_id: str
    evaluated_at: Timestamp
    received_at: Timestamp
    channel: Annotated[str, Field(max_length=40)]
    attempt: Annotated[int, Field(ge=1)]
    first_evaluation: bool


class MetricsProjection(StrictModel):
    """Proyección `metrics` (U3 §3; U11 BR-U11-01). Sin `feature_vector` ni `justification`."""

    entry_type: Literal["recommendation", "human_decision", "explanation_view"]
    seq: Annotated[int, Field(ge=0)]
    recorded_at: Timestamp
    case_id: UUID
    outcome: Outcome | None = None
    decision: Decision | None = None
    final_outcome: FinalOutcome | None = None
    used_factors: list[str] | None = None
    explanation_viewed_before: bool | None = None
    actor_role: Role | None = None
    recommendation_entry_id: str | None = None
    evaluated_at: Timestamp | None = None
    decided_at: Timestamp | None = None
    viewed_at: Timestamp | None = None
    model_version_id: str | None = None
    channel: Annotated[str, Field(max_length=40)] | None = None
    received_at: Timestamp | None = None
    attempt: Annotated[int, Field(ge=1)] | None = None
    first_evaluation: bool | None = None
    recommendation: MetricsRecommendationRef | None = None
    delivery_status: str | None = None


class FreezeProjection(StrictModel):
    """Proyección `monitoring_freezes`, entrada `freeze` (U3 §3)."""

    seq: Annotated[int, Field(ge=0)]
    freeze_id: str
    model_version_id: str
    frozen_at: Timestamp
    recorded_at: Timestamp
    context_package: FreezeContextPackage


class FrozenResolutionProjection(StrictModel):
    """Proyección `monitoring_freezes`, entrada `frozen_resolution` (U3 §3)."""

    seq: Annotated[int, Field(ge=0)]
    model_version_id: str
    action: Literal["reactivar", "descartar", "investigar"]
    recorded_at: Timestamp


#: `GET /v1/entries` devuelve la forma de la proyección pedida; `full` es la entrada completa.
EntryProjection = (
    RegistryEntry | ExplanationProjection | MetricsProjection | FreezeProjection | FrozenResolutionProjection
)
