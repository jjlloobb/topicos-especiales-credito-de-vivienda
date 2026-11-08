"""Consultas de lectura en la replica (Paso 8 del plan; BR-U3-15, 17; domain-entities §3; US-403).

`GET /v1/entries` con la proyeccion del consumidor, `POST /v1/monitoring/daily:query` (los conteos se **suman aqui, en el
servidor**), `GET /v1/monitoring/freezes` y el atraso del agregador. Todo sale del pool `projections` (1 conexion, replica,
`registry_verifier`, 2 s). Una proyeccion o un campo no permitidos es 403 sin datos parciales (`projections.Forbidden`).
"""

from collections.abc import Collection
from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID

import psycopg
from vectra_common.errors import DependencyTimeout, Forbidden, ValidationFailed
from vectra_contracts.catalog import Scope
from vectra_contracts.models.api import InvalidParam
from vectra_contracts.models.monitoring import MonitoringQuery, MonitoringWindow
from vectra_contracts.models.registry import EntryFilter

from vectra_registry import projections
from vectra_registry.chain import Row, decode
from vectra_registry.pools import Connection, Pools
from vectra_registry.projections import (
    Consumer,
    DailyCount,
    EntryTotals,
    InvalidEntry,
    delivery_status,
    project,
    project_all,
    project_monitoring_daily,
)

STATEMENT_TIMEOUT_MS = 2000
ROW_COLUMNS = (
    "seq, idempotency_key, entry_type, case_id, model_version_id, policy_version_id, actor_kind, actor_id, actor_role, "
    "occurred_at, recorded_at, correlation_id, contract_version, canonical, prev_hash, hash"
)
#: Cada scope de lectura es un consumidor; su proyeccion por omision en `GET /v1/entries` (BR-U3-15).
CONSUMER_OF = {
    Scope.REGISTRY_READ_EXPLANATION: Consumer.EXPLANATION,
    Scope.REGISTRY_READ_METRICS: Consumer.METRICS,
    Scope.REGISTRY_READ_MONITORING: Consumer.MONITORING,
}
DEFAULT_PROJECTION = {
    Consumer.EXPLANATION: "explanation",
    Consumer.METRICS: "metrics",
    Consumer.MONITORING: "monitoring_freezes",
}
#: Los tipos de entrada que pertenecen a cada proyeccion: la consulta los filtra en SQL para que la pagina salga llena.
PROJECTION_TYPES = {
    "explanation": ("recommendation",),
    "metrics": ("recommendation", "human_decision", "explanation_view"),
    "monitoring_freezes": ("freeze", "frozen_resolution"),
}


def to_row(values: tuple[Any, ...]) -> Row:
    """Una fila de `registry_entries` en el orden de `ROW_COLUMNS`."""
    return Row(
        seq=int(values[0]),
        idempotency_key=values[1],
        entry_type=values[2],
        case_id=values[3],
        model_version_id=values[4],
        policy_version_id=values[5],
        actor_kind=values[6],
        actor_id=values[7],
        actor_role=values[8],
        occurred_at=values[9].astimezone(UTC),
        recorded_at=values[10].astimezone(UTC),
        correlation_id=values[11],
        contract_version=values[12],
        canonical=bytes(values[13]),
        prev_hash=bytes(values[14]),
        hash=bytes(values[15]),
    )


async def fetch_rows(conn: Connection, where: str, params: tuple[Any, ...] | dict[str, Any] = ()) -> list[Row]:
    cursor = await conn.execute(f"SELECT {ROW_COLUMNS} FROM registry_entries {where}", params)  # noqa: S608
    return [to_row(values) for values in await cursor.fetchall()]


async def start_read(conn: Connection) -> None:
    """Una lectura corta con tope de tiempo: nunca frena el *replay* del standby sincrono (BR-U3-13b)."""
    await conn.execute(f"SET LOCAL statement_timeout = {STATEMENT_TIMEOUT_MS}")  # noqa: S608


def timed_out(error: psycopg.Error) -> DependencyTimeout:
    return DependencyTimeout()


# --- GET /v1/entries --------------------------------------------------------------------------------------------------------


def resolve_consumer(scopes: Collection[Scope], projection: str | None) -> tuple[Consumer, str]:
    """El consumidor y la proyeccion de una consulta. Una proyeccion que ningun scope del llamador permite es 403 (BR-U3-15)."""
    consumers = [CONSUMER_OF[scope] for scope in CONSUMER_OF if scope in scopes]
    if not consumers:
        raise Forbidden()
    if projection is None:
        projection = DEFAULT_PROJECTION[consumers[0]]
    for consumer in consumers:
        if projection in projections.PERMITTED[consumer]:
            return consumer, projection
    raise Forbidden()


def _types(projection: str, requested: list[Any] | None) -> list[str]:
    allowed = PROJECTION_TYPES[projection]
    return [t for t in allowed if requested is None or t in {str(r) for r in requested}]


def reference_of(row: Row) -> int | None:
    """El `seq` que una `human_decision` o `explanation_view` referencia en `recommendation_entry_id` (el `registry_entry_id` es el `seq`)."""
    reference = decode(row.canonical)["payload"].get("recommendation_entry_id")
    return int(reference) if isinstance(reference, str) and reference.isdigit() else None


async def _references(conn: Connection, page: list[Row]) -> dict[int, Row]:
    """Las recomendaciones que referencian las decisiones de la pagina, resueltas en el servidor, tengan la fecha que tengan."""
    wanted: set[int] = set()
    for row in page:
        if row.entry_type == "human_decision" and (reference := reference_of(row)) is not None:
            wanted.add(reference)
    if not wanted:
        return {}
    found = await fetch_rows(conn, "WHERE seq = ANY(%s)", (sorted(wanted),))
    return {row.seq: row for row in found}


async def _delivery(conn: Connection, page: list[Row]) -> dict[UUID, list[object]]:
    """Las referencias de las `human_decision` de cada caso con una `recommendation` en la pagina (BR-U3-14)."""
    cases = sorted({row.case_id for row in page if row.entry_type == "recommendation" and row.case_id is not None})
    if not cases:
        return {}
    decisions = await fetch_rows(conn, "WHERE entry_type = 'human_decision' AND case_id = ANY(%s)", (cases,))
    by_case: dict[UUID, list[object]] = {case: [] for case in cases}
    for decision in decisions:
        if decision.case_id is not None:
            by_case[decision.case_id].append(decode(decision.canonical)["payload"].get("recommendation_entry_id"))
    return by_case


async def list_entries(pools: Pools, scopes: Collection[Scope], flt: EntryFilter) -> dict[str, Any]:
    """`Page[EntryProjection]` (`items` y `next_seq_after`, `null` en la ultima pagina)."""
    consumer, projection = resolve_consumer(scopes, flt.projection)
    if projection == "explanation" and (flt.case_id is None or flt.seq is None):
        # BR-U7-13: la explicacion se pide por caso y por `seq`.
        names = [name for name, value in (("case_id", flt.case_id), ("seq", flt.seq)) if value is None]
        raise ValidationFailed(invalid_params=[InvalidParam(name=name, reason_code="required") for name in names])
    clauses = ["seq > %(after)s", "entry_type = ANY(%(types)s)"]
    params: dict[str, Any] = {
        "after": flt.seq_after if flt.seq_after is not None else -1,
        "types": _types(projection, flt.entry_type),
        "limit": flt.limit + 1,
    }
    for column, name, op, value in (
        ("case_id", "case_id", "=", flt.case_id),
        ("seq", "seq", "=", flt.seq),
        ("recorded_at", "from", ">=", flt.recorded_from),
        ("recorded_at", "to", "<=", flt.recorded_to),
    ):
        if value is not None:
            clauses.append(f"{column} {op} %({name})s")
            params[name] = value
    where = "WHERE " + " AND ".join(clauses) + " ORDER BY seq LIMIT %(limit)s"
    try:
        async with pools.projections.connection() as conn, conn.transaction():
            await start_read(conn)
            rows = await fetch_rows(conn, where, params)
            more = len(rows) > flt.limit
            page = rows[: flt.limit]
            references = await _references(conn, page) if projection == "metrics" else {}
            delivery = await _delivery(conn, page) if projection == "metrics" else {}
    except psycopg.errors.QueryCanceled as error:
        raise timed_out(error) from error
    try:
        items = project_all(
            consumer,
            projection,
            page,
            resolve_reference=lambda row: references.get(reference_of(row) or -1),
            delivery_status_of=lambda row: (
                delivery_status(row.seq, delivery.get(row.case_id, [])) if row.case_id is not None else None
            ),
        )
    except projections.Forbidden as error:
        raise Forbidden() from error
    return {"items": items, "next_seq_after": page[-1].seq if more and page else None}


# --- Monitoreo (BR-U3-17) -----------------------------------------------------------------------------------------------------


async def monitoring_lag(conn: Connection, now: datetime) -> tuple[int, int]:
    """`(watermark_seq, lag_seconds)`: 0 si la marca es la cabeza; si no, `now - recorded_at` de la entrada `last_seq + 1` (BR-U3-17)."""
    cursor = await conn.execute("SELECT last_seq FROM monitoring_watermark WHERE id = 1")
    row = await cursor.fetchone()
    last_seq = int(row[0]) if row else 0  # type: ignore[call-overload]
    cursor = await conn.execute("SELECT recorded_at FROM registry_entries WHERE seq = %s", (last_seq + 1,))
    pending = await cursor.fetchone()
    if pending is None:
        return last_seq, 0
    recorded_at: datetime = pending[0]  # type: ignore[assignment]
    return last_seq, max(0, int((now - recorded_at).total_seconds()))


def _days(query: MonitoringQuery) -> tuple[date, date]:
    spans = [(r.from_day, r.to_day) for r in query.ranges]
    if query.unattributable_range is not None:
        spans.append((query.unattributable_range.from_day, query.unattributable_range.to_day))
    return min(s[0] for s in spans), max(s[1] for s in spans)


async def monitoring_daily(pools: Pools, scopes: Collection[Scope], query: MonitoringQuery, now: datetime) -> MonitoringWindow:
    """`POST /v1/monitoring/daily:query`: solo lectura en la replica, con los conteos sumados en el servidor."""
    if Scope.REGISTRY_READ_MONITORING not in scopes:
        raise Forbidden()
    first, last = _days(query)
    window = {"first": first, "last": last}
    try:
        async with pools.projections.connection() as conn, conn.transaction():
            await start_read(conn)
            cursor = await conn.execute(
                'SELECT population, model_version_id, day, attribute, "group", band, result, decision, count '
                "FROM monitoring_daily WHERE day BETWEEN %(first)s AND %(last)s",
                window,
            )
            daily = [DailyCount(*values) for values in await cursor.fetchall()]  # type: ignore[arg-type]
            cursor = await conn.execute(
                "SELECT population, model_version_id, day, total, invalid FROM monitoring_entry_totals "
                "WHERE day BETWEEN %(first)s AND %(last)s",
                window,
            )
            totals = [EntryTotals(*values) for values in await cursor.fetchall()]  # type: ignore[arg-type]
            cursor = await conn.execute(
                "SELECT seq, population, model_version_id, day, reason FROM monitoring_invalid "
                "WHERE day BETWEEN %(first)s AND %(last)s ORDER BY seq",
                window,
            )
            invalid = [InvalidEntry(*values) for values in await cursor.fetchall()]  # type: ignore[arg-type]
            watermark, lag = await monitoring_lag(conn, now)
    except psycopg.errors.QueryCanceled as error:
        raise timed_out(error) from error
    try:
        return project_monitoring_daily(
            Consumer.MONITORING, query, daily, totals, invalid, watermark_seq=watermark, lag_seconds=lag
        )
    except projections.Forbidden as error:  # pragma: no cover - el scope ya se comprobo
        raise Forbidden() from error


def freeze_records(rows: list[Row]) -> list[dict[str, Any]]:
    """Los `FreezeRecord` de U0: cada `freeze` con las `frozen_resolution` posteriores de su version, en orden (U9; BR-U3-17)."""
    records: list[dict[str, Any]] = []
    latest: dict[str | None, dict[str, Any]] = {}
    for row in rows:
        projected = project(Consumer.MONITORING, "monitoring_freezes", row)
        if projected is None:
            continue
        if row.entry_type == "freeze":
            record = {
                "freeze_id": projected["freeze_id"],
                "model_version_id": projected["model_version_id"],
                "frozen_at": projected["frozen_at"],
                "context_package": projected["context_package"],
                "resolutions": [],
            }
            records.append(record)
            latest[row.model_version_id] = record
        elif row.model_version_id in latest:
            latest[row.model_version_id]["resolutions"].append(
                {"action": projected["action"], "recorded_at": projected["recorded_at"]}
            )
    return records


async def monitoring_freezes(pools: Pools, scopes: Collection[Scope]) -> list[dict[str, Any]]:
    """`GET /v1/monitoring/freezes`."""
    if Scope.REGISTRY_READ_MONITORING not in scopes:
        raise Forbidden()
    try:
        async with pools.projections.connection() as conn, conn.transaction():
            await start_read(conn)
            rows = await fetch_rows(
                conn, "WHERE entry_type IN ('freeze', 'frozen_resolution') ORDER BY seq"
            )
    except psycopg.errors.QueryCanceled as error:
        raise timed_out(error) from error
    return freeze_records(rows)
