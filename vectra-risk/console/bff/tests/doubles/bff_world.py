"""El mundo de los dobles y una solicitud valida por endpoint, para la matriz y los ejemplos de la API.

`populate(doubles)` deja cada destino en un estado que **acepta** la accion de cada endpoint (cada regla de objeto tiene su
objeto en el estado que admite), de modo que una celda de la matriz da 2xx solo si los tres controles pasan. Los cuerpos se
validan con los modelos de U0 de la ruta del BFF.
"""

import re
from dataclasses import dataclass, field
from typing import Any

import bff_builders as b
from bff_doubles import Doubles
from strategies.domain import application_dict
from vectra_contracts.routes import REGISTRY

CASE_LISTO = b.uuid_of(1)
CASE_NO_DISPONIBLE = b.uuid_of(2)
CASE_DECIDIDO = b.uuid_of(3)
CASE_ANONIMIZADO = b.uuid_of(4)
SOURCE = "ds-1"
POLICY = "pv-1"
P = "/api/console"
_IDS = (
    CASE_LISTO,
    CASE_NO_DISPONIBLE,
    CASE_DECIDIDO,
    "mv-registrado",
    "mv-lista",
    "mv-congelado",
    "mv-inactivo",
    "mv-activo",
    SOURCE,
    POLICY,
    "chk-1",
    "freeze-mv-1",
)


@dataclass(frozen=True)
class Endpoint:
    operation_id: str
    method: str
    path: str
    body: Any = None
    query: str = ""
    headers: dict[str, str] = field(default_factory=dict)

    @property
    def path_template(self) -> str:
        """La plantilla de la ruta del BFF (la de C03 y `REGISTRY`), con el identificador de la solicitud sustituido por `{id}`."""
        return re.sub(r"(?<=/)(?:" + "|".join(re.escape(i) for i in _IDS) + r")(?=/|$)", "{id}", self.path)


def populate(doubles: Doubles) -> None:
    case, gov = doubles.case, doubles.governance
    case.details = {
        CASE_LISTO: b.case_detail(CASE_LISTO, "listo"),
        CASE_NO_DISPONIBLE: b.case_detail(CASE_NO_DISPONIBLE, "no_disponible", entry_id=None),
        CASE_DECIDIDO: b.case_detail(CASE_DECIDIDO, "decidido", final_outcome="desfavorable"),
        CASE_ANONIMIZADO: b.case_detail(CASE_ANONIMIZADO, "no_disponible", anonymized=True, entry_id=None),
    }
    case.identifiers = {
        CASE_LISTO: b.case_identifiers(CASE_LISTO),
        CASE_ANONIMIZADO: b.case_identifiers(CASE_ANONIMIZADO, anonymized=True),
    }
    for model_id, state in (
        ("mv-registrado", "registrado"),
        ("mv-lista", "lista_para_aprobacion"),
        ("mv-congelado", "congelado"),
        ("mv-inactivo", "inactivo"),
        ("mv-activo", "activo"),
    ):
        gov.add_model(model_id, state)
    gov.add_model("mv-cand", "registrado", source_candidate_for=SOURCE)
    gov.policies = [b.policy_version(POLICY, "propuesta")]
    gov.sources = [b.data_source(SOURCE, "en_evaluacion", report=True)]


def _decision_body() -> dict[str, Any]:
    return {
        "decision": "sigue",
        "final_outcome": "favorable",
        "used_factors": ["ninguno"],
        "justification": "",
    }


def _registration() -> dict[str, Any]:
    sha = "b" * 64
    return {
        "artifact_uri": "s3://m/a.onnx",
        "artifact_format": "onnx",
        "artifact_sha256": sha,
        "explainer_uri": "s3://m/e.bin",
        "explainer_sha256": sha,
        "manifest_uri": "s3://m/m.json",
        "manifest_sha256": sha,
    }


def _requests() -> dict[str, Endpoint]:
    def e(
        op: str, method: str, path: str, body: Any = None, query: str = "", **headers: str
    ) -> tuple[str, Endpoint]:
        return op, Endpoint(op, method, P + path, body, query, headers)

    return dict(
        [
            e("get_api_console_me", "GET", "/me"),
            e(
                "post_api_console_client-errors",
                "POST",
                "/client-errors",
                {"error_code": "render_error", "route_template": "/casos/:id", "app_version": "1.0.0"},
            ),
            e("get_api_console_cases", "GET", "/cases", query="state=listo&page_size=10"),
            e("get_api_console_cases_failures", "GET", "/cases/failures"),
            e("get_api_console_cases_id", "GET", f"/cases/{CASE_LISTO}"),
            e(
                "post_api_console_cases",
                "POST",
                "/cases",
                application_dict(),
                **{"idempotency-key": "11111111-1111-4111-8111-111111111111"},
            ),
            e(
                "post_api_console_cases_id_explanation-views",
                "POST",
                f"/cases/{CASE_LISTO}/explanation-views",
            ),
            e(
                "post_api_console_cases_id_decision",
                "POST",
                f"/cases/{CASE_LISTO}/decision",
                _decision_body(),
            ),
            e(
                "post_api_console_cases_id_applicant-summary",
                "POST",
                f"/cases/{CASE_DECIDIDO}/applicant-summary",
            ),
            e("post_api_console_cases_id_retry", "POST", f"/cases/{CASE_NO_DISPONIBLE}/retry"),
            e("get_api_console_cases_id_dossier", "GET", f"/cases/{CASE_LISTO}/dossier"),
            e("post_api_console_integrity-checks", "POST", "/integrity-checks", {"mode": "full"}),
            e("get_api_console_integrity-checks_id", "GET", "/integrity-checks/chk-1"),
            e("get_api_console_models", "GET", "/models", query="state=activo"),
            e("get_api_console_models_id", "GET", "/models/mv-activo"),
            e("post_api_console_models", "POST", "/models", _registration()),
            e("post_api_console_models_id_validations", "POST", "/models/mv-registrado/validations"),
            e(
                "post_api_console_data-sources_id_comparisons",
                "POST",
                f"/data-sources/{SOURCE}/comparisons",
                {"candidate_version_id": "mv-cand"},
            ),
            e(
                "post_api_console_models_id_approval",
                "POST",
                "/models/mv-lista/approval",
                {"decision": "aprobado"},
            ),
            e(
                "post_api_console_models_id_frozen-resolution",
                "POST",
                "/models/mv-congelado/frozen-resolution",
                {"action": "reactivar", "justification": "revisado"},
            ),
            e("post_api_console_models_id_retirement", "POST", "/models/mv-inactivo/retirement"),
            e("get_api_console_policies", "GET", "/policies"),
            e(
                "post_api_console_policies",
                "POST",
                "/policies",
                {
                    "cutoff": "0.5000",
                    "low_confidence_threshold": "0.6000",
                    "channel_rules": [],
                    "normative": [],
                },
            ),
            e(
                "post_api_console_policies_id_approval",
                "POST",
                f"/policies/{POLICY}/approval",
                {"decision": "aprobada"},
            ),
            e("get_api_console_data-sources", "GET", "/data-sources"),
            e(
                "post_api_console_data-sources",
                "POST",
                "/data-sources",
                {"name": "Buro", "description": "x", "provides_features": ["f"], "owner": "riesgos"},
            ),
            e(
                "post_api_console_data-sources_id_decision",
                "POST",
                f"/data-sources/{SOURCE}/decision",
                {"decision": "aprobada"},
            ),
            e("get_api_console_disparity", "GET", "/disparity"),
            e("get_api_console_freezes", "GET", "/freezes"),
            e("get_api_console_freezes_id", "GET", "/freezes/freeze-mv-1"),
        ]
    )


REQUESTS = _requests()
ENDPOINTS = tuple(REQUESTS.values())


def contract_of(endpoint: Endpoint) -> Any:
    return next(r for r in REGISTRY["console-bff"] if r.operation_id == endpoint.operation_id)
