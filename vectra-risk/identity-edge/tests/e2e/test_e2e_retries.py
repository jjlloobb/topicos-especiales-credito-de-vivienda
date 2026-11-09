"""Sin reintentos de Envoy ante un 503 del backend (P-U2-02; NFR-U2-11). Se ejecutan en el Paso 16 (ítem 8 de la guía).

El backend es el eco de `tests/e2e/echo/` en modo 503 (`X-Echo-Fail: 503`), que cuenta las llamadas por `X-Echo-Key`. Cada réplica del eco
lleva su contador, y `VECTRA_E2E_ECHO_URLS` lista todas (un port-forward por pod): la suma es lo que el backend recibió.
P-U2-02: un `POST` no se reintenta nunca; el `GET` de `/api/console/**` solo se reintenta ante `connect-failure`, no ante un 503.
"""

import time

import e2e_support as support
import httpx

INTAKE = "/api/intake/v1/intake/applications"
CONSOLE = "/api/console/v1/ping"
FAIL = {"X-Echo-Fail": "503"}


def test_post_to_a_backend_with_503_gets_exactly_one_call(gateway: httpx.Client, channel_token: str) -> None:
    """Un `POST` a `/api/intake/**` cuyo backend da 503 recibe exactamente 1 llamada: Envoy no reintenta (P-U2-02)."""
    key = f"post-503-{time.time_ns()}"
    response = gateway.post(INTAKE, headers=support.bearer(channel_token, **FAIL, **{"X-Echo-Key": key}), json={})
    assert response.status_code == 503, f"HTTP {response.status_code}: {response.text[:200]}"
    assert support.echo_calls(key) == 1


def test_idempotent_get_with_503_is_not_retried_on_503(gateway: httpx.Client, console_token: str) -> None:
    """Un `GET` de `/api/console/**` solo se reintenta ante `connect-failure`; con un 503 del backend, también 1 sola llamada (P-U2-02)."""
    key = f"get-503-{time.time_ns()}"
    response = gateway.get(CONSOLE, headers=support.bearer(console_token, **FAIL, **{"X-Echo-Key": key}))
    assert response.status_code == 503, f"HTTP {response.status_code}: {response.text[:200]}"
    assert support.echo_calls(key) == 1
