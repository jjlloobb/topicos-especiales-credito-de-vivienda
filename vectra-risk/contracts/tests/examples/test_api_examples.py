"""Respuestas exactas de la capa de API (PBT-10, Paso 11)."""

import asyncio
import io
import json
import logging as std
import time

import pytest
from strategies import auth as a

from vectra_common import logging as vlog
from vectra_common import process
from vectra_common.errors import DependencyUnavailable
from vectra_common.jwks_cache import JwksCache
from vectra_common.authn import Authenticator
from vectra_common.metrics import AUTHZ_DENIED
from vectra_contracts.catalog import Role
from vectra_contracts.models.api import DecisionIn, DecisionRef
from vectra_contracts.routes import RouteContract

pytestmark = pytest.mark.api
GET = RouteContract("svc", "GET", "/v1/x", None, DecisionRef, roles=frozenset({Role.ANALISTA}))
MFA = RouteContract("svc", "GET", "/v1/mfa", None, DecisionRef, roles=frozenset({Role.ANALISTA}), mfa=True)
POST = RouteContract("svc", "POST", "/v1/y", DecisionIn, DecisionRef, roles=frozenset({Role.ANALISTA}))
JSON = {"content-type": "application/json"}
GOOD = {"decision": "sigue", "final_outcome": "favorable", "used_factors": ["ninguno"], "justification": ""}


@pytest.fixture(autouse=True)
def reset():
    process.reset_for_tests()
    yield
    process.reset_for_tests()


def check(response, status, code):
    assert response.status_code == status
    body = response.json()
    assert body["code"] == code and body["status"] == status
    assert response.headers["content-type"] == "application/problem+json"
    assert body["type"] == f"urn:vectra:problem:{code}" and body["correlation_id"]
    assert set(body) <= {"type", "title", "status", "code", "correlation_id", "reason", "invalid_params"}


async def test_br_u0_31_malformed_400_and_415():
    async with a.client_for([POST]) as c:
        check(await c.post("/v1/y", content=b"{no json", headers={**a.bearer(), **JSON}), 400, "malformed_request")
        check(await c.post("/v1/y", content=b"{}", headers={**a.bearer(), "content-type": "text/plain"}), 415, "unsupported_media_type")
        check(await c.post("/v1/y", content=b"{}", headers=a.bearer()), 415, "unsupported_media_type")


async def test_br_u0_30_422_without_values():
    bad = {**GOOD, "final_outcome": "SECRETO", "extra": "OTRO-SECRETO"}
    async with a.client_for([POST]) as c:
        response = await c.post("/v1/y", json=bad, headers=a.bearer())
    check(response, 422, "validation_error")
    assert "SECRETO" not in response.text
    assert {p["name"] for p in response.json()["invalid_params"]} == {"final_outcome", "extra"}


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"authorization": "Bearer malo"},
        {"authorization": f"Bearer {a.token(alg='none', key=None)}"},
        {"authorization": f"Bearer {a.token(aud='otro')}"},
        {"authorization": f"Bearer {a.token(exp=int(time.time()) - 31)}"},
    ],
)
async def test_br_u0_70_401(headers):
    async with a.client_for([GET]) as c:
        check(await c.get("/v1/x", headers=headers), 401, "unauthenticated")


async def test_br_u0_70_many_audiences_accepted():
    async with a.client_for([GET]) as c:
        assert (await c.get("/v1/x", headers=a.bearer(aud=["otra", a.AUDIENCE]))).status_code == 200


async def test_br_u0_73_403_logged_and_counted():
    out = io.StringIO()
    async with a.client_for([GET]) as c:
        vlog.configure("svc", out)
        before = AUTHZ_DENIED.labels(code="forbidden", route_template="/v1/x")._value.get()
        check(await c.get("/v1/x", headers=a.bearer(roles=["cro"])), 403, "forbidden")
    assert AUTHZ_DENIED.labels(code="forbidden", route_template="/v1/x")._value.get() == before + 1
    denied = [json.loads(line) for line in out.getvalue().splitlines() if "authz.denied" in line][0]
    assert denied["principal_subject"] == "user-1" and denied["error_code"] == "forbidden" and denied["route_template"] == "/v1/x"
    vlog.configure("svc")


async def test_br_u0_73_401_counted_with_route_template():
    before = AUTHZ_DENIED.labels(code="unauthenticated", route_template="/v1/x")._value.get()
    async with a.client_for([GET]) as c:
        await c.get("/v1/x")
    assert AUTHZ_DENIED.labels(code="unauthenticated", route_template="/v1/x")._value.get() == before + 1


async def test_br_u0_72_mfa_required():
    now = int(time.time())
    async with a.client_for([MFA]) as c:
        check(await c.get("/v1/mfa", headers=a.bearer(acr="pwd")), 403, "mfa_required")
        check(await c.get("/v1/mfa", headers=a.bearer(auth_time=now - 901)), 403, "mfa_required")
        assert (await c.get("/v1/mfa", headers=a.bearer(auth_time=now - 890))).status_code == 200


async def test_404_is_problem_after_authentication():
    async with a.client_for([GET]) as c:
        check(await c.get("/v1/no-existe", headers=a.bearer()), 404, "not_found")
        check(await c.get("/v1/no-existe"), 401, "unauthenticated")


async def test_br_u0_60_third_party_exception_is_internal_error():
    out = io.StringIO()

    async def boom(_):
        raise RuntimeError("cédula 1020304050")

    async with a.client_for([GET], handler=boom) as c:
        vlog.configure("svc", out)
        response = await c.get("/v1/x", headers=a.bearer())
    check(response, 500, "internal_error")
    assert "1020304050" not in response.text and "1020304050" not in out.getvalue()
    vlog.configure("svc")


async def test_nfr_u0_12_jwks_down_expired_cache_503():
    async def down():
        raise DependencyUnavailable()

    auth = Authenticator(issuer=a.ISSUER, audience=a.AUDIENCE, jwks=JwksCache(down))
    async with a.client_for([GET], auth=auth) as c:
        check(await c.get("/v1/x", headers=a.bearer()), 503, "dependency_unavailable")


async def test_nfr_u0_11_100_concurrent_unknown_kid_one_refresh():
    calls = []

    async def fetch():
        calls.append(1)
        await asyncio.sleep(0)
        return a.jwks_document()

    auth = a.authenticator(fetch)
    async with a.client_for([GET], auth=auth) as c:
        await asyncio.gather(*(c.get("/v1/x", headers=a.bearer(kid="falso")) for _ in range(100)))
    assert len(calls) == 1


async def test_nfr_u0_13_httpx_log_with_pii_absent():
    out = io.StringIO()
    async with a.client_for([GET]):
        vlog.configure("svc", out)
        std.getLogger("httpx").info("GET /?doc=1020304050")
    assert "1020304050" not in out.getvalue()
    vlog.configure("svc")


async def test_br_u0_06_fail_closed_travels_as_200():
    from strategies.domain import CASE, NOW

    from vectra_contracts.catalog import FailClosedCause
    from vectra_contracts.models.explanation import FailClosed

    async def handler(_):
        return FailClosed(case_id=CASE, status="en_sincronizacion", cause=FailClosedCause.TIMEOUT, retryable=True, occurred_at=NOW)

    async with a.client_for([GET], handler=handler) as c:
        response = await c.get("/v1/x", headers=a.bearer())
    assert response.status_code == 200 and response.json()["kind"] == "fail_closed"
