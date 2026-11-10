"""`window` (BR-U9-08, BR-U9-15): inicio de la ventana por version y rangos."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta, timezone

import pytest
from vectra_bias.window import Span, evaluated_versions, last_reactivation, version_ranges, window_start
from vectra_contracts.models.monitoring import VersionWindow

TODAY = date(2026, 11, 9)


def _utc(day: date, hour: int = 0, minute: int = 0) -> datetime:
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=UTC)


def test_the_ranges_with_30_days_are_those_of_br_u9_15():
    r = version_ranges(TODAY, 30, TODAY - timedelta(days=60), None)
    assert r.before == Span(TODAY - timedelta(days=36), TODAY - timedelta(days=7))
    assert r.after == Span(TODAY - timedelta(days=29), TODAY)
    assert r.last_7_days == Span(TODAY - timedelta(days=6), TODAY)
    assert r.human_after == r.after
    assert r.window_start == TODAY - timedelta(days=60)


def test_the_ranges_come_from_window_days_not_from_a_hard_coded_30():
    r = version_ranges(TODAY, 14, TODAY - timedelta(days=60), None)
    assert r.after == Span(TODAY - timedelta(days=13), TODAY)
    assert r.before == Span(TODAY - timedelta(days=20), TODAY - timedelta(days=7))


def test_a_reactivation_at_2350_utc_of_day_d_starts_the_window_on_d_plus_1():
    d = date(2026, 11, 5)
    assert window_start(d - timedelta(days=40), _utc(d, 23, 50)) == d + timedelta(days=1)
    r = version_ranges(TODAY, 30, d - timedelta(days=40), _utc(d, 23, 50))
    assert r.window_start == d + timedelta(days=1)
    assert r.after == Span(d + timedelta(days=1), TODAY)
    assert r.last_7_days == Span(d + timedelta(days=1), TODAY)


def test_the_reactivation_instant_is_taken_in_utc_whatever_its_offset():
    local = datetime(2026, 11, 5, 20, 0, tzinfo=timezone(timedelta(hours=-5)))  # 01:00 UTC del 6
    assert local.date() == date(2026, 11, 5)
    assert window_start(date(2026, 1, 1), local) == date(2026, 11, 7)


def test_the_window_never_starts_before_the_first_day_with_data():
    first = TODAY - timedelta(days=3)
    assert window_start(first, _utc(TODAY - timedelta(days=20))) == first


def test_with_fewer_than_7_days_of_data_before_is_without_data():
    for days in range(1, 8):
        first = TODAY - timedelta(days=days - 1)
        r = version_ranges(TODAY, 30, first, None)
        assert r.before is None, days
    assert version_ranges(TODAY, 30, TODAY - timedelta(days=8), None).before is not None


def test_a_reactivation_today_leaves_no_range_at_all():
    r = version_ranges(TODAY, 30, TODAY - timedelta(days=60), _utc(TODAY, 10))
    assert r.window_start == TODAY + timedelta(days=1)
    assert r.before is None
    assert r.after is None
    assert r.last_7_days is None
    assert r.human_after is None


@dataclass(frozen=True)
class _Resolution:
    action: str
    recorded_at: datetime


@dataclass(frozen=True)
class _Record:
    """Doble minimo de `FreezeRecord`: `last_reactivation` solo lee la version y las resoluciones."""

    model_version_id: str
    resolutions: list[_Resolution]


def _record(version: str, *actions: tuple[str, datetime]) -> _Record:
    return _Record(version, [_Resolution(a, t) for a, t in actions])


def test_investigar_then_reactivar_counts_the_reactivar():
    d = date(2026, 11, 3)
    record = _record("v1", ("reactivar", _utc(d, 8)), ("investigar", _utc(d + timedelta(days=2), 9)))
    assert last_reactivation([record])["v1"] == _utc(d, 8)  # la ultima `reactivar`, no la ultima resolucion
    later = _record("v1", ("investigar", _utc(d, 8)), ("reactivar", _utc(d + timedelta(days=1), 9)))
    assert last_reactivation([record, later])["v1"] == _utc(d + timedelta(days=1), 9)


def test_two_reactivations_the_last_one_wins_and_descartar_does_not_count():
    d = date(2026, 11, 1)
    record = _record(
        "v1",
        ("reactivar", _utc(d)),
        ("descartar", _utc(d + timedelta(days=5))),
        ("reactivar", _utc(d + timedelta(days=3))),
    )
    assert last_reactivation([record]) == {"v1": _utc(d + timedelta(days=3))}
    assert last_reactivation([_record("v2", ("descartar", _utc(d)))]) == {}


def test_only_versions_with_recommendations_today_or_yesterday_are_evaluated():
    def vw(v, pop, last):
        return VersionWindow(
            model_version_id=v, population=pop, first_day=TODAY - timedelta(days=50), last_day=last
        )

    versions = [
        vw("hoy", "modelo", TODAY),
        vw("ayer", "modelo", TODAY - timedelta(days=1)),
        vw("antier", "modelo", TODAY - timedelta(days=2)),
        vw("solo-humana", "humana", TODAY),
    ]
    assert evaluated_versions(versions, TODAY) == ["ayer", "hoy"]


@pytest.mark.parametrize("window_days", [7, 30, 90])
def test_ranges_are_ordered_and_end_before_or_on_today(window_days):
    r = version_ranges(TODAY, window_days, TODAY - timedelta(days=200), None)
    for span in (r.before, r.after, r.last_7_days):
        assert span is not None
        assert span.from_day <= span.to_day <= TODAY
