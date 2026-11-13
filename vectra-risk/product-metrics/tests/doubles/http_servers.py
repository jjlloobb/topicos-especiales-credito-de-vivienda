"""El doble de U3 y un emisor de token de prueba servidos por HTTP real (uvicorn en un hilo, puerto libre) para el proceso real (CA-3).

La logica del doble no se duplica: el servidor HTTP entrega cada solicitud a `RegistryDouble.handle`, con su latencia, sus fallos
inyectados y su contador de conexiones simultaneas.
"""

from __future__ import annotations

import threading
import time
from typing import Any
from urllib.parse import parse_qs

import httpx
import jwt
import uvicorn
from registry_double import TOKEN, RegistryDouble
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route


class Server:
    """Un servidor uvicorn en un hilo, en un puerto que elige el sistema operativo."""

    def __init__(self, app: Any, host: str = "127.0.0.1") -> None:
        """`host="0.0.0.0"` solo para `test_image.py`: el contenedor llega al doble por `host.docker.internal`, no por el 127.0.0.1 del host."""
        self._server = uvicorn.Server(
            uvicorn.Config(app, host=host, port=0, log_level="error", lifespan="off")
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


#: La `aud` que Keycloak acepta en la aserción: su emisor (U00-T04), distinto de la URL de token del doble.
ASSERTION_AUDIENCE = "https://vectra.localtest.me/auth/realms/vectra"


def token_app(audiences: list[str] | None = None) -> Starlette:
    """El `/token` de Keycloak: como el real, responde 400 `Invalid token audience` si la `aud` de la aserción no es el emisor."""
    seen = audiences if audiences is not None else []

    async def token(request: Request) -> JSONResponse:
        form = parse_qs((await request.body()).decode())
        audience = jwt.decode(form["client_assertion"][0], options={"verify_signature": False})["aud"]
        seen.append(audience)
        if audience != ASSERTION_AUDIENCE:
            return JSONResponse({"error": "invalid_client", "error_description": "Invalid token audience"}, status_code=400)
        return JSONResponse({"access_token": TOKEN, "expires_in": 300})

    return Starlette(routes=[Route("/token", token, methods=["POST"])])
