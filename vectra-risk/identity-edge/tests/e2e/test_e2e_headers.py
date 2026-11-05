"""Cabeceras por perfil y límites del gateway (US-611; BR-U2-08, 10, 13, 14). Se ejecutan en el Paso 16.

Los perfiles salen de domain-entities §4.1 (`gateway_design.profiles()`), los límites y `Retry-After` de `routes.yaml`.
"""

import time
from concurrent.futures import ThreadPoolExecutor

import e2e_support as support
import gateway_design as gd
import httpx
import pytest

# Una ruta de cada perfil que no necesita token: las del cierre de `/api` dan 404 con el perfil `api` (BR-U2-10).
PAGE_PATHS = [("spa", "/"), ("api", "/api/unknown")]


def expected(profile: str) -> dict[str, str]:
    profiles = gd.profiles()
    return {**profiles["common"].set, **profiles[profile].set}


def assert_headers(response: httpx.Response, wanted: dict[str, str]) -> None:
    for name, value in wanted.items():
        assert response.headers.get(name) == value, f"{name}: {response.headers.get(name)!r}, esperado {value!r}"


@pytest.mark.parametrize(("profile", "path"), PAGE_PATHS, ids=[p for p, _ in PAGE_PATHS])
def test_spa_and_api_security_headers(gateway: httpx.Client, profile: str, path: str) -> None:
    """`curl -I`: CSP sin `unsafe-inline`, HSTS, `nosniff`, `DENY` y `Referrer-Policy` (US-611)."""
    response = gateway.get(path)
    assert_headers(response, expected(profile))
    csp = response.headers["content-security-policy"]
    assert "unsafe-inline" not in csp and "unsafe-eval" not in csp
    assert response.headers["x-frame-options"] == "DENY"
    assert "frame-ancestors 'none'" in csp
    assert response.headers["strict-transport-security"].startswith("max-age=")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["referrer-policy"]


def test_auth_and_grafana_security_headers(gateway: httpx.Client) -> None:
    """`auth` agrega `frame-ancestors 'self'`; `grafana` fija `SAMEORIGIN` y la misma política (BR-U2-13)."""
    profiles = gd.profiles()
    login = gateway.get(f"{support.REALM_PATH}/.well-known/openid-configuration")
    assert_headers(login, profiles["common"].set)
    assert profiles["auth"].add["Content-Security-Policy"] in login.headers.get_list("content-security-policy")
    grafana = gateway.get("/grafana/")
    assert_headers(grafana, expected("grafana"))


@pytest.mark.parametrize(("profile", "path"), PAGE_PATHS, ids=[p for p, _ in PAGE_PATHS])
def test_csp_requires_trusted_types(gateway: httpx.Client, profile: str, path: str) -> None:
    """La CSP de `spa` y `api` incluye `require-trusted-types-for 'script'` y `trusted-types 'none'` (NFR Requirements de U10, Q7)."""
    designed = gd.profiles()[profile].set["Content-Security-Policy"]
    assert "require-trusted-types-for 'script'" in designed and "trusted-types 'none'" in designed
    csp = gateway.get(path).headers["content-security-policy"]
    assert "require-trusted-types-for 'script'" in csp
    assert "trusted-types 'none'" in csp


def test_rate_limit_returns_429_with_retry_after(gateway: httpx.Client, console_token: str) -> None:
    """Por encima de `console` req/s de un mismo usuario: 429 `rate_limited` con `Retry-After` fijo (BR-U2-08)."""
    limit = gd.rate_limit_numbers()["console"]
    assert limit == support.rate_limit("console")["requests"]
    wanted = gd.retry_after()["second"]
    assert wanted == support.route("console")["retry_after"]

    def call(_: int) -> httpx.Response:
        return gateway.get("/api/console/v1/ping", headers=support.bearer(console_token))

    with ThreadPoolExecutor(max_workers=limit * 2) as pool:
        replies = list(pool.map(call, range(limit * 4)))
    limited = [r for r in replies if r.status_code == 429]
    assert limited, f"ninguna de {len(replies)} solicitudes en ráfaga dio 429 (límite {limit}/s)"
    for reply in limited:
        assert reply.headers["retry-after"] == wanted
        assert reply.json()["code"] == "rate_limited"
    time.sleep(2)  # la ventana de 1 s


def test_body_over_the_limit_returns_413_payload_too_large(gateway: httpx.Client, console_token: str) -> None:
    """Un cuerpo mayor que `max_body` de la ruta -> 413 `payload_too_large`, sin eco del contenido (BR-U2-08)."""
    limit = support.max_body_bytes("console")
    assert gd.body_limit("/api/console/**") == support.route("console")["max_body"]
    marker = "contenido-que-no-debe-volver"
    body = (marker * (limit // len(marker) + 2))[: limit + 1]
    response = gateway.post("/api/console/v1/ping", headers=support.bearer(console_token, **{"Content-Type": "text/plain"}), content=body)
    assert response.status_code == 413
    assert response.json()["code"] == "payload_too_large"
    assert marker not in response.text


def test_auth_admin_is_not_routed(gateway: httpx.Client) -> None:
    """`/auth/admin` y el realm `master` no se exponen: 404 `Problem` sin `server` ni `x-envoy-*` (BR-U2-10, BR-U2-14; X10)."""
    for path in ("/auth/admin/master/console/", "/auth/admin", "/auth/realms/master/protocol/openid-connect/certs"):
        response = gateway.get(path)
        assert response.status_code == 404, (path, response.status_code)
        assert response.json()["code"] == "not_found"
        assert "server" not in response.headers
        assert not [h for h in response.headers if h.startswith(tuple(support.routes()["client"]["response_remove_prefixes"]))]
