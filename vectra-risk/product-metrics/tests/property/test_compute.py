"""PBT-U11-01, 03, 06 y 07 sobre `compute` (business-logic-model §3).

Los oraculos cuentan **por definicion** (BR-U11-03, 04, 05, 07) sobre las `Spec` de negocio; no reusan `compute` ni `model`.
Las instantaneas se generan plegando entradas generadas (P-1, opcion a).
"""

from __future__ import annotations

import random
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from fractions import Fraction

from entries import (
    NOW,
    Spec,
    month_bounds,
    moments,
    render,
    spec_lists,
)
from hypothesis import given
from hypothesis import strategies as st
from vectra_product.compute import BusinessMetrics, PeriodKey, compute, snapshot_of
from vectra_product.model import Decision, InvalidEntry, parse_entry
from vectra_product.params import Params

PARAMS = Params(0.6, 3, 50, 1.0, 1.0, 0.8, 0.7, None)
KINDS = {"sigue": "sustentada", "se_aparta": "cambiada", "resuelve_revision": "revision_resuelta"}


def build(specs: list[Spec], now: datetime) -> BusinessMetrics:
    parsed = [parse_entry(spec.seq, render(spec)) for spec in specs]
    return compute(snapshot_of(parsed, now), PARAMS, now)


def periods(now: datetime) -> dict[PeriodKey, tuple[date, date]]:
    yesterday = now.date() - timedelta(days=1)
    out = {
        PeriodKey("day"): (yesterday, yesterday),
        PeriodKey("30d"): (yesterday - timedelta(days=29), yesterday),
    }
    if now.day > 1:
        out[PeriodKey("month_to_date")] = (now.date().replace(day=1), yesterday)
    for label, first, last in month_bounds(now):
        out[PeriodKey("month", label)] = (first, last)
    return out


def counted(specs: list[Spec], first: date, last: date) -> list[Spec]:
    return [s for s in specs if s.valid and first <= s.decided.astimezone(UTC).date() <= last]


# --- PBT-U11-01 -------------------------------------------------------------------------------------------------------


@given(data=st.data())
def test_pbt_u11_01_counts_match_the_oracle_and_ratios_are_sound(data: st.DataObject) -> None:
    now = data.draw(moments)
    specs = data.draw(spec_lists(now))
    result = build(specs, now)

    assert set(result.periods) == set(
        periods(now)
    )  # el dia 1 no hay `month_to_date`; siempre los 6 meses cerrados
    for key, (first, last) in periods(now).items():
        chosen = counted(specs, first, last)
        attributable = [s for s in chosen if s.rec is not None]
        period = result.periods[key]

        # North Star: numerador = vista previa y factores distintos de ["ninguno"]; denominador = atribuibles.
        expected_cells: dict[tuple[str, str, str], list[int]] = {}
        expected_breakdown: dict[tuple[str, str, str], int] = {}
        expected_sustained: dict[tuple[str, str], list[int]] = {}
        for s in attributable:
            assert s.rec is not None
            cell = expected_cells.setdefault((s.rec.channel, s.rec.outcome, s.rec.model), [0, 0])
            cell[1] += 1
            pair = expected_sustained.setdefault((s.rec.channel, s.rec.outcome), [0, 0])
            pair[1] += 1
            if s.viewed and s.factors != ("ninguno",):
                cell[0] += 1
                bkey = (KINDS[s.decision], s.rec.channel, s.rec.outcome)
                expected_breakdown[bkey] = expected_breakdown.get(bkey, 0) + 1
            if s.decision == "sigue":
                pair[0] += 1
        got_cells = {k: [r.numerator, r.denominator] for k, r in period.north_star.cells.items()}
        assert got_cells == expected_cells
        assert dict(period.north_star.breakdown) == expected_breakdown
        assert {
            k: [r.numerator, r.denominator] for k, r in period.sustained.cells.items()
        } == expected_sustained

        total = period.north_star.total
        assert total.denominator == len(attributable)
        assert total.numerator == sum(1 for s in attributable if s.viewed and s.factors != ("ninguno",))
        assert period.sustained.total.numerator == sum(1 for s in attributable if s.decision == "sigue")

        # Una decision no atribuible nunca entra en un cociente y se cuenta aparte.
        if key.period == "month":
            assert period.unattributable is None
        else:
            assert period.unattributable == sum(1 for s in chosen if s.rec is None)

        for ratio in [
            total,
            period.sustained.total,
            *period.north_star.cells.values(),
            *period.sustained.cells.values(),
        ]:
            assert 0 <= ratio.numerator <= ratio.denominator or ratio.denominator == 0
            if ratio.denominator == 0:
                assert ratio.rate is None  # nunca 0 cuando no hay decisiones
            else:
                assert ratio.rate is not None and 0.0 <= ratio.rate <= 1.0
                assert ratio.rate == ratio.numerator / ratio.denominator


@given(data=st.data())
def test_pbt_u11_01_invalid_and_degraded_follow_the_definition(data: st.DataObject) -> None:
    now = data.draw(moments)
    specs = data.draw(spec_lists(now))
    result = build(specs, now)
    yesterday = now.date() - timedelta(days=1)
    in_window = [s for s in specs if yesterday - timedelta(days=29) <= s.decided.date() <= yesterday]
    invalid = [s for s in in_window if not s.valid]
    assert result.invalid_entries == len(invalid)
    assert result.degraded == (
        len(in_window) > 0 and Fraction(len(invalid), len(in_window)) > Fraction(1, 100)
    )


# --- PBT-U11-03 -------------------------------------------------------------------------------------------------------


@given(data=st.data())
def test_pbt_u11_03_order_duplicates_and_recorded_at_do_not_matter(data: st.DataObject) -> None:
    now = data.draw(moments)
    specs = data.draw(spec_lists(now))
    baseline = build(specs, now)

    # Permutaciones y duplicados (mismo `seq`).
    seed = data.draw(st.integers(0, 2**32))
    shuffled = specs + [s for s in specs if data.draw(st.booleans())]
    random.Random(seed).shuffle(shuffled)
    assert build(shuffled, now) == baseline

    # `recorded_at` hasta 24 h despues del momento de negocio: solo cuenta el margen de 5 min (BR-U11-10), que respeta `valid`.
    moved = [s if not s.valid else replace(s, delay_s=data.draw(st.integers(-300, 86400))) for s in specs]
    assert build(moved, now) == baseline


# --- PBT-U11-06 -------------------------------------------------------------------------------------------------------


def nearest_rank(values: list[int], percent: int) -> int:
    """El menor valor con al menos `percent` % de las muestras iguales o por debajo (definicion, sin ordenar ni indexar)."""
    need = Fraction(percent, 100) * len(values)
    return min(v for v in values if sum(1 for x in values if x <= v) >= need)


@given(data=st.data())
def test_pbt_u11_06_origination_only_standard_cases_with_oracle_quantiles(data: st.DataObject) -> None:
    now = data.draw(moments)
    specs = data.draw(spec_lists(now))
    result = build(specs, now)
    yesterday = now.date() - timedelta(days=1)
    first = now.date() - timedelta(days=35)

    expected: dict[date, list[int]] = {}
    for s in specs:
        rec = s.rec
        if not s.valid or rec is None:
            continue
        # Caso estandar (BR-U11-05): ni `manual` ni `revision_requerida`, y `first_evaluation` (no basta `attempt = 1`).
        if rec.channel == "manual" or rec.outcome == "revision_requerida" or not rec.first_evaluation:
            continue
        # Solo cuentan las decisiones que el estado conserva (35 dias por `decided_at`).
        if s.decided.date() < first:
            continue
        day = rec.evaluated.astimezone(UTC).date()
        if first <= day <= yesterday:
            expected.setdefault(day, []).append(rec.elapsed_s)

    assert set(result.origination) == set(expected)
    for day, values in expected.items():
        out = result.origination[day]
        assert out.count == len(values)
        assert (out.p50, out.p80, out.p95) == tuple(float(nearest_rank(values, p)) for p in (50, 80, 95))
        assert out.under_target_ratio == sum(1 for v in values if v < 3600) / len(values)


# --- PBT-U11-07 -------------------------------------------------------------------------------------------------------


@given(data=st.data())
def test_pbt_u11_07_cuts_add_up_to_the_total_and_ratios_are_sums_of_counts(data: st.DataObject) -> None:
    now = data.draw(moments)
    specs = data.draw(spec_lists(now))
    result = build(specs, now)
    for period in result.periods.values():
        north, sustained = period.north_star, period.sustained
        cells = north.cells.values()
        # La suma de los conteos por celda es el conteo del total `all`, y la razon total es sum(num) / sum(den).
        assert north.total.numerator == sum(c.numerator for c in cells)
        assert north.total.denominator == sum(c.denominator for c in cells)
        assert north.total.numerator == sum(north.breakdown.values())
        for cut, groups in (
            ("channel", north.by_channel),
            ("outcome", north.by_outcome),
            ("model", north.by_model),
        ):
            assert sum(r.numerator for r in groups.values()) == north.total.numerator, cut
            assert sum(r.denominator for r in groups.values()) == north.total.denominator, cut
        for index, groups in ((0, north.by_channel), (1, north.by_outcome), (2, north.by_model)):
            for value, ratio in groups.items():
                members = [c for k, c in north.cells.items() if k[index] == value]
                assert (ratio.numerator, ratio.denominator) == (
                    sum(m.numerator for m in members),
                    sum(m.denominator for m in members),
                )
        scells = sustained.cells.values()
        assert sustained.total.numerator == sum(c.numerator for c in scells)
        assert sustained.total.denominator == sum(c.denominator for c in scells)
        assert sustained.total.denominator == north.total.denominator  # mismo denominador: las atribuibles
        for index, groups in ((0, sustained.by_channel), (1, sustained.by_outcome)):
            assert sum(r.denominator for r in groups.values()) == sustained.total.denominator
            for value, ratio in groups.items():
                members = [c for k, c in sustained.cells.items() if k[index] == value]
                assert (ratio.numerator, ratio.denominator) == (
                    sum(m.numerator for m in members),
                    sum(m.denominator for m in members),
                )
    view = result.explanation_view
    assert view.total.numerator == sum(c.numerator for c in view.cells.values())
    assert view.total.denominator == sum(c.denominator for c in view.cells.values())


def test_the_fixed_clock_constant_is_what_the_builders_assume() -> None:
    assert NOW == datetime(2026, 10, 6, 10, 0, tzinfo=UTC)
    assert isinstance(parse_entry(1, render(Spec(seq=1, decided=NOW - timedelta(days=1)))), Decision)
    assert isinstance(parse_entry(1, render(Spec(seq=1, decided=NOW, flaw="role"))), InvalidEntry)
