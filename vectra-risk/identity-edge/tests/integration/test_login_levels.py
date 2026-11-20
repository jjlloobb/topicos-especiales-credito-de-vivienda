"""Los niveles de autenticacion del realm con el Keycloak real: descubrimiento y segundo login con sesion abierta (U02-T27).

Keycloak 26.8.1 arma una tabla nivel -> vigencia con las condiciones `conditional-level-of-authentication` del flujo y falla con `Duplicate key 2` si dos
declaran el mismo nivel. Estas pruebas leen el flujo tal como lo dejo la importacion (el fixture `stack` de `conftest.py`), sin repararlo.
"""

import secrets
from typing import Any

import pytest
import realm_stack as rs
from test_realm_import import SYNTHETIC_PER_ROLE, login

MFA_ROLES = sorted(SYNTHETIC_PER_ROLE)


def _no_level_table_error(stack: rs.Stack) -> list[str]:
    return [ln.strip()[:300] for ln in stack.keycloak_log_lines("Duplicate key")]


def test_discovery_answers_200_with_the_levels_of_the_realm(stack: rs.Stack) -> None:
    http = stack.client()
    try:
        response = http.get(f"/auth/realms/{rs.REALM}/.well-known/openid-configuration")
    finally:
        http.close()
    assert response.status_code == 200, f"HTTP {response.status_code}; log: {_no_level_table_error(stack)[-1:]}"
    document = response.json()
    assert document["issuer"].endswith(f"/realms/{rs.REALM}")
    # Keycloak anade los niveles numericos (0 de la cookie SSO, 1 y 2 del flujo) a los nombres de `acr.loa.map`.
    assert {"pwd", "mfa"} <= set(document["acr_values_supported"]), document.get("acr_values_supported")
    assert set(document["acr_values_supported"]) <= {"pwd", "mfa", "0", "1", "2"}, document["acr_values_supported"]
    assert "S256" in document["code_challenge_methods_supported"]


@pytest.mark.parametrize("role", MFA_ROLES)
def test_loa_login_with_an_open_session_does_not_break_keycloak(stack: rs.Stack, role: str) -> None:
    """Volver a entrar con la cookie del primer login (el `sesion_abierta` de la tarea): llega al `redirect_uri` con el nivel `mfa` y sin repetir el TOTP."""
    username = SYNTHETIC_PER_ROLE[role]
    flow, first = login(stack, username)
    try:
        assert first.code, rs.explain_failed_login(stack, username, first)
        again = flow.start()
        text = rs.page_text(again.html)
        assert again.code, f"el segundo login con sesion abierta no llego al redirect_uri: HTTP {again.status}, pagina: «{text}»; log: {_no_level_table_error(stack)[-1:]}"
        access = rs.claims(flow.exchange(again.code)["access_token"])
        assert access["acr"] == "mfa"
        assert "otp" in access.get("amr", []) or role == "operacion"
    finally:
        flow.close()


def test_loa_open_session_with_acr_values_mfa_is_not_asked_for_the_totp_again(stack: rs.Stack) -> None:
    """Con la sesion abierta en nivel `mfa` y vigente, pedir `acr_values=mfa` (sin `prompt`) se satisface con la cookie."""
    username = "cumplimiento-2"
    flow, first = login(stack, username)
    try:
        assert first.code, rs.explain_failed_login(stack, username, first)
        again = flow.start(acr_values="mfa")
        assert again.code, f"HTTP {again.status}: «{rs.page_text(again.html)}»; log: {_no_level_table_error(stack)[-1:]}"
        assert rs.claims(flow.exchange(again.code)["access_token"])["acr"] == "mfa"
    finally:
        flow.close()


@pytest.mark.parametrize("role", MFA_ROLES)
def test_loa_a_role_with_mandatory_mfa_does_not_get_a_code_without_the_totp(stack: rs.Stack, role: str) -> None:
    username = SYNTHETIC_PER_ROLE[role]
    flow = rs.Login(stack)
    try:
        page = flow.post(flow.start(), {"username": username, "password": stack.synth(username, "PASSWORD")})
        assert page.code is None and page.location is None, f"{username} obtuvo un codigo con solo la contrasena"
        assert 'name="otp"' in page.html, rs.page_text(page.html)
    finally:
        flow.close()


def test_loa_a_wrong_totp_gives_no_code(stack: rs.Stack) -> None:
    username = "ingeniero-2"
    flow = rs.Login(stack)
    try:
        page = flow.post(flow.start(), {"username": username, "password": stack.synth(username, "PASSWORD")})
        assert 'name="otp"' in page.html
        wrong = flow.post(page, {"otp": "000000"})
        assert wrong.code is None and wrong.location is None
    finally:
        flow.close()


def test_loa_break_glass_without_a_totp_does_not_get_a_code(stack: rs.Stack) -> None:
    """`break-glass` es el rol de cliente `realm-management.realm-admin` (`cond-role-break-glass`): sin segundo factor no hay codigo."""
    password = secrets.token_urlsafe(18)
    account = stack.create_user(f"u02t27-{secrets.token_hex(3)}", password, "analista")
    try:
        # un usuario con el rol de cliente `realm-admin` y ningun factor registrado
        clients = stack.admin("GET", "/clients", params={"clientId": "realm-management"}).json()
        client_id = clients[0]["id"]
        role = stack.admin("GET", f"/clients/{client_id}/roles/realm-admin").json()
        assert stack.admin("POST", f"/users/{account.user_id}/role-mappings/clients/{client_id}", json=[role]).status_code == 204
        assert stack.admin("DELETE", f"/users/{account.user_id}/role-mappings/realm", json=[stack.admin("GET", "/roles/analista").json()]).status_code == 204
        flow = rs.Login(stack)
        try:
            step = flow.post(flow.start(), {"username": account.username, "password": password})
            assert step.code is None and step.location is None, "un usuario con realm-admin y sin factor obtuvo un codigo"
        finally:
            flow.close()
    finally:
        stack.delete_user(account.user_id)


def test_loa_a_user_without_any_mfa_role_logs_in_with_the_password_only(stack: rs.Stack) -> None:
    """Sin ninguno de los roles con MFA el flujo de nivel 2 no corre: entra con la contrasena y el token queda en el nivel `pwd`, como antes."""
    password = secrets.token_urlsafe(18)
    account = stack.create_user(f"u02t27-{secrets.token_hex(3)}", password, "analista")
    try:
        assert stack.admin("DELETE", f"/users/{account.user_id}/role-mappings/realm", json=[stack.admin("GET", "/roles/analista").json()]).status_code == 204
        flow = rs.Login(stack)
        try:
            step = flow.post(flow.start(), {"username": account.username, "password": password})
            assert step.code, f"HTTP {step.status}: «{rs.page_text(step.html)}»; log: {_no_level_table_error(stack)[-1:]}"
            access: dict[str, Any] = rs.claims(flow.exchange(step.code)["access_token"])
            assert access["acr"] == "pwd", access.get("acr")
            assert "otp" not in access.get("amr", [])
            again = flow.start()  # con la sesion abierta (nivel pwd): tampoco rompe Keycloak
            assert again.code, f"HTTP {again.status}: «{rs.page_text(again.html)}»; log: {_no_level_table_error(stack)[-1:]}"
        finally:
            flow.close()
    finally:
        stack.delete_user(account.user_id)


def test_loa_an_analyst_without_a_factor_does_not_enter_today(stack: rs.Stack) -> None:
    """Estado conocido, no deseado (CANDIDATAS.md, U02-T22): BR-U2-03 dice que el MFA del `analista` es opcional, pero el realm se lo pide siempre (`conditional-user-configured`
    sobre un subflujo no filtra) y sin factor no entra. U02-T27 no lo cambia; quien lo arregle cambia esta prueba."""
    password = secrets.token_urlsafe(18)
    account = stack.create_user(f"u02t27-{secrets.token_hex(3)}", password, "analista")
    try:
        flow = rs.Login(stack)
        try:
            step = flow.post(flow.start(), {"username": account.username, "password": password})
            assert step.code is None and step.location is None, "un analista sin factor obtuvo un codigo: el defecto se arreglo, actualiza esta prueba y la candidata"
        finally:
            flow.close()
    finally:
        stack.delete_user(account.user_id)
