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
    REALM_PARAMETERS,
    TOTP_ACTION,
    lint_realm,
)
from vectra_contracts.catalog import SCOPE_HOLDERS, Role, Scope

REALM_DIR = Path(__file__).resolve().parents[2] / "keycloak" / "realm"
ENVS = ("kind", "staging", "prod")
SUBSTITUTION = re.compile(r"\$\(env:[A-Z][A-Z0-9_]*\)")
TECHNICAL_CLIENTS = tuple(ADMIN_CLIENT_ROLES)
MFA_ROLES = ("ingeniero_riesgo", "cro", "cumplimiento")


def load(env: str) -> dict[str, Any]:
    data = yaml.safe_load((REALM_DIR / f"realm.{env}.yaml").read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


@pytest.fixture(params=ENVS)
def env(request: pytest.FixtureRequest) -> str:
    return str(request.param)


def client_of(realm: dict[str, Any], client_id: str) -> dict[str, Any]:
    return next(c for c in realm["clients"] if c["clientId"] == client_id)


def audiences(client: dict[str, Any]) -> set[str]:
    return {
        m["config"]["included.custom.audience"]
        for m in client.get("protocolMappers", [])
        if m["protocolMapper"] == "oidc-audience-mapper"
    }


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
    for key, value in {**design.brute_force_fields(), **REALM_PARAMETERS}.items():
        assert realm[key] == value
        assert type(realm[key]) is type(value)
    assert realm["revokeRefreshToken"] is True  # BR-U2-06: rotacion
    assert realm["refreshTokenMaxReuse"] == 0  # reusar uno invalidado no se tolera
    assert json.loads(realm["attributes"]["acr.loa.map"]) == {"pwd": 1, "mfa": 2}
    assert realm["registrationAllowed"] is False
    assert realm["passwordPolicy"]


def test_realm_files_events_without_personal_data_in_the_realm_fields(env: str) -> None:
    realm = load(env)
    assert realm["eventsEnabled"] is True
    assert realm["eventsListeners"] == ["jboss-logging"]
    assert realm["adminEventsEnabled"] is True
    assert realm["adminEventsDetailsEnabled"] is False  # sin la representacion del recurso (BR-U2-16)


# --- login: OTP condicional por rol, TOTP y WebAuthn -----------------------------------------


def flow_by_alias(realm: dict[str, Any], alias: str) -> dict[str, Any]:
    return next(f for f in realm["authenticationFlows"] if f["alias"] == alias)


def test_realm_files_login_flow_has_conditional_otp_per_mfa_role(env: str) -> None:
    realm = load(env)
    assert realm["browserFlow"] == "vectra-browser"
    configs = {c["alias"]: c["config"] for c in realm["authenticatorConfig"]}
    forms = flow_by_alias(realm, "vectra-browser forms")
    subflows = [e for e in forms["authenticationExecutions"] if e.get("flowAlias")]
    covered = {}
    for sub in subflows:
        flow = flow_by_alias(realm, sub["flowAlias"])
        conds = [e for e in flow["authenticationExecutions"] if e.get("authenticator") == "conditional-user-role"]
        for cond in conds:
            conf = configs[cond["authenticatorConfig"]]
            assert conf["negate"] == "false"
            covered[conf["condUserRole"]] = sub
        assert sub["requirement"] == "CONDITIONAL"
    assert {*MFA_ROLES, OPERACION} <= set(covered)
    # El segundo factor es TOTP o WebAuthn (opcional como segundo metodo, BR-U2-03).
    factor = flow_by_alias(realm, "vectra-mfa-cro factor")
    assert {(e["authenticator"], e["requirement"]) for e in factor["authenticationExecutions"]} == {
        ("auth-otp-form", "ALTERNATIVE"),
        ("webauthn-authenticator", "ALTERNATIVE"),
    }


def test_realm_files_totp_and_webauthn_required_actions_are_enabled(env: str) -> None:
    actions = {a["alias"]: a for a in load(env)["requiredActions"]}
    for alias in (TOTP_ACTION, "webauthn-register"):
        assert actions[alias]["enabled"] is True
        assert actions[alias]["defaultAction"] is False


# --- clientes de usuario (domain-entities §2.1) ----------------------------------------------


def test_realm_files_user_clients_are_those_of_the_design(env: str) -> None:
    realm = load(env)
    host = design.hostnames()[env]
    ids = set(design.user_client_ids())
    assert ids == {"vectra-console", "promotion-tool", "grafana"}
    assert ids <= {c["clientId"] for c in realm["clients"]}

    console = client_of(realm, "vectra-console")
    assert console["publicClient"] is True
    assert console["standardFlowEnabled"] is True
    assert console["attributes"]["pkce.code.challenge.method"] == "S256"
    assert console["redirectUris"] == [f"https://{host}/callback", f"https://{host}/stepup-callback"]
    assert console["webOrigins"] == [f"https://{host}"]
    assert console["attributes"]["post.logout.redirect.uris"] == f"https://{host}/"
    assert audiences(console) == set(design.user_audiences())

    promotion = client_of(realm, "promotion-tool")
    assert promotion["publicClient"] is True
    assert promotion["attributes"]["pkce.code.challenge.method"] == "S256"
    assert promotion["redirectUris"] == ["http://127.0.0.1"]
    assert audiences(promotion) == {"governance-service"}
    assert promotion["optionalClientScopes"] == [Scope.GOVERNANCE_PROMOTION.value]
    assert promotion["defaultClientScopes"] == []

    grafana = client_of(realm, "grafana")
    assert grafana["publicClient"] is False
    assert grafana["clientAuthenticatorType"] == "client-jwt"
    assert "secret" not in grafana

    for client in (console, promotion, grafana):
        assert any(m["name"] == "roles" and m["config"]["claim.name"] == "roles" for m in client["protocolMappers"])


def test_realm_files_name_claim_is_only_in_the_id_token_of_the_console(env: str) -> None:
    for client in load(env)["clients"]:
        for mapper in client.get("protocolMappers", []):
            if mapper["protocolMapper"] == "oidc-full-name-mapper":
                assert client["clientId"] == "vectra-console"
                assert mapper["config"]["id.token.claim"] == "true"
                assert mapper["config"]["access.token.claim"] == "false"


def test_realm_files_promotion_scope_is_assignable_only_to_ingeniero_riesgo(env: str) -> None:
    realm = load(env)
    mappings = {m["clientScope"]: m["roles"] for m in realm["scopeMappings"] if "clientScope" in m}
    assert mappings[Scope.GOVERNANCE_PROMOTION.value] == ["ingeniero_riesgo"]
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
        assert audiences(client) == expected_audiences
        assert client["attributes"]["access.token.lifespan"] == "300"
        assert client["attributes"]["client_credentials.use_refresh_token"] == "false"  # noqa: S105


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
    for client_id in ("channel-simulator", "verification-reader"):
        assert (client_id in ids) == (env in NON_PROD)
    simulator = {c.client_id: c for c in design.service_clients()}["channel-simulator"]
    assert simulator.non_prod_only


def test_realm_files_verification_reader_and_product_metrics_have_exact_scopes(env: str) -> None:
    realm = load(env)
    if env in NON_PROD:
        reader = client_of(realm, "verification-reader")
        assert set(reader["optionalClientScopes"]) == {"registry:read:metrics", "registry:read:monitoring"}
    assert client_of(realm, "product-metrics")["optionalClientScopes"] == ["registry:read:metrics"]


def test_realm_files_case_service_cannot_get_a_core_token_in_production() -> None:
    prod = load("prod")
    case = client_of(prod, "case-service")
    assert Scope.CORE_READ_CREDIT.value not in obtainable_scopes(prod, case)
    assert "core-banking-mock" not in audiences(case)
    assert Scope.CORE_READ_CREDIT.value not in {s["name"] for s in prod["clientScopes"]}
    for env in NON_PROD:
        realm = load(env)
        case = client_of(realm, "case-service")
        assert Scope.CORE_READ_CREDIT.value in obtainable_scopes(realm, case)
        assert "core-banking-mock" in audiences(case)


def test_realm_files_no_client_has_keycloak_default_scopes(env: str) -> None:
    realm = load(env)
    assert realm["defaultDefaultClientScopes"] == []
    assert realm["defaultOptionalClientScopes"] == []
    for client in realm["clients"]:
        assert client["defaultClientScopes"] == []


def test_realm_files_access_token_has_no_personal_claims(env: str) -> None:
    for client in load(env)["clients"]:
        for mapper in client.get("protocolMappers", []):
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


def test_realm_files_synthetic_users_in_kind_and_staging() -> None:
    names = design.synthetic_usernames()
    assert len(names) == 10
    for env in NON_PROD:
        realm = load(env)
        locals_ = {u["username"]: u for u in realm["users"] if "serviceAccountClientId" not in u}
        assert set(locals_) == set(names)
        by_role: dict[str, int] = {}
        for user in locals_.values():
            roles = user["realmRoles"]
            assert len(roles) == 1
            by_role[roles[0]] = by_role.get(roles[0], 0) + 1
            assert (TOTP_ACTION in user["requiredActions"]) == (roles[0] in (*MFA_ROLES, OPERACION))
            kinds = {c["type"] for c in user["credentials"]}
            assert kinds == {"password", "otp"}
        assert by_role == {**dict.fromkeys((r.value for r in Role), 2), OPERACION: 2}
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
    assert config["connectionUrl"].startswith("ldaps://") and config["connectionUrl"].endswith(":636")
    assert config["editMode"] == "READ_ONLY"  # INF-U2-07
    assert config["importEnabled"] == "true"
    assert config["changedSyncPeriod"] == "900"  # cada 15 min
    assert config["cachePolicy"] == "NO_CACHE"
    assert config["useTruststoreSpi"] == "always"
    for env in NON_PROD:
        assert "components" not in load(env)


def test_realm_files_prod_realm_with_a_synthetic_user_is_rejected() -> None:
    prod = load("prod")
    prod["users"].append(next(u for u in load("kind")["users"] if u["username"] == "cro-1"))
    assert "usuario-local-en-prod" in {v.rule for v in lint_realm(prod, "prod")}


# --- sin secretos en claro (CA-3) ---------------------------------------------------------------

SECRET_KEYS = frozenset({"secret", "password", "secretdata", "bindcredential", "clientsecret", "value", "seed"})


def literal_secrets(node: Any, path: str = "") -> list[str]:
    """Los campos de secreto con un valor que no es una referencia `$(env:NOMBRE)`."""
    found = []
    if isinstance(node, dict):
        for key, value in node.items():
            here = f"{path}.{key}"
            if str(key).lower() in SECRET_KEYS and not _is_reference(value):
                found.append(here)
            else:
                found += literal_secrets(value, here)
    elif isinstance(node, list):
        for i, value in enumerate(node):
            found += literal_secrets(value, f"{path}[{i}]")
    return found


def _is_reference(value: Any) -> bool:
    if isinstance(value, list):
        return all(_is_reference(v) for v in value)
    if not isinstance(value, str):
        return False
    return bool(SUBSTITUTION.search(value)) and not re.search(r"[A-Za-z0-9+/=]{16,}", SUBSTITUTION.sub("", value))


def test_realm_has_no_secret_values(env: str) -> None:
    assert literal_secrets(load(env)) == []
    text = (REALM_DIR / f"realm.{env}.yaml").read_text(encoding="utf-8")
    assert set(re.findall(r"\$\(\w+:", text)) <= {"$(env:"}


@pytest.mark.parametrize(
    "mutation",
    [
        lambda r: r["users"][0].__setitem__("credentials", [{"type": "password", "value": "Hunter2-Hunter2"}]),
        lambda r: r["users"][0].__setitem__(
            "credentials", [{"type": "otp", "secretData": '{"value":"JBSWY3DPEHPK3PXP"}'}]
        ),
        lambda r: r["clients"][0].__setitem__("secret", "s3cr3t"),
        lambda r: r["clients"][0].__setitem__("secret", "$(env:)"),
    ],
)
def test_realm_has_no_secret_values_detector_fails_on_a_literal(mutation: Any) -> None:
    realm = load("kind")
    mutation(realm)
    assert literal_secrets(realm)


def test_realm_has_no_secret_values_detector_accepts_references() -> None:
    assert literal_secrets({"credentials": [{"type": "password", "value": "$(env:SYNTH_CRO_1_PASSWORD)"}]}) == []
