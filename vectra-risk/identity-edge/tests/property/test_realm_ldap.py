"""PBT-U2-02: el usuario obtiene un rol <=> pertenece a exactamente un grupo mapeado (BR-U2-15)."""

from hypothesis import given
from realm_lint import lint_group_role_map, resolve_ldap_role
from realm_strategies import ldap_assignments, mapped_group_maps


@given(data=ldap_assignments())
def test_role_iff_exactly_one_mapped_group(data: tuple[dict[str, str], list[str]]) -> None:
    mapping, groups = data
    mapped = [g for g in groups if g in mapping]
    role = resolve_ldap_role(groups, mapping)
    if len(mapped) == 1:
        assert role == mapping[mapped[0]]
    else:
        # Cero grupos mapeados: sin rol. Dos o mas: ROLE_CONFLICT, ningun rol (nunca acceso de mas).
        assert role is None


@given(data=ldap_assignments())
def test_group_order_and_unmapped_groups_never_change_the_outcome(data: tuple[dict[str, str], list[str]]) -> None:
    mapping, groups = data
    only_mapped = [g for g in groups if g in mapping]
    assert resolve_ldap_role(groups, mapping) == resolve_ldap_role(list(reversed(only_mapped)), mapping)


@given(mapping=mapped_group_maps)
def test_every_generated_group_role_map_is_accepted(mapping: dict[str, str]) -> None:
    assert lint_group_role_map({"groups": mapping}) == []
