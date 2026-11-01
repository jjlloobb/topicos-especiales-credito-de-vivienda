"""`require` a traves de la app: `any_scopes`, MFA y `max_age` (BR-U0-71, 72)."""

import time
from datetime import UTC, datetime
from decimal import ROUND_DOWN, Decimal, getcontext

import pytest
from strategies import auth as a

from vectra_common import process
from vectra_common.authz import authorize, require
from vectra_common.deadline import parse
from vectra_common.errors import MfaRequired
from vectra_contracts.catalog import Role, Scope
from vectra_contracts.errors import ContractViolation
from vectra_contracts.finance import to_decimal4_str
from vectra_contracts.models.api import Principal
from vectra_contracts.outcome import quantize_probability
from vectra_contracts.routes import RouteContract

CASE, SCORING = Scope.REGISTRY_APPEND_CASE, Scope.REGISTRY_APPEND_SCORING
ANY = RouteContract("svc", "GET", "/v1/any", any_scopes=frozenset({CASE, SCORING}))
PLAIN = RouteContract("svc", "GET", "/v1/plain", roles=frozenset({Role.ANALISTA}))
SHORT = RouteContract("svc", "GET", "/v1/short", roles=frozenset({Role.ANALISTA}), mfa=True, mfa_max_age=60)


@pytest.fixture(autouse=True)
def reset():
    process.reset_for_tests()
    yield
    process.reset_for_tests()


async def _none(_):
    return None


async def test_br_u0_71_any_scopes_through_app():
    async with a.client_for([ANY], handler=_none) as c:
        assert (await c.get("/v1/any", headers=a.bearer(roles=None, scope=SCORING.value))).status_code == 204
        assert (await c.get("/v1/any", headers=a.bearer(roles=None, scope=Scope.BIAS_COMPARE.value))).status_code == 403


async def test_br_u0_72_route_without_mfa_accepts_password_login():
    async with a.client_for([PLAIN], handler=_none) as c:
        assert (await c.get("/v1/plain", headers=a.bearer(acr="pwd"))).status_code == 204


async def test_br_u0_72_route_specific_max_age():
    now = int(time.time())
    async with a.client_for([SHORT], handler=_none) as c:
        assert (await c.get("/v1/short", headers=a.bearer(auth_time=now - 120))).status_code == 403
        assert (await c.get("/v1/short", headers=a.bearer(auth_time=now - 10))).status_code == 204


def test_br_u0_72_authorize_uses_given_max_age():
    moment = datetime(2026, 1, 1, tzinfo=UTC)
    principal = Principal(subject="s", kind="user", acr="mfa", auth_time=datetime(2025, 12, 31, 23, 58, tzinfo=UTC), token_expiry=moment)
    with pytest.raises(MfaRequired):
        authorize(principal, frozenset(), frozenset(), frozenset(), True, moment, max_age=60)
    authorize(principal, frozenset(), frozenset(), frozenset(), True, moment, max_age=600)


def test_p_u0_02_requirement_marker_is_complete():
    scopes, any_scopes, roles = frozenset({CASE}), frozenset({SCORING}), frozenset({Role.CRO})
    marker = require(scopes, roles, any_scopes, True, 77).vectra_requirement
    assert (marker.scopes, marker.any_scopes, marker.roles, marker.mfa, marker.max_age) == (scopes, any_scopes, roles, True, 77)
    assert require(roles=roles).vectra_requirement.mfa is False


def test_deadline_parse_returns_utc():
    assert parse("2026-10-31T07:00:00-05:00").tzinfo is UTC


def test_p_u0_10_quantization_ignores_global_context():
    context = getcontext()
    prec, rounding = context.prec, context.rounding
    try:
        context.prec, context.rounding = 2, ROUND_DOWN
        assert quantize_probability(0.12345678) == "0.1235"
        assert quantize_probability(1.0) == "1.0000"
        assert to_decimal4_str(Decimal("0.123456")) == "0.1235"
    finally:
        context.prec, context.rounding = prec, rounding


def test_requirements_message():
    with pytest.raises(ContractViolation) as error:
        require()
    assert str(error.value) == "una ruta sin scopes ni roles no puede arrancar (BR-U0-71)"
