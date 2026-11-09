"""Los caminos de falla de `append` que la base real no produce con facilidad, con un doble de la conexion (Paso 16; NFR-U3-52).

Cubre las ramas de `append.py` que las pruebas de integracion no recorren: el reloj por omision, la cancelacion del commit, el rollback
de una transaccion que falla, el tope de 64 KiB con el `seq` real y la conexion que se cae (`psycopg.OperationalError`, BR-U3-04, 07).
"""

import asyncio
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any

import psycopg
import pytest
from entries import NOW, make
from vectra_common.errors import DependencyUnavailable, PayloadTooLarge
from vectra_registry import append
from vectra_registry.chain import GENESIS_PREV_HASH


class Cursor:
    def __init__(self, row: tuple[Any, ...] | None) -> None:
        self.row = row

    async def fetchone(self) -> tuple[Any, ...] | None:
        return self.row


class FakeConn:
    """Una conexion que responde lo justo para `_work`: la llave es nueva y la cabeza es `head_seq`."""

    def __init__(self, head_seq: int = 0, fail_on: str | None = None, commit_error: BaseException | None = None) -> None:
        self.head_seq = head_seq
        self.fail_on = fail_on
        self.commit_error = commit_error
        self.rolled_back = False
        self.committed = False

    async def execute(self, sql: str, params: Any = None) -> Cursor:
        if self.fail_on and self.fail_on in sql:
            raise ValueError("falla simulada")
        if "FROM registry_entries WHERE idempotency_key" in sql:
            return Cursor(None)
        if "FROM registry_head" in sql:
            return Cursor((self.head_seq, GENESIS_PREV_HASH, NOW, NOW))
        return Cursor(None)

    async def commit(self) -> None:
        if self.commit_error:
            raise self.commit_error
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True

    async def cancel_safe(self) -> None:
        return None

    def add_notice_handler(self, handler: Any) -> None:
        return None

    def remove_notice_handler(self, handler: Any) -> None:
        return None


class FakePools:
    def __init__(self, conn: FakeConn | None = None, error: BaseException | None = None) -> None:
        self.conn = conn
        self.error = error
        self.append = self

    @asynccontextmanager
    async def connection(self) -> Any:
        if self.error:
            raise self.error
        yield self.conn


def clock() -> datetime:
    return NOW


async def run(pools: FakePools, entry_type: str = "model_event") -> append.AppendOutcome:
    return await append.append_entry(pools, make(entry_type), clock=clock)  # type: ignore[arg-type]


def test_el_reloj_por_omision_es_la_hora_actual_en_utc() -> None:
    assert abs((append._utc_now() - datetime.now(UTC)).total_seconds()) < 5  # noqa: SLF001


async def test_un_append_en_el_doble_escribe_y_confirma() -> None:
    conn = FakeConn()
    outcome = await run(FakePools(conn))
    assert outcome.created and outcome.ack.seq == 1 and conn.committed and not conn.rolled_back


async def test_un_commit_que_falla_cancela_la_tarea_y_propaga_el_error() -> None:
    conn = FakeConn(commit_error=RuntimeError("commit roto"))
    with pytest.raises(RuntimeError, match="commit roto"):
        await run(FakePools(conn))


async def test_un_commit_cancelado_propaga_la_cancelacion() -> None:
    conn = FakeConn(commit_error=asyncio.CancelledError())
    with pytest.raises(asyncio.CancelledError):
        await run(FakePools(conn))
    assert not conn.rolled_back  # una cancelacion no hace rollback: el pool descarta la conexion


async def test_una_transaccion_que_falla_hace_rollback_y_propaga_el_error() -> None:
    conn = FakeConn(fail_on="registry_head")
    with pytest.raises(ValueError, match="falla simulada"):
        await run(FakePools(conn))
    assert conn.rolled_back and not conn.committed


async def test_una_cancelacion_durante_el_trabajo_no_hace_rollback() -> None:
    class Cancelled(FakeConn):
        async def execute(self, sql: str, params: Any = None) -> Cursor:
            raise asyncio.CancelledError()

    conn = Cancelled()
    with pytest.raises(asyncio.CancelledError):
        await run(FakePools(conn))
    assert not conn.rolled_back


async def test_br_u3_07_el_tope_de_64_kib_se_vuelve_a_medir_con_el_seq_real(monkeypatch: pytest.MonkeyPatch) -> None:
    """El estimado (con `seq = 0`) cabe, pero el canonico con el `seq` real (digitos de mas) ya no: 413 y sin escribir."""
    entry = make("model_event")
    estimate = len(append.build_canonical(entry, 0, NOW))
    monkeypatch.setattr(append, "MAX_CANONICAL", estimate)
    conn = FakeConn(head_seq=10**9)
    with pytest.raises(PayloadTooLarge):
        await run(FakePools(conn))
    assert conn.rolled_back and not conn.committed


async def test_br_u3_04_una_conexion_caida_es_503_dependency_unavailable() -> None:
    with pytest.raises(DependencyUnavailable):
        await run(FakePools(error=psycopg.OperationalError("conexion perdida")))


async def test_br_u3_04_un_lock_no_disponible_es_503() -> None:
    with pytest.raises(DependencyUnavailable):
        await run(FakePools(error=psycopg.errors.LockNotAvailable("lock")))


async def test_p_u3_02_el_tope_de_2_5_s_del_handler_es_503(monkeypatch: pytest.MonkeyPatch) -> None:
    """Una consulta que no responde: `asyncio.timeout(HANDLER_TIMEOUT)` la corta y el llamador recibe 503 (fail-closed)."""

    class Slow(FakeConn):
        async def execute(self, sql: str, params: Any = None) -> Cursor:
            await asyncio.sleep(5)
            return Cursor(None)

    monkeypatch.setattr(append, "HANDLER_TIMEOUT", 0.05)
    with pytest.raises(DependencyUnavailable):
        await run(FakePools(Slow()))
