"""PBT-U3-09: el agregador equivale al recalculo directo desde las entradas (BR-U3-17; business-logic-model §2.5).

Para toda secuencia de `recommendation` y `human_decision` (varias recomendaciones por caso, decisiones que referencian una que no
es la ultima, recomendaciones posteriores a la decision, empates de `evaluated_at`, etiquetas invalidas, una invalida como la mas
reciente, decisiones sobre una recomendacion inexistente, sobre una entrada que no es `recommendation` o sobre una invalida), con
otras entradas intercaladas y un corte entre lotes con reinicio, `monitoring_daily` y `monitoring_entry_totals` son iguales al
recalculo directo con la regla de una por caso; ningun conteo es negativo (lo exige el `CHECK` de la tabla) y repetir una corrida
no cambia nada.

El recalculo directo (`direct`) no es incremental: mira todas las entradas de una vez y decide, por caso, cual recomendacion cuenta.
`HYPOTHESIS_PROFILE=ci uv run pytest decision-registry/tests/property/test_aggregator.py`.
"""

import uuid
from collections import Counter
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any

import psycopg
import pytest
from cli_support import LABELS, decision, dsn, raw_insert, rec
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from registry_pg import Db, admin_url, pg, roles, template_db  # noqa: F401
from vectra_registry import aggregator

pytestmark = pytest.mark.integration

NOW = datetime(2026, 11, 8, 12, 0, tzinfo=UTC)
BASE = datetime(2026, 11, 3, 0, 0, tzinfo=UTC)
CASES = [uuid.UUID(int=i + 1) for i in range(4)]
VARIANTS = {
    "a": LABELS,
    "b": {"sexo": "M", "rango_edad": "66+", "region": "caribe", "estrato": "6", "banda_capacidad_pago": "gt_30"},
    "bad_region": {**LABELS, "region": "marte"},
    "bad_band": {**LABELS, "banda_capacidad_pago": "gt_90"},
}
ATTRIBUTES = ("sexo", "rango_edad", "region", "estrato")
OUTCOMES = ("favorable", "desfavorable", "revision_requerida")
DECISIONS = ("sigue", "se_aparta", "resuelve_revision")


@dataclass(frozen=True)
class Op:
    kind: str  # rec | dec | other
    case: int = 0
    version: str = "mv-1"
    labels: str = "a"
    minutes: int = 0  # desplazamiento del momento de negocio: con valores chicos hay empates
    outcome: str = "favorable"
    ref: int = 0  # decision: indice (modulo el largo) de la entrada previa que referencia; -1 = seq inexistente
    final: str = "favorable"
    choice: str = "sigue"


ops = st.one_of(
    st.builds(
        Op,
        kind=st.just("rec"),
        case=st.integers(0, 3),
        version=st.sampled_from(["mv-1", "mv-2"]),
        labels=st.sampled_from(sorted(VARIANTS)),
        minutes=st.integers(0, 3),
        outcome=st.sampled_from(OUTCOMES),
    ),
    st.builds(
        Op,
        kind=st.just("dec"),
        case=st.integers(0, 3),
        minutes=st.integers(0, 3),
        ref=st.integers(-1, 40),
        final=st.sampled_from(["favorable", "desfavorable"]),
        choice=st.sampled_from(DECISIONS),
    ),
    st.builds(Op, kind=st.just("other")),
)


def materialize(sequence: list[Op]) -> list[dict[str, Any]]:
    """Las entradas de la secuencia; `seq` empieza en 1 (el 0 es la genesis). Una decision con `ref` apunta a una entrada previa."""
    entries: list[dict[str, Any]] = []
    for position, op in enumerate(sequence):
        at = BASE + timedelta(days=position % 3, minutes=op.minutes)
        if op.kind == "rec":
            entries.append(rec(at, CASES[op.case], version=op.version, outcome=op.outcome, labels=VARIANTS[op.labels]))
        elif op.kind == "dec":
            ref = 10_000 if op.ref < 0 or not position else 1 + (op.ref % position)
            entries.append(decision(at, CASES[op.case], ref, final=op.final, kind=op.choice))
        else:
            entries.append({"entry_type": "freeze", "model_version_id": "mv-1", "recorded_at": at, "payload": {}})
    return entries


def direct(entries: list[dict[str, Any]]) -> tuple[Counter[tuple[Any, ...]], dict[tuple[Any, ...], list[int]]]:
    """Recalculo directo: mira todas las entradas a la vez y, por caso, decide cual recomendacion cuenta."""
    by_seq = {i + 1: e for i, e in enumerate(entries)}

    def valid(e: dict[str, Any]) -> bool:
        labels = e["payload"]["monitoring_labels"]
        return (
            labels["sexo"] in aggregator.GROUPS["sexo"]
            and labels["rango_edad"] in aggregator.GROUPS["rango_edad"]
            and labels["region"] in aggregator.GROUPS["region"]
            and labels["estrato"] in aggregator.GROUPS["estrato"]
            and labels["banda_capacidad_pago"] in aggregator.BANDS
            and e["payload"]["outcome"] in aggregator.OUTCOMES
        )

    def day_of(e: dict[str, Any], field: str) -> date:
        return datetime.fromisoformat(e["payload"][field]).date()

    cells: Counter[tuple[Any, ...]] = Counter()
    totals: dict[tuple[Any, ...], list[int]] = {}

    def total(key: tuple[Any, ...], invalid: bool) -> None:
        cell = totals.setdefault(key, [0, 0])
        cell[0] += 1
        cell[1] += invalid

    def add(population: str, ref: dict[str, Any], day: date, result: str, kind: str) -> None:
        labels = ref["payload"]["monitoring_labels"]
        for attribute in ATTRIBUTES:
            cells[(population, ref["model_version_id"], day, attribute, labels[attribute], labels["banda_capacidad_pago"], result, kind)] += 1

    final_ref: dict[uuid.UUID, int | None] = {}  # caso -> seq contado por la ultima decision atribuible
    best: dict[uuid.UUID, tuple[datetime, int]] = {}
    for seq, e in sorted(by_seq.items()):
        if e["entry_type"] == "recommendation":
            total(("modelo", e["model_version_id"], day_of(e, "evaluated_at")), not valid(e))
            if valid(e):
                key = (datetime.fromisoformat(e["payload"]["evaluated_at"]), seq)
                if e["case_id"] not in best or key > best[e["case_id"]]:
                    best[e["case_id"]] = key
        elif e["entry_type"] == "human_decision":
            ref = by_seq.get(int(e["payload"]["recommendation_entry_id"]))
            day = day_of(e, "decided_at")
            if ref is None or ref["entry_type"] != "recommendation":
                total(("humana", "-", day), True)
                continue
            total(("humana", ref["model_version_id"], day), not valid(ref))
            if valid(ref):
                add("humana", ref, day, e["payload"]["final_outcome"], e["payload"]["decision"])
            final_ref[e["case_id"]] = int(e["payload"]["recommendation_entry_id"]) if valid(ref) else None
    for case in {e["case_id"] for e in entries if e["entry_type"] == "recommendation" and valid(e)} | set(final_ref):
        if case in final_ref:
            seq = final_ref[case]
        else:
            seq = best[case][1] if case in best else None
        if seq is not None:
            ref = by_seq[seq]
            add("modelo", ref, day_of(ref, "evaluated_at"), ref["payload"]["outcome"], "-")
    return cells, totals


def stored(db: Db) -> tuple[Counter[tuple[Any, ...]], dict[tuple[Any, ...], list[int]]]:
    cells: Counter[tuple[Any, ...]] = Counter()
    for r in db.query('SELECT population, model_version_id, day, attribute, "group", band, result, decision, count FROM monitoring_daily'):
        cells[tuple(r[:8])] = int(r[8])  # type: ignore[call-overload]
    totals = {tuple(r[:3]): [int(r[3]), int(r[4])] for r in db.query("SELECT population, model_version_id, day, total, invalid FROM monitoring_entry_totals")}  # type: ignore[call-overload]
    return cells, totals


@pytest.fixture(scope="module")
def shared(pg: Any, template_db: str) -> Iterator[Db]:  # noqa: F811
    """Una base para todos los ejemplos: se vacia entre uno y otro (el superusuario salta el trigger de solo-anexar)."""
    name = "p_" + uuid.uuid4().hex[:12]
    with psycopg.connect(admin_url(pg), autocommit=True) as conn:
        conn.execute(f'CREATE DATABASE "{name}" TEMPLATE "{template_db}" OWNER registry_migrator')
    yield Db(pg, name)
    with psycopg.connect(admin_url(pg), autocommit=True) as conn:
        conn.execute(f'DROP DATABASE "{name}" WITH (FORCE)')


def clean(db: Db) -> None:
    with db.connect() as conn:
        conn.execute("SET session_replication_role = replica")
        conn.execute("DELETE FROM registry_entries WHERE seq > 0")
        conn.execute("TRUNCATE monitoring_daily, monitoring_entry_totals, monitoring_case_index, monitoring_invalid")
        conn.execute("UPDATE monitoring_watermark SET last_seq = 0 WHERE id = 1")


class Crash(Exception):
    pass


@settings(deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    sequence=st.lists(ops, min_size=1, max_size=40),
    size=st.integers(1, 6),
    crash=st.one_of(st.none(), st.integers(1, 8)),
)
def test_pbt_u3_09_el_agregador_equivale_al_recalculo_directo(shared: Db, pg: Any, sequence: list[Op], size: int, crash: int | None) -> None:  # noqa: F811
    clean(shared)
    entries = materialize(sequence)
    raw_insert(shared, entries, first_seq=1)
    url = dsn(pg, shared, "registry_aggregator")
    if crash is not None:  # el proceso muere en el lote `crash`: ese lote se deshace entero
        seen = {"n": 0}

        def hook() -> None:
            seen["n"] += 1
            if seen["n"] == crash:
                raise Crash

        try:
            aggregator.run(url, size=size, clock=lambda: NOW, before_commit=hook)
        except Crash:
            pass
    aggregator.run(url, size=size, clock=lambda: NOW)
    expected_cells, expected_totals = direct(entries)
    cells, totals = stored(shared)
    assert dict(cells) == {k: v for k, v in expected_cells.items() if v}
    assert totals == expected_totals
    assert all(v >= 0 for v in cells.values())
    again = aggregator.run(url, size=size, clock=lambda: NOW)  # repetir no cambia nada
    assert again.entries == 0 and stored(shared) == (cells, totals)
