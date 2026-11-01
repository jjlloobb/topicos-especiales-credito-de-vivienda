"""Servidor de 8081: `/metrics`, `/healthz`, `/readyz` (NFR-U0-48). Sin rutas de negocio."""

import asyncio
from collections.abc import Callable
from typing import Final

import uvicorn
from fastapi import FastAPI
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

from vectra_common import process
from vectra_common.metrics import REGISTRY

OPS_PORT: Final = 8081
GRACEFUL_SHUTDOWN: Final = 10  # segundos; los disenos de U7 a U10 piden una espera acotada
APP_PORT: Final = 8080


def create_ops_app(readiness: Callable[[], bool] | None = None, *, init_process: bool = True) -> Starlette:
    """`readiness` por omision es solo el proceso; `/healthz` nunca depende de el."""
    if init_process:
        process.ensure_service()

    async def metrics(_: Request) -> Response:
        return Response(generate_latest(REGISTRY), media_type=CONTENT_TYPE_LATEST)

    async def healthz(_: Request) -> Response:
        return JSONResponse({"status": "ok"})

    async def readyz(_: Request) -> Response:
        try:
            ready = readiness() if readiness is not None else True
        except Exception:  # noqa: BLE001 - un predicado que falla significa no listo
            ready = False
        return JSONResponse({"status": "ok" if ready else "not_ready"}, status_code=200 if ready else 503)

    return Starlette(
        routes=[Route("/metrics", metrics), Route("/healthz", healthz), Route("/readyz", readyz)]
    )


async def serve(
    app: FastAPI, *, host: str = "0.0.0.0", port: int = APP_PORT, ops_port: int = OPS_PORT  # noqa: S104
) -> None:
    """Sirve la app y `app.state.ops_app` en un solo proceso; si una se detiene, se detiene la otra."""
    servers = [
        uvicorn.Server(
            uvicorn.Config(
                app,
                host=host,
                port=port,
                log_config=None,
                access_log=False,
                timeout_graceful_shutdown=GRACEFUL_SHUTDOWN,
            )
        ),
        uvicorn.Server(
            uvicorn.Config(
                app.state.ops_app, host=host, port=ops_port, log_config=None, access_log=False, lifespan="off"
            )
        ),
    ]
    tasks = [asyncio.create_task(server.serve()) for server in servers]
    await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    for server in servers:
        server.should_exit = True
    await asyncio.gather(*tasks)


def run_service(app: FastAPI) -> None:
    """Punto de entrada de cada servicio HTTP: 8080 con el contrato y 8081 con las sondas."""
    asyncio.run(serve(app))
