"""Sesiones y refresh tokens (BR-U2-06): la rotación y la reutilización de un refresh invalidado. Se ejecutan en el Paso 16."""

import e2e_support as support
from e2e_support import Flow


def refresh(flow: Flow, refresh_token: str):
    return flow.http.post(
        support.TOKEN_PATH,
        data={"grant_type": "refresh_token", "client_id": flow.client_id, "refresh_token": refresh_token},
    )


def test_reused_refresh_token_revokes_the_session() -> None:
    """Cada uso emite un refresh nuevo e invalida el anterior; reusar el invalidado revoca la sesión (BR-U2-06)."""
    username = "analista-1"
    flow = Flow()
    try:
        step = flow.login(username, support.synth(username, "PASSWORD"))
        assert step.code, "el login no terminó en un código"
        first = flow.exchange(step.code)["refresh_token"]
        rotated = refresh(flow, first)
        assert rotated.status_code == 200, rotated.text
        second = rotated.json()["refresh_token"]
        assert second != first, "el refresh no rotó"
        reused = refresh(flow, first)
        assert reused.status_code == 400 and reused.json()["error"] == "invalid_grant"
        # Reusar el invalidado revocó la sesión: el refresh vigente tampoco sirve.
        revoked = refresh(flow, second)
        assert revoked.status_code == 400 and revoked.json()["error"] == "invalid_grant"
    finally:
        flow.close()
