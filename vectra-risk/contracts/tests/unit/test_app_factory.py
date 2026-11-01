"""P-U0-01, P-U0-02, P-U0-12, BR-U0-71; capa de API."""

import pytest
from fastapi import FastAPI
from strategies import auth as a

from vectra_common import process
from vectra_common.app_factory import AccessLogMiddleware, AuthnMiddleware, ProblemHandlerMiddleware, TelemetryMiddleware, audit_routes, check_contract, create_app
from vectra_common.authz import require
from vectra_common.metrics import HTTP_DURATION, histogram
from vectra_contracts.catalog import Role, Scope
from vectra_contracts.errors import ContractViolation
from vectra_contracts.models.api import DecisionIn, DecisionRef
from vectra_contracts.routes import RouteContract

READ = RouteContract("svc", "GET", "/v1/x/{id}", None, DecisionRef, roles=frozenset({Role.ANALISTA}))
WRITE = RouteContract("svc", "POST", "/v1/y", DecisionIn, DecisionRef, roles=frozenset({Role.ANALISTA}))
BODY = {"decision": "sigue", "final_outcome": "favorable", "used_factors": ["ninguno"], "justification": ""}


@pytest.fixture(autouse=True)
def reset():
    process.reset_for_tests()
    yield
    process.reset_for_tests()


def test_p_u0_01_middleware_order():
    app = create_app("svc", [READ], {("GET", READ.path): a.ok_handler}, authenticator=a.authenticator())
    names = [m.cls for m in app.user_middleware]
    assert names == [TelemetryMiddleware, AccessLogMiddleware, ProblemHandlerMiddleware, AuthnMiddleware]
    assert app.state.pipeline == ("TelemetryMiddleware", "AuthnMiddleware", "AuthzDependency", "BodyGuard", "PydanticStrict", "handler", "ProblemHandler", "AccessLog")


def test_p_u0_12_handler_missing_or_extra():
    with pytest.raises(ContractViolation):
        create_app("svc", [READ], {}, authenticator=a.authenticator())
    with pytest.raises(ContractViolation):
        create_app("svc", [READ], {("GET", READ.path): a.ok_handler, ("GET", "/otra"): a.ok_handler}, authenticator=a.authenticator())


def test_nfr_u0_15_route_without_requirements_fails_at_startup():
    route = RouteContract("svc", "GET", "/v1/z")
    with pytest.raises(ContractViolation):
        create_app("svc", [route], {("GET", "/v1/z"): a.ok_handler}, authenticator=a.authenticator())


def test_p_u0_02_audit_detects_unmarked_route():
    app = FastAPI()

    async def endpoint():
        return None

    app.add_api_route("/x", endpoint)
    with pytest.raises(ContractViolation):
        audit_routes(app)
    assert require(roles=frozenset({Role.CRO})).vectra_requirement.roles == {Role.CRO}


def test_br_u0_71_post_with_read_scope_requires_read_only():
    bad = RouteContract("svc", "POST", "/v1/q", scopes=frozenset({Scope.REGISTRY_READ_MONITORING}))
    with pytest.raises(ContractViolation):
        check_contract(bad)
    check_contract(RouteContract("svc", "POST", "/v1/monitoring/daily:query", scopes=frozenset({Scope.REGISTRY_READ_MONITORING}), read_only=True))
    with pytest.raises(ContractViolation):
        check_contract(RouteContract("svc", "GET", "/v1/q", scopes=frozenset({Scope.REGISTRY_READ_MONITORING}), read_only=True))


def test_max_body_hard_limit():
    with pytest.raises(ContractViolation):
        check_contract(RouteContract("svc", "POST", "/v1/q", roles=frozenset({Role.CRO}), max_body_bytes=129 * 1024))


def test_batch_process_cannot_create_app():
    process.init("batch")
    with pytest.raises(ContractViolation):
        create_app("svc", [READ], {("GET", READ.path): a.ok_handler}, authenticator=a.authenticator())


async def test_happy_path_and_histogram_label():
    async with a.client_for([READ]) as c:
        response = await c.get("/v1/x/123", headers=a.bearer())
    assert response.status_code == 200 and response.headers["traceparent"].startswith("00-")
    samples = {tuple(s.labels.items()): s.value for m in HTTP_DURATION.collect() for s in m.samples if s.name.endswith("_count")}
    key = (("service", "svc"), ("route_template", "/v1/x/{id}"), ("method", "GET"), ("status", "200"))
    assert samples[key] >= 1
    assert not any("123" in str(k) for k in samples)


def test_histogram_buckets_include_thresholds_and_are_required():
    edges = {s.labels["le"] for m in HTTP_DURATION.collect() for s in m.samples if s.name.endswith("_bucket")}
    assert {"0.03", "0.15", "0.4", "1.0"} <= edges
    with pytest.raises(ContractViolation):
        histogram("vectra_sin_buckets", "x", [], [])


async def test_body_limit_per_route():
    small = RouteContract("svc", "POST", "/v1/s", DecisionIn, DecisionRef, roles=frozenset({Role.ANALISTA}))
    large = RouteContract("svc", "POST", "/v1/l", DecisionIn, DecisionRef, roles=frozenset({Role.ANALISTA}), max_body_bytes=80 * 1024)
    padding = {**BODY, "justification": "x" * 2000}
    payload = b" " * (40 * 1024) + __import__("json").dumps(padding).encode()
    headers = {**a.bearer(), "content-type": "application/json"}
    async with a.client_for([small, large]) as c:
        assert (await c.post("/v1/s", content=payload, headers=headers)).status_code == 413
        assert (await c.post("/v1/l", content=payload, headers=headers)).status_code == 200


async def test_deadline_in_past_gives_504():
    async with a.client_for([READ]) as c:
        response = await c.get("/v1/x/1", headers={**a.bearer(), "x-vectra-deadline": "2020-01-01T00:00:00.000Z"})
    assert response.status_code == 504 and response.json()["code"] == "deadline_exceeded"


async def test_correlation_id_is_trace_id():
    trace = "a" * 32
    async with a.client_for([READ]) as c:
        response = await c.get("/v1/nada", headers={**a.bearer(), "traceparent": f"00-{trace}-{'b' * 16}-01"})
    assert response.status_code == 404 and response.json()["correlation_id"] == trace
    assert response.headers["traceparent"].split("-")[1] == trace


async def test_handler_may_return_none_or_response():
    from fastapi.responses import Response

    async def none(_):
        return None

    async def custom(_):
        return Response(status_code=202)

    async with a.client_for([READ], handler=none) as c:
        assert (await c.get("/v1/x/1", headers=a.bearer())).status_code == 204
    async with a.client_for([READ], handler=custom) as c:
        assert (await c.get("/v1/x/1", headers=a.bearer())).status_code == 202


