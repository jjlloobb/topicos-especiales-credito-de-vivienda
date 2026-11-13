"""Los dobles ligeros del gateway y del BFF (U12-T02, CA-8, CA-14 y CA-17), **validados contra el contrato**: lo que sirven existe en `contracts/openapi/case-service.yaml` y `console-bff.yaml`,
cada cuerpo 2xx valida con el modelo que el OpenAPI nombra y cada error es un `Problem` valido. Un doble con una ruta que no esta en el contrato, un estado que el contrato no declara o un campo
de mas, falla (`ContractError`). Los casos con fallos inyectados (429, 503, latencia) y los volumenes grandes usan este doble; los demas usan las apps reales (U8 y U10)."""

from __future__ import annotations

import copy
import json
import re
import uuid
from collections import Counter, deque
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import yaml
from vectra_contracts.catalog import ProblemCode
from vectra_contracts.models import api as api_models
from vectra_contracts.models import application as app_models
from vectra_contracts.models.api import Problem
from vectra_contracts.outcome import RecommendResult, read_wire

REPO = Path(__file__).resolve().parents[3]
OPENAPI = REPO / "contracts" / "openapi"
INTAKE_GATEWAY = "/api/intake/v1/intake/applications"
KEY_PATTERN = re.compile(r"^[\x21-\x7e]{1,128}$")
SCENARIO_PATTERN = re.compile(r"^[A-Za-z0-9_.:-]{1,100}$")
TEMPLATES = {"{id}": r"[^/]+"}
APPLICATION_VIEW = {
    "department_code": "11",
    "monthly_income": 8_000_000,
    "other_income": 0,
    "employment_type": "asalariado",
    "employment_months": 48,
    "monthly_obligations": 500_000,
    "max_days_past_due_12m": 0,
    "property_value": 300_000_000,
    "requested_amount": 150_000_000,
    "term_months": 180,
    "proposed_rate_ea": "0.1200",
    "property_condition": "usada",
    "channel": "web",
}
SHAP_IDS = ("installment_to_income", "loan_to_value", "age_years", "employment_type", "term_months")
OUTCOMES = ("favorable", "desfavorable", "revision_requerida")
CREATED = "2026-11-13T10:00:00Z"


class ContractError(AssertionError):
    """El doble sirvio algo que el contrato no dice."""


def _spec(name: str) -> dict[str, Any]:
    return yaml.safe_load((OPENAPI / name).read_text(encoding="utf-8"))  # type: ignore[no-any-return]


CASE_SPEC = _spec("case-service.yaml")
BFF_SPEC = _spec("console-bff.yaml")


def check_served(
    spec: dict[str, Any], method: str, template: str, status: int, body: bytes, model: type[Any] | None
) -> None:
    """La ruta y el metodo existen; el estado esta declarado; el cuerpo 2xx valida con el modelo que el OpenAPI nombra; un error es un `Problem`."""
    operation = spec["paths"].get(template, {}).get(method.lower())
    if operation is None:
        raise ContractError(f"ruta fuera del contrato: {method} {template}")
    declared = operation["responses"]
    if 200 <= status < 300:
        if str(status) not in declared:
            raise ContractError(
                f"{method} {template}: el contrato no declara {status} (declara {sorted(declared)})"
            )
        content = declared[str(status)].get("content", {}).get("application/json", {}).get("schema")
        if content is None:
            if body:
                raise ContractError(f"{method} {template}: {status} no lleva cuerpo")
            return
        name = content["$ref"].rsplit("/", 1)[-1]
        if model is None or not name.startswith(model.__name__.split("[")[0]):
            raise ContractError(f"{method} {template}: el contrato nombra {name}, el doble usa {model}")
        if model is api_models.CaseDetail:
            read_wire(model, body)  # `CaseDetail` contiene `Recommendation`: solo se lee con `read_wire`
        else:
            model.model_validate_json(body)  # estricto, sin campos de mas
    else:
        Problem.model_validate_json(body)


def problem(status: int, code: str, reason: str | None = None) -> dict[str, Any]:
    data: dict[str, Any] = {
        "type": f"urn:vectra:problem:{code}",
        "title": code,
        "status": status,
        "code": code,
        "correlation_id": "0" * 32,
    }
    if reason is not None:
        data["reason"] = reason
    Problem.model_validate_json(json.dumps(data))
    assert ProblemCode(code)
    return data


def recommendation_json(
    outcome: str, case_id: str, feature_ids: tuple[str, ...] = SHAP_IDS
) -> dict[str, Any]:
    body = {
        "kind": "recommendation",
        "case_id": case_id,
        "score": "0.4200",
        "confidence": "0.9000",
        "outcome": outcome,
        "reasons": [],
        "model_version_id": "mv-1",
        "policy_version_id": "p1",
        "explanation": {
            "model_version_id": "mv-1",
            "method": "shap",
            "shap_vector": [
                {"feature_id": f, "value": {"type": "decimal", "value": "0.3"}, "contribution": "0.12"}
                for f in feature_ids
            ],
            "base_value": "0.05",
            "narrative": "La relacion cuota/ingreso aumenta el riesgo.",
            "narrative_generator": "template:v1",
            "feature_dictionary_version": "d1",
            "posthoc_notice": "Aproximacion posterior.",
            "factuality_check": "passed",
        },
        "registry_entry_id": "7",
        "evaluated_at": CREATED,
        "feature_vector_hash": "a" * 64,
    }
    RecommendResult.from_wire(json.dumps(body))
    return body


_TEMPLATES: dict[str, dict[str, Any]] = {}


def case_detail_json(
    case_id: str, state: str, outcome: str, decision: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Un `CaseDetail` valido. Se valida una vez por `outcome`; los demas solo cambian el identificador y el estado (2 000 casos de la seccion `decisions` no se validan 2 000 veces)."""
    if outcome in _TEMPLATES:
        cached = copy.deepcopy(_TEMPLATES[outcome])
        cached["case_id"], cached["recommendation"]["case_id"], cached["state"] = case_id, case_id, state
        if decision is not None:
            cached["decision"] = decision
        return cached
    data: dict[str, Any] = {
        "case_id": case_id,
        "state": state,
        "channel": "web",
        "created_at": CREATED,
        "applicant_display": "A. G.",
        "application": APPLICATION_VIEW,
        "recommendation": recommendation_json(outcome, case_id),
        "recommendation_entry_id": "7",
        "model_frozen_after_recommendation": False,
        "anonymized": False,
        "attempts": 0,
        "outcome": outcome,
        "score": "0.4200",
    }
    if decision is not None:
        data["decision"] = decision
    read_wire(api_models.CaseDetail, json.dumps(data))
    _TEMPLATES[outcome] = copy.deepcopy(data)
    return data


class LightGateway(httpx.BaseTransport):
    """El gateway con el servicio de ingesta (U8) y el BFF (U10) detras, en proceso. Cada respuesta pasa por `check_served` antes de salir."""

    def __init__(self, clock: Any = None) -> None:
        self.clock = clock
        self.requests: list[httpx.Request] = []
        self.sent_at: list[float] = []
        self.sent_by_path: Counter[str] = Counter()
        self.intake_script: deque[tuple[int, dict[str, str]]] = (
            deque()
        )  # estados forzados (429, 503) que se consumen primero
        self.intake_bodies: list[bytes] = []
        self.intake_keys: list[str] = []
        self.keys_seen: dict[str, str] = {}
        self.cases: dict[str, dict[str, Any]] = {}
        self.decision_posts: Counter[str] = Counter()
        self.view_posts: Counter[str] = Counter()
        self.conflict_ids: set[str] = set()  # 409 `decision_already_recorded`
        self.invalid_ids: set[str] = set()  # 422
        self.auto_ready = True  # un caso aceptado queda `listo` (el servicio real tarda; aqui no importa)
        self.status_override: dict[str, int] = {}
        self.conflict_next = 0  # los proximos N casos aceptados quedan en 409 al decidirse
        self.models: dict[
            str, dict[str, Any]
        ] = {}  # U12-T03: las rutas de modelos del BFF (`ModelVersion`, validado contra el contrato)

    # ---- ruteo ---------------------------------------------------------------------------------------------------------------------------------
    def handle_request(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.clock is not None:
            self.sent_at.append(self.clock.monotonic())
        path = request.url.path
        self.sent_by_path[f"{request.method} {path}"] += 1
        if path == INTAKE_GATEWAY and request.method == "POST":
            return self._intake(request)
        if path.startswith("/api/console/"):
            return self._console(request)
        return self._reply(CASE_SPEC, request.method, path, 404, problem(404, "not_found"), None)

    def _reply(
        self,
        spec: dict[str, Any],
        method: str,
        template: str,
        status: int,
        payload: Any,
        model: type[Any] | None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        body = b"" if payload is None else json.dumps(payload).encode()
        if template in spec["paths"]:  # un 404 de una ruta que no existe no se valida contra el contrato
            check_served(spec, method, template, status, body, model)
        elif status < 400:
            raise ContractError(f"ruta fuera del contrato: {method} {template}")
        return httpx.Response(
            status, content=body, headers={"content-type": "application/json", **(headers or {})}
        )

    # ---- ingesta (U8) --------------------------------------------------------------------------------------------------------------------------
    def _intake(self, request: httpx.Request) -> httpx.Response:
        template = "/v1/intake/applications"  # el gateway reescribe `/api/intake/v1/...` a `/v1/...`
        self.intake_bodies.append(request.content)
        key = request.headers.get("Idempotency-Key", "")
        scenario = request.headers.get("X-Test-Scenario")
        if self.intake_script:
            status, headers = self.intake_script.popleft()
            return self._reply(
                CASE_SPEC,
                "POST",
                template,
                status,
                problem(
                    status,
                    {429: "rate_limited", 503: "dependency_unavailable"}.get(status, "validation_error"),
                ),
                None,
                headers,
            )
        if not KEY_PATTERN.fullmatch(key) or (
            scenario is not None and not SCENARIO_PATTERN.fullmatch(scenario)
        ):
            return self._reply(CASE_SPEC, "POST", template, 422, problem(422, "validation_error"), None)
        try:
            app_models.ApplicationIn.model_validate_json(request.content)
        except ValueError:
            return self._reply(CASE_SPEC, "POST", template, 422, problem(422, "validation_error"), None)
        self.intake_keys.append(key)
        digest = request.content.decode()
        if key in self.keys_seen:  # reenvio de la misma clave: la misma respuesta si el cuerpo es el mismo
            if self.keys_seen[key] != digest:
                return self._reply(
                    CASE_SPEC, "POST", template, 409, problem(409, "idempotency_conflict"), None
                )
        self.keys_seen[key] = digest
        case_id = str(uuid.uuid5(uuid.NAMESPACE_URL, key))
        if case_id not in self.cases:
            outcome = OUTCOMES[len(self.cases) % 3]
            self.cases[case_id] = case_detail_json(
                case_id, "listo" if self.auto_ready else "en_evaluacion", outcome
            )
            if self.conflict_next > 0:
                self.conflict_ids.add(case_id)
                self.conflict_next -= 1
        return self._reply(
            CASE_SPEC,
            "POST",
            template,
            200,
            {"case_id": case_id, "state": "en_evaluacion"},
            app_models.CaseRef,
        )

    # ---- BFF (U10) -----------------------------------------------------------------------------------------------------------------------------
    def _console(self, request: httpx.Request) -> httpx.Response:
        path, method = request.url.path, request.method
        forced = self.status_override.get(f"{method} {path}")
        for template, handler in self._routes():
            found = re.fullmatch(template.replace("{id}", "([^/]+)"), path)
            if found and handler[0] == method:
                if forced:
                    return self._reply(
                        BFF_SPEC,
                        method,
                        template,
                        forced,
                        problem(forced, "forbidden" if forced == 403 else "unauthenticated"),
                        None,
                    )
                return handler[1](request, template, *found.groups())
        return self._reply(BFF_SPEC, method, path, 404, problem(404, "not_found"), None)

    def _routes(self) -> list[tuple[str, tuple[str, Callable[..., httpx.Response]]]]:
        base = "/api/console"
        return [
            (f"{base}/me", ("GET", self._me)),
            (f"{base}/cases", ("GET", self._list)),
            (f"{base}/cases/{{id}}", ("GET", self._detail)),
            (f"{base}/cases/{{id}}/explanation-views", ("POST", self._view)),
            (f"{base}/cases/{{id}}/decision", ("POST", self._decide)),
            (f"{base}/models/{{id}}/frozen-resolution", ("POST", self._frozen)),
            (f"{base}/models", ("GET", self._models_list)),
            (f"{base}/models", ("POST", self._models_register)),
            (f"{base}/models/{{id}}", ("GET", self._model_detail)),
            (f"{base}/models/{{id}}/validations", ("POST", self._model_validation)),
            (f"{base}/models/{{id}}/approval", ("POST", self._model_approval)),
        ]

    def _me(self, request: httpx.Request, template: str) -> httpx.Response:
        body = {"role": "analista", "mfa": True, "auth_time": CREATED, "locale": "es-CO"}
        return self._reply(BFF_SPEC, "GET", template, 200, body, api_models.SessionInfo)

    def _list(self, request: httpx.Request, template: str) -> httpx.Response:
        state = request.url.params.get("state")
        page, size = int(request.url.params.get("page", "1")), int(request.url.params.get("page_size", "20"))
        items = [c for c in self.cases.values() if state is None or c["state"] == state]
        chosen = items[(page - 1) * size : page * size]
        summaries = [
            {
                k: c[k]
                for k in (
                    "case_id",
                    "state",
                    "channel",
                    "created_at",
                    "applicant_display",
                    "outcome",
                    "score",
                )
            }
            for c in chosen
        ]
        return self._reply(
            BFF_SPEC,
            "GET",
            template,
            200,
            {"items": summaries, "next_seq_after": None},
            api_models.Page[app_models.CaseSummary],
        )

    def _detail(self, request: httpx.Request, template: str, case_id: str) -> httpx.Response:
        case = self.cases.get(case_id)
        if case is None:
            return self._reply(BFF_SPEC, "GET", template, 404, problem(404, "not_found"), None)
        return self._reply(BFF_SPEC, "GET", template, 200, case, api_models.CaseDetail)

    def _view(self, request: httpx.Request, template: str, case_id: str) -> httpx.Response:
        self.view_posts[case_id] += 1
        return self._reply(BFF_SPEC, "POST", template, 204, None, None)

    def _decide(self, request: httpx.Request, template: str, case_id: str) -> httpx.Response:
        self.decision_posts[case_id] += 1
        case = self.cases.get(case_id)
        if case is None:
            return self._reply(BFF_SPEC, "POST", template, 404, problem(404, "not_found"), None)
        if case_id in self.invalid_ids:
            return self._reply(BFF_SPEC, "POST", template, 422, problem(422, "validation_error"), None)
        if case_id in self.conflict_ids or case["state"] != "listo":
            return self._reply(
                BFF_SPEC,
                "POST",
                template,
                409,
                problem(409, "conflict_state", "decision_already_recorded"),
                None,
            )
        try:
            api_models.DecisionIn.model_validate_json(request.content)
        except ValueError:
            return self._reply(BFF_SPEC, "POST", template, 422, problem(422, "validation_error"), None)
        case["state"] = "decidido"
        body = {
            "case_id": case_id,
            "registry_entry_id": "8",
            "recorded_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        }
        return self._reply(BFF_SPEC, "POST", template, 200, body, api_models.DecisionRef)

    def _frozen(self, request: httpx.Request, template: str, model_id: str) -> httpx.Response:
        return self._reply(BFF_SPEC, "POST", template, 204, None, None)

    # ---- rutas de modelos del BFF (U12-T03) ------------------------------------------------------------------------------------------------------
    def _models_list(self, request: httpx.Request, template: str) -> httpx.Response:
        from vectra_contracts.models.governance import ModelVersion

        state = request.url.params.get("state")
        items = [m for m in self.models.values() if state is None or m["state"] == state]
        return self._reply(
            BFF_SPEC,
            "GET",
            template,
            200,
            {"items": items, "next_seq_after": None},
            api_models.Page[ModelVersion],
        )

    def _models_register(self, request: httpx.Request, template: str) -> httpx.Response:
        import bff_builders
        from vectra_contracts.models.governance import ModelRegistration, ModelVersion

        try:
            body = ModelRegistration.model_validate_json(request.content)
        except ValueError:
            return self._reply(BFF_SPEC, "POST", template, 422, problem(422, "validation_error"), None)
        model_id = body.artifact_uri.split("/")[-2]
        if model_id in self.models:
            return self._reply(BFF_SPEC, "POST", template, 409, problem(409, "conflict_state"), None)
        self.models[model_id] = bff_builders.model_version(model_id, "registrado")
        return self._reply(BFF_SPEC, "POST", template, 200, self.models[model_id], ModelVersion)

    def _model_detail(self, request: httpx.Request, template: str, model_id: str) -> httpx.Response:
        from vectra_contracts.models.governance import ModelVersionDetail

        model = self.models.get(model_id)
        if model is None:
            return self._reply(BFF_SPEC, "GET", template, 404, problem(404, "not_found"), None)
        return self._reply(BFF_SPEC, "GET", template, 200, model, ModelVersionDetail)

    def _model_validation(self, request: httpx.Request, template: str, model_id: str) -> httpx.Response:
        import bff_builders
        from vectra_contracts.models.governance import ValidationRun

        if model_id not in self.models:
            return self._reply(BFF_SPEC, "POST", template, 404, problem(404, "not_found"), None)
        self.models[model_id]["state"] = "en_validacion"
        return self._reply(
            BFF_SPEC, "POST", template, 200, bff_builders.validation_run(model_id), ValidationRun
        )

    def _model_approval(self, request: httpx.Request, template: str, model_id: str) -> httpx.Response:
        from vectra_contracts.models.governance import ModelApprovalIn

        if model_id not in self.models:
            return self._reply(BFF_SPEC, "POST", template, 404, problem(404, "not_found"), None)
        ModelApprovalIn.model_validate_json(request.content)
        self.models[model_id]["state"] = "aprobado"
        return self._reply(BFF_SPEC, "POST", template, 204, None, None)
