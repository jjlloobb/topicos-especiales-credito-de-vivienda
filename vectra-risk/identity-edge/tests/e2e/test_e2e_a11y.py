"""Accesibilidad del login y del tema (P-U2-08; US-611). Se ejecutan en el Paso 16, con `playwright install chromium`.

El navegador no habla con el clúster: `bridge` atiende cada solicitud con `httpx`, que verifica el TLS contra
`VECTRA_E2E_CA_BUNDLE`. Así no hace falta instalar la CA del clúster en Chromium ni desactivar la verificación.
`axe-core` (con `axe-playwright-python`) no debe reportar violaciones `serious` ni `critical`.
"""

from collections.abc import Iterator
from urllib.parse import urlparse

import e2e_support as support
import httpx
import pytest
from axe_playwright_python.sync_playwright import Axe
from e2e_support import Flow
from playwright.sync_api import Page, Route

BLOCKING = {"serious", "critical"}
# `host` y la longitud los pone la conexión; el cuerpo ya viene descodificado por httpx.
HOP_BY_HOP = {"host", "content-length", "content-encoding", "transfer-encoding", "connection"}


def bridge(page: Page, client: httpx.Client) -> list[str]:
    """Atiende todas las solicitudes de la página con `client`; devuelve la lista (viva) de URLs solicitadas."""
    requested: list[str] = []

    def handle(route: Route) -> None:
        request = route.request
        requested.append(request.url)
        headers = {k: v for k, v in request.all_headers().items() if k.lower() not in HOP_BY_HOP}
        reply = client.request(request.method, request.url, headers=headers, content=request.post_data_buffer)
        out: dict[str, str] = {}
        for name, value in reply.headers.multi_items():
            if name.lower() in HOP_BY_HOP:
                continue
            out[name] = f"{out[name]}\n{value}" if name in out and name.lower() == "set-cookie" else value
        route.fulfill(status=reply.status_code, headers=out, body=reply.content)
        client.cookies.clear()

    page.route("**/*", handle)
    return requested


@pytest.fixture
def bridged(page: Page) -> Iterator[tuple[Page, list[str], httpx.Client]]:
    client = support.gateway_client()
    requested = bridge(page, client)
    yield page, requested, client
    client.close()


def violations(page: Page) -> list[str]:
    found = Axe().run(page).response["violations"]
    return [f"{v['id']} ({v['impact']}): {v['help']}" for v in found if v["impact"] in BLOCKING]


def authorize_url(client: httpx.Client) -> str:
    flow = Flow(client)
    return flow.authorize_url()


def test_login_page_has_no_serious_accessibility_violations(bridged: tuple[Page, list[str], httpx.Client]) -> None:
    page, _, client = bridged
    page.goto(authorize_url(client))
    page.wait_for_selector("form")
    assert violations(page) == []


def test_totp_page_has_no_serious_accessibility_violations(bridged: tuple[Page, list[str], httpx.Client]) -> None:
    """La página de ingresar el código TOTP de un usuario sintético aprobador."""
    page, _, client = bridged
    username = "ingeniero-1"
    page.goto(authorize_url(client))
    page.fill("input[name=username]", username)
    page.fill("input[name=password]", support.synth(username, "PASSWORD"))
    page.click("input[type=submit], button[type=submit]")
    page.wait_for_selector("input[name=otp]")
    assert violations(page) == []


def test_password_change_page_has_no_serious_accessibility_violations(
    bridged: tuple[Page, list[str], httpx.Client], ephemeral_user: object
) -> None:
    """La página de cambio de contraseña (`UPDATE_PASSWORD` pendiente) de un usuario efímero sin MFA."""
    page, _, client = bridged
    account = ephemeral_user(role="analista", required_actions=["UPDATE_PASSWORD"])  # type: ignore[operator]
    page.goto(authorize_url(client))
    page.fill("input[name=username]", account.username)
    page.fill("input[name=password]", account.password)
    page.click("input[type=submit], button[type=submit]")
    page.wait_for_selector("input[name=password-new]")
    assert violations(page) == []


def test_theme_loads_no_resource_from_another_origin(bridged: tuple[Page, list[str], httpx.Client]) -> None:
    """P-U2-08: el tema no carga fuentes, scripts ni imágenes de otro origen."""
    page, requested, client = bridged
    page.goto(authorize_url(client))
    page.wait_for_load_state("networkidle")
    own = urlparse(str(client.base_url)).netloc
    foreign = [u for u in requested if urlparse(u).scheme in ("http", "https") and urlparse(u).netloc != own]
    assert requested, "la página no hizo ninguna solicitud"
    assert foreign == [], foreign
