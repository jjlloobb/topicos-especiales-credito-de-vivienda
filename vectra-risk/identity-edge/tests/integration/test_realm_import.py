"""El realm de Git, importado como lo importa kind, deja entrar a cada rol con su nivel (U02-T22).

Keycloak y keycloak-config-cli reales (`realm_stack.py`); el realm entra **sin editar** y nada repara lo que config-cli deje. Escenarios en serie, en el mismo contenedor:
los de lectura y login primero; la idempotencia y la migracion al final (borran y reimportan el realm).
"""

import re
import time
from typing import Any

import design_values as design
import pytest
import realm_stack as rs
import yaml
from vectra_contracts.routes import MFA_MAX_AGE

SYNTHETIC_PER_ROLE = {"analista": "analista-1", "ingeniero_riesgo": "ingeniero-1", "cro": "cro-1", "cumplimiento": "cumplimiento-1", "operacion": "operacion-1"}
OLD_ALIASES = {"loa-mfa", "amr-otp", "amr-hwk"}


def realm_yaml() -> dict[str, Any]:
    return dict(yaml.safe_load(rs.REALM_FILE.read_text(encoding="utf-8").replace("$(env:", "(env:")))


def expected_config_aliases() -> set[str]:
    return {c["alias"] for c in realm_yaml()["authenticatorConfig"]}


def login(stack: rs.Stack, username: str, **params: Any) -> tuple[rs.Login, rs.Step]:
    flow = rs.Login(stack)
    step = flow.login(username, stack.synth(username, "PASSWORD"), stack.synth(username, "TOTP_SEED"), **params)
    return flow, step


def tokens_of(stack: rs.Stack, username: str, **params: Any) -> dict[str, Any]:
    flow, step = login(stack, username, **params)
    try:
        code = step.code
        assert code, rs.explain_failed_login(stack, username, step)
        return flow.exchange(code)
    finally:
        flow.close()


# --- CA-6: cada ejecucion tiene su configuracion -------------------------------------------------------------------


def test_executions_have_their_authenticator_config(stack: rs.Stack) -> None:
    report = rs.read_links(stack, rs.REALM_FILE)
    rs.measure(f"ejecuciones tras importar {rs.REALM_FILE.name}: {report.summary()}")
    problems = report.unlinked + report.wrong + report.misaligned
    assert report.ok, f"{report.summary()}:\n  " + "\n  ".join(problems)


def test_required_actions_state(stack: rs.Stack) -> None:
    """P-2 (c): `VERIFY_PROFILE` declarada en el YAML y deshabilitada en Keycloak. Imprime el estado que dejo la importacion."""
    actions = rs.required_actions(stack)
    profile = actions.get("VERIFY_PROFILE")
    rs.measure(f"VERIFY_PROFILE tras importar: {({k: profile[k] for k in ('enabled', 'defaultAction', 'priority')} if profile else 'ausente')}")
    declared = next((a for a in realm_yaml()["requiredActions"] if a["alias"] == "VERIFY_PROFILE"), None)
    assert declared is not None, "el YAML no declara VERIFY_PROFILE"
    assert profile is not None and profile["enabled"] == declared["enabled"] is False, f"VERIFY_PROFILE en Keycloak: {profile}"


# --- CA-5: login por rol ---------------------------------------------------------------------------------------------


@pytest.mark.parametrize("role", sorted(SYNTHETIC_PER_ROLE))
def test_login_reaches_the_redirect_uri_with_its_level(stack: rs.Stack, role: str) -> None:
    username = SYNTHETIC_PER_ROLE[role]
    access = rs.claims(tokens_of(stack, username)["access_token"])
    rs.measure(f"{role}: acr={access.get('acr')} amr={access.get('amr')} roles={access.get('roles')} aud={access.get('aud')}")
    assert access["acr"] == "mfa"
    if role == "operacion":
        return  # `vectra-console` no tiene este rol en `scopeMappings`: lo que traiga `roles` se anota
    assert "otp" in access.get("amr", [])
    assert access["roles"] == [role]
    audience = access["aud"] if isinstance(access["aud"], list) else [access["aud"]]
    assert "console-bff" in audience
    assert not {"preferred_username", "email", "name"} & set(access)


# --- CA-7: step-up, TOTP reusado, fuerza bruta -----------------------------------------------------------------------


def test_stepup_reaches_acr_mfa_with_a_recent_auth_time(stack: rs.Stack) -> None:
    """BR-U2-04: `prompt=login`, `max_age=0` y `acr_values=mfa` hacia `/stepup-callback`."""
    flow, step = login(stack, "ingeniero-2", redirect_path="/stepup-callback", acr_values="mfa", prompt="login", max_age=0)
    try:
        assert step.code, rs.explain_failed_login(stack, "ingeniero-2", step)
        access = rs.claims(flow.exchange(step.code)["access_token"])
    finally:
        flow.close()
    assert access["acr"] == "mfa"
    assert time.time() - access["auth_time"] <= MFA_MAX_AGE
    assert {"mfa", "otp"} & set(access.get("amr", []))


def test_reused_totp_code_gives_no_authorization_code(stack: rs.Stack) -> None:
    username, seed = "cro-2", stack.synth("cro-2", "TOTP_SEED")
    first, step = login(stack, username)
    try:
        assert step.code, rs.explain_failed_login(stack, username, step)
    finally:
        first.close()
    used = rs._LAST_OTP[seed]
    second = rs.Login(stack)
    try:
        page = second.post(second.start(), {"username": username, "password": stack.synth(username, "PASSWORD")})
        assert 'name="otp"' in page.html, rs.page_text(page.html)
        again = second.post(page, {"otp": used})
    finally:
        second.close()
    assert again.code is None and again.location is None, "el mismo codigo TOTP dio un codigo de autorizacion"


def test_brute_force_locks_the_ephemeral_user_at_the_failure_factor(stack: rs.Stack) -> None:
    fields = stack.realm_representation()
    designed = design.brute_force_fields()
    assert len(designed) == 8
    assert {k: fields[k] for k in designed} == designed
    factor = int(designed["failureFactor"])
    # `quickLoginCheckMilliSeconds` no lo fija el realm: rige el de Keycloak (1000 ms); mas de eso entre fallos, o el bloqueo rapido (60 s) cuenta antes de tiempo.
    pause = fields.get("quickLoginCheckMilliSeconds", 1000) / 1000 + 0.5
    account = stack.create_user(f"u02t22-{rs.secrets.token_hex(3)}", rs.secrets.token_urlsafe(18), "analista")
    try:
        for attempt in range(1, factor + 1):
            flow = rs.Login(stack)
            try:
                step = flow.login(account.username, rs.secrets.token_urlsafe(18), None)
            finally:
                flow.close()
            assert step.code is None
            time.sleep(pause if attempt < factor else 1)
            status = stack.brute_force_status(account.user_id)
            deadline = time.time() + 10
            while attempt == factor and not status["disabled"] and time.time() < deadline:
                time.sleep(0.25)
                status = stack.brute_force_status(account.user_id)
            if attempt < factor:
                assert not status["disabled"], f"bloqueado en el fallo {attempt}, antes de {factor}: {status}"
        assert status["disabled"] and status["numFailures"] == factor, status
        assert status["numTemporaryLockouts"] == 1, status
        rs.measure(f"fuerza bruta: bloqueado en el fallo {factor}: {status}")
    finally:
        stack.delete_user(account.user_id)


# --- CA-8: idempotencia y migracion ------------------------------------------------------------------------------------


def _config_count(stack: rs.Stack) -> int:
    return len(stack.partial_export().get("authenticatorConfig", []))


def test_idempotent_second_import_leaves_the_same_state(stack: rs.Stack) -> None:
    before = rs.read_links(stack, rs.REALM_FILE)
    configs_before = _config_count(stack)
    log = stack.import_realm(rs.REALM_FILE)
    after = rs.read_links(stack, rs.REALM_FILE)
    configs_after = _config_count(stack)
    skipped = bool(re.search(r"checksum|no changes|unchanged", log, re.IGNORECASE))
    rs.measure(f"idempotencia: ejecuciones {before.summary()} -> {after.summary()}; authenticatorConfig en partial-export {configs_before} -> {configs_after}; config-cli omitio la segunda pasada por suma de control: {skipped}")
    rs.measure("idempotencia: lineas de la segunda pasada sobre la suma de control: " + " | ".join(ln[:160] for ln in log.splitlines() if re.search(r"checksum|no changes|unchanged", ln, re.IGNORECASE)))
    assert before.ok and after.ok, after.summary()
    assert configs_before == configs_after
    assert sorted(before.linked) == sorted(after.linked)


def test_migration_from_the_previous_realm_ends_with_every_execution_linked_and_a_working_login(stack: rs.Stack) -> None:
    stack.delete_realm()
    stack.import_realm(rs.OLD_REALM_FILE)
    old = rs.read_links(stack, rs.OLD_REALM_FILE)
    rs.measure(f"migracion, realm viejo importado: {old.summary()}")
    stack.import_realm(rs.REALM_FILE)
    new = rs.read_links(stack, rs.REALM_FILE)
    exported = {c["alias"] for c in stack.partial_export().get("authenticatorConfig", [])}
    orphans = sorted(exported - expected_config_aliases())
    rs.measure(f"migracion, realm corregido encima: {new.summary()}; configuraciones huerfanas: {len(orphans)} {orphans}; VERIFY_PROFILE: {rs.required_actions(stack).get('VERIFY_PROFILE', {}).get('enabled')}")
    assert new.ok, new.summary() + "\n  " + "\n  ".join(new.unlinked + new.wrong + new.misaligned)
    access = rs.claims(tokens_of(stack, "ingeniero-2")["access_token"])
    rs.measure(f"migracion: login de ingeniero-2: acr={access.get('acr')}")
    assert access["acr"] == "mfa"
