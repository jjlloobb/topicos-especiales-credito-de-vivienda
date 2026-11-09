"""Conexiones por replica (P-U4-04; RESILIENCY-10, bulkhead). Paso 9 del plan.

Cinco conexiones por replica, cada una con su `application_name` (`governance:<replica>:<pool>`) para contarlas en
`pg_stat_activity`:

| Pool         | Conexiones | Uso                                                              |
|--------------|-----------|------------------------------------------------------------------|
| `tx`         | 2         | Transiciones y escrituras                                         |
| `read`       | 1         | Listados, informes, readiness                                     |
| `background` | 1         | Reconciliador y barridos (P-U4-02), sondeo del `etag` (P-U4-01)   |
| `listen`     | 1         | `LISTEN serving_config` (P-U4-01); la abre `convergence.py`       |

`GET /v1/serving-config` no usa ningun pool: responde desde memoria. El pool es propio y minimo (una cola de conexiones
psycopg 3 sincronas), como el de U3, para no sumar una dependencia al lock del workspace. Quien pide una conexion espera
`wait_timeout` como maximo; si no hay, `PoolTimeout` (el Paso 10 lo traduce a 503).
"""

import queue
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any, Final

import psycopg
from psycopg.rows import DictRow, dict_row
from vectra_common.errors import DependencyUnavailable

#: P-U4-04: (conexiones, espera maxima en segundos).
POOL_SIZES: Final = {"tx": (2, 5.0), "read": (1, 2.0), "background": (1, 15.0), "listen": (1, 0.0)}
CONNECT_TIMEOUT: Final = 2

Connection = psycopg.Connection[DictRow]


class PoolTimeout(DependencyUnavailable):
    """Ninguna conexion libre del pool dentro de la espera maxima."""


def app_name(replica: str, pool: str) -> str:
    return f"governance:{replica}:{pool}"


def _healthy(conn: Connection) -> bool:
    return not conn.closed and conn.info.transaction_status != psycopg.pq.TransactionStatus.UNKNOWN


class Pool:
    """Hasta `size` conexiones abiertas a pedido (o de golpe con `warm`). Una conexion a medias nunca vuelve al pool."""

    def __init__(self, name: str, dsn: str, replica: str, size: int, wait_timeout: float) -> None:
        self.name = name
        self.size = size
        self.wait_timeout = wait_timeout
        self._dsn = dsn
        self._application_name = app_name(replica, name)
        self._slots: queue.Queue[Connection | None] = queue.Queue()
        for _ in range(size):
            self._slots.put(None)  # un hueco que se llena al pedirlo

    def _connect(self) -> Connection:
        try:
            return psycopg.connect(
                self._dsn,
                row_factory=dict_row,
                application_name=self._application_name,
                connect_timeout=CONNECT_TIMEOUT,
            )
        except psycopg.OperationalError as error:
            raise DependencyUnavailable() from error

    @contextmanager
    def connection(self) -> Iterator[Connection]:
        try:
            slot = self._slots.get(timeout=self.wait_timeout)
        except queue.Empty as error:
            raise PoolTimeout() from error
        conn = slot
        try:
            if conn is None or conn.closed:
                conn = self._connect()
            yield conn
            if conn.info.transaction_status != psycopg.pq.TransactionStatus.IDLE:
                conn.rollback()
        except BaseException:
            if conn is not None:
                try:
                    if not conn.closed and conn.info.transaction_status != psycopg.pq.TransactionStatus.IDLE:
                        conn.rollback()
                except psycopg.Error:
                    conn.close()
                if not _healthy(conn):
                    conn.close()
                    conn = None
            raise
        finally:
            self._slots.put(conn)

    def warm(self) -> None:
        """Abre las `size` conexiones (para que `pg_stat_activity` las vea desde el arranque)."""
        held: list[Connection | None] = []
        for _ in range(self.size):
            held.append(self._slots.get(timeout=self.wait_timeout))
        try:
            for index, conn in enumerate(held):
                if conn is None or conn.closed:
                    held[index] = self._connect()
        finally:
            for conn in held:
                self._slots.put(conn)

    def close(self) -> None:
        """Cierra las conexiones ociosas (las que estan prestadas las cierra quien las tiene)."""
        for _ in range(self.size):
            try:
                conn = self._slots.get_nowait()
            except queue.Empty:
                return
            if conn is not None:
                conn.close()
            self._slots.put(None)


class Pools:
    """Los pools de una replica. `listen_connection` abre la conexion unica de `LISTEN` (la usa `convergence.py`)."""

    def __init__(self, dsn: str, replica: str) -> None:
        self.dsn = dsn
        self.replica = replica
        self._pools = {
            name: Pool(name, dsn, replica, size, wait) for name, (size, wait) in POOL_SIZES.items() if name != "listen"
        }
        self._listen_lock = threading.Lock()

    def tx(self) -> Any:
        return self._pools["tx"].connection()

    def read(self) -> Any:
        return self._pools["read"].connection()

    def background(self) -> Any:
        return self._pools["background"].connection()

    def listen_connection(self) -> Connection:
        """La conexion de `LISTEN`: autocommit y su propio `application_name`. Quien la pide la cierra."""
        try:
            return psycopg.connect(
                self.dsn,
                row_factory=dict_row,
                autocommit=True,
                application_name=app_name(self.replica, "listen"),
                connect_timeout=CONNECT_TIMEOUT,
            )
        except psycopg.OperationalError as error:
            raise DependencyUnavailable() from error

    def warm(self) -> None:
        for pool in self._pools.values():
            pool.warm()

    def close(self) -> None:
        for pool in self._pools.values():
            pool.close()
