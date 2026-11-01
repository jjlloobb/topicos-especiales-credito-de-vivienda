"""Gobierno (domain-entities §9.3; semantica en U4 domain-entities §1, §2 y §4)."""

from datetime import date
from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from vectra_contracts.models.base import (
    COP,
    Decimal4,
    InferenceServiceName,
    Sha256Hex,
    StrictModel,
    Timestamp,
    UnitDecimal4,
)
from vectra_contracts.models.monitoring import InitialDisparity, PrePostReport

ModelState = Literal[
    "registrado",
    "en_validacion",
    "validacion_fallida",
    "lista_para_aprobacion",
    "aprobado",
    "rechazado",
    "activo",
    "inactivo",
    "congelado",
    "retirado",
]
ArtifactFormat = Literal["onnx", "xgboost_json", "xgboost_ubj", "lightgbm_txt"]


class NormativeParams(StrictModel):
    vis_max_property_value: COP
    usury_cap_ea: Decimal4
    effective_from: date
    effective_to: date | None = None
    source_ref: Annotated[str, Field(max_length=300)]


class ServingConfig(StrictModel):
    model_version_id: str
    state: Literal["activo", "congelado"]
    policy_version_id: str
    feature_dictionary_version: str
    effective_from: Timestamp
    inference_service: InferenceServiceName
    etag: str
    normative_current: NormativeParams | None = None


class ChannelRule(StrictModel):
    channel: str
    cutoff: UnitDecimal4 | None = None


class PolicyDraft(StrictModel):
    cutoff: UnitDecimal4
    low_confidence_threshold: UnitDecimal4
    channel_rules: list[ChannelRule]
    normative: list[NormativeParams]

    @model_validator(mode="after")
    def _coherent(self) -> Self:
        channels = [rule.channel for rule in self.channel_rules]
        if len(set(channels)) != len(channels):
            raise ValueError("channel_rules_repeated")
        for item in self.normative:
            if item.effective_to is not None and item.effective_to <= item.effective_from:
                raise ValueError("effective_to_not_after_from")
        ordered = sorted(self.normative, key=lambda n: n.effective_from)
        for current, following in zip(ordered, ordered[1:], strict=False):
            if current.effective_to is None or current.effective_to > following.effective_from:
                raise ValueError("normative_overlap")
        return self


class PolicyVersion(PolicyDraft):
    policy_version_id: str
    state: Literal["propuesta", "activa", "rechazada", "historica"]
    proposed_by: str
    approved_by: str | None = None
    created_at: Timestamp

    @model_validator(mode="after")
    def _four_eyes(self) -> Self:
        if self.approved_by is not None and self.approved_by == self.proposed_by:
            raise ValueError("approver_is_proposer")
        return self


class ModelRegistration(StrictModel):
    artifact_uri: str
    artifact_format: ArtifactFormat
    artifact_sha256: Sha256Hex
    explainer_uri: str
    explainer_sha256: Sha256Hex
    manifest_uri: str
    manifest_sha256: Sha256Hex
    data_sources: list[str] = []
    source_candidate_for: str | None = None


class ModelVersion(StrictModel):
    model_version_id: str
    state: ModelState
    artifact_uri: str
    artifact_format: ArtifactFormat
    artifact_sha256: Sha256Hex
    explainer_uri: str
    explainer_sha256: Sha256Hex
    inference_service: InferenceServiceName
    manifest_uri: str
    manifest_sha256: Sha256Hex
    feature_dictionary_version: str
    data_sources: list[str]
    source_candidate_for: str | None = None
    registered_by: str
    approved_by: str | None = None
    investigation: bool
    archived_uri: str | None = None
    archived_at: Timestamp | None = None
    created_at: Timestamp
    updated_at: Timestamp


class SyncCheck(StrictModel):
    passed: bool
    predictor_version: str
    explainer_version: str
    samples_checked: int
    failure_reason: str | None = None


class ValidationReport(StrictModel):
    auc_roc: Decimal4
    auc_target: Decimal4
    auc_meets_target: bool
    initial_disparity: InitialDisparity
    sync_check: SyncCheck
    dataset_ref: str
    disclaimer: str


class ModelVersionDetail(ModelVersion):
    validation_report: ValidationReport | None = None


class ValidationRun(StrictModel):
    run_id: str
    model_version_id: str
    job_name: str
    mode: Literal["validacion", "source_comparison"]
    source_id: str | None = None
    baseline_version_id: str | None = None
    state: Literal["lanzado", "informe_recibido", "fallido", "timeout"]
    started_at: Timestamp
    deadline_at: Timestamp
    finished_at: Timestamp | None = None

    @model_validator(mode="after")
    def _mode_fields(self) -> Self:
        comparison = self.mode == "source_comparison"
        if comparison != (self.source_id is not None) or comparison != (self.baseline_version_id is not None):
            raise ValueError("mode_fields_incoherent")
        return self


class DataSourceProposal(StrictModel):
    name: str
    description: str
    provides_features: list[str]
    owner: str


class DataSource(DataSourceProposal):
    ds_id: str
    proposed_by: str
    state: Literal["propuesta", "en_evaluacion", "aprobada", "rechazada"]
    pre_post_report: PrePostReport | None = None
    decided_by: str | None = None


class ModelFilter(StrictModel):
    """`GET /v1/models?state=activo,congelado`: uno o varios estados."""

    state: list[ModelState] | None = None
    page: Annotated[int, Field(ge=1)] = 1
    page_size: Annotated[int, Field(ge=1, le=100)] = 20


class PolicyDecisionIn(StrictModel):
    """`rechazada` exige `justification` (U4 `rejection_justification`)."""

    decision: Literal["aprobada", "rechazada"]
    justification: Annotated[str, Field(max_length=2000)] | None = None

    @model_validator(mode="after")
    def _justified(self) -> Self:
        if self.decision == "rechazada" and not (self.justification and self.justification.strip()):
            raise ValueError("justification_required")
        return self


class ModelApprovalIn(StrictModel):
    decision: Literal["aprobado", "rechazado"]
    justification: Annotated[str, Field(max_length=2000)] | None = None


class FrozenResolutionIn(StrictModel):
    action: Literal["reactivar", "descartar", "investigar"]
    justification: Annotated[str, Field(min_length=1, max_length=2000)]


class DataSourceDecisionIn(StrictModel):
    decision: Literal["aprobada", "rechazada"]
    justification: Annotated[str, Field(max_length=2000)] | None = None


class SourceComparisonIn(StrictModel):
    candidate_version_id: str


class ActivationIn(StrictModel):
    evidence: Annotated[str, Field(max_length=500)]
