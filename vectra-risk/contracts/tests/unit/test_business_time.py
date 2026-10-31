"""BR-U0-37: funcion pura, fuera del pipeline de validacion."""

from datetime import timedelta

from strategies.domain import NOW

from vectra_contracts.validation import check_business_time


def test_br_u0_37_after_occurred_at():
    assert check_business_time({"decided_at": NOW + timedelta(milliseconds=1)}, NOW).reason_code == "after_occurred_at"


def test_br_u0_37_eight_days_before():
    assert check_business_time({"viewed_at": NOW - timedelta(days=8)}, NOW).reason_code == "older_than_7_days"


def test_br_u0_37_boundaries_valid():
    assert check_business_time({"frozen_at": NOW - timedelta(days=7)}, NOW) is None
    assert check_business_time({"evaluated_at": NOW - timedelta(hours=24)}, NOW) is None
    assert check_business_time({}, NOW) is None


def test_br_u0_37_received_at_is_not_a_business_moment():
    payload = {"evaluated_at": NOW, "received_at": NOW - timedelta(days=30)}
    assert check_business_time(payload, NOW) is None


def test_br_u0_37_rejects_non_timestamp():
    assert check_business_time({"escalated_at": "2026-01-01"}, NOW).reason_code == "not_a_timestamp"
