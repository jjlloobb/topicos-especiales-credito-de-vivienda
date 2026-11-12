"""El doble de U3 y un emisor de token de prueba servidos por HTTP real (uvicorn en un hilo, puerto libre) para el proceso real (CA-3).

La logica del doble no se duplica: el servidor HTTP entrega cada solicitud a `RegistryDouble.handle`, con su latencia, sus fallos
inyectados y su contador de conexiones simultaneas.
"""

from __future__ import annotations

import threading
import time
from typing import Any

import httpx
import uvicorn
from registry_double import TOKEN, RegistryDouble
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route


class Server:
    """Un servidor uvicorn en un hilo, en un puerto que elige el sistema operativo."""

    def __init__(self, app: Any) -> None:
        self._server = uvicorn.Server(
            uvicorn.Config(app, host="127.0.0.1", port=0, log_level="error", lifespan="off")
        )
        self._thread = threading.Thread(target=self._server.run, daemon=True)

    def start(self) -> Server:
        self._thread.start()
        deadline = time.monotonic() + 10
        while not self._server.started:
            if time.monotonic() > deadline:
                raise RuntimeError("el servidor de prueba no arranco")
            time.sleep(0.01)
        return self

    @property
    def url(self) -> str:
        port = self._server.servers[0].sockets[0].getsockname()[1]
        return f"http://127.0.0.1:{port}"

    def stop(self) -> None:
        self._server.should_exit = True
        self._thread.join(timeout=10)


def registry_app(double: RegistryDouble) -> Starlette:
    async def entries(request: Request) -> Response:
        outgoing = httpx.Request("GET", str(request.url), headers=dict(request.headers))
        answer = await double.handle(outgoing)
        return Response(answer.content, status_code=answer.status_code, media_type="application/json")

    return Starlette(routes=[Route("/v1/entries", entries)])


def token_app() -> Starlette:
    async def token(_request: Request) -> JSONResponse:
        return JSONResponse({"access_token": TOKEN, "expires_in": 300})

    return Starlette(routes=[Route("/token", token, methods=["POST"])])
