"""Los cinco dobles HTTP de los destinos del BFF (case, governance, registry, explainability, bias).

Cada doble es un `httpx.AsyncBaseTransport` que se inyecta por el parametro `transport` de `DependencyClient` (sin sockets, sin
clúster). Sirve **solo** rutas que estan en `REGISTRY[<destino>]` (se comprueba al registrarlas: un cambio de contrato rompe el
doble) y construye sus respuestas con los modelos de U0 (`bff_builders`).

Cada doble cuenta llamadas, guarda las cabeceras y el cuerpo recibidos y el timeout efectivo de cada una
(`request.extensions["timeout"]`), y admite: demora, caida (error de conexion), 5xx, un `Problem` dado y «no responde».
Como `httpx` no aplica el timeout cuando el transporte es propio, el doble lo aplica: una demora mayor que el timeout recibido
lanza `httpx.ReadTimeout` tras esperar de verdad ese tiempo (el corte es real, no simulado).
"""

import asyncio
import itertools
import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import parse_qs

import bff_builders as b
import httpx
from vectra_contracts.models.api import Problem
from vectra_contracts.routes import REGISTRY

Reply = tuple[int, Any]
_SEQ = itertools.count()  # orden global de las llamadas a todos los dobles
Responder = Callable[["Call"], Reply]


@dataclass
class Call:
    method: str
    path: str
    template: str
    params: dict[str, str]
    query: dict[str, list[str]]
    headers: dict[str, str]
    body: bytes
    timeout: float | None
    seq: int = field(default_factory=lambda: next(_SEQ))

    def json(self) -> Any:
        return json.loads(self.body)


@dataclass
class Override:
    status: int | None = None
    payload: Any = None
    delay: float = 0.0
    hang: bool = False
    down: bool = False


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
    return data


def _regex(template: str) -> re.Pattern[str]:
    parts = re.split(r"(\{[a-z_]+\})", template)
    return re.compile("^" + "".join("([^/]+)" if p.startswith("{") else re.escape(p) for p in parts) + "$")


class Double(httpx.AsyncBaseTransport):
    """Un destino. `service` es la clave de `REGISTRY`; las subclases llenan `self.responders`."""

    service: str

    def __init__(self) -> None:
        self.calls: list[Call] = []
        self.overrides: dict[tuple[str, str], Override] = {}
        self.default = Override()
        self.cancelled = 0
        self.completed = 0
        self.responders: dict[tuple[str, str], Responder] = {}
        self._compiled: list[tuple[str, str, re.Pattern[str]]] = []
        self.populate()
        declared = {(r.method, r.path) for r in REGISTRY[self.service]}
        for method, template in self.responders:
            if (method, template) not in declared:
                raise AssertionError(
                    f"{self.service} no declara {method} {template}: el doble sirve una ruta que no esta en REGISTRY"
                )
            self._compiled.append((method, template, _regex(template)))

    def populate(self) -> None:  # pragma: no cover - lo llenan las subclases
        raise NotImplementedError

    # --- control del doble -------------------------------------------------------------------------------------
    def down(self) -> None:
        self.default = Override(down=True)

    def hang(self) -> None:
        self.default = Override(hang=True)

    def fail(self, status: int = 503, code: str = "dependency_unavailable") -> None:
        self.default = Override(status=status, payload=problem(status, code))

    def delay_all(self, seconds: float) -> None:
        self.default = Override(delay=seconds)

    def override(self, method: str, template: str, **kwargs: Any) -> None:
        self.overrides[(method, template)] = Override(**kwargs)

    def reply(self, method: str, template: str, status: int, payload: Any = None) -> None:
        self.override(method, template, status=status, payload=payload)

    def count(self, method: str | None = None, template: str | None = None) -> int:
        return sum(
            1
            for c in self.calls
            if (method is None or c.method == method) and (template is None or c.template == template)
        )

    def reset_calls(self) -> None:
        self.calls.clear()

    # --- transporte --------------------------------------------------------------------------------------------
    def _match(self, method: str, path: str) -> tuple[str, dict[str, str]] | None:
        for m, template, pattern in self._compiled:
            found = pattern.match(path)
            if m == method and found:
                names = re.findall(r"\{([a-z_]+)\}", template)
                return template, dict(zip(names, found.groups(), strict=True))
        return None

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        matched = self._match(request.method, request.url.path)
        template, params = matched if matched else ("", {})
        timeouts = request.extensions.get("timeout") or {}
        call = Call(
            request.method,
            request.url.path,
            template,
            params,
            parse_qs(request.url.query.decode()),
            {k.lower(): v for k, v in request.headers.items()},
            request.content,
            timeouts.get("read"),
        )
        self.calls.append(call)
        rule = self.overrides.get((request.method, template), self.default)
        if rule.down:
            raise httpx.ConnectError("doble caido", request=request)
        try:
            if rule.hang or rule.delay:
                wait = asyncio.sleep(3600 if rule.hang else rule.delay)
                try:
                    await asyncio.wait_for(wait, timeout=call.timeout)
                except TimeoutError:
                    raise httpx.ReadTimeout("el doble no respondio a tiempo", request=request) from None
        except asyncio.CancelledError:
            self.cancelled += 1
            raise
        if rule.status is not None:
            status, payload = rule.status, rule.payload
        elif matched is None:
            status, payload = 404, problem(404, "not_found")
        else:
            status, payload = self.responders[(request.method, template)](call)
        self.completed += 1
        if payload is None:
            return httpx.Response(status, request=request)
        return httpx.Response(status, json=payload, request=request)


class CaseDouble(Double):
    service = "case-service"

    def populate(self) -> None:
        self.details: dict[str, dict[str, Any]] = {b.CASE_ID: b.case_detail()}
        self.identifiers: dict[str, dict[str, Any]] = {b.CASE_ID: b.case_identifiers()}
        self.write_status = 200
        r = self.responders
        r[("GET", "/v1/cases")] = lambda c: (200, b.page([b.case_summary()]))
        r[("POST", "/v1/cases")] = lambda c: (200, b.case_ref())
        r[("GET", "/v1/cases/failures")] = lambda c: (200, [b.persistent_failure()])
        r[("GET", "/v1/cases/{id}")] = lambda c: self._lookup(self.details, c)
        r[("GET", "/v1/cases/{id}/identifiers")] = lambda c: self._lookup(self.identifiers, c)
        r[("POST", "/v1/cases/{id}/explanation-views")] = lambda c: (204, None)
        r[("POST", "/v1/cases/{id}/decision")] = lambda c: (200, b.decision_ref(c.params["id"]))
        r[("POST", "/v1/cases/{id}/retry")] = lambda c: (200, b.case_ref(c.params["id"]))

    @staticmethod
    def _lookup(table: dict[str, dict[str, Any]], call: Call) -> Reply:
        found = table.get(call.params["id"])
        return (200, found) if found is not None else (404, problem(404, "not_found"))

    def writes(self) -> int:
        """Llamadas de **escritura** que recibio (todo lo que no es GET)."""
        return sum(1 for c in self.calls if c.method != "GET")


class GovernanceDouble(Double):
    service = "governance-service"

    def populate(self) -> None:
        self.models: dict[str, dict[str, Any]] = {}
        self.policies: list[dict[str, Any]] = []
        self.sources: list[dict[str, Any]] = []
        r = self.responders
        r[("GET", "/v1/models")] = self._list_models
        r[("GET", "/v1/models/{id}")] = lambda c: self._model(c)
        r[("GET", "/v1/policies")] = lambda c: (200, self.policies)
        r[("GET", "/v1/data-sources")] = lambda c: (200, self.sources)
        r[("POST", "/v1/models")] = lambda c: (200, b.model_version("mv-new", "registrado"))
        r[("POST", "/v1/models/{id}/validations")] = lambda c: (200, b.validation_run(c.params["id"]))
        r[("POST", "/v1/data-sources/{id}/comparisons")] = lambda c: (
            200,
            b.validation_run(c.json()["candidate_version_id"])
            | {"mode": "source_comparison", "source_id": c.params["id"], "baseline_version_id": "mv-1"},
        )
        r[("POST", "/v1/models/{id}/approval")] = lambda c: (204, None)
        r[("POST", "/v1/models/{id}/frozen-resolution")] = lambda c: (204, None)
        r[("POST", "/v1/models/{id}/retirement")] = lambda c: (
            200,
            b.model_version(c.params["id"], "retirado"),
        )
        r[("POST", "/v1/policies")] = lambda c: (200, b.policy_version("pv-new"))
        r[("POST", "/v1/policies/{id}/approval")] = lambda c: (204, None)
        r[("POST", "/v1/data-sources")] = lambda c: (200, b.data_source("ds-new", "propuesta", report=False))
        r[("POST", "/v1/data-sources/{id}/decision")] = lambda c: (204, None)

    def add_model(self, model_version_id: str, state: str, **over: Any) -> None:
        self.models[model_version_id] = b.model_version(model_version_id, state, **over)

    def _list_models(self, call: Call) -> Reply:
        wanted = {s for value in call.query.get("state", []) for s in value.split(",")}
        items = [m for m in self.models.values() if not wanted or m["state"] in wanted]
        return 200, b.page(items)

    def _model(self, call: Call) -> Reply:
        found = self.models.get(call.params["id"])
        return (200, found) if found is not None else (404, problem(404, "not_found"))

    def writes(self) -> int:
        return sum(1 for c in self.calls if c.method != "GET")


class RegistryDouble(Double):
    service = "decision-registry-service"

    def populate(self) -> None:
        self.integrity_status = 202
        r = self.responders
        r[("GET", "/v1/dossiers/{case_id}")] = lambda c: (200, b.registry_dossier(c.params["case_id"]))
        r[("POST", "/v1/integrity-checks")] = lambda c: (
            self.integrity_status,
            b.integrity_ref(already_active=self.integrity_status == 200),
        )
        r[("GET", "/v1/integrity-checks/{id}")] = lambda c: (200, b.integrity_status())


class ExplainabilityDouble(Double):
    service = "explainability-service"

    def populate(self) -> None:
        self.responders[("POST", "/v1/applicant-summaries")] = lambda c: (
            200,
            b.applicant_summary(c.json()["case_id"]),
        )


class BiasDouble(Double):
    service = "bias-monitoring-service"

    def populate(self) -> None:
        r = self.responders
        r[("GET", "/v1/disparity")] = lambda c: (
            200,
            b.disparity_view((c.query.get("version") or ["mv-default"])[0]),
        )
        r[("GET", "/v1/freezes")] = lambda c: (200, [b.freeze_summary()])
        r[("GET", "/v1/freezes/{id}")] = lambda c: (200, b.freeze_record())


DESTINATIONS = {
    "case": CaseDouble,
    "governance": GovernanceDouble,
    "registry": RegistryDouble,
    "explainability": ExplainabilityDouble,
    "bias": BiasDouble,
}


@dataclass
class Doubles:
    case: CaseDouble = field(default_factory=CaseDouble)
    governance: GovernanceDouble = field(default_factory=GovernanceDouble)
    registry: RegistryDouble = field(default_factory=RegistryDouble)
    explainability: ExplainabilityDouble = field(default_factory=ExplainabilityDouble)
    bias: BiasDouble = field(default_factory=BiasDouble)

    def transports(self) -> dict[str, Double]:
        return {name: getattr(self, name) for name in DESTINATIONS}

    def urls(self) -> dict[str, str]:
        return {name: f"http://{name}.test" for name in DESTINATIONS}
