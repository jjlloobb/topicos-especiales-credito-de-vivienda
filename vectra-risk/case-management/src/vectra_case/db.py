"""Acceso a `case-db` (Paso 13; NFR-U8-21, P-U8-03, P-U8-10). Pool propio de <= 5 conexiones, con el rol del proceso.

Sin `psycopg_pool` (no esta en el workspace): una cola de conexiones asincronas. Los fallos de la base se traducen a
`DependencyUnavailable` (503): conexion perdida, pool agotado y base en solo lectura (`default_transaction_read_only`).
"""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
from typing import Any, Final

import psycopg
from psycopg import errors
from psycopg.rows import dict_row
from vectra_common.errors import DependencyUnavailable

from vectra_case.config import CASE_DB_POOL_MAX, DB_ACQUIRE_TIMEOUT, DB_CONNECT_TIMEOUT

Conn = psycopg.AsyncConnection[dict[str, Any]]
_UNAVAILABLE: Final = (psycopg.OperationalError, errors.ReadOnlySqlTransaction, TimeoutError)


class Database:
    def __init__(self, dsn: str, size: int = CASE_DB_POOL_MAX) -> None:
        self._dsn = dsn
        self._size = size
        self._idle: asyncio.LifoQueue[Conn] = asyncio.LifoQueue()
        self._open = 0
        self._lock = asyncio.Lock()
        self._closed = False

    async def _connect(self) -> Conn:
        return await psycopg.AsyncConnection.connect(
            self._dsn, row_factory=dict_row, connect_timeout=DB_CONNECT_TIMEOUT
        )

    async def _acquire(self) -> Conn:
        if self._closed:
            raise DependencyUnavailable()
        while True:
            try:
                conn = self._idle.get_nowait()
            except asyncio.QueueEmpty:
                async with self._lock:
                    if self._open < self._size:
                        self._open += 1
                        try:
                            return await self._connect()
                        except BaseException:
                            self._open -= 1
                            raise
                conn = await asyncio.wait_for(self._idle.get(), DB_ACQUIRE_TIMEOUT)
            if conn.closed or conn.broken:
                self._open -= 1
                continue
            return conn

    @asynccontextmanager
    async def tx(self) -> AsyncIterator[Conn]:
        """Una transaccion: commit al salir bien, rollback si falla. Los errores de disponibilidad son 503."""
        try:
            conn = await self._acquire()
        except _UNAVAILABLE as exc:
            raise DependencyUnavailable() from exc
        try:
            async with conn.transaction():
                yield conn
        except _UNAVAILABLE as exc:
            raise DependencyUnavailable() from exc
        finally:
            if conn.closed or conn.broken:
                self._open -= 1
            else:
                self._idle.put_nowait(conn)

    async def ping(self) -> bool:
        try:
            async with self.tx() as conn:
                await conn.execute("SELECT 1")
        except DependencyUnavailable:
            return False
        return True

    async def close(self) -> None:
        self._closed = True
        while not self._idle.empty():
            conn = self._idle.get_nowait()
            with suppress(Exception):
                await conn.close()


def ready_probe(dsn: str) -> bool:
    """Readiness de `/readyz` (P-U8-03): hay conexion con `case-db`. Solo lectura sigue `Ready`."""
    try:
        with psycopg.connect(dsn, connect_timeout=1) as conn:
            conn.execute("SELECT 1")
    except psycopg.Error:
        return False
    return True
