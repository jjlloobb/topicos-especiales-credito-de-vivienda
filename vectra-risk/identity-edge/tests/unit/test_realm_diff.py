"""Proyeccion de `realm-drift` sobre Git (U02-T08, INF-U2-09, BR-U2-12): cada regla tiene un caso que pasa y uno que falla.

Los realms son los tres reales (`realm.{kind,staging,prod}.yaml`); la vista de Keycloak sale de `realm_exports`.
"""

import copy
from collections.abc import Callable
from typing import Any

import pytest
import realm_diff
from realm_exports import ENVS, MARKER, keycloak_view, load_git

Realm = dict[str, Any]


def count(git: Realm, kc: Realm) -> int:
    return realm_diff.drift_count(git, kc)


@pytest.fixture(params=ENVS)
def pair(request: pytest.FixtureRequest) -> tuple[Realm, Realm]:
    git = load_git(str(request.param))
    return git, keycloak_view(git)


def _entity(realm: Realm, key: str, field: str, value: str) -> Realm:
    return next(e for e in realm[key] if e[field] == value)


# --- la base: lo que Keycloak agrega por su cuenta no cuenta ---------------------------------------


def test_the_keycloak_view_of_git_has_zero_differences(pair: tuple[Realm, Realm]) -> None:
    git, kc = pair
    assert count(git, kc) == 0


def test_the_same_document_has_zero_differences(pair: tuple[Realm, Realm]) -> None:
    git, _ = pair
    assert count(git, copy.deepcopy(git)) == 0


def test_a_default_value_that_is_not_in_git_is_zero(pair: tuple[Realm, Realm]) -> None:
    git, kc = pair
    kc["clients"][0]["unaCosaNuevaDeKeycloak"] = True
    kc["campoNuevoDelRealm"] = {"a": 1}
    assert count(git, kc) == 0


def test_a_field_of_git_with_another_value_is_one(pair: tuple[Realm, Realm]) -> None:
    git, kc = pair
    kc["accessTokenLifespan"] += 1
    assert count(git, kc) == 1


def test_a_nested_field_of_git_with_another_value_is_one(pair: tuple[Realm, Realm]) -> None:
    git, kc = pair
    _entity(kc, "clients", "clientId", "promotion-tool")["attributes"]["pkce.code.challenge.method"] = "plain"
    assert count(git, kc) == 1


def test_a_field_of_git_that_keycloak_lacks_is_one(pair: tuple[Realm, Realm]) -> None:
    git, kc = pair
    del _entity(kc, "clients", "clientId", "promotion-tool")["redirectUris"]
    assert count(git, kc) == 1


def test_a_list_of_scalars_with_another_content_is_one(pair: tuple[Realm, Realm]) -> None:
    git, kc = pair
    _entity(kc, "clients", "clientId", "promotion-tool")["redirectUris"].append("http://otro")
    assert count(git, kc) == 1


def test_a_list_of_scalars_in_another_order_is_zero(pair: tuple[Realm, Realm]) -> None:
    git, kc = pair
    client = _entity(kc, "clients", "clientId", "vectra-console")
    assert len(client["redirectUris"]) > 1
    client["redirectUris"].reverse()
    assert count(git, kc) == 0


# --- entidades de Git que faltan en Keycloak: 1 cada una --------------------------------------------


def _drop(key: str, field: str, value: str) -> Callable[[Realm], None]:
    def mutate(realm: Realm) -> None:
        realm[key].remove(_entity(realm, key, field, value))

    return mutate


def _drop_role(realm: Realm) -> None:
    realm["roles"]["realm"].remove(next(r for r in realm["roles"]["realm"] if r["name"] == "cro"))


MISSING = {
    "client": _drop("clients", "clientId", "promotion-tool"),
    "client-scope": _drop("clientScopes", "name", "governance:freeze"),
    "role": _drop_role,
    "flow": _drop("authenticationFlows", "alias", "vectra-browser"),
    "user": _drop("users", "username", "service-account-keycloak-reader"),
    "required-action": _drop("requiredActions", "alias", "CONFIGURE_TOTP"),
    "authenticator-config": _drop("authenticatorConfig", "alias", "loa-pwd"),
}


@pytest.mark.parametrize("what", sorted(MISSING))
def test_an_entity_of_git_missing_in_keycloak_is_one(pair: tuple[Realm, Realm], what: str) -> None:
    git, kc = pair
    MISSING[what](kc)
    assert count(git, kc) == 1


def test_a_component_of_git_missing_in_keycloak_is_one() -> None:
    git = load_git("prod")
    kc = keycloak_view(git)
    kc["components"]["org.keycloak.storage.UserStorageProvider"] = []
    assert count(git, kc) == 1


def test_a_nested_mapper_of_git_missing_in_keycloak_is_one(pair: tuple[Realm, Realm]) -> None:
    git, kc = pair
    mappers = _entity(kc, "clients", "clientId", "promotion-tool")["protocolMappers"]
    mappers.pop()
    assert count(git, kc) == 1


# --- entidades de Keycloak que no estan en Git: 1 cada una ------------------------------------------


def _add_client(realm: Realm) -> None:
    realm["clients"].append({"clientId": "cliente-sobrante", "enabled": True})


def _add_scope(realm: Realm) -> None:
    realm["clientScopes"].append({"name": "scope:sobrante", "protocol": "openid-connect"})


def _add_role(realm: Realm) -> None:
    realm["roles"]["realm"].append({"name": "rol-sobrante"})


def _add_flow(realm: Realm) -> None:
    realm["authenticationFlows"].append(
        {"alias": "flujo-sobrante", "builtIn": False, "authenticationExecutions": []}
    )


def _add_required_action(realm: Realm) -> None:
    realm["requiredActions"].append({"alias": "ACCION_SOBRANTE", "name": "x"})


def _add_config(realm: Realm) -> None:
    realm["authenticatorConfig"].append({"alias": "config-sobrante", "config": {}})


EXTRA = {
    "client": _add_client,
    "client-scope": _add_scope,
    "role": _add_role,
    "flow": _add_flow,
    "required-action": _add_required_action,
    "authenticator-config": _add_config,
}


@pytest.mark.parametrize("what", sorted(EXTRA))
def test_an_entity_of_keycloak_not_in_git_is_one(pair: tuple[Realm, Realm], what: str) -> None:
    git, kc = pair
    EXTRA[what](kc)
    assert count(git, kc) == 1


def test_a_component_of_keycloak_not_in_git_is_one() -> None:
    git = load_git("prod")
    kc = keycloak_view(git)
    kc["components"]["org.keycloak.storage.UserStorageProvider"].append(
        {"name": "ldap-sobrante", "providerId": "ldap"}
    )
    assert count(git, kc) == 1


def test_a_user_of_keycloak_not_in_git_is_zero(pair: tuple[Realm, Realm]) -> None:
    git, kc = pair
    kc["users"].append({"username": "importado-de-ldap", "enabled": True})
    assert count(git, kc) == 0


@pytest.mark.parametrize(
    ("key", "field", "value"),
    [
        ("clients", "clientId", "account"),
        ("clients", "clientId", "admin-cli"),
        ("clientScopes", "name", "email"),
        ("roles", "name", "uma_authorization"),
        ("requiredActions", "alias", "UPDATE_PASSWORD"),
    ],
)
def test_an_entity_that_keycloak_brings_by_itself_is_zero(
    pair: tuple[Realm, Realm], key: str, field: str, value: str
) -> None:
    git, kc = pair
    if key == "roles":
        kc["roles"]["realm"].append({field: value})
    else:
        kc[key].append({field: value})
    assert count(git, kc) == 0


def test_a_built_in_flow_of_keycloak_is_zero(pair: tuple[Realm, Realm]) -> None:
    git, kc = pair
    kc["authenticationFlows"].append(
        {"alias": "registration", "builtIn": True, "authenticationExecutions": []}
    )
    assert count(git, kc) == 0


def test_the_name_of_a_built_in_entity_in_git_is_still_compared() -> None:
    git = load_git("kind")
    git["clients"].append({"clientId": "account", "enabled": False})
    kc = keycloak_view(git)
    kc["clients"] = [c for c in kc["clients"] if c != {"clientId": "account", "id": "id-account"}]
    assert count(git, kc) == 0
    _entity(kc, "clients", "clientId", "account")["enabled"] = True
    assert count(git, kc) == 1


# --- $(env:...) ------------------------------------------------------------------------------------


def _marker_paths(node: Any, path: tuple[Any, ...] = ()) -> list[tuple[Any, ...]]:
    found: list[tuple[Any, ...]] = []
    if isinstance(node, dict):
        for key, value in node.items():
            found += _marker_paths(value, (*path, key))
    elif isinstance(node, list):
        for index, value in enumerate(node):
            found += _marker_paths(value, (*path, index))
    elif isinstance(node, str) and MARKER in node:
        found.append(path)
    return found


def test_every_git_field_with_a_marker_ignores_any_value_in_keycloak(pair: tuple[Realm, Realm]) -> None:
    git, kc = pair
    paths = _marker_paths(git)
    assert paths, "el realm no tiene ningun $(env:...)"
    assert count(git, kc) == 0
    for variant in ("otro", "", None, 7, ["x", "y"]):
        other = copy.deepcopy(kc)
        for path in _marker_paths(git):
            # Se sustituye el valor de Keycloak en el campo, donde exista la entidad (por clave, no por posicion).
            _set_by_projection(git, other, path, variant)
        assert other != kc or variant == "valor-de-la-boveda"
        assert count(git, other) == 0


def _set_by_projection(git: Realm, kc: Realm, path: tuple[Any, ...], value: Any) -> None:
    gnode: Any = git
    knode: Any = kc
    for step in path[:-1]:
        if isinstance(step, int):
            entity = gnode[step]
            gnode = entity
            if isinstance(knode, list):
                key = next(
                    k for k in ("clientId", "name", "alias", "username", "type", "priority") if k in entity
                )
                knode = next(e for e in knode if e.get(key) == entity[key])
        else:
            gnode = gnode[step]
            knode = knode[step]
    last = path[-1]
    if isinstance(last, int):
        return  # elemento de una lista de escalares: la lista entera se ignora, se cubre con el campo
    knode[last] = value


def test_a_marker_field_is_ignored_but_the_same_field_without_marker_is_compared() -> None:
    git = load_git("kind")
    client = _entity(git, "clients", "clientId", "promotion-tool")
    client["attributes"]["default.acr.values"] = f"{MARKER}ACR)"
    kc = keycloak_view(git)
    _entity(kc, "clients", "clientId", "promotion-tool")["attributes"]["default.acr.values"] = "lo-que-sea"
    assert count(git, kc) == 0
    client["attributes"]["default.acr.values"] = "mfa"
    assert count(git, kc) == 1


def test_a_list_with_a_marker_inside_is_ignored_as_a_whole() -> None:
    git = load_git("prod")
    kc = keycloak_view(git)
    config = kc["components"]["org.keycloak.storage.UserStorageProvider"][0]["config"]
    config["connectionUrl"] = ["ldaps://otro:636", "ldaps://mas:636"]
    config["editMode"] = ["WRITABLE"]  # sin marcador: este si cuenta
    assert count(git, kc) == 1


# --- orden -----------------------------------------------------------------------------------------


def test_another_order_of_every_list_of_entities_is_zero(pair: tuple[Realm, Realm]) -> None:
    git, kc = pair
    for key in (
        "clients",
        "clientScopes",
        "requiredActions",
        "authenticationFlows",
        "authenticatorConfig",
        "users",
    ):
        kc[key].sort(key=lambda e: str(sorted(e.items(), key=str)))
    kc["roles"]["realm"].reverse()
    for client in kc["clients"]:
        client.get("protocolMappers", []).reverse()
    assert count(git, kc) == 0


def test_the_order_of_the_executions_of_a_flow_does_not_matter_but_their_priority_does(
    pair: tuple[Realm, Realm],
) -> None:
    git, kc = pair
    flow = _entity(kc, "authenticationFlows", "alias", "vectra-browser forms")
    flow["authenticationExecutions"].reverse()
    assert count(git, kc) == 0
    flow["authenticationExecutions"][0]["requirement"] = "DISABLED"
    assert count(git, kc) == 1


# --- secretos, IDs y timestamps ---------------------------------------------------------------------


def test_a_different_client_secret_is_zero(pair: tuple[Realm, Realm]) -> None:
    git, kc = pair
    for client in kc["clients"]:
        client["secret"] = "otro"  # noqa: S105
    assert count(git, kc) == 0


def test_a_different_credential_value_is_zero(pair: tuple[Realm, Realm]) -> None:
    git, kc = pair
    changed = 0
    for user in kc["users"]:
        for credential in user.get("credentials", []):
            credential.update(value="distinto", secretData="distinto", credentialData="distinto")
            changed += 1
    if changed:
        assert count(git, kc) == 0


def test_a_secret_in_git_is_never_compared() -> None:
    git = load_git("kind")
    _entity(git, "clients", "clientId", "promotion-tool")["secret"] = "literal-en-git"  # noqa: S105
    kc = keycloak_view(git)
    _entity(kc, "clients", "clientId", "promotion-tool")["secret"] = "otro"  # noqa: S105
    assert count(git, kc) == 0


def test_different_ids_and_timestamps_are_zero(pair: tuple[Realm, Realm]) -> None:
    git, kc = pair
    kc["id"] = "otro"
    kc["notBefore"] = 99
    for client in kc["clients"]:
        client["id"] = "otro"
        client["notBefore"] = 5
    for user in kc["users"]:
        user["id"] = "otro"
        user["createdTimestamp"] = 12345
        for credential in user.get("credentials", []):
            credential["createdDate"] = 777
    assert count(git, kc) == 0


def test_a_credential_of_another_type_is_not_a_secret() -> None:
    git = load_git("kind")
    kc = keycloak_view(git)
    user = _entity(kc, "users", "username", "analista-1")
    user["credentials"] = [c for c in user["credentials"] if c["type"] != "otp"]
    assert count(git, kc) == 1


# --- el total ---------------------------------------------------------------------------------------


def test_the_pushed_number_is_the_total_of_the_differences(pair: tuple[Realm, Realm]) -> None:
    git, kc = pair
    kc["accessTokenLifespan"] += 1
    MISSING["client"](kc)
    MISSING["role"](kc)
    EXTRA["flow"](kc)
    EXTRA["client-scope"](kc)
    differences = realm_diff.diff(git, kc)
    assert len(differences) == 5 == count(git, kc)
    assert {d.kind for d in differences} == {"value", "missing-in-keycloak", "unexpected-in-keycloak"}
    assert all(d.path for d in differences)


def test_diff_does_not_modify_its_inputs(pair: tuple[Realm, Realm]) -> None:
    git, kc = pair
    before = (copy.deepcopy(git), copy.deepcopy(kc))
    count(git, kc)
    assert (git, kc) == before
