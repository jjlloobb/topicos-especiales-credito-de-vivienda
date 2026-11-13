"""`case-service` **real** (`vectra_case.app.build_app`) en proceso sobre PostgreSQL de Testcontainers (U12-T02, CA-11; P-3 (a)). Usa el `harness` de U8 (autenticador falso por nombre de cliente, reloj
y dobles de sus destinos) dentro de un bucle de eventos en un hilo, y un envoltorio minimo que hace de gateway: reescribe `/api/intake/v1/...` a `/v1/...` (la ruta de `identity-edge/gateway/routes.yaml`) y
deja pasar solo a los clientes `channel` y `channel-simulator` (el `azp`)."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import httpx
from external_paths import use_u8_doubles
from sync_asgi import BackgroundLoop, SyncASGITransport

use_u8_doubles()
from u8_support import harness  # noqa: E402

GATEWAY_PREFIX = "/api/intake"
ALLOWED_AZP = (
    "simulator",
    "channel",
    "channel2",
)  # los nombres del autenticador falso de U8: `channel-simulator`, `channel-web`, `channel-web-2`


def gateway_rewrite(request: httpx.Request) -> httpx.Request:
    """Lo que hace el gateway delante de U8: reescribe la ruta y conserva las cabeceras (`Idempotency-Key`, `X-Test-Scenario`, `traceparent`, `Authorization`)."""
    path = request.url.path.removeprefix(GATEWAY_PREFIX)
    return httpx.Request(
        request.method, request.url.copy_with(path=path), headers=request.headers, content=request.content
    )


@contextmanager
def real_case_service(
    db: Any, *, allow_test_scenarios: bool = True
) -> Iterator[tuple[SyncASGITransport, Any]]:
    background = BackgroundLoop()
    context = harness(db, allow_test_scenarios=allow_test_scenarios)
    world = background.run(context.__aenter__())
    transport = SyncASGITransport(world.app, background, rewrite=gateway_rewrite)
    try:
        yield transport, world
    finally:
        transport.close()
        background.run(context.__aexit__(None, None, None))
        background.close()
