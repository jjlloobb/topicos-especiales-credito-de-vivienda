"""Proyeccion de `realm-drift` sobre Git (U02-T08, INF-U2-09, BR-U2-12): cada regla tiene un caso que pasa y uno que falla.

Los realms son los tres reales (`realm.{kind,staging,prod}.yaml`); la vista de Keycloak sale de `realm_exports`.
"""

import copy
from collections.abc import Callable
from typing import Any

import pytest
import realm_diff
from realm_exports import ENVS, MARKER, keycloak_view, load_git, resolve

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


def test_h10_git_fixes_the_brute_force_strategy_and_the_keycloak_view_takes_it_from_git(pair: tuple[Realm, Realm]) -> None:
    git, kc = pair
    assert git["bruteForceStrategy"] == "LINEAR"
    assert kc["bruteForceStrategy"] == git["bruteForceStrategy"]


def test_h10_keycloak_with_another_brute_force_strategy_is_one(pair: tuple[Realm, Realm]) -> None:
    git, kc = pair
    kc["bruteForceStrategy"] = "MULTIPLE"
    assert count(git, kc) == 1


def test_h10_keycloak_without_the_brute_force_strategy_is_one(pair: tuple[Realm, Realm]) -> None:
    git, kc = pair
    del kc["bruteForceStrategy"]
    assert count(git, kc) == 1


def test_h10_keycloak_with_another_max_temporary_lockouts_is_one(pair: tuple[Realm, Realm]) -> None:
    git, kc = pair
    kc["maxTemporaryLockouts"] = 3
    assert count(git, kc) == 1


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
        ("clients", "clientId", "admin-cli"),
        ("clientScopes", "name", "email"),
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


def test_every_git_field_with_a_marker_accepts_any_resolved_value(pair: tuple[Realm, Realm]) -> None:
    git, kc = pair
    paths = _marker_paths(git)
    assert paths, "el realm no tiene ningun $(env:...)"
    assert count(git, kc) == 0
    for filler in ("otro", "", "con espacios", "x" * 40):
        other = copy.deepcopy(kc)
        for path in _marker_paths(git):
            # Se sustituye el valor de Keycloak en el campo, donde exista la entidad (por clave, no por posicion).
            _set_by_projection(git, other, path, lambda text, f=filler: resolve(text, f))
        assert other != kc or filler == "resuelto"
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
    knode[last] = value(gnode[last]) if callable(value) else value


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


def test_f09_a_flow_of_the_list_is_zero_only_if_it_says_it_is_built_in(pair: tuple[Realm, Realm]) -> None:
    git, kc = pair
    kc["authenticationFlows"] = [f for f in kc["authenticationFlows"] if f["alias"] != "docker auth"]
    kc["authenticationFlows"].append(
        {"alias": "docker auth", "builtIn": True, "authenticationExecutions": []}
    )
    assert count(git, kc) == 0
    kc["authenticationFlows"][-1]["builtIn"] = False
    assert count(git, kc) == 1
    del kc["authenticationFlows"][-1]["builtIn"]
    assert count(git, kc) == 1


# --- F-11: service_account solo en clientes con cuenta de servicio -----------------------------------


def test_f11_service_account_scope_on_a_client_without_service_account_counts(
    pair: tuple[Realm, Realm],
) -> None:
    git, kc = pair
    public = next(
        c for c in kc["clients"] if c.get("serviceAccountsEnabled") is False and "defaultClientScopes" in c
    )
    public["defaultClientScopes"].append("service_account")
    assert count(git, kc) == 1


# --- S3: el texto literal que rodea al marcador se conserva -----------------------------------------------


def _ldap(realm: Realm) -> Realm:
    return realm["components"]["org.keycloak.storage.UserStorageProvider"][0]["config"]


def test_s3_ldap_url_without_tls_counts_and_any_host_with_the_literals_does_not() -> None:
    git = load_git("prod")
    kc = keycloak_view(git)
    _ldap(kc)["connectionUrl"] = ["ldaps://cualquier.host.banco:636"]
    assert count(git, kc) == 0
    _ldap(kc)["connectionUrl"] = ["ldap://otro:389"]
    assert count(git, kc) == 1
    _ldap(kc)["connectionUrl"] = ["ldaps://otro:389"]
    assert count(git, kc) == 1
    _ldap(kc)["connectionUrl"] = ["ldap://otro:636"]
    assert count(git, kc) == 1


def test_s3_prefix_and_suffix_do_not_overlap() -> None:
    git = load_git("prod")
    kc = keycloak_view(git)
    _ldap(kc)["connectionUrl"] = ["ldaps://:636"]  # el marcador resuelto a vacio
    assert count(git, kc) == 0
    _ldap(kc)["connectionUrl"] = ["ldaps://636"]  # el prefijo y el sufijo se solapan: no cabe el marcador
    assert count(git, kc) == 1


def test_s3_a_list_element_that_does_not_keep_its_literals_counts(pair: tuple[Realm, Realm]) -> None:
    git, kc = pair
    _console(kc)["redirectUris"] = ["https://x/callback", "https://x/otra"]
    assert count(git, kc) == 1
    _console(kc)["redirectUris"] = ["http://x/callback", "https://x/stepup-callback"]
    assert count(git, kc) == 1


def test_s3_every_scalar_marker_of_git_demands_a_string_that_keeps_its_literals(
    pair: tuple[Realm, Realm],
) -> None:
    git, kc = pair
    # Las credenciales y las acciones requeridas de un usuario no se comparan (S1).
    paths = [p for p in _marker_paths(git) if isinstance(p[-1], str) and "credentials" not in p]
    assert paths
    for path in paths:
        other = copy.deepcopy(kc)
        _set_by_projection(git, other, path, lambda _text: 7)
        if other != kc:
            assert count(git, other) >= 1, path


# --- F-08: los roles como conjunto exacto, en todos los lugares que los asignan ---------------------------


def _git_users(git: Realm) -> list[str]:
    return [u["username"] for u in git["users"]]


def test_f08_a_realm_role_that_git_does_not_declare_counts_on_every_declared_user(
    pair: tuple[Realm, Realm],
) -> None:
    git, kc = pair
    for name in _git_users(git):
        other = copy.deepcopy(kc)
        _entity(other, "users", "username", name)["realmRoles"].append("cro")
        assert count(git, other) >= 1, name


def test_f08_a_client_role_that_git_does_not_declare_counts_on_every_declared_user(
    pair: tuple[Realm, Realm],
) -> None:
    git, kc = pair
    for name in _git_users(git):
        user = _entity(git, "users", "username", name)
        other = copy.deepcopy(kc)
        kuser = _entity(other, "users", "username", name)
        kuser.setdefault("clientRoles", {})
        kuser["clientRoles"].setdefault("realm-management", []).append("realm-admin")
        if "realm-admin" in user.get("clientRoles", {}).get("realm-management", []):
            continue
        assert count(git, other) == 1, name
        other = copy.deepcopy(kc)
        _entity(other, "users", "username", name).setdefault("clientRoles", {})["broker"] = ["read-token"]
        assert count(git, other) == 1, name


def test_f08_roles_absent_in_git_and_in_keycloak_are_zero_and_the_exemptions_hold(
    pair: tuple[Realm, Realm],
) -> None:
    git, kc = pair
    for user in kc["users"]:
        assert set(user["realmRoles"]) >= {"default-roles-vectra"}
    assert count(git, kc) == 0


def test_f08_a_declared_user_gets_realm_admin_in_staging() -> None:
    git = load_git("staging")
    kc = keycloak_view(git)
    _entity(kc, "users", "username", "analista-1")["clientRoles"] = {"realm-management": ["realm-admin"]}
    assert count(git, kc) == 1


@pytest.mark.parametrize("which", ["scopeMappings", "clientScopeMappings"])
def test_f08_scope_mappings_that_git_does_not_declare_count(pair: tuple[Realm, Realm], which: str) -> None:
    git, kc = pair
    if which == "scopeMappings":
        kc[which].append({"client": "vectra-console", "roles": ["realm-admin"]})
        assert count(git, kc) == 1
        entry = next(m for m in kc[which] if m.get("roles") and m.get("clientScope") != "offline_access")
        entry["roles"].append("realm-admin")
        assert count(git, kc) == 2
    else:
        kc[which]["realm-management"].append({"client": "vectra-console", "roles": ["realm-admin"]})
        assert count(git, kc) == 1
        kc[which]["broker"] = [{"client": "vectra-console", "roles": ["read-token"]}]
        assert count(git, kc) == 2


# --- D-8: los composites de los roles ------------------------------------------------------------------


def _role(realm: Realm, name: str) -> Realm:
    return next(r for r in realm["roles"]["realm"] if r["name"] == name)


def test_d8_the_default_composites_of_keycloak_are_zero(pair: tuple[Realm, Realm]) -> None:
    git, kc = pair
    assert _role(kc, "default-roles-vectra")["composites"]["client"] == {
        "account": ["view-profile", "manage-account"]
    }
    assert count(git, kc) == 0


def test_d8_realm_admin_as_a_composite_of_the_default_role_counts(pair: tuple[Realm, Realm]) -> None:
    git, kc = pair
    _role(kc, "default-roles-vectra")["composites"]["client"]["realm-management"] = ["realm-admin"]
    assert count(git, kc) == 1


def test_d8_any_change_to_the_default_composites_counts(pair: tuple[Realm, Realm]) -> None:
    git, kc = pair
    _role(kc, "default-roles-vectra")["composites"]["realm"].append("cro")
    assert count(git, kc) == 1
    _role(kc, "default-roles-vectra")["composites"]["client"]["account"].remove("manage-account")
    assert count(git, kc) == 2
    del _role(kc, "default-roles-vectra")["composites"]
    assert count(git, kc) == 1  # sin composites, el campo entero difiere de los de Keycloak


def test_d8_a_composite_on_another_keycloak_role_counts(pair: tuple[Realm, Realm]) -> None:
    git, kc = pair
    _role(kc, "offline_access")["composites"] = {"realm": ["cro"]}
    assert count(git, kc) == 1


def test_d8_the_composites_of_a_git_role_are_compared_with_git(pair: tuple[Realm, Realm]) -> None:
    git, kc = pair
    _role(kc, "cro")["composites"] = {"realm": ["analista"]}
    assert count(git, kc) == 1
    _role(git, "cro")["composites"] = {"realm": ["analista"]}
    assert count(git, kc) == 0
    _role(kc, "cro")["composites"] = {"realm": ["analista", "operacion"]}
    assert count(git, kc) == 1
