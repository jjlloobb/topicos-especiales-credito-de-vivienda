"""Catalogos cerrados del contrato (domain-entities §3, §6, §7)."""

from enum import StrEnum
from types import MappingProxyType
from typing import Final


class Scope(StrEnum):
    CASE_RECOMMEND = "case:recommend"
    SCORING_EXPLAIN = "scoring:explain"
    GOVERNANCE_READ_SERVING = "governance:read-serving"
    GOVERNANCE_FREEZE = "governance:freeze"
    GOVERNANCE_VALIDATION_REPORT = "governance:validation-report"
    GOVERNANCE_PROMOTION = "governance:promotion"
    BIAS_COMPARE = "bias:compare"
    GOVERNANCE_READ_DICTIONARY = "governance:read-dictionary"
    GOVERNANCE_READ_FEATURE_SPEC = "governance:read-feature-spec"
    REGISTRY_APPEND_CASE = "registry:append:case"
    REGISTRY_APPEND_SCORING = "registry:append:scoring"
    REGISTRY_APPEND_GOVERNANCE = "registry:append:governance"
    REGISTRY_READ_EXPLANATION = "registry:read:explanation"
    REGISTRY_READ_MONITORING = "registry:read:monitoring"
    REGISTRY_READ_METRICS = "registry:read:metrics"
    INTAKE_SUBMIT = "intake:submit"
    CORE_READ_CREDIT = "core:read-credit"
    CORE_WRITE_CREDIT = "core:write-credit"

    @property
    def is_read(self) -> bool:
        """Scope de lectura: `<dominio>:read:<recurso>` o `<dominio>:read-<recurso>` (BR-U0-71)."""
        return ":read:" in self.value or ":read-" in self.value


SCOPE_HOLDERS: Final = MappingProxyType(
    {
        Scope.CASE_RECOMMEND: ("case-worker",),
        Scope.SCORING_EXPLAIN: ("scoring-service",),
        Scope.GOVERNANCE_READ_SERVING: ("scoring-service", "case-service", "case-worker"),
        Scope.GOVERNANCE_FREEZE: ("bias-monitoring-job",),
        Scope.GOVERNANCE_VALIDATION_REPORT: ("model-validation-job",),
        Scope.GOVERNANCE_PROMOTION: ("promotion-tool",),
        Scope.BIAS_COMPARE: ("governance-service",),
        Scope.GOVERNANCE_READ_DICTIONARY: ("explainability-service",),
        Scope.GOVERNANCE_READ_FEATURE_SPEC: ("case-worker",),
        Scope.REGISTRY_APPEND_CASE: ("case-service",),
        Scope.REGISTRY_APPEND_SCORING: ("scoring-service",),
        Scope.REGISTRY_APPEND_GOVERNANCE: ("governance-service",),
        Scope.REGISTRY_READ_EXPLANATION: ("explainability-service",),
        Scope.REGISTRY_READ_MONITORING: ("bias-monitoring-service", "bias-monitoring-job", "verification-reader"),
        Scope.REGISTRY_READ_METRICS: ("product-metrics", "verification-reader"),
        Scope.INTAKE_SUBMIT: ("channel", "channel-simulator"),
        Scope.CORE_READ_CREDIT: ("case-service",),
        Scope.CORE_WRITE_CREDIT: (),
    }
)


class Role(StrEnum):
    ANALISTA = "analista"
    INGENIERO_RIESGO = "ingeniero_riesgo"
    CRO = "cro"
    CUMPLIMIENTO = "cumplimiento"


class ReasonCode(StrEnum):
    SCORE_BAJO_CORTE = "score_bajo_corte"
    SCORE_SOBRE_CORTE = "score_sobre_corte"
    BAJA_CONFIANZA = "baja_confianza"
    VIS = "vis"
    NO_VIS = "no_vis"
    TASA_SOBRE_USURA = "tasa_sobre_usura"
    PARAMETRO_NORMATIVO_NO_VIGENTE = "parametro_normativo_no_vigente"


class FailClosedCause(StrEnum):
    """En el orden de precedencia de BR-U0-02 (BR-U0-03)."""

    MODEL_FROZEN = "model_frozen"
    SERVING_CONFIG_UNAVAILABLE = "serving_config_unavailable"
    MODEL_OUTPUT_INVALID = "model_output_invalid"
    TIMEOUT = "timeout"
    EXPLAINER_UNAVAILABLE = "explainer_unavailable"
    EXPLAINER_ERROR = "explainer_error"
    VERSION_MISMATCH = "version_mismatch"
    FEATURE_DICTIONARY_INCOMPLETE = "feature_dictionary_incomplete"
    FACTUALITY_FAILED = "factuality_failed"
    REGISTRY_UNAVAILABLE = "registry_unavailable"

    @property
    def category(self) -> str:
        return _CAUSE_CATEGORY[self]

    @property
    def number(self) -> int:
        return list(FailClosedCause).index(self) + 1


_CAUSE_CATEGORY: Final = {
    FailClosedCause.MODEL_OUTPUT_INVALID: "calidad",
    FailClosedCause.VERSION_MISMATCH: "desincronia",
    FailClosedCause.EXPLAINER_UNAVAILABLE: "dependencia",
    FailClosedCause.EXPLAINER_ERROR: "calidad",
    FailClosedCause.TIMEOUT: "dependencia",
    FailClosedCause.FACTUALITY_FAILED: "calidad",
    FailClosedCause.FEATURE_DICTIONARY_INCOMPLETE: "desincronia",
    FailClosedCause.REGISTRY_UNAVAILABLE: "dependencia",
    FailClosedCause.MODEL_FROZEN: "congelamiento",
    FailClosedCause.SERVING_CONFIG_UNAVAILABLE: "dependencia",
}
if set(_CAUSE_CATEGORY) != set(FailClosedCause):  # una causa sin categoria no carga
    raise RuntimeError("toda FailClosedCause necesita category")


def _causes_by_category() -> dict[str, frozenset[FailClosedCause]]:
    grouped: dict[str, set[FailClosedCause]] = {}
    for cause, category in _CAUSE_CATEGORY.items():
        grouped.setdefault(category, set()).add(cause)
    return {category: frozenset(causes) for category, causes in grouped.items()}


FAIL_CLOSED_CAUSES_BY_CATEGORY: Final = MappingProxyType(_causes_by_category())


class LocalCause(StrEnum):
    SERVING_CONFIG_UNAVAILABLE = "serving_config_unavailable"
    SCORING_UNREACHABLE = "scoring_unreachable"
    SCORING_REJECTED = "scoring_rejected"


class ProblemCode(StrEnum):
    MALFORMED_REQUEST = "malformed_request"
    UNSUPPORTED_MEDIA_TYPE = "unsupported_media_type"
    VALIDATION_ERROR = "validation_error"
    UNAUTHENTICATED = "unauthenticated"
    FORBIDDEN = "forbidden"
    MFA_REQUIRED = "mfa_required"
    NOT_FOUND = "not_found"
    CONFLICT_STATE = "conflict_state"
    PAYLOAD_TOO_LARGE = "payload_too_large"
    RATE_LIMITED = "rate_limited"
    DEPENDENCY_UNAVAILABLE = "dependency_unavailable"
    INTERNAL_ERROR = "internal_error"
    UNPROCESSABLE_EXPLANATION = "unprocessable_explanation"
    DEADLINE_EXCEEDED = "deadline_exceeded"


PROBLEM_STATUS: Final = MappingProxyType(
    {
        ProblemCode.MALFORMED_REQUEST: 400,
        ProblemCode.UNSUPPORTED_MEDIA_TYPE: 415,
        ProblemCode.VALIDATION_ERROR: 422,
        ProblemCode.UNAUTHENTICATED: 401,
        ProblemCode.FORBIDDEN: 403,
        ProblemCode.MFA_REQUIRED: 403,
        ProblemCode.NOT_FOUND: 404,
        ProblemCode.CONFLICT_STATE: 409,
        ProblemCode.PAYLOAD_TOO_LARGE: 413,
        ProblemCode.RATE_LIMITED: 429,
        ProblemCode.DEPENDENCY_UNAVAILABLE: 503,
        ProblemCode.INTERNAL_ERROR: 500,
        ProblemCode.UNPROCESSABLE_EXPLANATION: 422,
        ProblemCode.DEADLINE_EXCEEDED: 504,
    }
)


class ProblemReason(StrEnum):
    DECISION_ALREADY_RECORDED = "decision_already_recorded"
    TRANSITION_PENDING = "transition_pending"
    VERSION_MISMATCH = "version_mismatch"
    FEATURE_DICTIONARY_INCOMPLETE = "feature_dictionary_incomplete"
    FACTUALITY_FAILED = "factuality_failed"
    NO_ACTIVE_VERSION = "no_active_version"
    ACTIVE_VERSION_FROZEN = "active_version_frozen"


REASON_ALLOWED_CODE: Final = MappingProxyType(
    {
        ProblemReason.DECISION_ALREADY_RECORDED: ProblemCode.CONFLICT_STATE,
        ProblemReason.TRANSITION_PENDING: ProblemCode.CONFLICT_STATE,
        ProblemReason.VERSION_MISMATCH: ProblemCode.CONFLICT_STATE,
        ProblemReason.FEATURE_DICTIONARY_INCOMPLETE: ProblemCode.UNPROCESSABLE_EXPLANATION,
        ProblemReason.FACTUALITY_FAILED: ProblemCode.UNPROCESSABLE_EXPLANATION,
        ProblemReason.NO_ACTIVE_VERSION: ProblemCode.CONFLICT_STATE,
        ProblemReason.ACTIVE_VERSION_FROZEN: ProblemCode.CONFLICT_STATE,
    }
)


class CreditStatus(StrEnum):
    EN_ESTUDIO = "en_estudio"
    APROBADO = "aprobado"
    DESEMBOLSADO = "desembolsado"
    RECHAZADO = "rechazado"
    CANCELADO = "cancelado"
    SIN_CREDITO = "sin_credito"
    NO_DISPONIBLE = "no_disponible"
    NO_INTEGRADO = "no_integrado"


class CaseState(StrEnum):
    EN_EVALUACION = "en_evaluacion"
    LISTO = "listo"
    EN_SINCRONIZACION = "en_sincronizacion"
    NO_DISPONIBLE = "no_disponible"
    MODELO_CONGELADO = "modelo_congelado"
    DECIDIDO = "decidido"
    VENCIDO = "vencido"


class Outcome(StrEnum):
    FAVORABLE = "favorable"
    DESFAVORABLE = "desfavorable"
    REVISION_REQUERIDA = "revision_requerida"


class FinalOutcome(StrEnum):
    FAVORABLE = "favorable"
    DESFAVORABLE = "desfavorable"


class Decision(StrEnum):
    SIGUE = "sigue"
    SE_APARTA = "se_aparta"
    RESUELVE_REVISION = "resuelve_revision"


class ServingState(StrEnum):
    ACTIVO = "activo"
    CONGELADO = "congelado"
    NO_DISPONIBLE = "no_disponible"


class ExplainerError(StrEnum):
    TIMEOUT = "timeout"
    UNAVAILABLE = "unavailable"
    ERROR = "error"
    VERSION_MISMATCH = "version_mismatch"
    FACTUALITY_FAILED = "factuality_failed"
    FEATURE_DICTIONARY_INCOMPLETE = "feature_dictionary_incomplete"


class RegistryError(StrEnum):
    UNAVAILABLE = "unavailable"


class EntryType(StrEnum):
    RECOMMENDATION = "recommendation"
    FAIL_CLOSED = "fail_closed"
    HUMAN_DECISION = "human_decision"
    EXPLANATION_VIEW = "explanation_view"
    MODEL_EVENT = "model_event"
    POLICY_EVENT = "policy_event"
    DATA_SOURCE_EVENT = "data_source_event"
    FREEZE = "freeze"
    FROZEN_RESOLUTION = "frozen_resolution"
    GENESIS = "genesis"
    CHECKPOINT = "checkpoint"


class LogEvent(StrEnum):
    """Catalogo de eventos (domain-entities §8.1, BR-U0-51)."""

    AUTHZ_DENIED = "authz.denied"
    RECOMMENDATION_FAIL_CLOSED = "recommendation.fail_closed"
    APPLICANT_SUMMARY_GENERATED = "applicant_summary.generated"
    CASE_VIEWED = "case.viewed"
    CASE_RETRY_REQUESTED = "case.retry_requested"
    EVALUATION_RESULT_DISCARDED = "evaluation.result_discarded"
    DISPARITY_VIEWED = "disparity.viewed"
    FREEZE_CONTEXT_VIEWED = "freeze_context.viewed"
    CONSOLE_CLIENT_ERROR = "console.client_error"
    REGISTRY_IDEMPOTENCY_CONFLICT = "registry.idempotency_conflict"


LOG_RECORD_FIELDS: Final = frozenset(
    {
        "timestamp",
        "level",
        "service",
        "correlation_id",
        "span_id",
        "event",
        "case_id",
        "model_version_id",
        "policy_version_id",
        "entry_type",
        "status",
        "http_method",
        "route_template",
        "duration_ms",
        "error_code",
        "fail_closed_cause",
        "attempt",
        "principal_kind",
        "principal_role",
        "seq",
        "recommendation_entry_id",
        "window_from",
        "window_to",
        "app_version",
        "principal_subject",
        "exception_type",
    }
)

#: Grupo de identificacion de §1.1 mas `free_text`: nunca en features ni en el registro
#: (BR-U0-34, BR-U0-95). `department_code` queda fuera por decision de la cuarta revision.
IDENTIFICATION_FIELDS: Final = frozenset(
    {
        "full_name",
        "document_type",
        "document_number",
        "birth_date",
        "phone",
        "email",
        "address",
        "municipality_code",
    }
)
FORBIDDEN_REGISTRY_KEYS: Final = IDENTIFICATION_FIELDS | {"free_text"}
