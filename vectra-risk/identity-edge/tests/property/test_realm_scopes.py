"""PBT-U2-03: scopes solo del catalogo de U0; `core:write-credit` nunca; `governance:freeze` solo en el job."""

from hypothesis import given
from realm_builders import realm_copy, service_client
from realm_lint import lint_realm
from realm_strategies import CATALOG_SCOPES, client_ids, client_scope_lists
from vectra_contracts.catalog import Scope


def rules_for(client_id: str, scopes: list[str]) -> set[str]:
    realm = realm_copy("kind")
    # El cliente generado sustituye al del mismo nombre, si existe.
    realm["clients"] = [c for c in realm["clients"] if c["clientId"] != client_id]
    realm["clients"].append(service_client(client_id, scopes, ["decision-registry-service"]))
    return {v.rule for v in lint_realm(realm, "kind")}


@given(client_id=client_ids, scopes=client_scope_lists)
def test_catalog_write_credit_and_freeze_invariants(client_id: str, scopes: list[str]) -> None:
    fired = rules_for(client_id, scopes)
    assert ("scope-fuera-del-catalogo" in fired) == any(s not in CATALOG_SCOPES for s in scopes)
    assert ("core-write-credit-prohibido" in fired) == (Scope.CORE_WRITE_CREDIT.value in scopes)
    freeze = Scope.GOVERNANCE_FREEZE.value in scopes
    assert ("governance-freeze-solo-en-el-job" in fired) == (freeze and client_id != "bias-monitoring-job")


@given(client_id=client_ids, scopes=client_scope_lists)
def test_a_realm_with_a_violating_client_is_never_accepted(client_id: str, scopes: list[str]) -> None:
    violating = (
        any(s not in CATALOG_SCOPES for s in scopes)
        or Scope.CORE_WRITE_CREDIT.value in scopes
        or (Scope.GOVERNANCE_FREEZE.value in scopes and client_id != "bias-monitoring-job")
    )
    if violating:
        assert rules_for(client_id, scopes)
