"""`compute(snapshot, params, now) -> BusinessMetrics` (BR-U11-01..10; domain-entities §3). Funcion pura, sin E/S.

Firma real (P-1, opcion a): la tarea pedia `compute(entries, params, now)`, pero los meses cerrados no viven como entradas
(NFR-U11-12), asi que `entries` es la `Snapshot` de `state`: las decisiones de 35 dias y los contadores de los meses. El plegado de
una decision a esos contadores (`fold`, `absorb`) tambien vive aqui, sin E/S, y `state` lo usa al leer cada pagina.

Todos los periodos son dias UTC **completos** y sin el dia en curso (BR-U11-08).
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping, MutableMapping
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Final, NamedTuple

from vectra_product import config
from vectra_product.model import (
    BRK,
    DEN,
    NUM,
    OUTCOME_NAMES,
    RESUELVE_REVISION,
    SE_APARTA,
    SIGUE,
    SUS,
    VIEW,
    Counts,
    Decision,
    InvalidEntry,
    Params,
    Snapshot,
)
from vectra_product.noise import DayWindow, days_below_floor

#: Desglose de la North Star (domain-entities §5).
BREAKDOWN_KINDS: Final = {SIGUE: "sustentada", SE_APARTA: "cambiada", RESUELVE_REVISION: "revision_resuelta"}
ALL: Final = "all"
QUANTILES: Final = ((50, "0.5"), (80, "0.8"), (95, "0.95"))


class PeriodKey(NamedTuple):
    period: str  # `day`, `30d`, `month_to_date` o `month`
    month: str | None = None  # `AAAA-MM`, solo con `period="month"`


@dataclass(frozen=True, slots=True)
class Ratio:
    numerator: int
    denominator: int

    @property
    def rate(self) -> float | None:
        """Ausente (no 0) si el denominador es 0 (BR-U11-03)."""
        return self.numerator / self.denominator if self.denominator else None


@dataclass(frozen=True, slots=True)
class NorthStar:
    """BR-U11-03. Conteos con todos los cortes; razones solo en el total y por un corte (BR-U11-08)."""

    cells: Mapping[tuple[str, str, str], Ratio]  # (channel, outcome, model_version_id)
    breakdown: Mapping[tuple[str, str, str], int]  # (kind, channel, outcome)
    total: Ratio
    by_channel: Mapping[str, Ratio]
    by_outcome: Mapping[str, Ratio]
    by_model: Mapping[str, Ratio]


@dataclass(frozen=True, slots=True)
class Sustained:
    """BR-U11-04: decisiones `sigue` sobre las atribuibles."""

    cells: Mapping[tuple[str, str], Ratio]  # (channel, outcome)
    total: Ratio
    by_channel: Mapping[str, Ratio]
    by_outcome: Mapping[str, Ratio]


@dataclass(frozen=True, slots=True)
class PeriodMetrics:
    north_star: NorthStar
    sustained: Sustained
    unattributable: int | None  # sin dato en los meses cerrados (no hay serie con `month`)


@dataclass(frozen=True, slots=True)
class ExplanationView:
    """Tasa de consulta de la ventana de 7 dias que termina ayer (BR-U11-07)."""

    cells: Mapping[str, Ratio]  # por `channel`
    total: Ratio


@dataclass(frozen=True, slots=True)
class OriginationDay:
    """BR-U11-05: casos estandar cuya recomendacion se evaluo ese dia."""

    count: int
    p50: float
    p80: float
    p95: float
    under_target_ratio: float


@dataclass(frozen=True, slots=True)
class BusinessMetrics:
    periods: Mapping[PeriodKey, PeriodMetrics]
    explanation_view: ExplanationView
    explanation_view_daily: Mapping[date, DayWindow]  # ventana de 7 dias que termina ese dia
    noise_days_below_floor: int
    origination: Mapping[date, OriginationDay]
    invalid_entries: int  # ventana de 30 dias
    degraded: bool


# --- plegado: decision -> contadores (puro; lo usa `state` al leer cada pagina) ---------------------------------------


def month_index(day: int) -> int:
    """Indice de mes del ordinal de un dia: `ano * 12 + mes - 1`."""
    parsed = date.fromordinal(day)
    return parsed.year * 12 + parsed.month - 1


def month_label(index: int) -> str:
    return f"{index // 12:04d}-{index % 12 + 1:02d}"


def fold(counts: Counts, decision: Decision) -> None:
    """Suma una decision **atribuible** en los contadores de un dia o de un mes. Las no atribuibles no entran en ningun cociente
    (BR-U11-01): quien llama no se las pasa."""
    channel, outcome = decision.channel, decision.outcome
    counts[(DEN, channel, outcome, decision.model)] += 1
    if decision.viewed:
        counts[(VIEW, channel, outcome, "")] += 1
        if not decision.no_factors:
            counts[(NUM, channel, outcome, decision.model)] += 1
            counts[(BRK, channel, outcome, decision.decision)] += 1
    if decision.decision == SIGUE:
        counts[(SUS, channel, outcome, "")] += 1


def first_relevant_month(today: date) -> int:
    """El mas viejo de los 6 meses cerrados anteriores al mes en curso."""
    return today.year * 12 + today.month - 1 - config.CLOSED_MONTHS


def absorb(
    entries: MutableMapping[int, Decision | InvalidEntry],
    months: MutableMapping[int, Counts],
    entry: Decision | InvalidEntry,
    today: date,
) -> None:
    """Pliega una entrada nueva: sus contadores de mes y, si es de los ultimos 35 dias, el estado de decisiones (NFR-U11-12).

    El mes de una decision se pliega aunque todavia no sea de los cerrados: el reloj avanza entre pasadas y el mes en curso se
    cierra sin que nadie lo relea. Lo que no se pliega nunca es lo mas viejo que el sexto mes cerrado.
    """
    if isinstance(entry, Decision) and entry.attributable:
        index = month_index(entry.day)
        if index >= first_relevant_month(today):
            fold(months.setdefault(index, Counter()), entry)
    if entry.day is None or entry.day >= today.toordinal() - config.STATE_WINDOW_DAYS:
        entries[entry.seq] = entry


def discard_old(
    entries: MutableMapping[int, Decision | InvalidEntry], months: MutableMapping[int, Counts], today: date
) -> None:
    """Descarta lo que ya no se usa: decisiones de mas de 35 dias y meses mas viejos que el sexto cerrado."""
    floor = today.toordinal() - config.STATE_WINDOW_DAYS
    for seq in [seq for seq, entry in entries.items() if entry.day is not None and entry.day < floor]:
        del entries[seq]
    oldest = first_relevant_month(today)
    for index in [index for index in months if index < oldest]:
        del months[index]


def snapshot_of(entries: Iterable[Decision | InvalidEntry], now: datetime) -> Snapshot:
    """La instantanea de una lectura completa sobre `entries` (sin repetir un `seq`): oraculo de equivalencia de PBT-U11-02."""
    today = now.astimezone(UTC).date()
    kept: dict[int, Decision | InvalidEntry] = {}
    months: dict[int, Counts] = {}
    seen: set[int] = set()
    for entry in entries:
        if entry.seq not in seen:
            seen.add(entry.seq)
            absorb(kept, months, entry, today)
    return Snapshot(kept, months)


# --- agregacion --------------------------------------------------------------------------------------------------------


def _group[K: tuple[str, ...]](cells: Mapping[K, tuple[int, int]], position: int) -> dict[str, Ratio]:
    """La razon por un solo corte: la suma de los conteos de todas las celdas con ese valor, nunca un promedio de razones."""
    sums: dict[str, list[int]] = {}
    for cell, (numerator, denominator) in cells.items():
        pair = sums.setdefault(cell[position], [0, 0])
        pair[0] += numerator
        pair[1] += denominator
    return {value: Ratio(*pair) for value, pair in sums.items()}


def _total[K: tuple[str, ...]](cells: Mapping[K, tuple[int, int]]) -> Ratio:
    return Ratio(sum(n for n, _ in cells.values()), sum(d for _, d in cells.values()))


def _period(counts: Counts, unattributable: int | None) -> PeriodMetrics:
    north: dict[tuple[str, str, str], list[int]] = {}
    sustained: dict[tuple[str, str], list[int]] = {}
    breakdown: dict[tuple[str, str, str], int] = {}
    for (tag, channel, outcome, last), count in counts.items():
        name = OUTCOME_NAMES[outcome]
        if tag == DEN:
            north.setdefault((channel, name, str(last)), [0, 0])[1] += count
            sustained.setdefault((channel, name), [0, 0])[1] += count
        elif tag == NUM:
            north.setdefault((channel, name, str(last)), [0, 0])[0] += count
        elif tag == BRK:
            key = (BREAKDOWN_KINDS[int(last)], channel, name)
            breakdown[key] = breakdown.get(key, 0) + count
        elif tag == SUS:
            sustained.setdefault((channel, name), [0, 0])[0] += count
    north_pairs = {cell: (pair[0], pair[1]) for cell, pair in north.items()}
    sustained_pairs = {cell: (pair[0], pair[1]) for cell, pair in sustained.items()}
    return PeriodMetrics(
        NorthStar(
            {cell: Ratio(*pair) for cell, pair in north_pairs.items()},
            breakdown,
            _total(north_pairs),
            _group(north_pairs, 0),
            _group(north_pairs, 1),
            _group(north_pairs, 2),
        ),
        Sustained(
            {cell: Ratio(*pair) for cell, pair in sustained_pairs.items()},
            _total(sustained_pairs),
            _group(sustained_pairs, 0),
            _group(sustained_pairs, 1),
        ),
        unattributable,
    )


def _quantile(sorted_values: list[float], percent: int) -> float:
    """Rango mas cercano: el menor valor con al menos `percent` % de las muestras por debajo o iguales."""
    rank = -(-len(sorted_values) * percent // 100)
    return sorted_values[rank - 1]


def _origination(samples: Mapping[int, list[float]], target_seconds: float) -> dict[date, OriginationDay]:
    out: dict[date, OriginationDay] = {}
    for day in sorted(samples):
        values = sorted(samples[day])
        p50, p80, p95 = (_quantile(values, percent) for percent, _ in QUANTILES)
        under = sum(1 for value in values if value < target_seconds)
        out[date.fromordinal(day)] = OriginationDay(len(values), p50, p80, p95, under / len(values))
    return out


def compute(snapshot: Snapshot, params: Params, now: datetime) -> BusinessMetrics:
    today = now.astimezone(UTC).date()
    ordinal = today.toordinal()
    yesterday = ordinal - 1
    floor = ordinal - config.STATE_WINDOW_DAYS  # lo mas viejo que el estado garantiza completo
    window_30d = yesterday - config.PERIOD_30D_DAYS + 1

    by_day: dict[int, Counts] = {}
    unattributable: Counter[int] = Counter()
    samples: dict[int, list[float]] = {}
    valid_30d = 0
    invalid_30d = 0
    for entry in snapshot.entries.values():
        if isinstance(entry, InvalidEntry):
            if entry.day is None or window_30d <= entry.day <= yesterday:
                invalid_30d += 1
            continue
        if entry.standard and floor <= entry.eval_day <= yesterday:
            samples.setdefault(entry.eval_day, []).append(entry.elapsed)
        if not floor <= entry.day <= yesterday:
            continue
        if entry.day >= window_30d:
            valid_30d += 1
        if entry.attributable:
            fold(by_day.setdefault(entry.day, Counter()), entry)
        else:
            unattributable[entry.day] += 1

    def over(first: int, last: int) -> tuple[Counts, int]:
        counts: Counts = Counter()
        missing = 0
        for day in range(first, last + 1):
            counts.update(by_day.get(day, {}))
            missing += unattributable[day]
        return counts, missing

    periods: dict[PeriodKey, PeriodMetrics] = {}
    periods[PeriodKey("day")] = _period(*over(yesterday, yesterday))
    periods[PeriodKey("30d")] = _period(*over(window_30d, yesterday))
    if today.day > 1:  # el dia 1 de cada mes no se publica `month_to_date`
        periods[PeriodKey("month_to_date")] = _period(*over(today.replace(day=1).toordinal(), yesterday))
    current = today.year * 12 + today.month - 1
    for index in range(current - config.CLOSED_MONTHS, current):
        periods[PeriodKey("month", month_label(index))] = _period(snapshot.months.get(index, Counter()), None)

    # Tasa de consulta: ventana de 7 dias por dia, desde el primer dia con la ventana completa en el estado.
    span = config.VIEW_WINDOW_DAYS
    viewed_by_day = {day: sum(v for k, v in c.items() if k[0] == VIEW) for day, c in by_day.items()}
    decisions_by_day = {day: sum(v for k, v in c.items() if k[0] == DEN) for day, c in by_day.items()}
    daily: dict[date, DayWindow] = {}
    for end in range(floor + span - 1, yesterday + 1):
        days = range(end - span + 1, end + 1)
        daily[date.fromordinal(end)] = DayWindow(
            sum(viewed_by_day.get(day, 0) for day in days), sum(decisions_by_day.get(day, 0) for day in days)
        )
    week, _ = over(yesterday - span + 1, yesterday)
    channels: dict[str, list[int]] = {}
    for (tag, channel, _outcome, _last), count in week.items():
        if tag in (VIEW, DEN):
            channels.setdefault(channel, [0, 0])[0 if tag == VIEW else 1] += count
    cells = {channel: Ratio(*pair) for channel, pair in channels.items()}
    view = ExplanationView(
        cells, Ratio(sum(c.numerator for c in cells.values()), sum(c.denominator for c in cells.values()))
    )

    total_30d = valid_30d + invalid_30d
    return BusinessMetrics(
        periods=periods,
        explanation_view=view,
        explanation_view_daily=daily,
        noise_days_below_floor=days_below_floor(
            list(daily.values()), params.noise_floor, params.noise_min_decisions
        ),
        origination=_origination(samples, params.target_origination_hours * 3600),
        invalid_entries=invalid_30d,
        degraded=total_30d > 0 and invalid_30d / total_30d > config.DEGRADED_RATIO,
    )
