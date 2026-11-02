"""Lectura de vuelta de los `realm.{kind,staging,prod}.yaml` reales (Paso 2 del plan de U2).

Cada valor sale de domain-entities, business-rules e infrastructure-design (ver
`design_values.py`) o del catalogo de U0, no de una lista escrita aqui.
"""

import json
import re
from pathlib import Path
from typing import Any

import design_values as design
import pytest
import yaml
from realm_lint import (
    ADMIN_CLIENT_ROLES,
    BREAK_GLASS,
    NON_PROD,
    OPERACION,
    REALM_ADMIN,
    REALM_MANAGEMENT,
    TOTP_ACTION,
    lint_realm,
    otp_seed_reference,
)
from vectra_contracts.catalog import SCOPE_HOLDERS, Role, Scope

REALM_DIR = Path(__file__).resolve().parents[2] / "keycloak" / "realm"
ENVS = ("kind", "staging", "prod")
REFERENCE = re.compile(r"^\$\(env:[A-Z][A-Z0-9_]*\)$")
TECHNICAL_CLIENTS = tuple(ADMIN_CLIENT_ROLES)
MFA_ROLES = design.mfa_required_roles()  # columna MFA de §1.1 (y `operacion`)
BREAK_GLASS_ROLE = f"{REALM_MANAGEMENT}.{REALM_ADMIN}"


def load(env: str) -> dict[str, Any]:
    data = yaml.safe_load((REALM_DIR / f"realm.{env}.yaml").read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


@pytest.fixture(params=ENVS)
def env(request: pytest.FixtureRequest) -> str:
    return str(request.param)


def client_of(realm: dict[str, Any], client_id: str) -> dict[str, Any]:
    return next(c for c in realm["clients"] if c["clientId"] == client_id)


def _audience_mappers(mappers: list[dict[str, Any]]) -> set[str]:
    return {m["config"]["included.custom.audience"] for m in mappers if m["protocolMapper"] == "oidc-audience-mapper"}


def audiences(client: dict[str, Any], realm: dict[str, Any] | None = None, requested: set[str] | None = None) -> set[str]:
    """La audiencia de un token: la de los mappers del cliente y la de cada scope pedido que el cliente puede
    obtener (el mapper de audiencia va dentro del client scope)."""
    found = _audience_mappers(client.get("protocolMappers", []))
    if realm is not None:
        wanted = obtainable_scopes(realm, client) if requested is None else requested & obtainable_scopes(realm, client)
        for scope in realm["clientScopes"]:
            if scope["name"] in wanted:
                found |= _audience_mappers(scope.get("protocolMappers", []))
    return found


def obtainable_scopes(realm: dict[str, Any], client: dict[str, Any]) -> set[str]:
    """Los scopes que un cliente puede obtener: los suyos que el realm define como client scope."""
    defined = {s["name"] for s in realm.get("clientScopes", [])}
    return (set(client["optionalClientScopes"]) | set(client["defaultClientScopes"])) & defined


def design_clients(env: str) -> dict[str, tuple[set[str], set[str]]]:
    """Cliente de servicio -> (scopes, audiencias) de domain-entities §2.2 para `env`."""
    out = {}
    for c in design.service_clients():
        if env == "prod" and c.non_prod_only:
            continue
        keep = lambda items: {i.name for i in items if not (env == "prod" and i.non_prod_only)}  # noqa: E731
        out[c.client_id] = (keep(c.scopes), keep(c.audiences))
    return out


# --- archivos y parametros -------------------------------------------------------------------


def test_realm_files_exist_and_pass_realm_lint(env: str) -> None:
    assert lint_realm(load(env), env) == []


def test_realm_files_realm_name_and_business_roles(env: str) -> None:
    realm = load(env)
    assert realm["realm"] == "vectra"
    names = {r["name"] for r in realm["roles"]["realm"]}
    assert names == {r.value for r in Role} | {OPERACION}


def test_realm_files_parameters_are_those_of_the_design(env: str) -> None:
    realm = load(env)
    expected = {**design.brute_force_fields(), **design.token_and_session_parameters()}
    assert set(expected) >= {"failureFactor", "accessTokenLifespan", "ssoSessionIdleTimeout", "ssoSessionMaxLifespan"}
    for key, value in expected.items():
        assert realm[key] == value
        assert type(realm[key]) is type(value)
    assert realm["revokeRefreshToken"] is True  # BR-U2-06: rotacion
    assert realm["refreshTokenMaxReuse"] == 0  # reusar uno invalidado no se tolera
    assert json.loads(realm["attributes"]["acr.loa.map"]) == design.loa_map() == {"pwd": 1, "mfa": 2}
    assert realm["registrationAllowed"] is False
    assert realm["passwordPolicy"]
    assert "persistent" not in json.dumps(realm).lower()  # D6: las sesiones persistentes son del servidor


def test_realm_files_events_without_personal_data_in_the_realm_fields(env: str) -> None:
    realm = load(env)
    assert realm["eventsEnabled"] is True
    assert realm["eventsListeners"] == ["jboss-logging"]  # BR-U2-16: el filtro de username/email es de Alloy (U1)
    assert realm["adminEventsEnabled"] is True
    assert realm["adminEventsDetailsEnabled"] is False  # sin la representacion del recurso


# --- login: LoA, OTP condicional por rol, TOTP y WebAuthn ------------------------------------


def flow_by_alias(realm: dict[str, Any], alias: str) -> dict[str, Any]:
    return next(f for f in realm["authenticationFlows"] if f["alias"] == alias)


def executions(realm: dict[str, Any], flow_alias: str) -> list[dict[str, Any]]:
    return flow_by_alias(realm, flow_alias)["authenticationExecutions"]


def level_subflows(realm: dict[str, Any]) -> list[dict[str, Any]]:
    """Los subflujos condicionales del formulario del login, con sus condiciones y su segundo factor."""
    configs = {c["alias"]: c["config"] for c in realm["authenticatorConfig"]}
    out = []
    for sub in executions(realm, "vectra-browser forms"):
        assert sub["requirement"] == "CONDITIONAL"
        items = executions(realm, sub["flowAlias"])
        levels = [
            int(configs[e["authenticatorConfig"]]["loa-condition-level"])
            for e in items
            if e.get("authenticator") == "conditional-level-of-authentication"
        ]
        roles = [
            configs[e["authenticatorConfig"]]
            for e in items
            if e.get("authenticator") == "conditional-user-role"
        ]
        factors = [
            {(x["authenticator"], x["requirement"]) for x in executions(realm, e["flowAlias"])}
            for e in items
            if e.get("flowAlias")
        ]
        out.append({"alias": sub["flowAlias"], "levels": levels, "roles": roles, "factors": factors, "items": items})
    return out


def test_realm_files_login_flow_reaches_acr_mfa_for_every_mfa_role(env: str) -> None:
    realm = load(env)
    loa = design.loa_map()
    assert realm["browserFlow"] == "vectra-browser"
    subflows = level_subflows(realm)
    # Nivel 1 (pwd): contrasena.
    (first,) = [s for s in subflows if s["levels"] == [loa["pwd"]]]
    assert any(e.get("authenticator") == "auth-username-password-form" for e in first["items"])
    # Nivel 2 (mfa): condicion de nivel Y de rol Y segundo factor TOTP o WebAuthn (BR-U2-03).
    second_factor = {("auth-otp-form", "ALTERNATIVE"), ("webauthn-authenticator", "ALTERNATIVE")}
    for role in sorted(MFA_ROLES | {BREAK_GLASS_ROLE}):
        (sub,) = [s for s in subflows if s["levels"] == [loa["mfa"]] and any(r["condUserRole"] == role for r in s["roles"])]
        assert all(r["negate"] == "false" for r in sub["roles"])
        assert sub["factors"] == [second_factor]
        assert all(e["requirement"] == "REQUIRED" for e in sub["items"])
        assert not any(e.get("authenticator") == "conditional-user-configured" for e in sub["items"])  # siempre
    # Los roles con MFA opcional (analista): solo si ya configuraron el factor.
    for role in design.optional_mfa_roles():
        (sub,) = [s for s in subflows if any(r["condUserRole"] == role for r in s["roles"])]
        assert sub["levels"] == [loa["mfa"]]
        assert any(e.get("authenticator") == "conditional-user-configured" for e in sub["items"])
    # Los clientes de usuario piden el nivel mfa por defecto (acr_values).
    for client_id in design.user_client_ids():
        assert client_of(realm, client_id)["attributes"]["default.acr.values"] == "mfa"


def test_realm_files_break_glass_requires_mfa_through_its_realm_admin_role() -> None:
    prod = load("prod")
    (glass,) = [u for u in prod["users"] if u["username"] == BREAK_GLASS]
    assert glass["realmRoles"] == []  # no lo cubre ninguna condicion de rol de realm
    assert glass["clientRoles"] == {REALM_MANAGEMENT: [REALM_ADMIN]}
    covering = [s for s in level_subflows(prod) if any(r["condUserRole"] == BREAK_GLASS_ROLE for r in s["roles"])]
    assert len(covering) == 1 and covering[0]["levels"] == [design.loa_map()["mfa"]]


def test_realm_files_totp_and_webauthn_required_actions_are_enabled(env: str) -> None:
    actions = {a["alias"]: a for a in load(env)["requiredActions"]}
    for alias in (TOTP_ACTION, "webauthn-register"):
        assert actions[alias]["enabled"] is True
        assert actions[alias]["defaultAction"] is False


# --- clientes de usuario (domain-entities §2.1) ----------------------------------------------


def test_realm_files_public_hostname_comes_from_the_deployment_values(env: str) -> None:
    assert design.public_hostname_contract()
    text = (REALM_DIR / f"realm.{env}.yaml").read_text(encoding="utf-8")
    assert not re.search(r"https?://(?!127\.0\.0\.1)[\w.-]*(localtest\.me|banco\.internal)", text)


def test_realm_files_user_clients_are_those_of_the_design(env: str) -> None:
    realm = load(env)
    ids = set(design.user_client_ids())
    assert len(ids) == 3 and ids <= {c["clientId"] for c in realm["clients"]}
    uris = design.console_uris()

    console = client_of(realm, "vectra-console")
    assert console["publicClient"] is True
    assert console["standardFlowEnabled"] is True
    assert console["attributes"]["pkce.code.challenge.method"] == "S256"
    assert console["redirectUris"] == uris["redirectUris"]
    assert console["webOrigins"] == uris["webOrigins"]
    assert console["attributes"]["post.logout.redirect.uris"] == uris["post_logout"][0]
    assert audiences(console) == set(design.user_audiences())

    spec = design.promotion_tool()
    promotion = client_of(realm, "promotion-tool")
    assert promotion["publicClient"] is True
    assert promotion["attributes"]["pkce.code.challenge.method"] == "S256"
    assert promotion["redirectUris"] == spec["redirectUris"]
    assert audiences(promotion) == {spec["audience"]}
    assert promotion["optionalClientScopes"] == [spec["scope"]]
    assert promotion["defaultClientScopes"] == []

    grafana = client_of(realm, "grafana")
    assert grafana["publicClient"] is False
    assert grafana["clientAuthenticatorType"] == "client-jwt"
    assert "secret" not in grafana
    assert grafana["redirectUris"] == [design.grafana_callback()]

    for client in (console, promotion, grafana):
        assert any(m["name"] == "roles" and m["config"]["claim.name"] == "roles" for m in client["protocolMappers"])
        # domain-entities §1.2 y §1.3: acr, amr y auth_time en el token de usuario.
        mappers = {m["protocolMapper"] for m in client["protocolMappers"]}
        assert {"oidc-acr-mapper", "oidc-amr-mapper", "oidc-sub-mapper"} <= mappers
        assert any(m["config"].get("claim.name") == "auth_time" for m in client["protocolMappers"])


def test_realm_files_name_claim_is_only_in_the_id_token_of_the_console(env: str) -> None:
    names = 0
    for client in load(env)["clients"]:
        for mapper in client.get("protocolMappers", []):
            if mapper["protocolMapper"] == "oidc-full-name-mapper":
                names += 1
                assert client["clientId"] == "vectra-console"
                assert mapper["config"]["id.token.claim"] == "true"
                assert mapper["config"]["access.token.claim"] == "false"
    assert names == 1


def test_realm_files_promotion_scope_is_assignable_only_to_ingeniero_riesgo(env: str) -> None:
    realm = load(env)
    spec = design.promotion_tool()
    mappings = {m["clientScope"]: m["roles"] for m in realm["scopeMappings"] if "clientScope" in m}
    assert mappings[str(spec["scope"])] == [spec["role"]]
    assert client_of(realm, "promotion-tool")["fullScopeAllowed"] is False


# --- identidades de servicio (domain-entities §2.2) ------------------------------------------


def test_realm_files_service_clients_match_the_design_table(env: str) -> None:
    realm = load(env)
    expected = design_clients(env)
    assert {"case-service", "case-worker", "bias-monitoring-job", "product-metrics"} <= set(expected)
    present = {c["clientId"] for c in realm["clients"]} - set(design.user_client_ids()) - set(TECHNICAL_CLIENTS)
    assert present == set(expected)
    for client_id, (scopes, expected_audiences) in expected.items():
        client = client_of(realm, client_id)
        assert client["serviceAccountsEnabled"] is True
        assert client["clientAuthenticatorType"] == "client-jwt"
        assert "secret" not in client
        assert client["defaultClientScopes"] == []
        assert set(client["optionalClientScopes"]) == scopes
        assert obtainable_scopes(realm, client) == scopes
        assert audiences(client, realm) == expected_audiences
        assert client["attributes"]["access.token.lifespan"] == "300"
        assert client["attributes"]["client_credentials.use_refresh_token"] == "false"  # noqa: S105


def test_realm_files_audience_follows_the_requested_scope(env: str) -> None:
    """F-05: el token lleva solo la audiencia del scope pedido, no la union de las del cliente."""
    realm = load(env)
    by_scope = {s["name"]: _audience_mappers(s.get("protocolMappers", [])) for s in realm["clientScopes"]}
    for client_id in design_clients(env):
        client = client_of(realm, client_id)
        assert audiences(client) == set()  # sin mapper fijo en el cliente
        for scope in client["optionalClientScopes"]:
            assert len(by_scope[scope]) == 1
            assert audiences(client, realm, {scope}) == {design.scope_audience(scope)} == by_scope[scope]
    # Un cliente que pide un solo scope no obtiene las demas audiencias.
    case = client_of(realm, "case-service")
    assert audiences(case, realm, {"registry:append:case"}) == {"decision-registry-service"}


def test_realm_files_service_scopes_are_consistent_with_the_u0_catalog(env: str) -> None:
    realm = load(env)
    for client_id, (scopes, _) in design_clients(env).items():
        catalog = {s.value for s, holders in SCOPE_HOLDERS.items() if client_id in holders}
        assert scopes <= catalog
    holders = {s.value: set(h) for s, h in SCOPE_HOLDERS.items()}
    for client in realm["clients"]:
        for scope in client["optionalClientScopes"]:
            assert client["clientId"] in holders[scope]


def test_realm_files_only_bias_monitoring_job_has_freeze_and_nobody_has_core_write(env: str) -> None:
    realm = load(env)
    for client in realm["clients"]:
        scopes = set(client["optionalClientScopes"]) | set(client["defaultClientScopes"])
        assert Scope.CORE_WRITE_CREDIT.value not in scopes
        assert (Scope.GOVERNANCE_FREEZE.value in scopes) == (client["clientId"] == "bias-monitoring-job")
    assert Scope.CORE_WRITE_CREDIT.value not in {s["name"] for s in realm["clientScopes"]}


def test_realm_files_client_specific_to_non_production(env: str) -> None:
    ids = {c["clientId"] for c in load(env)["clients"]}
    non_prod = {c.client_id for c in design.service_clients() if c.non_prod_only}
    assert non_prod == {"channel-simulator", "verification-reader"}
    for client_id in non_prod:
        assert (client_id in ids) == (env in NON_PROD)


def test_realm_files_verification_reader_and_product_metrics_have_exact_scopes(env: str) -> None:
    realm = load(env)
    expected = design_clients(env)
    if env in NON_PROD:
        reader = client_of(realm, "verification-reader")
        assert set(reader["optionalClientScopes"]) == expected["verification-reader"][0]
    assert set(client_of(realm, "product-metrics")["optionalClientScopes"]) == expected["product-metrics"][0]


def test_realm_files_case_service_cannot_get_a_core_token_in_production() -> None:
    prod = load("prod")
    case = client_of(prod, "case-service")
    assert Scope.CORE_READ_CREDIT.value not in obtainable_scopes(prod, case)
    assert "core-banking-mock" not in audiences(case, prod)
    assert Scope.CORE_READ_CREDIT.value not in {s["name"] for s in prod["clientScopes"]}
    for env in NON_PROD:
        realm = load(env)
        case = client_of(realm, "case-service")
        assert Scope.CORE_READ_CREDIT.value in obtainable_scopes(realm, case)
        assert "core-banking-mock" in audiences(case, realm)


def test_realm_files_no_client_has_keycloak_default_scopes(env: str) -> None:
    realm = load(env)
    assert realm["defaultDefaultClientScopes"] == []
    assert realm["defaultOptionalClientScopes"] == []
    for client in realm["clients"]:
        assert client["defaultClientScopes"] == []


def test_realm_files_access_token_has_no_personal_claims(env: str) -> None:
    realm = load(env)
    for owner in [*realm["clients"], *realm["clientScopes"]]:
        for mapper in owner.get("protocolMappers", []):
            claim = mapper["config"].get("claim.name")
            if claim in ("preferred_username", "email", "name"):
                assert mapper["config"]["access.token.claim"] == "false"


# --- administracion (INF-U2-05a) --------------------------------------------------------------


def test_realm_files_admin_clients_and_their_service_accounts(env: str) -> None:
    realm = load(env)
    accounts = {u["serviceAccountClientId"]: u for u in realm["users"] if "serviceAccountClientId" in u}
    assert set(accounts) == set(ADMIN_CLIENT_ROLES)
    for client_id, roles in ADMIN_CLIENT_ROLES.items():
        client = client_of(realm, client_id)
        assert client["serviceAccountsEnabled"] is True
        assert client["clientAuthenticatorType"] == "client-jwt"
        assert client["optionalClientScopes"] == [] and client["defaultClientScopes"] == []
        assert "secret" not in client
        assigned = set(accounts[client_id]["clientRoles"][REALM_MANAGEMENT])
        assert assigned == roles


# --- usuarios por entorno (domain-entities §3) -------------------------------------------------


def role_of(username: str) -> str:
    prefix = username.rsplit("-", 1)[0]
    (role,) = [r for r in (*(r.value for r in Role), OPERACION) if r.startswith(prefix)]
    return role


def test_realm_files_synthetic_users_in_kind_and_staging() -> None:
    names = design.synthetic_usernames()
    per_role = design.users_per_role()
    assert len(names) == per_role * (len(Role) + 1)  # 4 roles de negocio + `operacion`
    for env in NON_PROD:
        realm = load(env)
        locals_ = {u["username"]: u for u in realm["users"] if "serviceAccountClientId" not in u}
        assert set(locals_) == set(names)
        by_role: dict[str, int] = {}
        for name, user in locals_.items():
            roles = user["realmRoles"]
            assert roles == [role_of(name)]
            by_role[roles[0]] = by_role.get(roles[0], 0) + 1
            # E1-E4 (domain-entities §3): sin CONFIGURE_TOTP; credencial otp con la forma unica.
            assert TOTP_ACTION not in user["requiredActions"]
            kinds = [c["type"] for c in user["credentials"]]
            assert sorted(kinds) == ["otp", "password"]
            otp = next(c for c in user["credentials"] if c["type"] == "otp")
            assert json.loads(otp["secretData"]) == {"value": otp_seed_reference(name)}
            assert json.loads(otp["credentialData"]) == {
                "subType": "totp", "digits": 6, "period": 30, "algorithm": "HmacSHA1", "secretEncoding": "BASE32",
            }  # fmt: skip
            assert set(otp) == {"type", "secretData", "credentialData"}
        assert set(by_role.values()) == {per_role} and len(by_role) == len(Role) + 1
        assert BREAK_GLASS not in locals_


def test_realm_files_prod_has_only_break_glass_and_ldap_federation() -> None:
    realm = load("prod")
    locals_ = [u for u in realm["users"] if "serviceAccountClientId" not in u]
    assert [u["username"] for u in locals_] == [BREAK_GLASS]
    glass = locals_[0]
    assert glass["clientRoles"] == {REALM_MANAGEMENT: [REALM_ADMIN]}
    assert TOTP_ACTION in glass["requiredActions"]
    (ldap,) = realm["components"]["org.keycloak.storage.UserStorageProvider"]
    config = {k: v[0] for k, v in ldap["config"].items()}
    assert ldap["providerId"] == "ldap"
    assert config["connectionUrl"] == "ldaps://$(env:LDAP_HOST):636"
    assert config["editMode"] == "READ_ONLY"  # INF-U2-07
    assert config["importEnabled"] == "true"
    assert config["changedSyncPeriod"] == "900"  # cada 15 min
    # D2: lo que depende del LDAP del banco sale de `$(env:LDAP_*)`; lo demas, el valor por defecto de Keycloak.
    fixed = {"editMode", "importEnabled", "changedSyncPeriod", "connectionUrl"}
    for key, value in config.items():
        assert key in fixed or REFERENCE.match(value), key
    assert {"vendor", "usersDn", "usernameLDAPAttribute", "rdnLDAPAttribute", "uuidLDAPAttribute"} <= set(config)
    assert not {"cachePolicy", "fullSyncPeriod", "authType", "useTruststoreSpi", "priority"} & set(config)
    assert "subComponents" not in ldap  # D1: los mappers de grupo son de otra tarea
    for env in NON_PROD:
        assert "components" not in load(env)


def test_realm_files_group_role_map_is_not_part_of_this_task() -> None:
    assert not (REALM_DIR / "group-role-map.yaml").exists()  # D1


def test_realm_files_prod_realm_with_a_synthetic_user_is_rejected() -> None:
    prod = load("prod")
    prod["users"].append(next(u for u in load("kind")["users"] if u["username"] == "cro-1"))
    assert "usuario-local-en-prod" in {v.rule for v in lint_realm(prod, "prod")}


# --- sin secretos en claro (CA-3) ---------------------------------------------------------------

SECRET_KEYS = frozenset(
    {
        "secret", "password", "bindcredential", "clientsecret", "value", "seed", "privatekey",
        "certificate", "jwt.credential.certificate", "keystorepassword", "keypassword", "truststorepassword",
    }
)  # fmt: skip
JSON_STRING_KEYS = frozenset({"secretdata"})


def is_reference(value: Any) -> bool:
    """Una referencia es exactamente `$(env:NOMBRE)`: nada antes, nada despues."""
    if isinstance(value, list):
        return all(is_reference(v) for v in value)
    return isinstance(value, str) and REFERENCE.match(value) is not None


def literal_secrets(node: Any, path: str = "") -> list[str]:
    """Los campos de secreto con un valor que no es exactamente una referencia `$(env:NOMBRE)`."""
    found = []
    if isinstance(node, dict):
        for key, value in node.items():
            here, name = f"{path}.{key}", str(key).lower()
            if name in JSON_STRING_KEYS:
                try:
                    parsed = json.loads(value)
                except (TypeError, ValueError):
                    parsed = None
                if not (isinstance(parsed, dict) and parsed and all(is_reference(v) for v in parsed.values())):
                    found.append(here)
            elif name in SECRET_KEYS and not is_reference(value):
                found.append(here)
            else:
                found += literal_secrets(value, here)
    elif isinstance(node, list):
        for i, value in enumerate(node):
            found += literal_secrets(value, f"{path}[{i}]")
    return found


def test_realm_has_no_secret_values(env: str) -> None:
    assert literal_secrets(load(env)) == []
    text = (REALM_DIR / f"realm.{env}.yaml").read_text(encoding="utf-8")
    assert set(re.findall(r"\$\(\w+:", text)) <= {"$(env:"}
    assert not re.search(r"-----BEGIN", text)


def _kind_user(realm: dict[str, Any]) -> dict[str, Any]:
    return realm["users"][0]


@pytest.mark.parametrize(
    "mutation",
    [
        lambda r: _kind_user(r).__setitem__("credentials", [{"type": "password", "value": "Hunter2-Hunter2"}]),
        lambda r: _kind_user(r).__setitem__(
            "credentials", [{"type": "password", "value": "$(env:SYNTH_CRO_1_PASSWORD)Hunter2"}]
        ),
        lambda r: _kind_user(r).__setitem__(
            "credentials", [{"type": "otp", "secretData": '{"value":"JBSWY3DPEHPK3PXP"}'}]
        ),
        lambda r: _kind_user(r).__setitem__(
            "credentials", [{"type": "otp", "secretData": '{"value":"$(env:X_TOTP_SEED)JBSWY3DP"}'}]
        ),
        lambda r: r["clients"][0].__setitem__("secret", "s3cr3t"),
        lambda r: r["clients"][0].__setitem__("secret", "$(env:)"),
        lambda r: r.__setitem__("components", {"org.keycloak.keys.KeyProvider": [{"config": {"privateKey": ["MIIEvQ"]}}]}),
        lambda r: r.__setitem__("components", {"k": [{"config": {"certificate": ["MIICert"]}}]}),
    ],
)
def test_realm_has_no_secret_values_detector_fails_on_a_literal(mutation: Any) -> None:
    realm = load("kind")
    mutation(realm)
    assert literal_secrets(realm)


def test_realm_has_no_secret_values_detector_accepts_references() -> None:
    node = {
        "credentials": [
            {"type": "password", "value": "$(env:SYNTH_CRO_1_PASSWORD)"},
            {"type": "otp", "secretData": '{"value":"$(env:SYNTH_CRO_1_TOTP_SEED)"}'},
        ]
    }
    assert literal_secrets(node) == []
