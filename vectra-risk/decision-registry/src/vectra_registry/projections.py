"""Proyecciones de lectura (Paso 5 del plan; BR-U3-15; domain-entities §3; US-403).

Cada consumidor recibe **solo** la proyeccion que le corresponde y, dentro de ella, solo los campos permitidos. Pedir una
proyeccion o un campo fuera de lo permitido es `Forbidden` (la API lo responde 403): sin datos parciales, ni de una entrada
ni de una pagina. El filtrado lo hace el servicio, no el cliente. `feature_vector`, `justification` y `actor_id` salen
unicamente en `full`.

Las proyecciones `full`, `explanation`, `metrics` y `monitoring_freezes` salen de entradas (`project`); `monitoring_daily` sale
de los conteos de las tablas derivadas (BR-U3-17), sumados aqui (`project_monitoring_daily`). La proyeccion `monitoring` por
filas se retiro (U9 FD, 2026-10-08): pedirla es `Forbidden`.
"""

import base64
from collections import defaultdict
from collections.abc import Callable, Collection, Iterable
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from typing import Any

from vectra_contracts.models.monitoring import (
    MonitoringMarginalCount,
    MonitoringQuery,
    MonitoringWindow,
    RangeTotals,
    VersionWindow,
)

from vectra_registry.chain import Row, decode, format_timestamp

#: Las filas de las tablas derivadas que no se atribuyen a una version llevan `-` (domain-entities §1.3).
UNATTRIBUTABLE = "-"
MAX_INVALID_SEQS = 100


class Forbidden(Exception):  # noqa: N818 (el nombre es el del contrato: BR-U3-15, `403 forbidden`)
    """Proyeccion o campo no permitidos para el consumidor (BR-U3-15)."""


class Consumer(StrEnum):
    """Quien lee: `cro`/`cumplimiento` por el BFF (`full`) o el scope de lectura de un servicio."""

    FULL = "full"
    EXPLANATION = "registry:read:explanation"
    METRICS = "registry:read:metrics"
    MONITORING = "registry:read:monitoring"


PERMITTED: dict[Consumer, frozenset[str]] = {
    Consumer.FULL: frozenset({"full"}),
    Consumer.EXPLANATION: frozenset({"explanation"}),
    Consumer.METRICS: frozenset({"metrics"}),
    Consumer.MONITORING: frozenset({"monitoring_daily", "monitoring_freezes"}),
}

FULL_FIELDS = frozenset(
    {
        "seq", "idempotency_key", "entry_type", "case_id", "model_version_id", "policy_version_id", "actor", "occurred_at",
        "recorded_at", "correlation_id", "contract_version", "payload", "prev_hash", "hash", "canonical",
    }
)  # fmt: skip
_METRICS_COMMON = frozenset(
    {
        "entry_type", "case_id", "outcome", "decision", "final_outcome", "used_factors", "explanation_viewed_before",
        "actor_role", "recorded_at", "seq", "recommendation_entry_id", "evaluated_at", "decided_at", "viewed_at",
    }
)  # fmt: skip
#: Campos permitidos por (proyeccion, `entry_type`); una entrada de otro tipo no pertenece a la proyeccion.
FIELDS: dict[str, dict[str, frozenset[str]]] = {
    "explanation": {"recommendation": frozenset({"seq", "case_id", "model_version_id", "payload"})},
    "metrics": {
        "recommendation": _METRICS_COMMON
        | {"model_version_id", "channel", "received_at", "attempt", "first_evaluation", "delivery_status"},
        "human_decision": _METRICS_COMMON | {"recommendation"},
        "explanation_view": _METRICS_COMMON,
    },
    "monitoring_freezes": {
        "freeze": frozenset({"seq", "freeze_id", "model_version_id", "frozen_at", "recorded_at", "context_package"}),
        "frozen_resolution": frozenset({"seq", "model_version_id", "action", "recorded_at"}),
    },
}
PROJECTIONS = frozenset({"full", "explanation", "metrics", "monitoring_daily", "monitoring_freezes"})


def _check(consumer: Consumer, projection: str, fields: Collection[str] | None) -> None:
    """Todo o nada: se valida la proyeccion y los campos pedidos antes de tocar una sola entrada."""
    if projection not in PROJECTIONS or projection not in PERMITTED.get(consumer, frozenset()):
        raise Forbidden(f"proyeccion no permitida: {projection}")
    if fields is None:
        return
    if projection == "monitoring_daily":
        raise Forbidden("monitoring_daily no tiene campos de entrada")
    allowed = FULL_FIELDS if projection == "full" else frozenset().union(*FIELDS[projection].values())
    extra = set(fields) - allowed
    if extra:
        raise Forbidden(f"campos no permitidos: {sorted(extra)}")


def _stamp(moment: Any) -> str:
    return format_timestamp(moment)


def _case(row: Row) -> str | None:
    return str(row.case_id) if row.case_id is not None else None


def _full(row: Row) -> dict[str, Any]:
    body = decode(row.canonical)
    return {
        "seq": row.seq,
        "idempotency_key": str(row.idempotency_key),
        "entry_type": row.entry_type,
        "case_id": _case(row),
        "model_version_id": row.model_version_id,
        "policy_version_id": row.policy_version_id,
        "actor": body["actor"],
        "occurred_at": _stamp(row.occurred_at),
        "recorded_at": _stamp(row.recorded_at),
        "correlation_id": row.correlation_id,
        "contract_version": row.contract_version,
        "payload": body["payload"],
        "prev_hash": row.prev_hash.hex(),
        "hash": row.hash.hex(),
        "canonical": base64.b64encode(row.canonical).decode("ascii"),
    }


def _recommendation_ref(referenced: Row | None) -> dict[str, Any] | None:
    """La recomendacion que referencia una decision, resuelta en el servidor; `None` si no existe o no es una `recommendation`."""
    if referenced is None or referenced.entry_type != "recommendation":
        return None
    payload = decode(referenced.canonical)["payload"]
    return {
        "seq": referenced.seq,
        "outcome": payload.get("outcome"),
        "model_version_id": referenced.model_version_id,
        **{name: payload.get(name) for name in ("evaluated_at", "received_at", "channel", "attempt", "first_evaluation")},
    }


def _metrics(row: Row, referenced: Row | None, delivery_status: str | None) -> dict[str, Any] | None:
    payload = decode(row.canonical)["payload"]
    base: dict[str, Any] = {
        "entry_type": row.entry_type,
        "case_id": _case(row),
        "recorded_at": _stamp(row.recorded_at),
        "seq": row.seq,
    }
    if row.actor_role is not None:
        base["actor_role"] = row.actor_role
    names: tuple[str, ...]
    match row.entry_type:
        case "recommendation":
            names = ("outcome", "evaluated_at", "channel", "received_at", "attempt", "first_evaluation")
            base["model_version_id"] = row.model_version_id
            if delivery_status is not None:
                base["delivery_status"] = delivery_status
        case "human_decision":
            names = (
                "decision", "final_outcome", "used_factors", "explanation_viewed_before", "decided_at",
                "recommendation_entry_id",
            )  # fmt: skip
            base["recommendation"] = _recommendation_ref(referenced)
        case "explanation_view":
            names = ("viewed_at", "recommendation_entry_id")
        case _:
            return None
    return base | {name: payload.get(name) for name in names}


def _freezes(row: Row) -> dict[str, Any] | None:
    payload = decode(row.canonical)["payload"]
    if row.entry_type == "freeze":
        return {
            "seq": row.seq,
            "freeze_id": payload.get("freeze_id"),
            "model_version_id": row.model_version_id,
            "frozen_at": payload.get("frozen_at"),
            "recorded_at": _stamp(row.recorded_at),
            "context_package": payload.get("context_package"),
        }
    if row.entry_type == "frozen_resolution":
        return {
            "seq": row.seq,
            "model_version_id": row.model_version_id,
            "action": payload.get("action"),
            "recorded_at": _stamp(row.recorded_at),
        }
    return None


def delivery_status(recommendation_seq: int, decision_references: Iterable[object]) -> str:
    """BR-U3-14, P-U7-03: `delivery_status` de una `recommendation`, calculado al leer y nunca guardado.

    `decision_references` son los `recommendation_entry_id` de las `human_decision` del caso: `entregada` si alguna referencia
    esta recomendacion; `no_entregada` si el caso tiene una decision que referencia otra; `pendiente_de_decision` si aun no hay decision.
    """
    referenced = [str(reference) for reference in decision_references]
    if not referenced:
        return "pendiente_de_decision"
    return "entregada" if str(recommendation_seq) in referenced else "no_entregada"


def project(  # noqa: PLR0911
    consumer: Consumer,
    projection: str,
    row: Row,
    *,
    fields: Collection[str] | None = None,
    referenced: Row | None = None,
    delivery_status: str | None = None,
) -> dict[str, Any] | None:
    """La proyeccion de una entrada para un consumidor.

    `None` si la entrada no pertenece a la proyeccion (por ejemplo, un `freeze` en `metrics`). `fields` acota las claves de
    primer nivel; uno fuera de lo permitido es `Forbidden`. `referenced` es la `recommendation` que referencia una
    `human_decision` y `delivery_status`, el estado de entrega de una `recommendation`; ambos los resuelve el servicio al leer.
    """
    _check(consumer, projection, fields)
    out: dict[str, Any] | None
    match projection:
        case "full":
            out = _full(row)
        case "explanation":
            explanation = decode(row.canonical)["payload"].get("explanation") if row.entry_type == "recommendation" else None
            out = (
                {
                    "seq": row.seq,
                    "case_id": _case(row),
                    "model_version_id": row.model_version_id,
                    "payload": {"explanation": explanation},
                }
                if row.entry_type == "recommendation"
                else None
            )
        case "metrics":
            out = _metrics(row, referenced, delivery_status)
        case "monitoring_freezes":
            out = _freezes(row)
        case _:
            return None  # monitoring_daily: sus datos son conteos de la tabla derivada, no entradas
    if out is None or fields is None:
        return out
    return {name: value for name, value in out.items() if name in fields}


def project_all(
    consumer: Consumer,
    projection: str,
    rows: Iterable[Row],
    *,
    fields: Collection[str] | None = None,
    resolve_reference: Callable[[Row], Row | None] | None = None,
    delivery_status_of: Callable[[Row], str | None] | None = None,
) -> list[dict[str, Any]]:
    """La proyeccion de una pagina de entradas, sin las que no pertenecen a ella. Todo o nada (BR-U3-15)."""
    _check(consumer, projection, fields)
    page: list[dict[str, Any]] = []
    for row in rows:
        out = project(
            consumer,
            projection,
            row,
            fields=fields,
            referenced=resolve_reference(row) if resolve_reference and row.entry_type == "human_decision" else None,
            delivery_status=delivery_status_of(row) if delivery_status_of and row.entry_type == "recommendation" else None,
        )
        if out is not None:
            page.append(out)
    return page


# --- monitoring_daily: la suma en el servidor sobre las tablas derivadas (BR-U3-17) ---------------------------------------


@dataclass(frozen=True)
class DailyCount:
    """Una fila de `monitoring_daily` (domain-entities §1.3); `decision` es `-` en la poblacion `modelo`."""

    population: str
    model_version_id: str
    day: date
    attribute: str
    group: str
    band: str
    result: str
    decision: str
    count: int


@dataclass(frozen=True)
class EntryTotals:
    """Una fila de `monitoring_entry_totals`; `model_version_id = '-'` es una decision sin recomendacion atribuible."""

    population: str
    model_version_id: str
    day: date
    total: int
    invalid: int


@dataclass(frozen=True)
class InvalidEntry:
    """Una fila de `monitoring_invalid`."""

    seq: int
    population: str
    model_version_id: str
    day: date
    reason: str


def project_monitoring_daily(  # noqa: PLR0913
    consumer: Consumer,
    query: MonitoringQuery,
    daily: Iterable[DailyCount],
    totals: Iterable[EntryTotals],
    invalid: Iterable[InvalidEntry],
    *,
    watermark_seq: int,
    lag_seconds: int,
) -> MonitoringWindow:
    """La proyeccion `monitoring_daily` (U9 domain-entities §1.2): por cada rango, los conteos marginales sumados.

    Suma, sin el dia, por (poblacion, version, atributo, grupo, banda, resultado, decision); `totals` por rango (`range_id`)
    sin las filas no atribuibles; `unattributable_invalid` es un solo valor: los `invalid` de las filas `-` dentro del
    `unattributable_range` (0 si no se pidio); hasta 100 `invalid_seqs`, los menores, de los dias pedidos.
    """
    _check(consumer, "monitoring_daily", None)
    daily_rows, total_rows, invalid_rows = list(daily), list(totals), list(invalid)

    def in_range(request: Any, population: str, version: str, day: date) -> bool:
        return (
            population == request.population
            and version != UNATTRIBUTABLE
            and request.model_version_id in (None, version)
            and request.from_day <= day <= request.to_day
        )

    counts: list[MonitoringMarginalCount] = []
    range_totals: list[RangeTotals] = []
    for request in query.ranges:
        summed: dict[tuple[str, str, str, str, str, str, str], int] = defaultdict(int)
        for row in daily_rows:
            if in_range(request, row.population, row.model_version_id, row.day):
                summed[(row.population, row.model_version_id, row.attribute, row.group, row.band, row.result, row.decision)] += row.count
        counts += [
            MonitoringMarginalCount.model_validate(
                {
                    "population": population, "model_version_id": version, "range_id": request.range_id, "attribute": attribute,
                    "group": group, "band": band, "result": result, "decision": None if decision == "-" else decision,
                    "count": count,
                },
                strict=False,
            )  # fmt: skip
            for (population, version, attribute, group, band, result, decision), count in sorted(summed.items())
        ]
        chosen = [t for t in total_rows if in_range(request, t.population, t.model_version_id, t.day)]
        range_totals.append(
            RangeTotals(
                range_id=request.range_id,
                total_entries=sum(t.total for t in chosen),
                invalid_entries=sum(t.invalid for t in chosen),
            )
        )
    window = query.unattributable_range
    unattributable = (
        sum(t.invalid for t in total_rows if t.model_version_id == UNATTRIBUTABLE and window.from_day <= t.day <= window.to_day)
        if window
        else 0
    )
    versions: dict[tuple[str, str], tuple[date, date]] = {}
    if query.include_versions:
        for row in daily_rows:
            key = (row.model_version_id, row.population)
            first, last = versions.get(key, (row.day, row.day))
            versions[key] = (min(first, row.day), max(last, row.day))
    seqs = sorted(
        {
            entry.seq
            for entry in invalid_rows
            if any(in_range(request, entry.population, entry.model_version_id, entry.day) for request in query.ranges)
            or (window and entry.model_version_id == UNATTRIBUTABLE and window.from_day <= entry.day <= window.to_day)
        }
    )
    return MonitoringWindow(
        versions=[
            VersionWindow.model_validate(
                {"model_version_id": version, "population": population, "first_day": first, "last_day": last}, strict=False
            )
            for (version, population), (first, last) in sorted(versions.items())
        ],
        counts=counts,
        totals=range_totals,
        unattributable_invalid=unattributable,
        invalid_seqs=seqs[:MAX_INVALID_SEQS],
        watermark_seq=watermark_seq,
        lag_seconds=lag_seconds,
    )


__all__ = [
    "FIELDS", "FULL_FIELDS", "PERMITTED", "PROJECTIONS", "Consumer", "DailyCount", "EntryTotals", "Forbidden", "InvalidEntry",
    "delivery_status", "project", "project_all", "project_monitoring_daily",
]  # fmt: skip
