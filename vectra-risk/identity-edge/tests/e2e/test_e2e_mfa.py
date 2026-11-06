"""MFA del aprobador (US-601; BR-U2-03, BR-U2-04): aprobador sin TOTP y step-up sin SPA. Se ejecutan en el Paso 16."""

import re
import time

import e2e_support as support
from e2e_support import Flow
from vectra_contracts.routes import MFA_MAX_AGE

# BR-U2-04: `auth_time` de <= `MFA_MAX_AGE` s para firmar (BR-U0-72), del catálogo de contratos.
MAX_AUTH_AGE = MFA_MAX_AGE


def test_approver_without_totp_gets_no_token(approver_without_totp: support.Account) -> None:
    """H5: con un rol de aprobador y `CONFIGURE_TOTP` pendiente, Keycloak pide configurar el TOTP y no entrega código."""
    flow = Flow()
    try:
        step = flow.password(flow.start(), approver_without_totp.username, approver_without_totp.password)
        assert step.code is None and step.location is None, "el aprobador sin TOTP obtuvo un código de autorización"
        assert step.status == 200
        assert re.search(r'<form[^>]*id="kc-totp-settings-form"', step.html) and 'name="totp"' in step.html, "la página no es la de configurar el TOTP"
        # Ni siquiera con la contraseña por el endpoint de token: `vectra-console` no admite el grant de contraseña.
        response = flow.http.post(
            support.TOKEN_PATH,
            data={"grant_type": "password", "client_id": flow.client_id, "username": approver_without_totp.username, "password": approver_without_totp.password},
        )
        assert response.status_code in (400, 401, 403) and "access_token" not in response.text
    finally:
        flow.close()


def test_stepup_without_spa_reaches_acr_mfa() -> None:
    """Flujo OIDC con `acr_values=mfa`, `prompt=login` y `max_age=0` hasta el token con `acr = mfa` (BR-U2-04).

    El diálogo y la ventana emergente en la consola se prueban en U10; aquí solo el flujo hasta el token.
    """
    username = "ingeniero-1"
    password = support.synth(username, "PASSWORD")
    seed = support.synth(username, "TOTP_SEED")
    flow = Flow()
    try:
        first = flow.login(username, password)
        assert first.code, f"el login de {username} no terminó en un código"
        assert support.decode(flow.exchange(first.code)["access_token"])["acr"] == "mfa"  # BR-U2-03: el segundo factor siempre
        step = flow.password(flow.start(redirect_path="/stepup-callback", acr_values="mfa", prompt="login", max_age=0), username, password)
        if step.location is None and 'name="otp"' in step.html:
            step = flow.otp(step, seed)
        assert step.code, "el step-up no terminó en un código en /stepup-callback"
        claims = support.decode(flow.exchange(step.code)["access_token"])
        assert claims["acr"] == "mfa"
        assert time.time() - claims["auth_time"] <= MAX_AUTH_AGE
        assert "mfa" in claims.get("amr", []) or "otp" in claims.get("amr", [])
    finally:
        flow.close()
