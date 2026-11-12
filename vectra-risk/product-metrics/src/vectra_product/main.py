"""Proceso de `product-metrics` (INF-U11-01; NFR-U11-07, 21). Sin API de negocio: solo el servidor de 8081 de `create_ops_app`.

`run` es el codigo probable sin subproceso: recibe sus dependencias (lector, parametros, relojes, espera, evento de parada y puerto)
y la ejercen las pruebas en el mismo proceso. `main()` solo lee el entorno de cableado y la llama.

- **Orden** (`main`): `process.init("service")`, `logging.configure`, `params.load` (si falla, sale con codigo distinto de 0 **sin servir
  nada**), cliente y `Reader`, `ProductState`, el `collector` registrado, `create_ops_app(readiness)` y el servidor de 8081.
- **Readiness:** lista si hay instantanea publicada **o** el breaker hacia U3 esta abierto o semiabierto (una pasada fallida o vencida
  no basta; al cerrarse el breaker sin instantanea vuelve a 503). Un predicado que lanza una excepcion es 503 (lo resuelve `ops_server`).
- **Sin `run_service` ni `ops_server.serve`**, que exigen una app de 8080. Se sirve la app de `create_ops_app` con un `uvicorn.Server`
  propio que **no captura señales**: uvicorn, al salir de una señal capturada, la vuelve a emitir y el proceso muere con estado -15 en
  lugar de 0. Aqui `SIGTERM` activa `stop`: no se toman ciclos nuevos, la pagina en curso termina, la pasada a medias se descarta y el
  proceso sale con codigo 0.
- **Entorno** (solo aqui y solo cableado): `VECTRA_REGISTRY_URL` (obligatoria), `VECTRA_POLICY_PATH` (opcional) y las `VECTRA_CLIENT_ID`,
  `VECTRA_TOKEN_URL`, `VECTRA_CLIENT_KEY_PATH` y `VECTRA_CLIENT_KEY_ID` que lee `vectra_common.service_token.provider_from_env`.
  NFR-U11-21: el unico acceso HTTP saliente es `vectra_common.deps` (ningun modulo importa `httpx`) y no hay rutas de negocio.
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import random
import signal
import time
from collections.abc import Awaitable, Callable, Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

import uvicorn
from vectra_common import process
from vectra_common.deps import CircuitState
from vectra_common.logging import configure, log_access
from vectra_common.metrics import REGISTRY
from vectra_common.ops_server import OPS_PORT, create_ops_app

from vectra_product import params as params_module
from vectra_product.collector import Holder, Operations, register
from vectra_product.model import Params
from vectra_product.params import ParamsError
from vectra_product.reader import Reader, build_client
from vectra_product.scheduler import Scheduler
from vectra_product.state import ProductState

REGISTRY_URL_ENV: Final = "VECTRA_REGISTRY_URL"
POLICY_PATH_ENV: Final = "VECTRA_POLICY_PATH"
SERVICE_NAME: Final = "product-metrics"
#: Codigos de salida del arranque: parametros invalidos y entorno incompleto (el proceso no sirve nada).
EXIT_PARAMS: Final = 2
EXIT_ENV: Final = 3


def make_readiness(holder: Holder, reader: Reader) -> Callable[[], bool]:
    """NFR-U11-07: instantanea publicada, o breaker abierto o semiabierto (semiabierto cuenta como «U3 no responde»)."""

    def ready() -> bool:
        return holder.current is not None or reader.breaker_state in (
            CircuitState.OPEN,
            CircuitState.HALF_OPEN,
        )

    return ready


class _OpsServer(uvicorn.Server):
    """`uvicorn.Server` que no captura `SIGTERM` ni `SIGINT`: `main` los trata con `stop` y el proceso sale con codigo 0."""

    @contextlib.contextmanager
    def capture_signals(self) -> Iterator[None]:
        yield


async def run(
    reader: Reader,
    params: Params,
    *,
    stop: asyncio.Event,
    port: int = OPS_PORT,
    host: str = "0.0.0.0",  # noqa: S104 - el servidor de sondas escucha en todas las interfaces del pod
    wall: Callable[[], datetime] = lambda: datetime.now(UTC),
    monotonic: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    rng: random.Random | None = None,
) -> None:
    """Sirve 8081 y corre el planificador hasta que `stop` se activa; despues detiene el servidor y libera las series registradas."""
    holder = Holder()
    operations = Operations()
    collector = register(holder, REGISTRY)
    server: _OpsServer | None = None
    try:
        state = ProductState(reader, wall, operations.read)
        scheduler = Scheduler(
            state,
            params,
            holder,
            operations,
            wall=wall,
            monotonic=monotonic,
            sleep=sleep,
            rng=rng if rng is not None else random.Random(),  # noqa: S311 - un desfase de planificacion, no criptografia
            stop=stop,
        )
        app = create_ops_app(make_readiness(holder, reader))
        server = _OpsServer(
            uvicorn.Config(app, host=host, port=port, log_config=None, access_log=False, lifespan="off")
        )
        serving = asyncio.ensure_future(server.serve())
        running = asyncio.ensure_future(scheduler.run())
        await asyncio.wait({serving, running}, return_when=asyncio.FIRST_COMPLETED)
        stop.set()  # si el servidor cayo (puerto ocupado), el planificador tambien para
        server.should_exit = True
        await asyncio.gather(running, serving)
    finally:
        REGISTRY.unregister(collector)
        operations.close()


def _read_params() -> Params:
    path = Path(os.environ.get(POLICY_PATH_ENV, str(params_module.POLICY_PATH)))
    return params_module.load(path)


async def _amain(stop: asyncio.Event, port: int) -> int:
    url = os.environ.get(REGISTRY_URL_ENV)
    if not url:
        log_access(error_code="registry_url_missing")
        return EXIT_ENV
    try:
        params = _read_params()
    except ParamsError:
        log_access(error_code="params_invalid")
        return EXIT_PARAMS  # sin servir nada: la readiness nunca llega a 200
    client = build_client(url)
    try:
        await run(Reader(client), params, stop=stop, port=port)
    finally:
        await client.aclose()
    return 0


def main(port: int = OPS_PORT) -> int:
    process.init("service")
    configure(SERVICE_NAME)

    async def go() -> int:
        stop = asyncio.Event()
        loop = asyncio.get_running_loop()
        for number in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(number, stop.set)
        return await _amain(stop, port)

    return asyncio.run(go())


if __name__ == "__main__":
    raise SystemExit(main())
