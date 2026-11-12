"""`model.parse_entry`: cada regla de exclusion de BR-U11-10, una por una, y la compactacion de P-U11-04."""

from __future__ import annotations

import sys
from typing import Any

import pytest
from entries import NOW, Spec, day_at, render
from vectra_product.model import (
    MANUAL,
    NO_OUTCOME,
    REVISION_REQUERIDA,
    SIGUE,
    Decision,
    InvalidEntry,
    parse_entry,
)


def entry(**changes: Any) -> dict[str, Any]:
    item = render(Spec(seq=5, decided=day_at(1)))
    item.update(changes)
    return item


def test_a_valid_entry_is_compact_and_interned() -> None:
    first = parse_entry(5, entry())
    second = parse_entry(6, entry())
    assert isinstance(first, Decision) and isinstance(second, Decision)
    assert first.decision == SIGUE and first.attributable and first.viewed and not first.no_factors
    assert first.channel is second.channel and first.model is second.model  # cadenas internadas (P-U11-04)
    assert first.channel is sys.intern(first.channel)
    assert not hasattr(first, "__dict__")  # `__slots__`
    assert first.standard
    assert "Decision(seq=5" in repr(first)


def test_a_null_reference_is_valid_but_not_attributable() -> None:
    parsed = parse_entry(5, entry(recommendation=None))
    assert isinstance(parsed, Decision) and not parsed.attributable and not parsed.standard
    assert parsed.outcome == NO_OUTCOME


def test_standard_needs_every_condition() -> None:
    base = entry()
    assert parse_entry(1, base).standard  # type: ignore[union-attr]
    for field, value in (("channel", MANUAL), ("first_evaluation", False), ("outcome", "revision_requerida")):
        item = entry(recommendation={**base["recommendation"], field: value})
        parsed = parse_entry(1, item)
        assert isinstance(parsed, Decision) and not parsed.standard, field
    assert REVISION_REQUERIDA == 2


@pytest.mark.parametrize(
    "changes",
    [
        {"entry_type": "recommendation"},
        {"decision": "desconocida"},
        {"decision": None},
        {"decision": 1},
        {"used_factors": "ingreso"},
        {"used_factors": []},
        {"used_factors": ["ninguno", "ingreso"]},
        {"used_factors": ["ingreso", "ingreso"]},
        {"used_factors": [1]},
        {"explanation_viewed_before": "true"},
        {"explanation_viewed_before": None},
        {"actor_role": "cro"},
        {"actor_role": "root"},
        {"actor_role": ["analista"]},
        {"actor_role": None},
        {"decided_at": None},
        {"decided_at": "ayer"},
        {"decided_at": "2026-10-05T12:00:00"},  # sin zona horaria
        {"decided_at": 5},
        {"recorded_at": None},
        {"recommendation": "x"},
        {"recommendation": {}},
    ],
)
def test_each_exclusion_rule(changes: dict[str, Any]) -> None:
    assert isinstance(parse_entry(5, entry(**changes)), InvalidEntry)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("seq", -1),
        ("seq", True),
        ("outcome", "otro"),
        ("outcome", 3),
        ("model_version_id", None),
        ("evaluated_at", "no"),
        ("received_at", None),
        ("channel", "x" * 41),
        ("channel", None),
        ("attempt", 0),
        ("attempt", 1.5),
        ("first_evaluation", 1),
    ],
)
def test_each_exclusion_rule_of_the_resolved_recommendation(field: str, value: Any) -> None:
    item = entry()
    item["recommendation"] = {**item["recommendation"], field: value}
    assert isinstance(parse_entry(5, item), InvalidEntry), field


@pytest.mark.parametrize(
    ("field", "value"),
    [("channel", ""), ("channel", "x" * 40), ("model_version_id", ""), ("model_version_id", "m" * 100_000)],
)
def test_values_the_u0_contract_admits_are_not_excluded(field: str, value: str) -> None:
    """`MetricsRecommendationRef` no exige longitud minima en `channel` ni tope en `model_version_id`: excluirlos cambiaria las cifras."""
    item = entry()
    item["recommendation"] = {**item["recommendation"], field: value}
    parsed = parse_entry(5, item)
    assert isinstance(parsed, Decision)
    assert getattr(parsed, "channel" if field == "channel" else "model") == value


def test_missing_required_fields_are_excluded() -> None:
    for name in (
        "decision",
        "used_factors",
        "explanation_viewed_before",
        "decided_at",
        "recorded_at",
        "recommendation",
        "actor_role",
    ):
        item = entry()
        del item[name]
        assert isinstance(parse_entry(5, item), InvalidEntry), name


def test_the_invalid_entry_keeps_the_best_known_day() -> None:
    by_decided = parse_entry(5, entry(decision="otra"))
    assert isinstance(by_decided, InvalidEntry) and by_decided.day == day_at(1).toordinal()
    by_recorded = parse_entry(5, entry(decision="otra", decided_at=None))
    assert isinstance(by_recorded, InvalidEntry) and by_recorded.day is not None
    unknown = parse_entry(5, entry(decision="otra", decided_at=None, recorded_at="x"))
    assert isinstance(unknown, InvalidEntry) and unknown.day is None
    assert "InvalidEntry(seq=5" in repr(unknown)


def test_offsets_other_than_utc_are_normalized() -> None:
    item = entry(decided_at="2026-10-05T23:30:00-05:00", recorded_at="2026-10-06T04:31:00+00:00")
    parsed = parse_entry(5, item)
    assert isinstance(parsed, Decision) and parsed.day == NOW.replace(day=6).toordinal()  # 04:30 UTC del 6
