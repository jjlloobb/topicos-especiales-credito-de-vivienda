"""Expediente y verificacion bajo demanda (Paso 8 del plan; BR-U3-13b, 14; P-U3-05; NFR-U3-21, 43; US-402, US-403).

`GET /v1/dossiers/{case_id}` lee de la **primaria** (pool `dossier`, para incluir lo recien escrito): las entradas del caso con
su `canonical` exacto en base64, el `delivery_status` de cada `recommendation` (calculado al leer), la verificacion `range`
(del checkpoint anterior al posterior, o a la cabeza) y la ultima verificacion `full` terminada. `POST /v1/integrity-checks`
**solo registra** la solicitud (la API no firma ni lee el bucket WORM: la ejecuta el CronJob `registry-verify-ondemand`).
"""

import asyncio
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID, uuid4

from prometheus_client import Counter
from psycopg import errors
from vectra_common.errors import DependencyTimeout, NotFound
from vectra_common.metrics import REGISTRY
from vectra_contracts.models.registry import (
    IntegrityCheckRef,
    IntegrityCheckRequest,
    IntegrityCheckStatus,
    IntegrityReport,
)

from vectra_registry.chain import Row, decode
from vectra_registry.pools import Connection, Pools
from vectra_registry.projections import Consumer, delivery_status, project
from vectra_registry.queries import STATEMENT_TIMEOUT_MS, fetch_rows
from vectra_registry.verify import ListSource, verify

#: BR-U3-13b: tramos de a lo sumo 10 000 entradas por consulta.
CHUNK = 10_000
DOSSIER_NOT_VERIFIED = Counter(
    "vectra_registry_dossier_not_verified_total",
    "Expedientes cuyo tramo no verifico (BR-U3-14; alimenta RegistryChainBroken)",
    registry=REGISTRY,
)


def _covered(row: Row) -> int | None:
    payload = decode(row.canonical).get("payload")
    covered = payload.get("checkpoint_seq") if isinstance(payload, dict) else None
    return covered if isinstance(covered, int) and not isinstance(covered, bool) else None


async def _range_rows(conn: Connection, low: int, high: int) -> list[Row]:
    """Las filas `low..high` en tramos cortos, mas las cubiertas por los checkpoints del tramo que quedan fuera de el."""
    rows: list[Row] = []
    start = max(low - 1, 0)  # la fila anterior solo ancla el enlace
    while start <= high:
        stop = min(start + CHUNK - 1, high)
        rows += await fetch_rows(conn, "WHERE seq BETWEEN %s AND %s ORDER BY seq", (start, stop))
        start = stop + 1
    seen = {row.seq for row in rows}
    outside = sorted(
        {c for row in rows if row.entry_type == "checkpoint" and (c := _covered(row)) is not None and c not in seen and c >= 0}
    )
    if outside:
        rows += await fetch_rows(conn, "WHERE seq = ANY(%s)", (outside,))
    return rows


async def _last_full(conn: Connection) -> dict[str, Any] | None:
    cursor = await conn.execute(
        "SELECT check_id, finished_at, report->>'result' FROM integrity_checks "
        "WHERE mode = 'full' AND status = 'terminada' ORDER BY finished_at DESC LIMIT 1"
    )
    row = await cursor.fetchone()
    if row is None:
        return None
    return {
        "check_id": str(row[0]),
        "finished_at": cast(datetime, row[1]).astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z"),
        "result": row[2],
    }


def integrity_status(report: IntegrityReport, from_seq: int, to_checkpoint: int | str) -> dict[str, Any]:
    """`IntegrityStatus` (U0 §9.6) a partir del informe `range`."""
    failed = report.result != "integra"
    return {
        "status": "not_verified" if failed else "verified",
        "from_checkpoint_seq": from_seq,
        "to_checkpoint_seq": to_checkpoint,
        "entries_checked": report.entries_checked,
        "first_inconsistent_seq": report.first_inconsistent_seq,
        "reason": report.reason,
    }


async def build_dossier(pools: Pools, case_id: UUID, public_keys: Sequence[bytes]) -> dict[str, Any]:
    """`RegistryDossier` de U0. 404 si el caso no tiene entradas."""
    try:
        async with pools.dossier.connection() as conn, conn.transaction():
            await conn.execute(f"SET LOCAL statement_timeout = {STATEMENT_TIMEOUT_MS * 5}")  # noqa: S608
            entries = await fetch_rows(conn, "WHERE case_id = %s ORDER BY seq", (case_id,))
            if not entries:
                raise NotFound()
            first, last = entries[0].seq, entries[-1].seq
            previous = await fetch_rows(
                conn, "WHERE entry_type = 'checkpoint' AND seq < %s ORDER BY seq DESC LIMIT 1", (first,)
            )
            later = await fetch_rows(conn, "WHERE entry_type = 'checkpoint' AND seq > %s ORDER BY seq LIMIT 1", (last,))
            low = (_covered(previous[0]) or 0) if previous else 0
            if later:
                high = later[0].seq
            else:
                head = await conn.execute("SELECT seq FROM registry_head")
                head_row = await head.fetchone()
                high = int(head_row[0]) if head_row else last  # type: ignore[call-overload]
            window = await _range_rows(conn, low, high)
            last_full = await _last_full(conn)
    except errors.QueryCanceled as error:
        raise DependencyTimeout() from error
    report = await asyncio.to_thread(
        verify, "range", ListSource(window), public_keys=public_keys, from_seq=low, to_seq=high
    )
    status = integrity_status(report, low, high if later else "head")
    if status["status"] == "not_verified":
        DOSSIER_NOT_VERIFIED.inc()
    decisions = [decode(row.canonical)["payload"].get("recommendation_entry_id") for row in entries if row.entry_type == "human_decision"]
    items: list[dict[str, Any]] = []
    for row in entries:
        item = project(Consumer.FULL, "full", row)
        assert item is not None  # noqa: S101 - `full` proyecta toda entrada
        if row.entry_type == "recommendation":
            item["delivery_status"] = delivery_status(row.seq, decisions)
        items.append(item)
    return {"case_id": str(case_id), "entries": items, "integrity": status, "last_full_verification": last_full}


# --- Verificacion bajo demanda (BR-U3-13b) ------------------------------------------------------------------------------------


_SELECT_CHECK = (
    "SELECT check_id, mode, status, progress_checked, progress_total, report, reason, requested_at, started_at, finished_at "
    "FROM integrity_checks"
)


def _stamp(moment: datetime | None) -> str | None:
    return moment.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z") if moment else None


async def request_check(
    pools: Pools, request: IntegrityCheckRequest, subject: str, now: datetime
) -> tuple[IntegrityCheckRef, bool]:
    """Registra la solicitud (BR-U3-13b): `(ref, created)`. Con otra activa de cualquier modo, devuelve la activa y no escribe."""
    async with pools.dossier.connection() as conn:
        check_id = uuid4()
        try:
            async with conn.transaction():
                active = await _active(conn)
                if active is not None:
                    return active, False
                await conn.execute(
                    "INSERT INTO integrity_checks (check_id, mode, from_seq, to_seq, requested_by, requested_at, status) "
                    "VALUES (%s, %s, %s, %s, %s, %s, 'pendiente')",
                    (check_id, request.mode, request.from_seq, request.to_seq, subject, now),
                )
        except errors.UniqueViolation:
            # Otra solicitud gano el cupo entre la lectura y la escritura: se devuelve la que quedo activa.
            async with conn.transaction():
                active = await _active(conn)
            assert active is not None  # noqa: S101
            return active, False
    return IntegrityCheckRef(check_id=str(check_id), mode=request.mode, requested_at=now, already_active=False), True


async def _active(conn: Connection) -> IntegrityCheckRef | None:
    cursor = await conn.execute(
        "SELECT check_id, mode, requested_at FROM integrity_checks WHERE status IN ('pendiente', 'en_curso') "
        "ORDER BY requested_at LIMIT 1"
    )
    row = await cursor.fetchone()
    if row is None:
        return None
    return IntegrityCheckRef.model_validate(
        {"check_id": str(row[0]), "mode": row[1], "requested_at": row[2], "already_active": True}, strict=False
    )


async def check_status(pools: Pools, check_id: str) -> IntegrityCheckStatus:
    """`GET /v1/integrity-checks/{id}`. Un identificador que no es un UUID o no existe es 404."""
    try:
        wanted = UUID(check_id)
    except ValueError as error:
        raise NotFound() from error
    async with pools.dossier.connection() as conn:
        cursor = await conn.execute(f"{_SELECT_CHECK} WHERE check_id = %s", (wanted,))
        row = await cursor.fetchone()
    if row is None:
        raise NotFound()
    return IntegrityCheckStatus.model_validate(
        {
            "check_id": str(row[0]),
            "mode": row[1],
            "status": row[2],
            "progress": {"checked": row[3], "total": row[4]},
            "report": row[5],
            "reason": row[6],
            "requested_at": row[7],
            "started_at": row[8],
            "finished_at": row[9],
        },
        strict=False,
    )


__all__ = ["build_dossier", "check_status", "integrity_status", "request_check"]
