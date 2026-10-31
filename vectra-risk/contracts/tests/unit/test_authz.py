"""BR-U0-71, 72."""

from datetime import timedelta

import pytest
from strategies.domain import NOW

from vectra_common.authz import authorize, is_authorized, mfa_satisfied, require
from vectra_common.errors import Forbidden, MfaRequired
from vectra_contracts.catalog import Role, Scope
from vectra_contracts.errors import ContractViolation
from vectra_contracts.models.api import Principal

R = Scope.REGISTRY_READ_METRICS
W = Scope.REGISTRY_APPEND_CASE


def principal(scopes=frozenset(), roles=frozenset(), acr=None, auth_time=None):
    return Principal(subject="s", kind="user", scopes=frozenset(scopes), roles=frozenset(roles), acr=acr, auth_time=auth_time, token_expiry=NOW)


def test_br_u0_71_scopes_subset_and_roles_intersection():
    assert is_authorized(principal({R, W}), frozenset({R}), frozenset(), frozenset())
    assert not is_authorized(principal({R}), frozenset({R, W}), frozenset(), frozenset())
    assert is_authorized(principal(roles={Role.CRO}), frozenset(), frozenset(), frozenset({Role.CRO, Role.ANALISTA}))
    assert not is_authorized(principal(roles={Role.CRO}), frozenset(), frozenset(), frozenset({Role.ANALISTA}))
    assert not is_authorized(principal({R}), frozenset({R}), frozenset(), frozenset({Role.CRO}))


def test_br_u0_71_any_scopes():
    assert is_authorized(principal({W}), frozenset(), frozenset({R, W}), frozenset())
    assert not is_authorized(principal(), frozenset(), frozenset({R, W}), frozenset())


def test_br_u0_71_deny_by_default():
    with pytest.raises(ContractViolation):
        require()


@pytest.mark.parametrize(
    ("acr", "age", "ok"),
    [("mfa", 900, True), ("mfa", 901, False), ("pwd", 0, False), (None, 0, False)],
)
def test_br_u0_72_mfa_boundaries(acr, age, ok):
    assert mfa_satisfied(principal(acr=acr, auth_time=NOW - timedelta(seconds=age)), NOW) is ok


def test_br_u0_72_authorize_errors():
    p = principal(roles={Role.CRO}, acr="pwd", auth_time=NOW)
    with pytest.raises(MfaRequired):
        authorize(p, frozenset(), frozenset(), frozenset({Role.CRO}), True, NOW)
    with pytest.raises(Forbidden):
        authorize(p, frozenset(), frozenset(), frozenset({Role.ANALISTA}), True, NOW)
    authorize(p, frozenset(), frozenset(), frozenset({Role.CRO}), False, NOW)
    assert not mfa_satisfied(principal(acr="mfa"), NOW)
