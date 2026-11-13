"""Un transporte **sincrono** de `httpx` sobre una app ASGI en proceso (U12-T02): los clientes de U12 son sincronos y las apps reales de U8 y U10 son asincronas. La app corre en un hilo con su propio
bucle de eventos; no hay sockets. `run()` ejecuta una corrutina en ese bucle (para abrir y cerrar lo que la app necesite: pools de la base, clientes)."""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

import httpx

T = TypeVar("T")


class BackgroundLoop:
    def __init__(self) -> None:
        self.loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self.loop.run_forever, daemon=True, name="u12t02-asgi-loop")
        self._thread.start()

    def run(self, coroutine: Awaitable[T], timeout: float = 120.0) -> T:
        return asyncio.run_coroutine_threadsafe(coroutine, self.loop).result(timeout)  # type: ignore[arg-type]

    def close(self) -> None:
        self.loop.call_soon_threadsafe(self.loop.stop)
        self._thread.join(timeout=10)
        self.loop.close()


class SyncASGITransport(httpx.BaseTransport):
    """`request -> (rewrite) -> app`. `rewrite` permite hacer de gateway: reescribir la ruta o cambiar cabeceras antes de la app."""

    def __init__(
        self,
        app: Any,
        background: BackgroundLoop,
        rewrite: Callable[[httpx.Request], httpx.Request] | None = None,
    ) -> None:
        self._background = background
        self._rewrite = rewrite
        self._client = background.run(self._make(app))

    @staticmethod
    async def _make(app: Any) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app, raise_app_exceptions=False), base_url="http://app.test"
        )

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        request.read()
        if self._rewrite is not None:
            request = self._rewrite(request)

        async def call() -> httpx.Response:
            response = await self._client.request(
                request.method,
                request.url.raw_path.decode(),
                headers=request.headers,
                content=request.content,
            )
            await response.aread()
            return response

        response = self._background.run(call())
        return httpx.Response(response.status_code, headers=response.headers, content=response.content)

    def close(self) -> None:
        self._background.run(self._client.aclose())
