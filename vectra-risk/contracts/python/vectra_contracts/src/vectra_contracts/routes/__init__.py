"""Registro de contratos de rutas (P-U0-12; component-methods.md y component-dependency.md §2)."""

from dataclasses import dataclass
from typing import Final, Literal

from pydantic import BaseModel, RootModel, TypeAdapter

from vectra_contracts.catalog import Role, Scope
from vectra_contracts.models import api as a
from vectra_contracts.models import application as ap
from vectra_contracts.models import features as f
from vectra_contracts.models import governance as g
from vectra_contracts.models import monitoring as m
from vectra_contracts.models import registry as r
from vectra_contracts.outcome import RecommendResult

Method = Literal["GET", "POST", "PUT", "DELETE"]
DEFAULT_MAX_BODY: Final = 32 * 1024
HARD_MAX_BODY: Final = 128 * 1024
MFA_MAX_AGE: Final = 900


@dataclass(frozen=True)
class RouteContract:
    service: str
    method: Method
    path: str
    request_model: type[BaseModel] | None = None
    response_model: type[BaseModel] | None = None
    scopes: frozenset[Scope] = frozenset()
    any_scopes: frozenset[Scope] = frozenset()
    roles: frozenset[Role] = frozenset()
    mfa: bool = False
    mfa_max_age: int = MFA_MAX_AGE
    port: int = 8080
    read_only: bool = False
    max_body_bytes: int = DEFAULT_MAX_BODY

    @property
    def operation_id(self) -> str:
        return f"{self.method.lower()}_{self.path.strip('/').replace('/', '_').replace('{', '').replace('}', '').replace(':', '_')}"


def _list_of[T](model: type[T]) -> type[BaseModel]:
    return RootModel[list[model]]  # type: ignore[valid-type]


ANALISTA: Final = frozenset({Role.ANALISTA})
CRO: Final = frozenset({Role.CRO})
CUMPLIMIENTO: Final = frozenset({Role.CUMPLIMIENTO})
INGENIERO: Final = frozenset({Role.INGENIERO_RIESGO})
ANALISTA_CRO: Final = frozenset({Role.ANALISTA, Role.CRO})
CRO_CUMPLIMIENTO: Final = frozenset({Role.CRO, Role.CUMPLIMIENTO})
ING_CRO_CUM: Final = frozenset({Role.INGENIERO_RIESGO, Role.CRO, Role.CUMPLIMIENTO})
ANA_CRO_CUM: Final = frozenset({Role.ANALISTA, Role.CRO, Role.CUMPLIMIENTO})
ALL_ROLES: Final = frozenset({Role.ANALISTA, Role.INGENIERO_RIESGO, Role.CRO, Role.CUMPLIMIENTO})


def _case() -> list[RouteContract]:
    s = "case-service"
    return [
        RouteContract(
            s,
            "POST",
            "/v1/intake/applications",
            ap.ApplicationIn,
            ap.CaseRef,
            scopes=frozenset({Scope.INTAKE_SUBMIT}),
        ),
        RouteContract(s, "POST", "/v1/cases", ap.ApplicationIn, ap.CaseRef, roles=ANALISTA),
        RouteContract(s, "GET", "/v1/cases", None, a.Page[ap.CaseSummary], roles=ANALISTA_CRO),
        RouteContract(s, "GET", "/v1/cases/failures", None, _list_of(ap.PersistentFailure), roles=CRO),
        RouteContract(s, "GET", "/v1/cases/{id}", None, a.CaseDetail, roles=ANALISTA_CRO),
        RouteContract(
            s, "GET", "/v1/cases/{id}/identifiers", None, ap.CaseIdentifiers, roles=CRO_CUMPLIMIENTO
        ),
        RouteContract(s, "POST", "/v1/cases/{id}/explanation-views", roles=ANALISTA),
        RouteContract(s, "POST", "/v1/cases/{id}/decision", a.DecisionIn, a.DecisionRef, roles=ANALISTA),
        RouteContract(s, "POST", "/v1/cases/{id}/retry", None, ap.CaseRef, roles=CRO),
    ]


def _scoring() -> list[RouteContract]:
    return [
        RouteContract(
            "scoring-service",
            "POST",
            "/v1/recommendations",
            a.ScoringRequest,
            RecommendResult,
            scopes=frozenset({Scope.CASE_RECOMMEND}),
        ),
    ]


def _explainability() -> list[RouteContract]:
    s = "explainability-service"
    return [
        RouteContract(
            s, "POST", "/v1/explanations", a.ExplainRequest, None, scopes=frozenset({Scope.SCORING_EXPLAIN})
        ),
        RouteContract(
            s,
            "POST",
            "/v1/applicant-summaries",
            a.ApplicantSummaryRequest,
            a.ApplicantSummary,
            roles=ANALISTA_CRO,
        ),
    ]


def _governance() -> list[RouteContract]:
    s = "governance-service"
    return [
        RouteContract(
            s, "POST", "/v1/models", g.ModelRegistration, g.ModelVersion, roles=INGENIERO, mfa=True
        ),
        RouteContract(
            s, "POST", "/v1/models/{id}/validations", None, g.ValidationRun, roles=INGENIERO, mfa=True
        ),
        RouteContract(
            s,
            "POST",
            "/v1/data-sources/{id}/comparisons",
            g.SourceComparisonIn,
            g.ValidationRun,
            roles=INGENIERO,
            mfa=True,
        ),
        RouteContract(
            s,
            "PUT",
            "/v1/validation-runs/{run_id}/source-counts",
            m.SourceCountsIn,
            scopes=frozenset({Scope.GOVERNANCE_VALIDATION_REPORT}),
            max_body_bytes=64 * 1024,
        ),
        RouteContract(
            s,
            "PUT",
            "/v1/models/{id}/validation-report",
            g.ValidationReport,
            scopes=frozenset({Scope.GOVERNANCE_VALIDATION_REPORT}),
            max_body_bytes=64 * 1024,
        ),
        RouteContract(s, "POST", "/v1/models/{id}/approval", g.ModelApprovalIn, roles=CRO, mfa=True),
        RouteContract(s, "POST", "/v1/models/{id}/retirement", None, g.ModelVersion, roles=CRO, mfa=True),
        RouteContract(s, "GET", "/v1/models", None, a.Page[g.ModelVersion], roles=ING_CRO_CUM),
        RouteContract(s, "GET", "/v1/models/{id}", None, g.ModelVersionDetail, roles=ING_CRO_CUM),
        RouteContract(
            s,
            "POST",
            "/v1/models/{id}/activation",
            g.ActivationIn,
            scopes=frozenset({Scope.GOVERNANCE_PROMOTION}),
            roles=INGENIERO,
            mfa=True,
        ),
        RouteContract(
            s,
            "POST",
            "/v1/models/{id}/freeze",
            m.FreezeContext,
            scopes=frozenset({Scope.GOVERNANCE_FREEZE}),
            max_body_bytes=64 * 1024,
        ),
        RouteContract(
            s, "POST", "/v1/models/{id}/frozen-resolution", g.FrozenResolutionIn, roles=CUMPLIMIENTO, mfa=True
        ),
        RouteContract(
            s,
            "GET",
            "/v1/serving-config",
            None,
            g.ServingConfig,
            scopes=frozenset({Scope.GOVERNANCE_READ_SERVING}),
        ),
        RouteContract(
            s,
            "GET",
            "/v1/models/{id}/feature-spec",
            None,
            f.FeatureSpec,
            scopes=frozenset({Scope.GOVERNANCE_READ_FEATURE_SPEC}),
        ),
        RouteContract(
            s,
            "GET",
            "/v1/models/{id}/feature-dictionary",
            None,
            f.FeatureDictionary,
            scopes=frozenset({Scope.GOVERNANCE_READ_DICTIONARY}),
        ),
        RouteContract(s, "GET", "/v1/policies", None, _list_of(g.PolicyVersion), roles=ANA_CRO_CUM),
        RouteContract(s, "POST", "/v1/policies", g.PolicyDraft, g.PolicyVersion, roles=CRO, mfa=True),
        RouteContract(s, "POST", "/v1/policies/{id}/approval", roles=CRO, mfa=True),
        RouteContract(s, "GET", "/v1/data-sources", None, _list_of(g.DataSource), roles=ING_CRO_CUM),
        RouteContract(
            s, "POST", "/v1/data-sources", g.DataSourceProposal, g.DataSource, roles=INGENIERO, mfa=True
        ),
        RouteContract(
            s, "POST", "/v1/data-sources/{id}/decision", g.DataSourceDecisionIn, roles=CUMPLIMIENTO, mfa=True
        ),
    ]


def _bias() -> list[RouteContract]:
    s = "bias-monitoring-service"
    return [
        RouteContract(
            s,
            "POST",
            "/v1/source-comparisons",
            m.CompareSourceRequest,
            m.PrePostReport,
            scopes=frozenset({Scope.BIAS_COMPARE}),
            max_body_bytes=64 * 1024,
        ),
        RouteContract(s, "GET", "/v1/disparity", None, m.DisparityView, roles=CRO_CUMPLIMIENTO),
        RouteContract(s, "GET", "/v1/freezes", None, _list_of(m.FreezeSummary), roles=CRO_CUMPLIMIENTO),
        RouteContract(s, "GET", "/v1/freezes/{id}", None, m.FreezeRecord, roles=CUMPLIMIENTO),
    ]


def _registry() -> list[RouteContract]:
    s = "decision-registry-service"
    return [
        RouteContract(
            s,
            "POST",
            "/v1/entries",
            r.RegistryEntryIn,
            None,
            any_scopes=frozenset(
                {Scope.REGISTRY_APPEND_CASE, Scope.REGISTRY_APPEND_SCORING, Scope.REGISTRY_APPEND_GOVERNANCE}
            ),
            max_body_bytes=80 * 1024,
        ),
        RouteContract(
            s,
            "GET",
            "/v1/entries",
            None,
            a.Page[r.RegistryEntry],
            any_scopes=frozenset(
                {Scope.REGISTRY_READ_EXPLANATION, Scope.REGISTRY_READ_METRICS, Scope.REGISTRY_READ_MONITORING}
            ),
        ),
        RouteContract(
            s,
            "POST",
            "/v1/monitoring/daily:query",
            m.MonitoringQuery,
            m.MonitoringWindow,
            scopes=frozenset({Scope.REGISTRY_READ_MONITORING}),
            read_only=True,
        ),
        RouteContract(
            s,
            "GET",
            "/v1/monitoring/freezes",
            None,
            _list_of(m.FreezeRecord),
            scopes=frozenset({Scope.REGISTRY_READ_MONITORING}),
        ),
        RouteContract(s, "GET", "/v1/dossiers/{case_id}", None, r.RegistryDossier, roles=CRO_CUMPLIMIENTO),
        RouteContract(
            s,
            "POST",
            "/v1/integrity-checks",
            r.IntegrityCheckRequest,
            r.IntegrityCheckRef,
            roles=CRO,
            mfa=True,
        ),
        RouteContract(s, "GET", "/v1/integrity-checks/{id}", None, r.IntegrityCheckStatus, roles=CRO),
    ]


def _core() -> list[RouteContract]:
    s = "core-banking-mock"
    return [
        RouteContract(
            s, "GET", "/v1/credits/{id}", None, a.CreditStatusView, scopes=frozenset({Scope.CORE_READ_CREDIT})
        ),
        RouteContract(
            s,
            "POST",
            "/v1/credits/{id}/status",
            a.CreditStatusView,
            scopes=frozenset({Scope.CORE_WRITE_CREDIT}),
        ),
    ]


def _bff() -> list[RouteContract]:
    s = "console-bff"
    p = "/api/console"
    return [
        RouteContract(s, "GET", f"{p}/me", None, a.SessionInfo, roles=ALL_ROLES),
        RouteContract(s, "POST", f"{p}/client-errors", a.ClientErrorReport, roles=ALL_ROLES),
        RouteContract(s, "GET", f"{p}/cases", None, a.Page[ap.CaseSummary], roles=ANALISTA_CRO),
        RouteContract(s, "GET", f"{p}/cases/failures", None, _list_of(ap.PersistentFailure), roles=CRO),
        RouteContract(s, "GET", f"{p}/cases/{{id}}", None, a.CaseDetail, roles=ANALISTA_CRO),
        RouteContract(s, "POST", f"{p}/cases", ap.ApplicationIn, ap.CaseRef, roles=ANALISTA),
        RouteContract(s, "POST", f"{p}/cases/{{id}}/explanation-views", roles=ANALISTA),
        RouteContract(s, "POST", f"{p}/cases/{{id}}/decision", a.DecisionIn, a.DecisionRef, roles=ANALISTA),
        RouteContract(
            s, "POST", f"{p}/cases/{{id}}/applicant-summary", None, a.ApplicantSummary, roles=ANALISTA_CRO
        ),
        RouteContract(s, "POST", f"{p}/cases/{{id}}/retry", None, ap.CaseRef, roles=CRO),
        RouteContract(s, "GET", f"{p}/cases/{{id}}/dossier", None, a.ConsoleDossier, roles=CRO_CUMPLIMIENTO),
        RouteContract(
            s,
            "POST",
            f"{p}/integrity-checks",
            r.IntegrityCheckRequest,
            r.IntegrityCheckRef,
            roles=CRO,
            mfa=True,
        ),
        RouteContract(s, "GET", f"{p}/integrity-checks/{{id}}", None, r.IntegrityCheckStatus, roles=CRO),
        RouteContract(s, "GET", f"{p}/models", None, a.Page[g.ModelVersion], roles=ING_CRO_CUM),
        RouteContract(s, "GET", f"{p}/models/{{id}}", None, g.ModelVersionDetail, roles=ING_CRO_CUM),
        RouteContract(
            s, "POST", f"{p}/models", g.ModelRegistration, g.ModelVersion, roles=INGENIERO, mfa=True
        ),
        RouteContract(
            s, "POST", f"{p}/models/{{id}}/validations", None, g.ValidationRun, roles=INGENIERO, mfa=True
        ),
        RouteContract(
            s,
            "POST",
            f"{p}/data-sources/{{id}}/comparisons",
            g.SourceComparisonIn,
            g.ValidationRun,
            roles=INGENIERO,
            mfa=True,
        ),
        RouteContract(s, "POST", f"{p}/models/{{id}}/approval", g.ModelApprovalIn, roles=CRO, mfa=True),
        RouteContract(
            s,
            "POST",
            f"{p}/models/{{id}}/frozen-resolution",
            g.FrozenResolutionIn,
            roles=CUMPLIMIENTO,
            mfa=True,
        ),
        RouteContract(s, "POST", f"{p}/models/{{id}}/retirement", None, g.ModelVersion, roles=CRO, mfa=True),
        RouteContract(s, "GET", f"{p}/policies", None, _list_of(g.PolicyVersion), roles=ANA_CRO_CUM),
        RouteContract(s, "POST", f"{p}/policies", g.PolicyDraft, g.PolicyVersion, roles=CRO, mfa=True),
        RouteContract(s, "POST", f"{p}/policies/{{id}}/approval", roles=CRO, mfa=True),
        RouteContract(s, "GET", f"{p}/data-sources", None, _list_of(g.DataSource), roles=ING_CRO_CUM),
        RouteContract(
            s, "POST", f"{p}/data-sources", g.DataSourceProposal, g.DataSource, roles=INGENIERO, mfa=True
        ),
        RouteContract(
            s,
            "POST",
            f"{p}/data-sources/{{id}}/decision",
            g.DataSourceDecisionIn,
            roles=CUMPLIMIENTO,
            mfa=True,
        ),
        RouteContract(s, "GET", f"{p}/disparity", None, m.DisparityView, roles=CRO_CUMPLIMIENTO),
        RouteContract(s, "GET", f"{p}/freezes", None, _list_of(m.FreezeSummary), roles=CRO_CUMPLIMIENTO),
        RouteContract(s, "GET", f"{p}/freezes/{{id}}", None, m.FreezeRecord, roles=CUMPLIMIENTO),
    ]


REGISTRY: Final[dict[str, list[RouteContract]]] = {
    "case-service": _case(),
    "scoring-service": _scoring(),
    "explainability-service": _explainability(),
    "governance-service": _governance(),
    "bias-monitoring-service": _bias(),
    "decision-registry-service": _registry(),
    "core-banking-mock": _core(),
    "console-bff": _bff(),
}


def all_routes() -> list[RouteContract]:
    return [route for routes in REGISTRY.values() for route in routes]


__all__ = [
    "DEFAULT_MAX_BODY",
    "HARD_MAX_BODY",
    "MFA_MAX_AGE",
    "REGISTRY",
    "RouteContract",
    "TypeAdapter",
    "all_routes",
]
