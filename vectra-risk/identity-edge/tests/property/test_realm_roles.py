"""PBT-U2-01: el validador acepta un conjunto de roles <=> tiene como maximo un rol de negocio."""

from typing import Any

from hypothesis import given
from realm_builders import BUSINESS_ROLES, realm_copy, user
from realm_lint import lint_realm
from realm_strategies import role_sets, role_sets_with_special

BASE = realm_copy("kind")


def realm_with(roles: list[str]) -> dict[str, Any]:
    realm = realm_copy("kind")
    # TOTP siempre: aqui solo se prueba la separacion de funciones.
    realm["users"].append(user("generado-1", roles, totp=True))
    return realm


def business_count(roles: list[str]) -> int:
    return sum(1 for r in roles if r in BUSINESS_ROLES)


def test_base_realm_is_valid_so_the_property_isolates_the_roles() -> None:
    assert lint_realm(BASE, "kind") == []


@given(roles=role_sets)
def test_realm_is_accepted_iff_at_most_one_business_role(roles: list[str]) -> None:
    accepted = lint_realm(realm_with(roles), "kind") == []
    assert accepted == (business_count(roles) <= 1)


@given(roles=role_sets_with_special)
def test_single_role_rule_fires_iff_more_than_one_business_role(roles: list[str]) -> None:
    fired = any(v.rule == "un-rol-de-negocio" for v in lint_realm(realm_with(roles), "kind"))
    assert fired == (business_count(roles) > 1)


@given(roles=role_sets_with_special)
def test_operacion_with_any_business_role_is_always_rejected(roles: list[str]) -> None:
    fired = any(v.rule == "operacion-con-rol-de-negocio" for v in lint_realm(realm_with(roles), "kind"))
    assert fired == ("operacion" in roles and business_count(roles) >= 1)
