"""Transportes de prueba: una app ASGI en proceso que respeta el timeout de la solicitud y puede simular una caida de red.

`httpx.ASGITransport` ignora el `timeout` de la solicitud; este lo aplica (`ReadTimeout`) para que `deps.call` se comporte como con
un socket real. El limite de conexiones de un cliente solo se ejerce con un servidor real (`servers.py`).
"""

import asyncio
from typing import Any

import httpx


class AsgiTransport(httpx.AsyncBaseTransport):
    def __init__(self, app: Any, fault: str | None = None) -> None:
        self._inner = httpx.ASGITransport(app=app, raise_app_exceptions=False)
        self.fault = fault  # `connect` (conexion rechazada o descartada, F22 apagado) | `timeout`

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        if self.fault == "connect":
            raise httpx.ConnectError("conexion rechazada", request=request)
        if self.fault == "timeout":
            raise httpx.ReadTimeout("tiempo agotado", request=request)
        timeout = request.extensions.get("timeout", {}).get("read")
        try:
            return await asyncio.wait_for(self._inner.handle_async_request(request), timeout)
        except TimeoutError:
            raise httpx.ReadTimeout("tiempo agotado", request=request) from None
