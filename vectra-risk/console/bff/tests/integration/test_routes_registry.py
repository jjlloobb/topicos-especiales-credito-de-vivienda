"""Paso 5 (CA-1): las 30 rutas con su handler y su regla declarada; el arranque que falla sin ella (P-U10-01; US-602).

Los 30 `RouteContract` son de U0 (`REGISTRY["console-bff"]`): aqui no se copian, se comprueba lo que el BFF les exige.
El oraculo de «roles» y «MFA» es C03 (`tools/role_matrix.py`), no `REGISTRY`.
"""

import re

import bff_doubles
import pytest
import role_matrix
from bff_doubles import Doubles
from bff_tokens import authenticator
from vectra_contracts.errors import ContractViolation
from vectra_contracts.routes import DEFAULT_MAX_BODY, MFA_MAX_AGE, REGISTRY

from console_bff import object_rules, routes
from console_bff.app import build
from console_bff.clients import DESTINATIONS, Upstreams


def test_the_registry_has_the_30_routes_of_c03() -> None:
    contracts = REGISTRY["console-bff"]
    assert len(contracts) == 30
    assert {(r.method, r.path) for r in contracts} == set(role_matrix.from_c03())


def test_mfa_routes_are_the_11_of_c03_all_with_900_seconds_and_the_default_body() -> None:
    """«`mfa` (900 s)» y «`max_body_bytes` por omision» sobre las 30 (BR-U10-01)."""
    oracle = role_matrix.from_c03()
    with_mfa = {key for key, (_, mfa) in oracle.items() if mfa}
    assert len(with_mfa) == 11
    for contract in REGISTRY["console-bff"]:
        assert contract.mfa is ((contract.method, contract.path) in with_mfa)
        assert contract.mfa_max_age == MFA_MAX_AGE == 900
        assert contract.max_body_bytes == DEFAULT_MAX_BODY == 32 * 1024


def test_every_route_has_a_handler_and_an_explicit_object_rule() -> None:
    doubles = Doubles()
    upstreams = Upstreams(doubles.urls(), transports=doubles.transports())
    handlers = routes.build_handlers(upstreams)
    assert set(handlers) == {(r.method, r.path) for r in REGISTRY["console-bff"]}
    ids = {r.operation_id for r in REGISTRY["console-bff"]}
    assert set(object_rules.OBJECT_RULES) == ids
    assert sum(1 for rule in object_rules.OBJECT_RULES.values() if rule is not None) == 11
    assert set(routes.PASSTHROUGH) <= ids


def test_a_route_without_a_declared_object_rule_does_not_start(monkeypatch: pytest.MonkeyPatch) -> None:
    """P-U10-01: `None` declarado vale; una clave ausente no. `create_app` falla al arrancar (deny by default)."""
    doubles = Doubles()
    rules = dict(object_rules.OBJECT_RULES)
    del rules["post_api_console_cases_id_decision"]
    monkeypatch.setattr(object_rules, "OBJECT_RULES", rules)
    with pytest.raises(ContractViolation, match="post_api_console_cases_id_decision"):
        build(doubles.urls(), authenticator=authenticator(), transports=doubles.transports())


def test_an_object_rule_for_a_route_that_does_not_exist_does_not_start(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    doubles = Doubles()
    monkeypatch.setattr(
        object_rules, "OBJECT_RULES", {**object_rules.OBJECT_RULES, "get_api_console_fantasma": None}
    )
    with pytest.raises(ContractViolation, match="get_api_console_fantasma"):
        build(doubles.urls(), authenticator=authenticator(), transports=doubles.transports())


def test_none_declared_is_a_valid_rule(monkeypatch: pytest.MonkeyPatch) -> None:
    doubles = Doubles()
    assert object_rules.OBJECT_RULES["get_api_console_cases"] is None
    app = build(doubles.urls(), authenticator=authenticator(), transports=doubles.transports())
    assert len([r for r in app.router.routes if getattr(r, "methods", None)]) == 30


def test_every_route_served_by_a_double_is_in_the_registry_of_its_destination() -> None:
    """Un cambio de contrato rompe el doble: sirve solo `(metodo, ruta)` de `REGISTRY[<destino>]`."""
    doubles = Doubles()
    for name, double in doubles.transports().items():
        declared = {(r.method, r.path) for r in REGISTRY[double.service]}
        assert set(double.responders) <= declared, name
        assert double.responders, name


def test_a_double_with_an_undeclared_route_cannot_be_built() -> None:
    class Wrong(bff_doubles.Double):
        service = "bias-monitoring-service"

        def populate(self) -> None:
            self.responders[("GET", "/v1/no-existe")] = lambda call: (200, {})

    with pytest.raises(AssertionError, match="no esta en REGISTRY"):
        Wrong()


def test_the_five_destinations_are_the_clients_of_the_bff() -> None:
    assert DESTINATIONS == ("case", "governance", "registry", "explainability", "bias")
    doubles = Doubles()
    upstreams = Upstreams(doubles.urls(), transports=doubles.transports())
    assert set(upstreams.clients) == set(DESTINATIONS)
    assert all(
        client.token_source is None for client in upstreams.clients.values()
    )  # sin `token_source`: sin reintento ante 401


def test_every_destination_path_of_a_handler_is_in_the_registry_of_its_destination() -> None:
    """Un endpoint del BFF, una llamada al destino (BR-U10-03): la ruta de destino existe en el contrato del destino."""
    names = {
        "case": "case-service",
        "governance": "governance-service",
        "registry": "decision-registry-service",
        "bias": "bias-monitoring-service",
    }
    by_service = {name: {(r.method, r.path) for r in REGISTRY[service]} for name, service in names.items()}
    for operation_id, (destination, _) in routes.PASSTHROUGH.items():
        contract = next(r for r in REGISTRY["console-bff"] if r.operation_id == operation_id)
        tail = contract.path.removeprefix("/api/console")
        template = re.sub(r"\{id\}", "{id}", f"/v1{tail}")
        assert (contract.method, template) in by_service[destination], operation_id


def test_asking_for_the_rule_of_a_route_that_declares_none_is_a_contract_violation() -> None:
    """`_rule` solo se pide para las 11 rutas con regla; una ruta con `None` declarado no tiene funcion que devolver."""
    contract = next(r for r in REGISTRY["console-bff"] if r.operation_id == "get_api_console_cases")
    with pytest.raises(ContractViolation, match="get_api_console_cases"):
        routes._rule(contract)  # noqa: SLF001
