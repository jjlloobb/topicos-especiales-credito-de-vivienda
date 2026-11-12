"""El plegado y el descarte de `compute` (lo que `state` usa al leer): retencion de 35 dias y de los meses (NFR-U11-11, 12)."""

from __future__ import annotations

from collections import Counter
from datetime import UTC, date, datetime

from entries import NOW, Spec, day_at, render, specs_on
from vectra_product.compute import (
    absorb,
    discard_old,
    first_relevant_month,
    month_index,
    month_label,
    snapshot_of,
)
from vectra_product.model import DEN, Counts, Decision, InvalidEntry, parse_entry

TODAY = NOW.date()


def entry(spec: Spec) -> Decision | InvalidEntry:
    return parse_entry(spec.seq, render(spec))


def den(counts: Counts) -> int:
    return sum(v for (tag, *_), v in counts.items() if tag == DEN)


def test_month_index_and_label_round_trip() -> None:
    assert month_label(month_index(date(2026, 9, 30).toordinal())) == "2026-09"
    assert month_label(month_index(date(2026, 1, 1).toordinal())) == "2026-01"
    assert month_label(month_index(date(2025, 12, 31).toordinal())) == "2025-12"


def test_the_sixth_closed_month_before_october_is_april() -> None:
    assert month_label(first_relevant_month(TODAY)) == "2026-04"
    assert month_label(first_relevant_month(date(2026, 1, 15))) == "2025-07"


def test_absorb_keeps_35_days_in_the_state_and_all_relevant_months_in_the_counters() -> None:
    entries: dict[int, Decision | InvalidEntry] = {}
    months: dict[int, Counts] = {}
    for spec in (*specs_on(3, 1, 1), *specs_on(40, 1, 2), *specs_on(250, 1, 3)):
        absorb(entries, months, entry(spec), TODAY)
    assert sorted(entries) == [1]  # solo la de 3 dias
    assert sorted(month_label(i) for i in months) == ["2026-08", "2026-10"]  # la de 250 dias no entra
    assert den(months[month_index(day_at(40).toordinal())]) == 1


def test_a_future_dated_decision_is_kept_and_folded() -> None:
    """`decided_at` puede superar a `recorded_at` en hasta 5 min: un dia que todavia no llega tambien cuenta para su mes."""
    spec = Spec(seq=1, decided=datetime(2026, 10, 31, 23, 58, tzinfo=UTC), delay_s=-240)
    entries: dict[int, Decision | InvalidEntry] = {}
    months: dict[int, Counts] = {}
    absorb(entries, months, entry(spec), date(2026, 10, 31))
    assert 1 in entries and den(months[month_index(date(2026, 10, 31).toordinal())]) == 1


def test_unattributable_and_invalid_entries_do_not_touch_the_month_counters() -> None:
    entries: dict[int, Decision | InvalidEntry] = {}
    months: dict[int, Counts] = {}
    absorb(entries, months, entry(Spec(seq=1, decided=day_at(3), rec=None)), TODAY)
    absorb(entries, months, entry(Spec(seq=2, decided=day_at(3), flaw="role")), TODAY)
    assert sorted(entries) == [1, 2] and months == {}


def test_an_invalid_entry_with_no_known_day_is_kept_until_the_next_full_pass() -> None:
    item = render(Spec(seq=1, decided=day_at(3)))
    item.update(decision="otra", decided_at=None, recorded_at=None)
    parsed = parse_entry(1, item)
    entries: dict[int, Decision | InvalidEntry] = {}
    absorb(entries, {}, parsed, TODAY)
    discard_old(entries, {}, date(2027, 1, 1))
    assert 1 in entries


def test_discard_old_drops_decisions_over_35_days_and_months_older_than_the_sixth_closed() -> None:
    entries: dict[int, Decision | InvalidEntry] = {}
    months: dict[int, Counts] = {}
    for spec in (*specs_on(3, 1, 1), *specs_on(40, 1, 2)):
        absorb(entries, months, entry(spec), TODAY)
    months[month_index(date(2025, 1, 1).toordinal())] = Counter({(DEN, "web", 0, "m"): 9})
    assert sorted(entries) == [1] and len(months) == 3
    # 40 dias despues: la decision de 3 dias ya tiene 43 (fuera del estado); los meses mas viejos que el sexto cerrado se van.
    discard_old(entries, months, date(2026, 11, 14))
    assert entries == {}
    assert sorted(month_label(i) for i in months) == ["2026-08", "2026-10"]


def test_snapshot_of_ignores_a_repeated_seq_in_the_counters_too() -> None:
    spec = Spec(seq=1, decided=day_at(40))  # fuera de los 35 dias: solo vive en el contador de su mes
    snapshot = snapshot_of([entry(spec), entry(spec), entry(spec)], NOW)
    assert snapshot.entries == {}
    assert den(snapshot.months[month_index(day_at(40).toordinal())]) == 1
