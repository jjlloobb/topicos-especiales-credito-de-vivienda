"""Paso 3: las pruebas de ejemplo de business-logic-model §3 que no dependen de E/S (PBT-10; US-503, 504, 505).

Reloj fijo: 6 de octubre de 2026, 10:00 UTC. «Ayer» es el 5 de octubre.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime

import pytest
from entries import NOW, RecSpec, Spec, day_at, render, specs_on
from registry_double import FakeToken, RegistryDouble
from vectra_common import process
from vectra_product.compute import BusinessMetrics, PeriodKey, Ratio, compute, snapshot_of
from vectra_product.model import InvalidEntry, parse_entry
from vectra_product.params import Params
from vectra_product.reader import Reader, build_client
from vectra_product.state import ProductState

PARAMS = Params(0.6, 3, 50, 1.0, 1.0, 0.8, 0.7, None)
DAY = PeriodKey("day")


def run(specs: list[Spec], now: datetime = NOW, params: Params = PARAMS) -> BusinessMetrics:
    parsed = [parse_entry(s.seq, render(s)) for s in specs]
    return compute(snapshot_of(parsed, now), params, now)


def viewed_burst(offset: int, total: int, viewed: int, first_seq: int, **changes: object) -> list[Spec]:
    """`total` decisiones atribuibles un dia, `viewed` con la explicacion vista."""
    return [
        *specs_on(offset, viewed, first_seq, viewed=True, **changes),
        *specs_on(offset, total - viewed, first_seq + viewed, viewed=False, **changes),
    ]


def test_north_star_example_10_decisions_gives_0_4_with_breakdown_2_1_1() -> None:
    specs = [
        *specs_on(1, 2, 1, decision="sigue", viewed=True, factors=("ingreso",)),
        *specs_on(1, 1, 3, decision="se_aparta", viewed=True, factors=("deuda",)),
        *specs_on(1, 1, 4, decision="resuelve_revision", viewed=True, factors=("ingreso", "deuda")),
        *specs_on(1, 3, 5, viewed=True, factors=("ninguno",)),
        *specs_on(1, 3, 8, viewed=False),
    ]
    north = run(specs).periods[DAY].north_star
    assert north.total == Ratio(4, 10)
    assert north.total.rate == 0.4
    kinds: dict[str, int] = {}
    for (kind, _channel, _outcome), count in north.breakdown.items():
        kinds[kind] = kinds.get(kind, 0) + count
    assert kinds == {"sustentada": 2, "cambiada": 1, "revision_resuelta": 1}


def test_a_day_without_decisions_publishes_no_rate_and_not_zero() -> None:
    result = run(specs_on(3, 5, 1))  # decisiones, pero ayer ninguna
    north = result.periods[DAY].north_star
    assert north.total == Ratio(0, 0)
    assert north.total.rate is None
    assert result.periods[DAY].sustained.total.rate is None
    assert north.cells == {} and north.by_channel == {}


def test_noise_3_days_at_0_5_with_n_50_and_f_0_6_gives_3() -> None:
    # Ventanas moviles de 7 dias: tres dias seguidos bajo el piso = tres ventanas consecutivas (las que terminan el 3, 4 y 5 de octubre).
    result = run(viewed_burst(3, 50, 25, 1))
    assert result.noise_days_below_floor == 3
    assert [w.decisions for w in list(result.explanation_view_daily.values())[-3:]] == [50, 50, 50]


def test_noise_3_days_at_50_decisions_each_also_gives_3() -> None:
    specs = [s for offset, first in ((3, 1), (2, 101), (1, 201)) for s in viewed_burst(offset, 50, 25, first)]
    assert run(specs).noise_days_below_floor == 3


def test_the_same_3_windows_with_40_decisions_do_not_add() -> None:
    result = run(viewed_burst(3, 40, 20, 1))
    assert [w.decisions for w in list(result.explanation_view_daily.values())[-3:]] == [40, 40, 40]
    assert result.noise_days_below_floor == 0


def test_with_7_day_windows_40_decisions_on_each_of_3_days_reach_n_from_the_second_day() -> None:
    """Lectura literal de «40 decisiones cada uno»: las ventanas de los dias 2 y 3 ya suman 80 y 120 (>= N)."""
    specs = [s for offset, first in ((3, 1), (2, 101), (1, 201)) for s in viewed_burst(offset, 40, 20, first)]
    assert run(specs).noise_days_below_floor == 2


def test_a_healthy_day_stops_the_count() -> None:
    healthy = viewed_burst(5, 60, 60, 1000)  # el 1 de octubre: tasa 1.0
    low = [s for offset, first in ((3, 1), (2, 101)) for s in viewed_burst(offset, 50, 10, first)]
    assert (
        run([*healthy, *low]).noise_days_below_floor == 2
    )  # las ventanas del 5 y 4 (en 4 de octubre ya entran 60 sanas)... ver abajo


@pytest.mark.parametrize(
    "changes",
    [
        {"channel": "manual"},
        {"attempt": 2, "first_evaluation": False},
        {
            "attempt": 1,
            "first_evaluation": False,
        },  # descongelado: `attempt` vuelve a 1 pero ya no es la primera evaluacion
        {"outcome": "revision_requerida"},
    ],
)
def test_non_standard_cases_stay_out_of_origination(changes: dict[str, object]) -> None:
    rec = replace(RecSpec(), **changes)
    result = run(specs_on(1, 1, 1, rec=rec))
    assert result.origination == {}
    assert result.periods[DAY].north_star.total.denominator == 1  # siguen siendo decisiones atribuibles


def test_standard_cases_enter_origination_by_the_day_of_evaluated_at() -> None:
    specs = [
        *specs_on(1, 2, 1, rec=RecSpec(elapsed_s=600, evaluated=day_at(1, 8))),
        *specs_on(1, 1, 3, rec=RecSpec(elapsed_s=7200, evaluated=day_at(1, 9))),
        *specs_on(1, 1, 4, rec=RecSpec(channel="manual", elapsed_s=5)),
    ]
    out = run(specs).origination[date(2026, 10, 5)]
    assert (out.count, out.p50, out.p80, out.p95) == (3, 600.0, 7200.0, 7200.0)
    assert out.under_target_ratio == pytest.approx(2 / 3)


def test_day_at_10_utc_does_not_include_todays_decisions() -> None:
    today = Spec(seq=1, decided=NOW.replace(hour=8))
    yesterday = Spec(seq=2, decided=day_at(1, 23))
    result = run([today, yesterday])
    assert result.periods[DAY].north_star.total == Ratio(1, 1)
    assert result.periods[PeriodKey("30d")].north_star.total == Ratio(1, 1)
    assert result.periods[PeriodKey("month_to_date")].north_star.total == Ratio(1, 1)
    assert result.periods[DAY].unattributable == 0


def test_on_day_1_there_is_no_month_to_date_and_month_includes_the_whole_previous_month() -> None:
    now = datetime(2026, 11, 1, 10, 0, tzinfo=UTC)
    specs = [
        Spec(seq=1, decided=datetime(2026, 10, 1, 0, 0, 1, tzinfo=UTC)),
        Spec(seq=2, decided=datetime(2026, 10, 31, 23, 59, 59, tzinfo=UTC)),
        Spec(seq=3, decided=datetime(2026, 9, 30, 23, 59, tzinfo=UTC)),
        Spec(
            seq=4, decided=datetime(2026, 4, 30, 12, tzinfo=UTC)
        ),  # el 7.o mes atras: ya no es de los 6 cerrados
    ]
    result = run(specs, now)
    assert PeriodKey("month_to_date") not in result.periods
    months = [key.month for key in result.periods if key.period == "month"]
    assert months == ["2026-05", "2026-06", "2026-07", "2026-08", "2026-09", "2026-10"]
    assert result.periods[PeriodKey("month", "2026-10")].north_star.total == Ratio(2, 2)
    assert result.periods[PeriodKey("month", "2026-09")].north_star.total == Ratio(1, 1)
    assert result.periods[PeriodKey("month", "2026-05")].north_star.total == Ratio(0, 0)
    assert result.periods[DAY].north_star.total == Ratio(1, 1)  # ayer, el 31 de octubre


def test_decided_at_3_min_after_recorded_at_is_valid_and_10_min_after_is_excluded() -> None:
    assert not isinstance(parse_entry(1, render(Spec(seq=1, decided=day_at(1), delay_s=-180))), InvalidEntry)
    assert isinstance(parse_entry(2, render(Spec(seq=2, decided=day_at(1), delay_s=-600))), InvalidEntry)
    assert isinstance(parse_entry(3, render(Spec(seq=3, decided=day_at(1), delay_s=-301))), InvalidEntry)
    assert not isinstance(parse_entry(4, render(Spec(seq=4, decided=day_at(1), delay_s=-300))), InvalidEntry)
    result = run([Spec(seq=1, decided=day_at(1), delay_s=-180), Spec(seq=2, decided=day_at(1), delay_s=-600)])
    assert result.periods[DAY].north_star.total.denominator == 1 and result.invalid_entries == 1


def test_actor_role_cro_is_excluded() -> None:
    result = run([Spec(seq=1, decided=day_at(1), flaw="role"), Spec(seq=2, decided=day_at(1))])
    assert result.periods[DAY].north_star.total.denominator == 1
    assert result.invalid_entries == 1


def test_an_unknown_decision_is_excluded_and_counted() -> None:
    result = run([Spec(seq=1, decided=day_at(1), flaw="decision")])
    assert result.invalid_entries == 1
    assert result.periods[DAY].north_star.total.denominator == 0
    assert result.degraded  # 1 de 1 excluida


def test_2_percent_invalid_entries_degrade_and_1_percent_does_not() -> None:
    bad = lambda first, n: specs_on(1, n, first, flaw="role")  # noqa: E731
    assert run([*specs_on(1, 98, 1), *bad(1000, 2)]).degraded is True
    assert run([*specs_on(1, 99, 1), *bad(1000, 1)]).degraded is False  # exactamente 1 %: no supera
    assert run([*specs_on(1, 100, 1)]).degraded is False
    assert run([]).degraded is False


def test_unattributable_decisions_are_counted_apart_and_never_enter_a_ratio() -> None:
    result = run([*specs_on(1, 2, 1), *specs_on(1, 3, 10, rec=None)])
    period = result.periods[DAY]
    assert period.unattributable == 3
    assert period.north_star.total == Ratio(2, 2)
    assert period.sustained.total == Ratio(2, 2)


@pytest.mark.asyncio
async def test_a_late_september_decision_registered_in_october_changes_month_2026_09_on_the_next_recompute() -> (
    None
):
    """NFR-U11-11, sobre `state` y `compute` con reloj fijo: el mes cerrado se republica cada dia."""
    process.init("service")
    late = Spec(
        seq=2, decided=datetime(2026, 9, 30, 22, 0, tzinfo=UTC), delay_s=5 * 86400
    )  # registrada el 5 de octubre
    earlier = Spec(seq=1, decided=datetime(2026, 9, 15, 12, tzinfo=UTC))
    double = RegistryDouble([render(earlier)])
    clock = [datetime(2026, 10, 5, 2, 30, tzinfo=UTC)]
    client = build_client("http://registry.invalid", token_source=FakeToken(), transport=double.transport())
    state = ProductState(Reader(client), lambda: clock[0])
    await state.full_pass()
    september = PeriodKey("month", "2026-09")
    snapshot = state.snapshot()
    assert snapshot is not None
    assert compute(snapshot, PARAMS, clock[0]).periods[september].north_star.total == Ratio(1, 1)

    double.add([render(late)])  # llega el 5 de octubre, con `decided_at` del 30 de septiembre
    clock[0] = datetime(2026, 10, 6, 2, 30, tzinfo=UTC)
    await state.full_pass()  # la recomputacion del 6 de octubre
    snapshot = state.snapshot()
    assert snapshot is not None
    assert compute(snapshot, PARAMS, clock[0]).periods[september].north_star.total == Ratio(2, 2)
