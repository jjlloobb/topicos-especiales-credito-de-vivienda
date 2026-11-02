"""Casos nombrados de `realm-lint` (Pasos 2 y 3 del plan de U2; BR-U2-01, 03, 09, 15; AUTONOMIA-03)."""

import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml
from realm_builders import find_client, find_user, realm_copy, user
from realm_lint import lint_group_role_map, lint_realm, resolve_ldap_role

TOOL = Path(__file__).resolve().parents[2] / "tools" / "realm_lint.py"


def rules(realm: dict[str, Any], env: str) -> set[str]:
    return {v.rule for v in lint_realm(realm, env)}


def scopes_of(client: dict[str, Any]) -> list[str]:
    return client["optionalClientScopes"]


# --- el realm de ejemplo es valido -----------------------------------------------------------


@pytest.mark.parametrize("env", ["kind", "staging", "prod"])
def test_valid_realm_is_accepted(env: str) -> None:
    assert lint_realm(realm_copy(env), env) == []


# --- BR-U2-01: un rol de negocio por usuario -------------------------------------------------


def test_user_with_two_roles_is_rejected() -> None:
    realm = realm_copy("kind")
    realm["users"].append(user("doble-1", ["analista", "cro"]))
    assert "un-rol-de-negocio" in rules(realm, "kind")


def test_user_with_one_role_is_accepted() -> None:
    realm = realm_copy("kind")
    realm["users"].append(user("solo-1", ["cumplimiento"]))
    assert lint_realm(realm, "kind") == []


# --- MFA por rol (BR-U2-03) y el rol tecnico `operacion` -------------------------------------


@pytest.mark.parametrize("role", ["ingeniero_riesgo", "cro", "cumplimiento"])
def test_approver_without_totp_is_rejected(role: str) -> None:
    realm = realm_copy("kind")
    realm["users"].append(user("sin-mfa-1", [role], totp=False))
    assert "mfa-obligatorio" in rules(realm, "kind")


def test_analista_without_totp_is_accepted() -> None:
    realm = realm_copy("kind")
    realm["users"].append(user("analista-3", ["analista"], totp=False))
    assert lint_realm(realm, "kind") == []


def test_operacion_without_required_totp_action_is_rejected() -> None:
    realm = realm_copy("kind")
    find_user(realm, "operacion-1")["requiredActions"] = []
    assert "mfa-obligatorio" in rules(realm, "kind")


def test_operacion_with_business_role_cro_is_rejected() -> None:
    realm = realm_copy("kind")
    realm["users"].append(user("mixto-1", ["operacion", "cro"]))
    assert "operacion-con-rol-de-negocio" in rules(realm, "kind")


def test_operacion_with_totp_required_is_accepted() -> None:
    realm = realm_copy("staging")
    assert find_user(realm, "operacion-1")["requiredActions"] == ["CONFIGURE_TOTP"]
    assert lint_realm(realm, "staging") == []


# --- usuarios locales por entorno -----------------------------------------------------------


def test_break_glass_alone_in_prod_is_accepted() -> None:
    realm = realm_copy("prod")
    assert [u["username"] for u in realm["users"]] == ["break-glass"]
    assert lint_realm(realm, "prod") == []


def test_break_glass_without_totp_is_rejected() -> None:
    realm = realm_copy("prod")
    find_user(realm, "break-glass")["requiredActions"] = []
    assert "mfa-obligatorio" in rules(realm, "prod")


def test_cro_1_in_prod_realm_is_rejected_by_break_glass_rule() -> None:
    realm = realm_copy("prod")
    realm["users"].append(user("cro-1", ["cro"]))
    violations = [v for v in lint_realm(realm, "prod") if v.rule == "usuario-local-en-prod"]
    assert violations
    assert "cro-1" in violations[0].where


def test_break_glass_rule_does_not_apply_to_synthetic_users_in_staging() -> None:
    assert lint_realm(realm_copy("staging"), "staging") == []


# --- scopes (AUTONOMIA-03) ------------------------------------------------------------------


def test_service_with_core_write_credit_is_rejected() -> None:
    realm = realm_copy("kind")
    scopes_of(find_client(realm, "case-service")).append("core:write-credit")
    assert "core-write-credit-prohibido" in rules(realm, "kind")


def test_scope_outside_the_u0_catalog_is_rejected() -> None:
    realm = realm_copy("kind")
    scopes_of(find_client(realm, "case-service")).append("registry:append:caso")
    assert "scope-fuera-del-catalogo" in rules(realm, "kind")


@pytest.mark.parametrize("scope", ["openid", "offline_access", "web-origins", "roles", "acr", "microprofile-jwt"])
def test_keycloak_own_scopes_are_outside_the_catalog_and_rejected(scope: str) -> None:
    realm = realm_copy("kind")
    find_client(realm, "vectra-console")["defaultClientScopes"].append(scope)
    assert "scope-fuera-del-catalogo" in rules(realm, "kind")


def test_service_other_than_bias_monitoring_job_with_governance_freeze_is_rejected() -> None:
    realm = realm_copy("kind")
    scopes_of(find_client(realm, "bias-monitoring-service")).append("governance:freeze")
    violations = [v for v in lint_realm(realm, "kind") if v.rule == "governance-freeze-solo-en-el-job"]
    assert violations
    assert "bias-monitoring-service" in violations[0].message


def test_bias_monitoring_job_with_governance_freeze_is_accepted() -> None:
    realm = realm_copy("kind")
    assert "governance:freeze" in scopes_of(find_client(realm, "bias-monitoring-job"))
    assert lint_realm(realm, "kind") == []


# --- core en produccion (U8 INF-U8-02) ------------------------------------------------------


def test_case_service_core_read_credit_in_prod_is_rejected() -> None:
    realm = realm_copy("prod")
    scopes_of(find_client(realm, "case-service")).append("core:read-credit")
    assert "case-service-core-en-prod" in rules(realm, "prod")


def test_case_service_core_banking_mock_audience_in_prod_is_rejected() -> None:
    realm = realm_copy("prod")
    find_client(realm, "case-service")["protocolMappers"].append(
        {
            "name": "aud-core",
            "protocol": "openid-connect",
            "protocolMapper": "oidc-audience-mapper",
            "config": {"included.client.audience": "core-banking-mock", "access.token.claim": "true"},
        }
    )
    assert "case-service-core-en-prod" in rules(realm, "prod")


def test_case_service_core_read_credit_in_staging_is_accepted() -> None:
    realm = realm_copy("staging")
    case_service = find_client(realm, "case-service")
    assert "core:read-credit" in scopes_of(case_service)
    assert any(m["config"]["included.client.audience"] == "core-banking-mock" for m in case_service["protocolMappers"])
    assert lint_realm(realm, "staging") == []


def test_case_service_without_core_in_prod_is_accepted() -> None:
    realm = realm_copy("prod")
    assert "core:read-credit" not in scopes_of(find_client(realm, "case-service"))
    assert lint_realm(realm, "prod") == []


# --- clientes que no existen en produccion --------------------------------------------------


def test_channel_simulator_in_prod_is_rejected() -> None:
    realm = realm_copy("prod")
    realm["clients"] = [*realm["clients"], find_client(realm_copy("kind"), "channel-simulator")]
    violations = [v for v in lint_realm(realm, "prod") if v.rule == "cliente-solo-no-productivo"]
    assert [v.where for v in violations] == ["cliente channel-simulator"]


def test_channel_simulator_in_kind_and_staging_is_accepted() -> None:
    for env in ("kind", "staging"):
        realm = realm_copy(env)
        assert find_client(realm, "channel-simulator")
        assert lint_realm(realm, env) == []


def test_verification_reader_in_prod_is_rejected() -> None:
    realm = realm_copy("prod")
    realm["clients"] = [*realm["clients"], find_client(realm_copy("kind"), "verification-reader")]
    violations = [v for v in lint_realm(realm, "prod") if v.rule == "cliente-solo-no-productivo"]
    assert any("verification-reader" in v.message for v in violations)


def test_verification_reader_with_other_scope_is_rejected() -> None:
    realm = realm_copy("kind")
    scopes_of(find_client(realm, "verification-reader")).append("registry:append:case")
    assert "scopes-exactos" in rules(realm, "kind")


def test_verification_reader_missing_one_scope_is_rejected() -> None:
    realm = realm_copy("kind")
    scopes_of(find_client(realm, "verification-reader")).remove("registry:read:monitoring")
    assert "scopes-exactos" in rules(realm, "kind")


def test_verification_reader_in_kind_with_its_two_scopes_is_accepted() -> None:
    realm = realm_copy("kind")
    assert sorted(scopes_of(find_client(realm, "verification-reader"))) == [
        "registry:read:metrics",
        "registry:read:monitoring",
    ]
    assert lint_realm(realm, "kind") == []


def test_product_metrics_with_an_extra_scope_is_rejected() -> None:
    realm = realm_copy("kind")
    scopes_of(find_client(realm, "product-metrics")).append("registry:read:monitoring")
    assert "scopes-exactos" in rules(realm, "kind")


def test_product_metrics_with_only_its_scope_is_accepted() -> None:
    realm = realm_copy("prod")
    assert scopes_of(find_client(realm, "product-metrics")) == ["registry:read:metrics"]
    assert lint_realm(realm, "prod") == []


# --- clientes de servicio (BR-U2-09) --------------------------------------------------------


def test_service_with_shared_secret_is_rejected() -> None:
    realm = realm_copy("kind")
    find_client(realm, "case-worker")["secret"] = "algo"  # noqa: S105
    assert "cliente-con-secreto" in rules(realm, "kind")


def test_user_app_with_secret_is_not_a_service_rule() -> None:
    realm = realm_copy("kind")
    find_client(realm, "vectra-console")["secret"] = "algo"  # noqa: S105
    assert "cliente-con-secreto" not in rules(realm, "kind")


def test_break_glass_with_realm_admin_of_realm_management_and_no_totp_is_rejected() -> None:
    realm = realm_copy("prod")
    broken = find_user(realm, "break-glass")
    assert broken["clientRoles"] == {"realm-management": ["realm-admin"]}
    broken["requiredActions"] = []
    assert "mfa-obligatorio" in rules(realm, "prod")


def service_account(username: str, target: str, **extra: Any) -> dict[str, Any]:
    return {"username": username, "serviceAccountClientId": target, "enabled": True, **extra}


def test_real_service_account_user_is_not_a_local_user_in_prod() -> None:
    realm = realm_copy("prod")
    realm["users"].append(service_account("service-account-case-worker", "case-worker"))
    assert lint_realm(realm, "prod") == []


def test_config_applier_service_account_with_realm_admin_needs_no_totp_in_prod() -> None:
    realm = realm_copy("prod")
    realm["users"].append(
        service_account(
            "service-account-case-worker",
            "case-worker",
            clientRoles={"realm-management": ["realm-admin"]},
            requiredActions=[],
        )
    )
    assert lint_realm(realm, "prod") == []


def test_service_account_prefix_alone_does_not_exempt_a_user_in_prod() -> None:
    realm = realm_copy("prod")
    realm["users"].append({"username": "service-account-x", "realmRoles": ["cro"], "requiredActions": []})
    assert {"usuario-local-en-prod", "mfa-obligatorio"} <= rules(realm, "prod")


def test_service_account_pointing_to_a_missing_app_does_not_exempt_a_user_in_prod() -> None:
    realm = realm_copy("prod")
    realm["users"].append(service_account("jdoe", "no-existe", realmRoles=["cro"]))
    assert {"usuario-local-en-prod", "mfa-obligatorio"} <= rules(realm, "prod")


def test_service_account_pointing_to_a_non_service_app_does_not_exempt_a_user_in_prod() -> None:
    realm = realm_copy("prod")
    realm["users"].append(service_account("service-account-vectra-console", "vectra-console"))
    assert "usuario-local-en-prod" in rules(realm, "prod")


def test_service_account_with_a_user_role_does_not_exempt_it_in_prod() -> None:
    realm = realm_copy("prod")
    realm["users"].append(service_account("service-account-case-worker", "case-worker", realmRoles=["cro"]))
    assert {"usuario-local-en-prod", "mfa-obligatorio"} <= rules(realm, "prod")


@pytest.mark.parametrize("field", ["defaultClientScopes", "optionalClientScopes"], ids=["default", "optional"])
def test_app_without_explicit_scope_lists_is_rejected(field: str) -> None:
    realm = realm_copy("kind")
    del find_client(realm, "case-worker")[field]
    assert "scopes-por-defecto-heredados" in rules(realm, "kind")


def test_service_without_private_key_jwt_is_rejected() -> None:
    realm = realm_copy("kind")
    find_client(realm, "case-worker")["clientAuthenticatorType"] = "client-secret"
    assert "servicio-sin-private-key-jwt" in rules(realm, "kind")


@pytest.mark.parametrize("app", ["vectra-console", "promotion-tool", "grafana"])
def test_wildcard_redirect_uri_is_rejected(app: str) -> None:
    realm = realm_copy("kind")
    find_client(realm, app)["redirectUris"].append("https://vectra.example.org/*")
    assert "redirect-uri-con-comodin" in rules(realm, "kind")


def test_wildcard_post_logout_redirect_uri_is_rejected() -> None:
    realm = realm_copy("kind")
    find_client(realm, "vectra-console")["attributes"]["post.logout.redirect.uris"] = "https://vectra.example.org/*"
    assert "redirect-uri-con-comodin" in rules(realm, "kind")


def test_exact_redirect_uris_are_accepted() -> None:
    assert lint_realm(realm_copy("kind"), "kind") == []


# --- claims prohibidos en el access token --------------------------------------------------


@pytest.mark.parametrize("claim", ["preferred_username", "email", "name"])
def test_forbidden_claim_in_access_token_is_rejected(claim: str) -> None:
    realm = realm_copy("kind")
    find_client(realm, "vectra-console")["protocolMappers"].append(
        {
            "name": f"leak-{claim}",
            "protocol": "openid-connect",
            "protocolMapper": "oidc-usermodel-property-mapper",
            "config": {"claim.name": claim, "access.token.claim": "true"},
        }
    )
    assert "claim-prohibido-en-access-token" in rules(realm, "kind")


def test_forbidden_claim_only_in_id_token_is_accepted() -> None:
    realm = realm_copy("kind")
    mapper = next(m for m in find_client(realm, "vectra-console")["protocolMappers"] if m["name"] == "name-id-token")
    assert mapper["config"]["claim.name"] == "name"
    assert lint_realm(realm, "kind") == []


@pytest.mark.parametrize("scope", ["profile", "email"])
def test_profile_and_email_scopes_are_rejected_as_outside_the_catalog_even_if_redefined(scope: str) -> None:
    realm = realm_copy("kind")
    find_client(realm, "vectra-console")["defaultClientScopes"].append(scope)
    realm["clientScopes"] = [{"name": scope, "protocol": "openid-connect", "protocolMappers": []}]
    assert "scope-fuera-del-catalogo" in rules(realm, "kind")


def test_scope_mapper_with_forbidden_claim_is_rejected() -> None:
    realm = realm_copy("kind")
    realm["clientScopes"] = [
        {
            "name": "profile",
            "protocolMappers": [{"name": "u", "protocolMapper": "x", "config": {"claim.name": "email"}}],
        }
    ]
    assert "claim-prohibido-en-access-token" in rules(realm, "kind")


# --- parametros versionados (domain-entities §6) y contrasenas (NFR-U2-24) -----------------


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("accessTokenLifespan", 600),
        ("ssoSessionIdleTimeout", 3600),
        ("ssoSessionMaxLifespan", 72000),
        ("bruteForceProtected", False),
        ("failureFactor", 10),
        ("waitIncrementSeconds", 30),
        ("maxFailureWaitSeconds", 1800),
        ("maxDeltaTimeSeconds", 3600),
        ("permanentLockout", False),
        ("maxTemporaryLockouts", 10),
        # Igual en valor pero de otro tipo: `1 == True` y `5.0 == 5` en Python.
        ("bruteForceProtected", 1),
        ("permanentLockout", 1),
        ("failureFactor", 5.0),
        ("failureFactor", "5"),
    ],
)
def test_realm_parameter_out_of_spec_is_rejected(key: str, value: object) -> None:
    realm = realm_copy("kind")
    realm[key] = value
    assert "parametro-del-realm" in rules(realm, "kind")


@pytest.mark.parametrize("key", ["accessTokenLifespan", "failureFactor", "permanentLockout"])
def test_missing_realm_parameter_is_rejected(key: str) -> None:
    realm = realm_copy("kind")
    del realm[key]
    assert "parametro-del-realm" in rules(realm, "kind")


def test_brute_force_fields_are_exactly_those_of_br_u2_05() -> None:
    realm = realm_copy("kind")
    assert {k: realm[k] for k in ("bruteForceProtected", "permanentLockout", "maxTemporaryLockouts", "failureFactor", "waitIncrementSeconds", "maxFailureWaitSeconds", "maxDeltaTimeSeconds")} == {
        "bruteForceProtected": True,
        "permanentLockout": True,
        "maxTemporaryLockouts": 3,
        "failureFactor": 5,
        "waitIncrementSeconds": 60,
        "maxFailureWaitSeconds": 900,
        "maxDeltaTimeSeconds": 43200,
    }
    assert lint_realm(realm, "kind") == []


@pytest.mark.parametrize(
    "policy",
    [
        None,
        "length(8) and notUsername and notEmail and passwordHistory(5) and hashAlgorithm(argon2)",
        "length(14) and notEmail and passwordHistory(5) and hashAlgorithm(argon2)",
        "length(14) and notUsername and passwordHistory(5) and hashAlgorithm(argon2)",
        "length(14) and notUsername and notEmail and passwordHistory(3) and hashAlgorithm(argon2)",
        "length(14) and notUsername and notEmail and passwordHistory(5) and hashAlgorithm(pbkdf2-sha512)",
        "length(14) and notUsername and notEmail and passwordHistory(5) and hashAlgorithm(argon2) and forceExpiredPasswordChange(90)",
    ],
)
def test_weak_password_policy_is_rejected(policy: str | None) -> None:
    realm = realm_copy("kind")
    if policy is None:
        del realm["passwordPolicy"]
    else:
        realm["passwordPolicy"] = policy
    assert "politica-de-contrasenas" in rules(realm, "kind")


def test_stronger_password_policy_is_accepted() -> None:
    realm = realm_copy("kind")
    realm["passwordPolicy"] = "length(20) and notUsername and notEmail and passwordHistory(8) and hashAlgorithm(argon2)"
    assert lint_realm(realm, "kind") == []


# --- group-role-map (BR-U2-15) -------------------------------------------------------------


def test_group_role_map_with_valid_roles_is_accepted() -> None:
    mapping = {"groups": {"cn=analistas,ou=g": "analista", "cn=ops,ou=g": "operacion", "cn=cro,ou=g": "cro"}}
    assert lint_group_role_map(mapping) == []


def test_group_role_map_with_unknown_role_is_rejected() -> None:
    violations = lint_group_role_map({"groups": {"cn=x,ou=g": "superusuario"}})
    assert [v.rule for v in violations] == ["group-role-map-invalido"]


def test_group_role_map_with_realm_admin_is_rejected() -> None:
    # `realm-admin` es solo de break-glass y del keycloak-config-cli: nunca sale de LDAP.
    assert lint_group_role_map({"groups": {"cn=x,ou=g": "realm-admin"}})


@pytest.mark.parametrize("bad", [{}, {"groups": []}, {"groups": {"": "cro"}}, [], "x"])
def test_malformed_group_role_map_is_rejected(bad: object) -> None:
    assert lint_group_role_map(bad)


# --- CLI ------------------------------------------------------------------------------------


def run_cli(*paths: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        [sys.executable, str(TOOL), *map(str, paths)], capture_output=True, text=True, check=False
    )


def write_realm(directory: Path, env: str, realm: dict[str, Any]) -> Path:
    path = directory / f"realm.{env}.yaml"
    path.write_text(yaml.safe_dump(realm, sort_keys=False), encoding="utf-8")
    return path


def test_cli_exits_zero_on_valid_realms(tmp_path: Path) -> None:
    paths = [write_realm(tmp_path, env, realm_copy(env)) for env in ("kind", "staging", "prod")]
    result = run_cli(*paths)
    assert result.returncode == 0, result.stdout + result.stderr


def test_cli_exits_nonzero_naming_file_and_rule_on_invalid_realm(tmp_path: Path) -> None:
    (tmp_path / "ok").mkdir()
    (tmp_path / "bad").mkdir()
    valid = write_realm(tmp_path / "ok", "kind", realm_copy("kind"))
    bad_realm = realm_copy("prod")
    bad_realm["users"].append(user("cro-1", ["cro"]))
    bad = write_realm(tmp_path / "bad", "prod", bad_realm)
    result = run_cli(valid, bad)
    assert result.returncode != 0
    output = result.stdout + result.stderr
    assert str(bad) in output
    assert "usuario-local-en-prod" in output
    assert str(valid) not in output


def test_cli_reports_every_violation_not_only_the_first(tmp_path: Path) -> None:
    realm = realm_copy("kind")
    realm["users"].append(user("doble-1", ["analista", "cro"]))
    scopes_of(find_client(realm, "case-service")).append("core:write-credit")
    result = run_cli(write_realm(tmp_path, "kind", realm))
    assert result.returncode != 0
    assert "un-rol-de-negocio" in result.stdout + result.stderr
    assert "core-write-credit-prohibido" in result.stdout + result.stderr


def test_cli_lints_group_role_map_by_file_name(tmp_path: Path) -> None:
    good = tmp_path / "group-role-map.yaml"
    good.write_text(yaml.safe_dump({"groups": {"cn=a,ou=g": "analista"}}), encoding="utf-8")
    assert run_cli(good).returncode == 0
    good.write_text(yaml.safe_dump({"groups": {"cn=a,ou=g": "nadie"}}), encoding="utf-8")
    result = run_cli(good)
    assert result.returncode != 0
    assert "group-role-map-invalido" in result.stdout + result.stderr


def test_cli_rejects_unknown_environment_in_file_name(tmp_path: Path) -> None:
    path = tmp_path / "realm.dev.yaml"
    path.write_text(yaml.safe_dump(realm_copy("kind")), encoding="utf-8")
    result = run_cli(path)
    assert result.returncode != 0
    assert "entorno" in result.stdout + result.stderr


def test_cli_fails_on_missing_file_and_on_invalid_yaml(tmp_path: Path) -> None:
    assert run_cli(tmp_path / "realm.kind.yaml").returncode != 0
    broken = tmp_path / "realm.kind.yaml"
    broken.write_text("users: [unclosed", encoding="utf-8")
    assert run_cli(broken).returncode != 0


def test_cli_without_arguments_is_a_usage_error() -> None:
    assert run_cli().returncode != 0


def test_resolve_ldap_role_uses_the_same_validation_as_the_table_lint() -> None:
    bad = {"cn=x,ou=g": "superusuario"}
    assert lint_group_role_map({"groups": bad})
    with pytest.raises(ValueError, match="superusuario"):
        resolve_ldap_role(["cn=x,ou=g"], bad)
