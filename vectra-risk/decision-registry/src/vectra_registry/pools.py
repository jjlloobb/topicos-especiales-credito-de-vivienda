"""Pools de conexiones del servicio (P-U3-04; INF-U3-04; NFR-U3-20, 21).

Cuatro pools aislados (bulkhead): `append` 2 y `dossier` 1 contra la primaria, `projections` 1 contra la replica y `health` 1
contra la primaria. Sumados son **5** conexiones por replica del servicio. Un pool lleno no espera mas que su limite: la
solicitud recibe 503 `dependency_unavailable` y el llamador la trata como `registry_unavailable` (fail-closed, BR-U0-02).

El pool es propio y minimo (una cola de conexiones psycopg 3 async) para no sumar una dependencia al lock del workspace.
"""

import asyncio
import time
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Final, Self

import psycopg
from vectra_common.errors import DependencyUnavailable
from vectra_common.metrics import histogram

#: P-U3-04: (conexiones, espera maxima en segundos).
POOL_SIZES: Final = {"append": (2, 0.5), "dossier": (1, 2.0), "projections": (1, 2.0), "health": (1, 1.0)}
POOL_WAIT: Final = histogram(
    "vectra_registry_pool_wait_seconds",
    "Espera por una conexion del pool (P-U3-04)",
    ["pool"],
    (0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0),
)
CONNECT_TIMEOUT: Final = 2

Connection = psycopg.AsyncConnection[tuple[object, ...]]


class Pool:
    """Hasta `size` conexiones abiertas a pedido; quien pide una espera `wait_timeout` o recibe 503."""

    def __init__(self, name: str, dsn: str, size: int, wait_timeout: float) -> None:
        self.name = name
        self._dsn = dsn
        self.size = size
        self.wait_timeout = wait_timeout
        # Cada elemento es una conexion abierta o `None` (un hueco que se llena al pedirlo).
        self._idle: asyncio.Queue[Connection | None] = asyncio.Queue()
        for _ in range(size):
            self._idle.put_nowait(None)

    async def _connect(self) -> Connection:
        try:
            return await psycopg.AsyncConnection.connect(self._dsn, connect_timeout=CONNECT_TIMEOUT)
        except psycopg.OperationalError as error:
            raise DependencyUnavailable() from error

    @asynccontextmanager
    async def connection(self) -> AsyncIterator[Connection]:
        """Una conexion del pool. Si la solicitud falla o se cancela, la conexion se descarta: nunca vuelve en un estado dudoso."""
        started = time.perf_counter()
        try:
            slot = await asyncio.wait_for(self._idle.get(), self.wait_timeout)
        except TimeoutError as error:
            POOL_WAIT.labels(pool=self.name).observe(time.perf_counter() - started)
            raise DependencyUnavailable() from error
        POOL_WAIT.labels(pool=self.name).observe(time.perf_counter() - started)
        conn = slot
        try:
            if conn is None or conn.closed:
                conn = await self._connect()
            yield conn
            if conn.info.transaction_status != psycopg.pq.TransactionStatus.IDLE:
                await conn.rollback()
        except BaseException as error:
            # Un error de negocio con la conexion ociosa (la transaccion ya hizo rollback) no la tira; una cancelacion o
            # una conexion a medias, si.
            if conn is not None and not conn.closed and not _reusable(conn, error):
                await asyncio.shield(_close(conn))
                conn = None
            raise
        finally:
            self._idle.put_nowait(conn)

    async def close(self) -> None:
        while not self._idle.empty():
            conn = self._idle.get_nowait()
            if conn is not None and not conn.closed:
                await conn.close()


def _reusable(conn: Connection, error: BaseException) -> bool:
    return not isinstance(error, asyncio.CancelledError) and (
        conn.info.transaction_status == psycopg.pq.TransactionStatus.IDLE
    )


async def _close(conn: Connection) -> None:
    try:
        await conn.close()
    except psycopg.Error:  # pragma: no cover - la conexion ya estaba rota
        pass


@dataclass(frozen=True)
class Pools:
    """Los cuatro pools del servicio (P-U3-04)."""

    append: Pool
    dossier: Pool
    projections: Pool
    health: Pool

    @classmethod
    def build(cls, dsns: Mapping[str, str]) -> Self:
        """`dsns` por pool: `append` y `dossier` con `registry_app`, `projections` con `registry_verifier` (replica) y `health`."""
        made = {name: Pool(name, dsns[name], size, wait) for name, (size, wait) in POOL_SIZES.items()}
        return cls(**made)

    async def close(self) -> None:
        for pool in (self.append, self.dossier, self.projections, self.health):
            await pool.close()
