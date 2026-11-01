"""`x-vectra-deadline` (NFR-U0-23 (b), (h))."""

import time
from datetime import timedelta

import pytest
from strategies.domain import NOW

from vectra_common.deadline import parse, read, to_header
from vectra_common.errors import DeadlineExceeded


def test_malformed_is_discarded():
    assert read({"x-vectra-deadline": "mañana"}, NOW) is None
    assert read({"x-vectra-deadline": "2026-10-31T12:00:00"}, NOW) is None
    assert read({}, NOW) is None


def test_past_exhausts_budget():
    with pytest.raises(DeadlineExceeded):
        read({"x-vectra-deadline": to_header(NOW - timedelta(milliseconds=1))}, NOW)
    with pytest.raises(DeadlineExceeded):
        read({"x-vectra-deadline": to_header(NOW)}, NOW)


def test_future_accepted():
    later = NOW + timedelta(hours=1)
    assert read({"x-vectra-deadline": to_header(later)}, NOW) == later


def test_header_format_rfc3339_ms():
    assert to_header(NOW) == "2026-10-31T12:00:00.000Z"
    assert parse("2026-10-31T07:00:00-05:00") == NOW


def test_header_is_utc_whatever_the_local_zone(monkeypatch):
    """Un runner en UTC no distingue `astimezone(UTC)` de la zona local: se fija una que no lo sea."""
    monkeypatch.setenv("TZ", "America/Bogota")
    time.tzset()
    try:
        assert to_header(NOW) == "2026-10-31T12:00:00.000Z"
    finally:
        monkeypatch.undo()
        time.tzset()
