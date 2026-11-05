"""Autorización y cabeceras internas en el gateway, con el eco como destino (P-U2-06; BR-U2-11). Se ejecutan en el Paso 16.

H1: `console-bff` y `case-service` son el backend de eco de `tests/e2e/echo/`, que devuelve las cabeceras que recibe.
H2: «token de otro servicio» espera 403 en el gateway, que autoriza por `azp` y scope sin `audiences`; el 401 por audiencia es de U8.
"""

import time
from typing import Any

import e2e_support as support
import httpx

INTAKE = "/api/intake/v1/intake/applications"
CONSOLE = "/api/console/v1/ping"
PREFIX = str(support.routes()["internal_header_prefix"])


def echoed(response: httpx.Response) -> dict[str, str]:
    assert response.status_code == 200, f"HTTP {response.status_code}: {response.text[:200]}"
    return {name.lower(): value for name, value in response.json()["headers"]}


def test_token_of_another_service_is_rejected_with_403(gateway: httpx.Client) -> None:
    """Un token de `scoring-service` presentado a `case-service` por el gateway: 403 `forbidden` (H2: `azp` y scope)."""
    other = "scoring-service"
    allowed = support.route("intake")["auth"]["claims"][0]["values"]
    assert other not in allowed
    token = support.service_token(gateway, other)
    response = gateway.post(INTAKE, headers=support.bearer(token), json={})
    assert response.status_code == 403, response.text
    assert response.json()["code"] == "forbidden"


def test_injected_x_vectra_sub_has_no_effect(gateway: httpx.Client, console_token: str) -> None:
    """`x-vectra-sub` entrante ni autentica ni llega al backend: el gateway la quita y pone la del JWT (P-U2-06)."""
    unauthenticated = gateway.get(CONSOLE, headers={"x-vectra-sub": "someone-else"})
    assert unauthenticated.status_code == 401
    arrived = echoed(gateway.get(CONSOLE, headers=support.bearer(console_token, **{"x-vectra-sub": "someone-else"})))
    assert "someone-else" not in arrived.values()
    assert not [name for name in arrived if name.startswith(PREFIX)]


def test_echo_idempotency_key_arrives_intact(gateway: httpx.Client, console_token: str, channel_token: str) -> None:
    """`Idempotency-Key` en `/api/intake/**` y en `/api/console/**` llega al backend sin cambios (P-U2-06)."""
    key = f"req-{time.time_ns()}-Ab_9~:/"
    intake = echoed(gateway.post(INTAKE, headers=support.bearer(channel_token, **{"Idempotency-Key": key}), json={}))
    console = echoed(gateway.post(CONSOLE, headers=support.bearer(console_token, **{"Idempotency-Key": key}), json={}))
    assert intake["idempotency-key"].encode() == key.encode()
    assert console["idempotency-key"].encode() == key.encode()


def test_echo_x_test_scenario_arrives_intact(gateway: httpx.Client, channel_token: str) -> None:
    """`X-Test-Scenario` en `/api/intake/**` llega al backend sin cambios (U8, revisión del FD)."""
    scenario = f"escenario-{time.time_ns()}-RECHAZO_por/Politica"
    arrived = echoed(gateway.post(INTAKE, headers=support.bearer(channel_token, **{"X-Test-Scenario": scenario}), json={}))
    assert arrived["x-test-scenario"].encode() == scenario.encode()


def test_echo_no_incoming_x_vectra_header_arrives(gateway: httpx.Client, console_token: str, channel_token: str) -> None:
    """Ninguna `x-vectra-*` llega al backend: ni las inyectadas ni las que el gateway copia del JWT (P-U2-06)."""
    injected: dict[str, Any] = {f"{PREFIX}{name}": "forged" for name in ("sub", "azp", "role", "internal")}
    for path, token in ((CONSOLE, console_token), (INTAKE, channel_token)):
        arrived = echoed(gateway.post(path, headers=support.bearer(token, **injected), json={}))
        assert not [name for name in arrived if name.startswith(PREFIX)], (path, arrived)
