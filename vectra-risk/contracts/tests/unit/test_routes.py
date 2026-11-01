"""Registro de contratos (P-U0-12) frente a component-methods.md y §7.2."""

import re
from pathlib import Path

import pytest

from vectra_common.app_factory import check_contract
from vectra_contracts.catalog import SCOPE_HOLDERS, Role, Scope
from vectra_contracts.routes import REGISTRY, all_routes

DOC = Path(__file__).resolve().parents[3] / "aidlc-docs/inception/application-design/component-methods.md"


def by_key(service):
    return {(r.method, r.path): r for r in REGISTRY[service]}


def test_every_route_declares_requirements_and_passes_startup_check():
    for route in all_routes():
        assert route.scopes or route.any_scopes or route.roles
        check_contract(route)


def test_autonomia_03_write_credit():
    route = by_key("core-banking-mock")[("POST", "/v1/credits/{id}/status")]
    assert route.scopes == {Scope.CORE_WRITE_CREDIT}
    assert SCOPE_HOLDERS[Scope.CORE_WRITE_CREDIT] == ()


def test_scopes_within_catalog():
    assert set(SCOPE_HOLDERS) == set(Scope)
    for route in all_routes():
        assert (route.scopes | route.any_scopes) <= set(Scope)


def test_monitoring_daily_query_read_only():
    route = by_key("decision-registry-service")[("POST", "/v1/monitoring/daily:query")]
    assert route.read_only and route.scopes == {Scope.REGISTRY_READ_MONITORING}


def test_entries_any_of_three_writers():
    route = by_key("decision-registry-service")[("POST", "/v1/entries")]
    assert route.any_scopes == {Scope.REGISTRY_APPEND_CASE, Scope.REGISTRY_APPEND_SCORING, Scope.REGISTRY_APPEND_GOVERNANCE}
    assert route.max_body_bytes == 80 * 1024


def test_freeze_body_limit():
    assert by_key("governance-service")[("POST", "/v1/models/{id}/freeze")].max_body_bytes == 64 * 1024


def _bff_rows():
    rows = []
    for line in DOC.read_text(encoding="utf-8").splitlines():
        match = re.match(r"\| `\w+\(.*?\)[^|]*` \| `(GET|POST) (/api/console/[^`]*)` \| ([^|]*) \| ([^|]*) \|", line)
        if match:
            rows.append(match.groups())
    return rows


def test_bff_matches_component_methods():
    rows = _bff_rows()
    assert len(rows) == 30
    routes = by_key("console-bff")
    assert len(routes) == 30
    for method, path, roles, mfa in rows:
        route = routes[(method, path)]
        if "todos" in roles:
            assert route.roles == set(Role)
        else:
            assert {r.value for r in route.roles} == {n.strip(" *") for n in roles.split(",")}, path
        assert route.mfa == mfa.strip().startswith("sí"), path


@pytest.mark.parametrize("service", sorted(REGISTRY))
def test_no_duplicate_routes(service):
    keys = [(r.method, r.path) for r in REGISTRY[service]]
    assert len(keys) == len(set(keys))
