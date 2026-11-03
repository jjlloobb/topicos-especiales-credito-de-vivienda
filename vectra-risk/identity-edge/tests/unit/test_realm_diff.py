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
        ("clients", "clientId", "account-console"),
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
    kc["authenticationFlows"] = [f for f in kc["authenticationFlows"] if f["alias"] != "registration"]
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


def test_a_list_with_a_marker_element_ignores_only_that_element() -> None:
    git = load_git("prod")
    kc = keycloak_view(git)
    config = kc["components"]["org.keycloak.storage.UserStorageProvider"][0]["config"]
    config["connectionUrl"] = ["ldaps://otro:636"]  # el elemento con marcador, ya resuelto
    assert count(git, kc) == 0
    config["connectionUrl"] = ["ldaps://otro:636", "ldaps://mas:636"]  # uno de mas
    assert count(git, kc) == 1
    config["editMode"] = ["WRITABLE"]  # un elemento de Git sin marcador que falta, y uno de mas
    assert count(git, kc) == 3


def _console(realm: Realm) -> Realm:
    return _entity(realm, "clients", "clientId", "vectra-console")


def test_s2_resolved_markers_in_redirect_uris_are_zero(pair: tuple[Realm, Realm]) -> None:
    git, kc = pair
    assert len(_console(git)["redirectUris"]) == 2 and all(MARKER in u for u in _console(git)["redirectUris"])
    _console(kc)["redirectUris"] = [
        "https://resuelto.example/callback",
        "https://resuelto.example/stepup-callback",
    ]
    assert count(git, kc) == 0
    _console(kc)["redirectUris"].reverse()
    assert count(git, kc) == 0


def test_s2_an_extra_element_in_a_marker_list_is_one(pair: tuple[Realm, Realm]) -> None:
    git, kc = pair
    _console(kc)["redirectUris"].append("https://atacante.example/*")
    assert count(git, kc) == 1
    _console(kc)["redirectUris"].append("https://otro-atacante.example/*")
    assert count(git, kc) == 2


def test_s2_a_literal_element_of_git_that_is_missing_is_one(pair: tuple[Realm, Realm]) -> None:
    git, kc = pair
    _console(git)["redirectUris"].append("http://127.0.0.1/literal")
    _console(kc)["redirectUris"].append("http://127.0.0.1/literal")
    assert count(git, kc) == 0
    _console(kc)["redirectUris"].remove("http://127.0.0.1/literal")
    assert count(git, kc) == 1


def test_s2_fewer_elements_than_markers_is_zero(pair: tuple[Realm, Realm]) -> None:
    git, kc = pair
    _console(kc)["redirectUris"] = ["https://resuelto.example/callback"]
    assert count(git, kc) == 0


# --- S1: en los usuarios no se comparan requiredActions ni credentials ------------------------------


def test_s1_break_glass_after_its_first_login_is_zero() -> None:
    git = load_git("prod")
    kc = keycloak_view(git)
    user = _entity(kc, "users", "username", "break-glass")
    user["requiredActions"] = []
    user["credentials"] = [*user["credentials"], {"type": "otp", "userLabel": "primer login"}]
    assert count(git, kc) == 0


def test_s1_break_glass_disabled_or_with_another_role_is_one() -> None:
    git = load_git("prod")
    kc = keycloak_view(git)
    _entity(kc, "users", "username", "break-glass")["enabled"] = False
    assert count(git, kc) == 1
    kc = keycloak_view(git)
    _entity(kc, "users", "username", "break-glass")["clientRoles"] = {"realm-management": ["view-realm"]}
    assert count(git, kc) == 2  # falta realm-admin y sobra view-realm
    kc = keycloak_view(git)
    _entity(kc, "users", "username", "break-glass")["realmRoles"].append("cro")
    assert count(git, kc) == 1


def test_s1_other_fields_of_a_user_are_still_compared(pair: tuple[Realm, Realm]) -> None:
    git, kc = pair
    user = _entity(kc, "users", "username", "service-account-keycloak-reader")
    user["requiredActions"] = ["UPDATE_PASSWORD"]
    user["credentials"] = [{"type": "password"}]
    assert count(git, kc) == 0
    user["enabled"] = False
    assert count(git, kc) == 1


# --- F-01: valores por defecto de un realm nuevo de Keycloak 26.8.1, en todos los niveles -------------


def test_f01_the_defaults_of_a_new_realm_are_zero(pair: tuple[Realm, Realm]) -> None:
    git, kc = pair
    assert {"clientScope": "offline_access", "roles": ["offline_access"]} in kc["scopeMappings"]
    assert "account" in kc["clientScopeMappings"]
    assert any("service_account" in c.get("defaultClientScopes", []) for c in kc["clients"])
    assert count(git, kc) == 0


@pytest.mark.parametrize(
    "mutate",
    [
        lambda kc: kc["scopeMappings"].append(
            {"clientScope": "offline_access", "roles": ["offline_access", "cro"]}
        ),
        lambda kc: kc["scopeMappings"].append({"clientScope": "profile", "roles": ["cro"]}),
        lambda kc: kc["clientScopeMappings"].update(
            {"realm-management": [{"client": "account-console", "roles": ["realm-admin"]}]}
        ),
        lambda kc: kc["clientScopeMappings"].update(
            {"account": [{"client": "account-console", "roles": ["manage-account", "view-groups", "extra"]}]}
        ),
    ],
    ids=["default-with-an-extra-role", "other-scope", "other-container", "default-with-another-role"],
)
def test_f01_an_entry_that_is_not_exactly_the_default_counts(
    pair: tuple[Realm, Realm], mutate: Callable[[Realm], Any]
) -> None:
    git, kc = pair
    kc["scopeMappings"] = [m for m in kc["scopeMappings"] if m.get("clientScope") != "offline_access"]
    kc["clientScopeMappings"].pop("account", None)
    mutate(kc)
    assert count(git, kc) >= 1


def test_f01_service_account_scope_is_only_exempt_in_default_client_scopes(pair: tuple[Realm, Realm]) -> None:
    git, kc = pair
    client = next(c for c in kc["clients"] if c.get("serviceAccountsEnabled"))
    client["defaultClientScopes"].append("scoring:explain")
    assert count(git, kc) == 1
    client["optionalClientScopes"].append("service_account")
    assert count(git, kc) == 2


def test_f01_default_roles_of_a_user_are_zero_but_any_other_role_counts(pair: tuple[Realm, Realm]) -> None:
    git, kc = pair
    name = next(u["username"] for u in git["users"] if "realmRoles" in u)
    user = _entity(kc, "users", "username", name)
    user["realmRoles"] += ["offline_access", "uma_authorization"]
    assert count(git, kc) == 0
    user["realmRoles"].append("cro")
    assert count(git, kc) == 1


def test_f05_there_is_a_single_source_of_the_default_roles() -> None:
    import keycloak_admin

    assert not hasattr(keycloak_admin, "KEYCLOAK_USER_ROLES")
    assert "default-roles-vectra" in realm_diff.BUILT_IN_NAMES[("roles", "realm")]


# --- F-02: una clave repetida, en cualquier nivel y de cualquier lado, cuenta -------------------------


def _lists(realm: Realm) -> list[tuple[tuple[str, ...], list[Any]]]:
    found: list[tuple[tuple[str, ...], list[Any]]] = []

    def walk(node: Any, path: tuple[str, ...]) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                walk(value, realm_diff.child_path(path, key))
        elif isinstance(node, list):
            if path in realm_diff.ENTITY_KEYS and node:
                found.append((path, node))
            for item in node:
                walk(item, path)

    walk(realm, ())
    return found


def test_f02_every_entity_level_is_covered() -> None:
    covered = {path for env in ENVS for path, _ in _lists(keycloak_view(load_git(env)))}
    assert covered == set(realm_diff.ENTITY_KEYS)


@pytest.mark.parametrize("side", ["keycloak", "git"])
@pytest.mark.parametrize("path", sorted(realm_diff.ENTITY_KEYS))
def test_f02_a_repeated_key_counts(path: tuple[str, ...], side: str) -> None:
    done = False
    for env in ENVS:
        git = load_git(env)
        kc = keycloak_view(git)
        target = kc if side == "keycloak" else git
        candidates = [items for p, items in _lists(target) if p == path and isinstance(items[0], dict)]
        if not candidates:
            continue
        items = candidates[0]
        items.insert(0, copy.deepcopy(items[0]))
        assert count(git, kc) >= 1, (env, path, side)
        done = True
    assert done, f"ningun entorno tiene el nivel {path}"


def test_f02_a_repeated_priority_that_hides_a_change_counts() -> None:
    git = load_git("staging")
    kc = keycloak_view(git)
    flow = _entity(kc, "authenticationFlows", "alias", "vectra-level-pwd")
    flow["authenticationExecutions"].insert(
        0, {**flow["authenticationExecutions"][0], "requirement": "DISABLED"}
    )
    assert count(git, kc) >= 1


# --- F-03: los flujos propios de Keycloak, por lista exacta de alias ---------------------------------


def test_f03_a_flow_outside_git_and_the_list_counts_even_if_it_says_built_in(
    pair: tuple[Realm, Realm],
) -> None:
    git, kc = pair
    kc["authenticationFlows"].append(
        {"alias": "puerta-trasera", "builtIn": True, "authenticationExecutions": []}
    )
    assert count(git, kc) == 1


def test_f03_a_flow_of_the_list_is_zero_even_if_it_says_it_is_not_built_in(pair: tuple[Realm, Realm]) -> None:
    git, kc = pair
    kc["authenticationFlows"] = [f for f in kc["authenticationFlows"] if f["alias"] != "docker auth"]
    kc["authenticationFlows"].append(
        {"alias": "docker auth", "builtIn": False, "authenticationExecutions": []}
    )
    assert count(git, kc) == 0


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
