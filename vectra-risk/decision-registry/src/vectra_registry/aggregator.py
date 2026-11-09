"""Agregador de monitoreo (Paso 12 acotado a la demo; BR-U3-17; PBT-U3-09; NFR-U3-24, 42; business-logic-model §2.5).

Cuenta las entradas `recommendation` y `human_decision` del registro en las tablas derivadas de domain-entities §1.3 (marginales por
atributo, totales, indice de caso e invalidas), en lotes de 5 000 entradas. Cada lote es **una transaccion**: toma la marca de agua con
`FOR UPDATE` (dos corridas solapadas se serializan y nunca cuentan dos veces), suma, resta, avanza la marca y confirma. Si el proceso
muere, el lote completo se repite sin contar dos veces porque la marca avanza en la misma transaccion que los conteos.

`run` itera lotes hasta la cabeza o hasta 240 s (el CronJob, `activeDeadlineSeconds: 280`); con `until_head` itera sin tope (el Job de
reconstruccion) y toma antes el *advisory lock* de la reconstruccion. `reset` (rol `registry_migrator`) vacia las cuatro tablas y deja
la marca justo antes de la primera entrada de los ultimos 181 dias.

Una recomendacion por caso (`monitoring_case_index`): sin decision cuenta la valida mas reciente por `(evaluated_at, seq)`; una
`human_decision` fija la que referencia. Para restar, las etiquetas se releen de `registry_entries` por `counted_seq`, asi que la
combinacion de etiquetas nunca se guarda fuera del registro.
"""

import json
import time
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any, Final
from uuid import UUID

import psycopg

from vectra_registry.locks import REBUILD_LOCK

BATCH_SIZE: Final = 5000
RUN_SECONDS: Final = 240.0
#: Retencion: se borran las filas con `day` de mas de 180 dias (BR-U3-17).
RETENTION_DAYS: Final = 180
#: El `reset` deja la marca antes de la primera entrada de los ultimos 181 dias (el dia extra cubre los 5 min de BR-U3-05 y el corte UTC).
RESET_DAYS: Final = 181
UNATTRIBUTABLE: Final = "-"

#: Catalogo de U0 §2.2 (los mismos que los `CHECK` de la migracion 0002).
GROUPS: Final[dict[str, frozenset[str]]] = {
    "sexo": frozenset({"F", "M", "no_informado"}),
    "rango_edad": frozenset({"18-25", "26-35", "36-45", "46-55", "56-65", "66+"}),
    "region": frozenset({"andina", "caribe", "pacifica", "orinoquia", "amazonia", "insular"}),
    "estrato": frozenset({"1", "2", "3", "4", "5", "6", "no_informado"}),
}
BANDS: Final = frozenset({"lt_20", "20_30", "gt_30"})
OUTCOMES: Final = frozenset({"favorable", "desfavorable", "revision_requerida"})
FINAL_OUTCOMES: Final = frozenset({"favorable", "desfavorable"})
DECISIONS: Final = frozenset({"sigue", "se_aparta", "resuelve_revision"})

#: De cada entrada solo salen los campos que se usan, extraidos en la consulta y no el `canonical` completo.
_FIELDS: Final = """
    seq, entry_type, case_id, model_version_id, recorded_at,
    CASE WHEN entry_type IN ('recommendation', 'human_decision') THEN jsonb_build_object(
        'at', COALESCE(p->>'evaluated_at', p->>'decided_at'),
        'labels', p->'monitoring_labels',
        'outcome', p->>'outcome',
        'final_outcome', p->>'final_outcome',
        'decision', p->>'decision',
        'ref', p->>'recommendation_entry_id') END
"""
_PAYLOAD: Final = (
    "CASE WHEN entry_type IN ('recommendation', 'human_decision') "
    "THEN (convert_from(canonical, 'UTF8')::jsonb)->'payload' END AS p"
)
BATCH_SQL: Final = f"""
    SELECT {_FIELDS} FROM (
        SELECT seq, entry_type, case_id, model_version_id, recorded_at, {_PAYLOAD}
        FROM (SELECT * FROM registry_entries WHERE seq > %s ORDER BY seq LIMIT %s) AS batch
    ) AS parsed ORDER BY seq
"""  # noqa: S608 - fragmentos constantes
ENTRY_SQL: Final = f"""
    SELECT {_FIELDS} FROM (
        SELECT seq, entry_type, case_id, model_version_id, recorded_at, {_PAYLOAD}
        FROM registry_entries WHERE seq = %s
    ) AS parsed
"""  # noqa: S608


class RebuildInProgress(Exception):
    """Otra reconstruccion (un `reset` o un `run --until-head`) tiene el *advisory lock* de BR-U3-17."""


@dataclass(frozen=True)
class Entry:
    """Lo que el agregador lee de una entrada."""

    seq: int
    entry_type: str
    case_id: UUID | None
    version: str | None
    recorded_at: datetime
    extra: dict[str, Any]

    @property
    def at(self) -> datetime | None:
        """El momento de negocio (`evaluated_at` o `decided_at`), o `None` si falta o no se lee."""
        text = self.extra.get("at")
        try:
            return datetime.fromisoformat(text).astimezone(UTC) if isinstance(text, str) else None
        except ValueError:
            return None

    @property
    def day(self) -> date:
        moment = self.at
        return (moment or self.recorded_at).astimezone(UTC).date()

    @property
    def labels(self) -> dict[str, str] | None:
        """Las cuatro etiquetas y la banda, o `None` si alguna esta fuera del catalogo (la entrada es invalida)."""
        raw = self.extra.get("labels")
        if not isinstance(raw, dict) or self.version is None:
            return None
        for attribute, groups in GROUPS.items():
            if raw.get(attribute) not in groups:
                return None
        if raw.get("banda_capacidad_pago") not in BANDS:
            return None
        return {name: str(raw[name]) for name in (*GROUPS, "banda_capacidad_pago")}

    @property
    def outcome_ok(self) -> bool:
        return self.extra.get("outcome") in OUTCOMES

    @property
    def valid_recommendation(self) -> bool:
        return self.entry_type == "recommendation" and self.labels is not None and self.outcome_ok and self.at is not None


@dataclass
class CaseRow:
    """Una fila de `monitoring_case_index`."""

    counted_seq: int | None
    evaluated_at: datetime
    fixed_by_decision: bool


def _entry(row: tuple[Any, ...]) -> Entry:
    seq, entry_type, case_id, version, recorded_at, extra = row
    return Entry(int(seq), str(entry_type), case_id, version, recorded_at, extra or {})


def _ref_seq(text: object) -> int | None:
    try:
        value = int(str(text))
    except ValueError:
        return None
    return value if value >= 0 else None


class Batch:
    """Los conteos de un lote: se acumulan en memoria y se escriben juntos, en la transaccion del lote."""

    def __init__(self, conn: psycopg.Connection[tuple[Any, ...]], cutoff: date) -> None:
        self.conn = conn
        self.cutoff = cutoff
        self.daily: defaultdict[tuple[str, ...], int] = defaultdict(int)
        self.totals: defaultdict[tuple[str, str, date], list[int]] = defaultdict(lambda: [0, 0])
        self.invalid: dict[int, tuple[str, str, date, str]] = {}
        self.cases: dict[UUID, CaseRow | None] = {}
        self.dirty: set[UUID] = set()
        self._entries: dict[int, Entry | None] = {}

    # --- lectura -----------------------------------------------------------------------------------------------------------

    def entry(self, seq: int) -> Entry | None:
        if seq not in self._entries:
            row = self.conn.execute(ENTRY_SQL, (seq,)).fetchone()
            self._entries[seq] = _entry(row) if row else None
        return self._entries[seq]

    def case(self, case_id: UUID) -> CaseRow | None:
        if case_id not in self.cases:
            row = self.conn.execute(
                "SELECT counted_seq, evaluated_at, fixed_by_decision FROM monitoring_case_index WHERE case_id = %s",
                (case_id,),
            ).fetchone()
            self.cases[case_id] = CaseRow(row[0], row[1], row[2]) if row else None
        return self.cases[case_id]

    def set_case(self, case_id: UUID, row: CaseRow) -> None:
        self.cases[case_id] = row
        self.dirty.add(case_id)

    # --- conteos -----------------------------------------------------------------------------------------------------------

    def add(self, rec: Entry, population: str, day: date, result: str, decision: str, sign: int) -> None:
        """Suma (o resta) a las cuatro marginales de `rec`. Un dia anterior a la retencion no se agrega."""
        labels = rec.labels
        assert labels is not None and rec.version is not None  # noqa: S101 - quien llama ya valido
        if day < self.cutoff:
            return
        for attribute in GROUPS:
            key = (population, rec.version, day.isoformat(), attribute, labels[attribute], labels["banda_capacidad_pago"], result, decision)
            self.daily[key] += sign

    def subtract_counted(self, counted_seq: int) -> None:
        """Resta la recomendacion contada, releyendo sus etiquetas, version, dia y resultado de `registry_entries`."""
        counted = self.entry(counted_seq)
        assert counted is not None  # noqa: S101 - el registro no borra filas
        self.add(counted, "modelo", counted.day, str(counted.extra["outcome"]), "-", -1)

    def total(self, population: str, version: str, day: date, *, invalid: bool, seq: int, reason: str) -> None:
        cell = self.totals[(population, version, day)]
        cell[0] += 1
        if invalid:
            cell[1] += 1
            self.invalid[seq] = (population, version, day, reason)

    # --- reglas por tipo ---------------------------------------------------------------------------------------------------

    def apply(self, entry: Entry) -> None:
        if entry.entry_type == "recommendation":
            self.recommendation(entry)
        elif entry.entry_type == "human_decision":
            self.decision(entry)

    def recommendation(self, rec: Entry) -> None:
        day = rec.day
        if day < self.cutoff or rec.version is None:
            return  # mas vieja que la retencion: no se agrega
        valid = rec.valid_recommendation
        self.total("modelo", rec.version, day, invalid=not valid, seq=rec.seq, reason="etiquetas_invalidas")
        if not valid or rec.case_id is None:
            return  # una recomendacion invalida nunca reemplaza a la contada
        assert rec.at is not None  # noqa: S101
        idx = self.case(rec.case_id)
        if idx is None:
            self.add(rec, "modelo", day, str(rec.extra["outcome"]), "-", 1)
            self.set_case(rec.case_id, CaseRow(rec.seq, rec.at, False))
        elif idx.fixed_by_decision or idx.counted_seq is None:
            return  # una recomendacion posterior a la decision no cambia nada
        elif (rec.at, rec.seq) > (idx.evaluated_at, idx.counted_seq):
            self.subtract_counted(idx.counted_seq)
            self.add(rec, "modelo", day, str(rec.extra["outcome"]), "-", 1)
            self.set_case(rec.case_id, CaseRow(rec.seq, rec.at, False))

    def decision(self, decision: Entry) -> None:
        day = decision.day
        if day < self.cutoff:
            return
        ref_seq = _ref_seq(decision.extra.get("ref"))
        ref = self.entry(ref_seq) if ref_seq is not None else None
        if ref is None or ref.entry_type != "recommendation" or ref.version is None:
            # Sin recomendacion a la que atribuirla (inexistente o de otro tipo): fila no atribuible.
            self.total("humana", UNATTRIBUTABLE, day, invalid=True, seq=decision.seq, reason="no_atribuible")
            return
        result, kind = decision.extra.get("final_outcome"), decision.extra.get("decision")
        if not ref.valid_recommendation or result not in FINAL_OUTCOMES or kind not in DECISIONS:
            self.total("humana", ref.version, day, invalid=True, seq=decision.seq, reason="etiquetas_invalidas")
            if decision.case_id is not None:
                self.fix_invalid(decision.case_id, ref)
            return
        self.total("humana", ref.version, day, invalid=False, seq=decision.seq, reason="")
        self.add(ref, "humana", day, str(result), str(kind), 1)
        if decision.case_id is not None:
            self.fix(decision.case_id, ref)

    def fix_invalid(self, case_id: UUID, ref: Entry) -> None:
        """La decision referencia una recomendacion invalida: resta la contada y fija el caso con `counted_seq = NULL`."""
        idx = self.case(case_id)
        if idx is not None and idx.counted_seq is not None:
            self.subtract_counted(idx.counted_seq)
        evaluated_at = idx.evaluated_at if idx else (ref.at or ref.recorded_at)
        self.set_case(case_id, CaseRow(None, evaluated_at, True))

    def fix(self, case_id: UUID, ref: Entry) -> None:
        """La decision fija la recomendacion que referencia: si no era la contada, resta esa y suma la referenciada."""
        idx = self.case(case_id)
        assert ref.at is not None  # noqa: S101 - valid_recommendation
        if idx is not None and idx.counted_seq == ref.seq:
            self.set_case(case_id, CaseRow(idx.counted_seq, idx.evaluated_at, True))
            return
        if idx is not None and idx.counted_seq is not None:
            self.subtract_counted(idx.counted_seq)
        self.add(ref, "modelo", ref.day, str(ref.extra["outcome"]), "-", 1)
        self.set_case(case_id, CaseRow(ref.seq, ref.at, True))

    # --- escritura ---------------------------------------------------------------------------------------------------------

    def flush(self) -> None:
        cur = self.conn.cursor()
        for key, delta in self.daily.items():
            pop, version, day, attribute, group, band, result, decision = key
            if delta > 0:
                cur.execute(
                    'INSERT INTO monitoring_daily (population, model_version_id, day, attribute, "group", band, result, decision, count) '
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) "
                    'ON CONFLICT (population, model_version_id, day, attribute, "group", band, result, decision) '
                    "DO UPDATE SET count = monitoring_daily.count + EXCLUDED.count",
                    (*key, delta),
                )
            elif delta < 0:
                where = (
                    'population = %s AND model_version_id = %s AND day = %s AND attribute = %s AND "group" = %s '
                    "AND band = %s AND result = %s AND decision = %s"
                )
                cur.execute(f"UPDATE monitoring_daily SET count = count + %s WHERE {where}", (delta, *key))  # noqa: S608
                cur.execute(f"DELETE FROM monitoring_daily WHERE {where} AND count = 0", key)  # noqa: S608
        for (pop, version, when), (total, invalid) in self.totals.items():
            cur.execute(
                "INSERT INTO monitoring_entry_totals (population, model_version_id, day, total, invalid) "
                "VALUES (%s, %s, %s, %s, %s) ON CONFLICT (population, model_version_id, day) "
                "DO UPDATE SET total = monitoring_entry_totals.total + EXCLUDED.total, "
                "invalid = monitoring_entry_totals.invalid + EXCLUDED.invalid",
                (pop, version, when, total, invalid),
            )
        for seq, (pop, version, when, reason) in self.invalid.items():
            cur.execute(
                "INSERT INTO monitoring_invalid (seq, population, model_version_id, day, reason) VALUES (%s, %s, %s, %s, %s) "
                "ON CONFLICT (seq) DO NOTHING",
                (seq, pop, version, when, reason),
            )
        for case_id in self.dirty:
            row = self.cases[case_id]
            assert row is not None  # noqa: S101
            cur.execute(
                "INSERT INTO monitoring_case_index (case_id, counted_seq, evaluated_at, fixed_by_decision) VALUES (%s, %s, %s, %s) "
                "ON CONFLICT (case_id) DO UPDATE SET counted_seq = EXCLUDED.counted_seq, "
                "evaluated_at = EXCLUDED.evaluated_at, fixed_by_decision = EXCLUDED.fixed_by_decision",
                (case_id, row.counted_seq, row.evaluated_at, row.fixed_by_decision),
            )


def cutoff_day(now: datetime) -> date:
    return (now.astimezone(UTC) - timedelta(days=RETENTION_DAYS)).date()


def process_batch(
    conn: psycopg.Connection[tuple[Any, ...]], size: int, now: datetime, *, before_commit: Callable[[], None] | None = None
) -> tuple[int, int]:
    """Un lote en **una** transaccion: `(entradas leidas, marca nueva)`. La marca avanza junto con los conteos."""
    with conn.transaction():
        row = conn.execute("SELECT last_seq FROM monitoring_watermark WHERE id = 1 FOR UPDATE").fetchone()
        assert row is not None  # noqa: S101 - la migracion la crea y el reset no la borra
        last = int(row[0])
        entries = [_entry(r) for r in conn.execute(BATCH_SQL, (last, size)).fetchall()]
        if not entries:
            return 0, last
        batch = Batch(conn, cutoff_day(now))
        for entry in entries:
            batch.apply(entry)
        batch.flush()
        conn.execute("UPDATE monitoring_watermark SET last_seq = %s, updated_at = now() WHERE id = 1", (entries[-1].seq,))
        if before_commit is not None:
            before_commit()
    return len(entries), entries[-1].seq


def purge(conn: psycopg.Connection[tuple[Any, ...]], now: datetime) -> int:
    """Retencion de 180 dias, en su propia transaccion; en `monitoring_case_index`, por el `evaluated_at` guardado."""
    day = cutoff_day(now)
    start = datetime(day.year, day.month, day.day, tzinfo=UTC)
    removed = 0
    with conn.transaction():
        for table in ("monitoring_daily", "monitoring_entry_totals", "monitoring_invalid"):
            removed += conn.execute(f"DELETE FROM {table} WHERE day < %s", (day,)).rowcount  # noqa: S608
        removed += conn.execute("DELETE FROM monitoring_case_index WHERE evaluated_at < %s", (start,)).rowcount
    return removed


def lag_seconds(conn: psycopg.Connection[tuple[Any, ...]], now: datetime) -> tuple[int, int]:
    """`(marca, atraso)`: 0 si la marca es la cabeza; si no, `now - recorded_at` de la entrada `last_seq + 1` (BR-U3-17)."""
    with conn.transaction():
        row = conn.execute("SELECT last_seq FROM monitoring_watermark WHERE id = 1").fetchone()
        assert row is not None  # noqa: S101
        last = int(row[0])
        nxt = conn.execute("SELECT recorded_at FROM registry_entries WHERE seq > %s ORDER BY seq LIMIT 1", (last,)).fetchone()
    return last, 0 if nxt is None else max(0, int((now - nxt[0]).total_seconds()))


@dataclass(frozen=True)
class RunReport:
    batches: int
    entries: int
    watermark: int
    reached_head: bool
    lag_seconds: int
    purged: int

    def as_json(self) -> str:
        return json.dumps(self.__dict__, sort_keys=True)


def _utc_now() -> datetime:
    return datetime.now(UTC)


def take_rebuild_lock(conn: psycopg.Connection[tuple[Any, ...]]) -> None:
    """`pg_try_advisory_lock(REBUILD_LOCK)` de sesion: si ya esta tomado, `RebuildInProgress` sin tocar nada."""
    row = conn.execute("SELECT pg_try_advisory_lock(%s)", (REBUILD_LOCK,)).fetchone()
    if not row or not row[0]:
        raise RebuildInProgress("otra reconstruccion del agregador esta en curso")


def run(
    dsn: str,
    *,
    until_head: bool = False,
    seconds: float = RUN_SECONDS,
    size: int = BATCH_SIZE,
    clock: Callable[[], datetime] = _utc_now,
    monotonic: Callable[[], float] = time.monotonic,
    before_commit: Callable[[], None] | None = None,
) -> RunReport:
    """Itera lotes hasta la cabeza o `seconds` (sin tope con `until_head`, que ademas toma el lock de la reconstruccion)."""
    started = monotonic()
    batches = entries = 0
    reached = False
    with psycopg.connect(dsn, connect_timeout=5, autocommit=True) as conn:
        if until_head:
            take_rebuild_lock(conn)
        while True:
            count, _ = process_batch(conn, size, clock(), before_commit=before_commit)
            batches += count > 0
            entries += count
            if count < size:
                reached = True
                break
            if not until_head and monotonic() - started >= seconds:
                break
        removed = purge(conn, clock())
        mark, lag = lag_seconds(conn, clock())
    return RunReport(batches, entries, mark, reached, lag, removed)


def reset(dsn: str, *, clock: Callable[[], datetime] = _utc_now) -> int:
    """`aggregator reset` (rol `registry_migrator`): vacia las cuatro tablas y deja la marca justo antes de la primera entrada de los
    ultimos 181 dias. Devuelve la marca. Toma antes el *advisory lock* y la fila de la marca con `FOR UPDATE` (espera al lote en curso)."""
    since = clock() - timedelta(days=RESET_DAYS)
    with psycopg.connect(dsn, connect_timeout=5, autocommit=True) as conn:
        take_rebuild_lock(conn)
        with conn.transaction():
            conn.execute("SELECT last_seq FROM monitoring_watermark WHERE id = 1 FOR UPDATE")
            conn.execute(
                "TRUNCATE monitoring_daily, monitoring_entry_totals, monitoring_case_index, monitoring_invalid"
            )
            first = conn.execute("SELECT min(seq) FROM registry_entries WHERE recorded_at >= %s", (since,)).fetchone()
            if first is not None and first[0] is not None:
                mark = max(int(first[0]) - 1, 0)
            else:  # nada dentro de la ventana: no hay nada que contar
                head = conn.execute("SELECT max(seq) FROM registry_entries").fetchone()
                mark = int(head[0]) if head and head[0] is not None else 0
            conn.execute("UPDATE monitoring_watermark SET last_seq = %s, updated_at = now() WHERE id = 1", (mark,))
    return mark
