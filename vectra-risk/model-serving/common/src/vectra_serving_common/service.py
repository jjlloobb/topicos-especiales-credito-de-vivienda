"""Pegamento HTTP comun: estado de readiness, 503 por saturacion y servidor en 8080 y 8081 (NFR-U6-40, P-U1-04)."""

import os
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, Final

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from vectra_common.ops_server import create_ops_app, run_service

from vectra_serving_common.concurrency import ConcurrencyLimiter, Saturated
from vectra_serving_common.metrics import DURATION
from vectra_serving_common.package_loader import LoadedPackage, ModelPackageIntegrityFailed, load_package

DEFAULT_MODEL_DIR: Final = "/mnt/models"  # donde el storage initializer de KServe deja el paquete
ENV_MODEL_DIR: Final = "MODEL_DIR"
ENV_VERSION: Final = "MODEL_VERSION_ID"  # la anotacion del InferenceService, por downward API


def not_ready() -> JSONResponse:
    return JSONResponse({"error": "not_ready"}, status_code=503)


def saturated() -> JSONResponse:
    return JSONResponse({"error": "saturated"}, status_code=503)


def timed[T](component: str, call: Callable[[], T]) -> T:
    start = time.perf_counter()
    try:
        return call()
    finally:
        DURATION.labels(component=component).observe(time.perf_counter() - start)


def guarded[T](limiter: ConcurrencyLimiter, call: Callable[[], T]) -> T | JSONResponse:
    """Ejecuta `call` si hay lugar; si no, 503 inmediato (el contador lo sube el limitador)."""
    try:
        with limiter.slot():
            return timed(limiter.component, call)
    except Saturated:
        return saturated()


def try_load(files: tuple[str, ...], component: str) -> LoadedPackage | None:
    """Carga y verifica el paquete de `MODEL_DIR` contra `MODEL_VERSION_ID`; `None` = no listo (ya se emitio la causa)."""
    try:
        return load_package(
            Path(os.environ.get(ENV_MODEL_DIR, DEFAULT_MODEL_DIR)),
            os.environ.get(ENV_VERSION, ""),
            files,
            component,
        )
    except ModelPackageIntegrityFailed:
        return None


def serve_forever(app: FastAPI, ready: Callable[[], bool]) -> None:
    app.state.ops_app = create_ops_app(ready)
    run_service(app)


def error_body(code: str, **extra: Any) -> dict[str, Any]:
    return {"error": code, **extra}
