"""Servidor de 8081: `/metrics`, `/healthz`, `/readyz` (NFR-U0-48). Sin rutas de negocio."""

from collections.abc import Callable

from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

from vectra_common import process
from vectra_common.metrics import REGISTRY


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
