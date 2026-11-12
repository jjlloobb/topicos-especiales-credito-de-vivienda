"""Consultas de lectura en la replica (Paso 8 del plan; BR-U3-15, 17; domain-entities §3; US-403).

`GET /v1/entries` con la proyeccion del consumidor, `POST /v1/monitoring/daily:query` (los conteos se **suman aqui, en el
servidor**), `GET /v1/monitoring/freezes` y el atraso del agregador. Todo sale del pool `projections` (1 conexion, replica,
`registry_verifier`, 2 s). Una proyeccion o un campo no permitidos es 403 sin datos parciales (`projections.Forbidden`).
"""

import time
from collections.abc import Collection
from datetime import UTC, date, datetime
from typing import Any, Final
from uuid import UUID

import psycopg
from vectra_common.errors import DependencyTimeout, Forbidden, ValidationFailed
from vectra_contracts.catalog import Scope
from vectra_contracts.models.api import InvalidParam
from vectra_contracts.models.monitoring import MonitoringQuery, MonitoringWindow
from vectra_contracts.models.registry import EntryFilter

from vectra_registry import projections
from vectra_registry.chain import Row, decode
from vectra_registry.pools import POOL_SIZES, Connection, Pools
from vectra_registry.projections import (
    Consumer,
    delivery_status,
    monitoring_window,
    project,
    project_all,
)

STATEMENT_TIMEOUT_MS = 2000
#: Lo que una solicitud retiene la conexion despues de su plazo: la sentencia en curso hasta su `statement_timeout`, cada
#: `monitoring_lag` (dos sentencias) y el commit o el rollback. Medido en U03-T07: con el tope igual a la espera del pool, una
#: respuesta 200 devolvia la conexion hasta 2,33 s despues de tomarla y una `explanation` concurrente agotaba su espera (503).
QUERY_RELEASE_MARGIN_S: Final = 0.5
#: Tope por solicitud de `POST /v1/monitoring/daily:query`, en segundos: la espera del pool `projections` (Paso 8 del plan; nfr-design,
#: tabla de pools) menos `QUERY_RELEASE_MARGIN_S`. Cuenta desde que la solicitud obtiene la conexion (U03-T07, P-2): lo que se acota es
#: cuanto tiempo se retiene la unica conexion del pool, y el margen garantiza que una `explanation` concurrente la obtenga a tiempo.
QUERY_BUDGET_S: Final = POOL_SIZES["projections"][1] - QUERY_RELEASE_MARGIN_S
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


class ReadBudget:
    """El presupuesto de una solicitud de lectura: `statement_timeout` es por sentencia y no acota la suma (U03-T07).

    Arranca al crearse (con la conexion ya en la mano). Antes de cada sentencia, `arm` fija `statement_timeout` al minimo entre
    `STATEMENT_TIMEOUT_MS` y lo que queda del presupuesto, o levanta `DependencyTimeout` (504 `deadline_exceeded`) si ya se agoto.
    El mismo patron que `append._commit`, que descuenta lo transcurrido.
    """

    def __init__(self) -> None:
        self._deadline = time.monotonic() + QUERY_BUDGET_S

    async def arm(self, conn: Connection) -> None:
        remaining_ms = int((self._deadline - time.monotonic()) * 1000)
        if remaining_ms < 1:  # `statement_timeout = 0` lo desactivaria
            raise DependencyTimeout()
        await conn.execute(f"SET LOCAL statement_timeout = {min(STATEMENT_TIMEOUT_MS, remaining_ms)}")  # noqa: S608


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


async def monitoring_lag(conn: Connection, now: datetime, budget: ReadBudget | None = None) -> tuple[int, int]:
    """`(watermark_seq, lag_seconds)`: 0 si la marca es la cabeza; si no, `now - recorded_at` de la entrada `last_seq + 1` (BR-U3-17).

    Con `budget` (daily:query) arma el tope antes de **cada** sentencia: son dos y heredarian el mismo `statement_timeout`."""
    if budget:
        await budget.arm(conn)
    cursor = await conn.execute("SELECT last_seq FROM monitoring_watermark WHERE id = 1")
    row = await cursor.fetchone()
    last_seq = int(row[0]) if row else 0  # type: ignore[call-overload]
    if budget:
        await budget.arm(conn)
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


#: Los rangos pedidos como una tabla (`unnest`) a la que se une cada tabla derivada: una sola pasada y la suma en PostgreSQL.
_RANGES = (
    "unnest(%(ids)s::text[], %(pops)s::text[], %(versions)s::text[], %(froms)s::date[], %(tos)s::date[]) "
    "AS r(range_id, population, model_version_id, from_day, to_day)"
)


async def monitoring_daily(pools: Pools, scopes: Collection[Scope], query: MonitoringQuery, now: datetime) -> MonitoringWindow:
    """`POST /v1/monitoring/daily:query`: solo lectura en la replica, con los conteos **sumados en SQL** (`GROUP BY`).

    El servicio nunca trae las filas diarias (hasta ~300 000 por solicitud con 3 versiones y 180 dias): PostgreSQL devuelve una
    fila por celda y rango (BR-U3-17).

    Toda la solicitud tiene un tope, `QUERY_BUDGET_S`, desde que obtiene la conexion: pasarse es 504 `deadline_exceeded` y la
    conexion vuelve al pool utilizable (U03-T07).
    """
    if Scope.REGISTRY_READ_MONITORING not in scopes:
        raise Forbidden()
    first, last = _days(query)
    window = query.unattributable_range
    params: dict[str, Any] = {
        "ids": [r.range_id for r in query.ranges],
        "pops": [r.population for r in query.ranges],
        "versions": [r.model_version_id for r in query.ranges],
        "froms": [r.from_day for r in query.ranges],
        "tos": [r.to_day for r in query.ranges],
        "first": first,
        "last": last,
        "u_from": window.from_day if window else None,
        "u_to": window.to_day if window else None,
    }
    match = (
        "t.population = r.population AND t.model_version_id <> '-' AND t.day BETWEEN r.from_day AND r.to_day "
        "AND (r.model_version_id IS NULL OR t.model_version_id = r.model_version_id)"
    )
    try:
        async with pools.projections.connection() as conn, conn.transaction():
            budget = ReadBudget()
            counts: dict[str, dict[tuple[str, str, str, str, str, str, str], int]] = {}
            # Un `GROUP BY` por rango, con los predicados en el orden de la llave primaria (poblacion, version, dia): el indice
            # acota las filas de cada rango; unir contra los 12 rangos a la vez hacia que PostgreSQL leyera la tabla entera.
            for request in query.ranges:
                version_filter = "model_version_id = %(version)s" if request.model_version_id else "model_version_id <> '-'"
                await budget.arm(conn)
                cursor = await conn.execute(
                    'SELECT population, model_version_id, attribute, "group", band, result, decision, sum(count)::bigint '  # noqa: S608
                    f"FROM monitoring_daily WHERE population = %(pop)s AND {version_filter} AND day BETWEEN %(from)s AND %(to)s "
                    'GROUP BY population, model_version_id, attribute, "group", band, result, decision',
                    {"pop": request.population, "version": request.model_version_id, "from": request.from_day, "to": request.to_day},
                    # Sin preparar: psycopg prepara la sentencia en la 6.a ejecucion y el servidor pasa al plan generico hacia la 11.a;
                    # ese plan no ve el rango de dias (estima 332 filas y lee 35 640) y cambia a Sort + GroupAggregate con desborde
                    # a disco: sin version, 421 ms -> 760-930 ms (U03-T07, P-6; ronda 2: medido con 15 ejecuciones seguidas).
                    prepare=False,
                )
                counts[request.range_id] = {
                    (str(a), str(b), str(c), str(d), str(e), str(f), str(g)): int(str(n))
                    for a, b, c, d, e, f, g, n in await cursor.fetchall()
                }
            await budget.arm(conn)
            cursor = await conn.execute(
                f"SELECT r.range_id, sum(t.total)::bigint, sum(t.invalid)::bigint FROM {_RANGES} "  # noqa: S608
                f"JOIN monitoring_entry_totals t ON {match} GROUP BY r.range_id",
                params,
            )
            range_totals = {str(i): (int(a), int(b)) for i, a, b in await cursor.fetchall()}  # type: ignore[call-overload]
            versions: dict[tuple[str, str], tuple[date, date]] = {}
            if query.include_versions:
                await budget.arm(conn)
                cursor = await conn.execute(
                    "SELECT model_version_id, population, min(day), max(day) FROM monitoring_daily "
                    "WHERE day BETWEEN %(first)s AND %(last)s GROUP BY model_version_id, population",
                    params,
                )
                versions = {(str(v), str(p)): (lo, hi) for v, p, lo, hi in await cursor.fetchall()}  # type: ignore[misc]
            await budget.arm(conn)
            cursor = await conn.execute(
                "SELECT coalesce(sum(invalid), 0)::bigint FROM monitoring_entry_totals "
                "WHERE model_version_id = '-' AND day BETWEEN %(u_from)s AND %(u_to)s",
                params,
            )
            unattributable = int((await cursor.fetchone() or (0,))[0]) if window else 0  # type: ignore[call-overload]
            await budget.arm(conn)
            cursor = await conn.execute(
                f"SELECT DISTINCT t.seq FROM monitoring_invalid t, {_RANGES} WHERE ({match}) "  # noqa: S608
                "OR (%(u_from)s::date IS NOT NULL AND t.model_version_id = '-' AND t.day BETWEEN %(u_from)s AND %(u_to)s) "
                "ORDER BY t.seq LIMIT 100",
                params,
            )
            invalid_seqs = [int(row[0]) for row in await cursor.fetchall()]  # type: ignore[call-overload]
            watermark, lag = await monitoring_lag(conn, now, budget)
    except psycopg.errors.QueryCanceled as error:
        raise timed_out(error) from error
    return monitoring_window(
        Consumer.MONITORING, query, counts, range_totals, versions, unattributable, invalid_seqs, watermark_seq=watermark, lag_seconds=lag
    )


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
