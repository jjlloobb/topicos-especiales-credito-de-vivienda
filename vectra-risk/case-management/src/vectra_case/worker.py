"""Proceso `case-worker` (Paso 15; INF-U8-04, 06; BR-U8-07; P-U8-01; NFR-U8-02, 03, 04, 22). `python -m vectra_case.worker` arranca.

Lee su configuracion del entorno (variables obligatorias, sin valores por omision), sirve **solo** las sondas y `/metrics` en 8081 con
`ops_server.create_ops_app` (readiness: solo `case-db`; governance y scoring caidos no la afectan) y corre el bucle. No expone 8080.

- Bucle: un semaforo de 16 trabajos en vuelo; con la cola vacia sondea cada 400 ms +- 100 ms; con trabajo, toma el siguiente sin esperar.
- `SIGTERM`/`SIGINT`: deja de sondear y espera las llamadas en vuelo hasta 20 s (`WORKER_SHUTDOWN_GRACE`); lo que no termine queda
  arrendado y otro worker lo retoma al vencer el arrendamiento (30 s). Las senales las maneja este modulo: uvicorn no las captura
  (se anula `capture_signals`, que vuelve a emitir la senal al salir y mataria el drenaje).
- `ops_server.serve` exige una app en 8080; este proceso no la tiene, asi que levanta uvicorn solo para la app de sondas (candidata de U0).
"""

import asyncio
import contextlib
import os
import signal
from collections.abc import Iterator
from contextlib import suppress
from dataclasses import dataclass
from random import Random
from typing import Final

import uvicorn
from vectra_common import logging as vlog
from vectra_common import process, service_token
from vectra_common.ops_server import GRACEFUL_SHUTDOWN, OPS_PORT, create_ops_app

from vectra_case.config import (
    GOVERNANCE_WORKER_POOL,
    POLL_INTERVAL,
    POLL_JITTER,
    WORKER_CONCURRENCY,
    WORKER_SHUTDOWN_GRACE,
)
from vectra_case.db import Database, ready_probe
from vectra_case.evaluation import Evaluator, ScoringClient, Taken
from vectra_case.governance_client import ServingConfigClient
from vectra_case.job_queue import JobQueue

SERVICE: Final = "case-worker"


@dataclass(frozen=True)
class WorkerSettings:
    """Variables obligatorias del Deployment (INF-U8-07): sin ellas el proceso no arranca (`KeyError`)."""

    db_dsn: str  # con el rol `case_worker`, nunca un superusuario
    governance_url: str
    scoring_url: str

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> "WorkerSettings":
        e = env if env is not None else dict(os.environ)
        return cls(e["CASE_DB_DSN"], e["CASE_GOVERNANCE_URL"], e["CASE_SCORING_URL"])


class Worker:
    def __init__(
        self,
        queue: JobQueue,
        evaluator: Evaluator,
        *,
        concurrency: int = WORKER_CONCURRENCY,
        rng: Random | None = None,
    ) -> None:
        self.queue = queue
        self.evaluator = evaluator
        self.rng = rng or Random()  # noqa: S311 (jitter del sondeo)
        self._sem = asyncio.Semaphore(concurrency)
        self._stop = asyncio.Event()
        self._tasks: set[asyncio.Task[None]] = set()

    def stop(self) -> None:
        self._stop.set()

    async def run_forever(self, grace: float = WORKER_SHUTDOWN_GRACE) -> None:
        """Sondea hasta `stop()`; despues espera las llamadas en vuelo hasta `grace` s."""
        while not self._stop.is_set():
            if not await self._slot():
                break  # `SIGTERM` con todos los huecos ocupados: la gracia empieza ya, no cuando termine un trabajo
            taken: Taken | None = None
            if not self._stop.is_set():
                try:
                    taken = await self.queue.take()
                except Exception as exc:  # noqa: BLE001 - la base caida no mata el bucle
                    vlog.log_exception(exc, "take_failed")
            if taken is None:
                self._sem.release()
                await self._idle()
                continue
            task = asyncio.create_task(self._process(taken))
            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)
        await self.drain(grace)

    async def _slot(self) -> bool:
        """Espera un hueco libre o el `stop()`: `False` si llego el `stop()` primero (sin hueco tomado)."""
        acquiring = asyncio.ensure_future(self._sem.acquire())
        stopping = asyncio.ensure_future(self._stop.wait())
        try:
            await asyncio.wait({acquiring, stopping}, return_when=asyncio.FIRST_COMPLETED)
        finally:
            stopping.cancel()
            if not acquiring.done():
                acquiring.cancel()
            await asyncio.gather(acquiring, stopping, return_exceptions=True)
        if acquiring.cancelled():
            return False
        return (
            True  # el hueco se tomo (aunque `stop()` tambien haya llegado: el bucle lo suelta al ver `stop`)
        )

    async def _idle(self) -> None:
        wait = POLL_INTERVAL + self.rng.uniform(-POLL_JITTER, POLL_JITTER)
        with suppress(TimeoutError):
            await asyncio.wait_for(self._stop.wait(), wait)

    async def _process(self, taken: Taken) -> None:
        try:
            await self.evaluator.run(taken)
        except Exception as exc:  # noqa: BLE001 - el trabajo sigue arrendado: otro worker lo retoma al vencer el arrendamiento
            vlog.log_exception(exc, "evaluation_failed")
        finally:
            self._sem.release()

    async def drain(self, grace: float) -> None:
        if not self._tasks:
            return
        _, pending = await asyncio.wait(set(self._tasks), timeout=grace)
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)


class _OpsServer(uvicorn.Server):
    """Un `uvicorn.Server` que no captura senales: las maneja `run` (uvicorn las volveria a emitir al salir)."""

    @contextlib.contextmanager
    def capture_signals(self) -> Iterator[None]:
        yield


def build_worker(settings: WorkerSettings) -> tuple[Worker, Database, ServingConfigClient, ScoringClient]:
    db = Database(settings.db_dsn)
    governance = ServingConfigClient(
        settings.governance_url,
        service_token.provider_from_env(
            "governance-service", ("governance:read-serving", "governance:read-feature-spec")
        ),
        pool=GOVERNANCE_WORKER_POOL,
    )
    scoring = ScoringClient(
        settings.scoring_url, service_token.provider_from_env("scoring-service", ("case:recommend",))
    )
    return Worker(JobQueue(db), Evaluator(db, governance, scoring)), db, governance, scoring


async def run(settings: WorkerSettings) -> None:
    process.ensure_service()
    vlog.configure(SERVICE)
    worker, db, governance, scoring = build_worker(settings)
    ops = _OpsServer(
        uvicorn.Config(
            create_ops_app(lambda: ready_probe(settings.db_dsn), init_process=False),
            host="0.0.0.0",  # noqa: S104 (las sondas las llama kubelet y Prometheus)
            port=OPS_PORT,
            log_config=None,
            access_log=False,
            lifespan="off",
            timeout_graceful_shutdown=GRACEFUL_SHUTDOWN,
        )
    )
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, worker.stop)
    ops_task = asyncio.create_task(ops.serve())
    work_task = asyncio.create_task(worker.run_forever())
    try:
        await work_task  # `SIGTERM` lo termina; si las sondas no pueden arrancar, `uvicorn` sale del proceso con 1 (puerto ocupado)
    finally:
        ops.should_exit = True
        await asyncio.gather(ops_task, return_exceptions=True)
        for closer in (scoring.aclose, governance.aclose, db.close):
            with suppress(Exception):
                await closer()


def main() -> None:
    asyncio.run(run(WorkerSettings.from_env()))


if __name__ == "__main__":
    main()
