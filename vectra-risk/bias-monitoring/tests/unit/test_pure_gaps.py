"""Paso 10 (NFR-U9-50): las ramas de `context`, `window`, `config` y `registry_client` que las pruebas de los pasos 4 a 8 no recorrian.

`freeze_rule`, `context` y `window` exigen el 100 % de ramas. Ninguna prueba cambia el comportamiento de los modulos.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from builders import uniform
from vectra_bias import config
from vectra_bias.context import _without_cells, build_context_package, departure_rates, measure
from vectra_bias.freeze_rule import attribute_limits, decide
from vectra_bias.registry_client import route_path
from vectra_bias.window import last_reactivation
from vectra_contracts.catalog import Decision
from vectra_contracts.models.monitoring import AffectedVolume, MonitoringMarginalCount
from world import freeze_record

TODAY = date(2026, 11, 9)
NOW = datetime(2026, 11, 9, 12, tzinfo=UTC)


def marginal(decision, group="F", count=40) -> MonitoringMarginalCount:
    return MonitoringMarginalCount(
        population="humana",
        model_version_id="v1",
        range_id="r",
        attribute="sexo",
        group=group,
        band="lt_20",
        result="favorable",
        decision=None if decision is None else Decision(decision),
        count=count,
    )


def test_departure_rates_ignore_a_review_resolution_and_an_entry_without_decision():
    rows = [
        marginal("se_aparta", count=10),
        marginal("sigue", count=30),
        marginal("resuelve_revision", count=99),
        marginal(None),
    ]
    [rate] = departure_rates(rows, 30)
    assert (rate.group, rate.band, rate.rate) == (
        "F",
        "lt_20",
        "0.2500",
    )  # 10 / (10 + 30); la revision no entra


def test_without_cells_keeps_the_text_sin_datos():
    assert _without_cells("sin_datos") == "sin_datos"


def test_a_context_package_needs_a_trigger_attribute():
    counts = uniform(0.5, 10)  # 10 < n_min: ninguna agregada, sin disparador
    after = measure(counts, 30, "modelo", "v1", TODAY, TODAY)
    assert after.trigger_attribute is None
    with pytest.raises(ValueError, match="context_without_trigger_attribute"):
        build_context_package(
            model_version_id="v1",
            computed_at=NOW,
            threshold_pp=Decimal(5),
            n_min=30,
            window_days=30,
            schedule="2,17,32,47 * * * *",
            stale_after_s=3600,
            window_start=TODAY,
            before=None,
            after=after,
            last_7_days=None,
            decision=decide("modelo", Decimal(5), attribute_limits(counts, 30)),
            affected_volume=AffectedVolume(total=1, favorable=1),
        )


def test_an_older_reactivation_in_another_record_does_not_replace_the_latest():
    later, earlier = NOW, NOW - timedelta(days=3)
    records = [
        _record("v1", [("reactivar", later)]),
        _record("v1", [("reactivar", earlier)]),
        _record("v1", [("investigar", NOW)]),
    ]
    assert last_reactivation(records) == {"v1": later}


def _record(version, resolutions):
    from vectra_contracts.models.monitoring import FreezeRecord

    return FreezeRecord.model_validate_json(
        __import__("json").dumps(freeze_record(version, NOW - timedelta(days=5), resolutions))
    )


def test_a_schedule_whose_minutes_do_not_divide_the_hour_is_rejected():
    raw = {
        "threshold_pp": 5,
        "n_min": 30,
        "window_days": 30,
        "schedule": "1,2,3,4,5,6,7 * * * *",
        "stale_after": "1h",
    }
    with pytest.raises(config.PolicyError, match="schedule_interval_not_allowed"):
        config.parse_policy(raw)


def test_route_path_fails_unless_the_contract_has_exactly_one_route():
    assert route_path("decision-registry-service", "GET", "/freezes") == "/v1/monitoring/freezes"
    with pytest.raises(LookupError):
        route_path("decision-registry-service", "GET", "/no-existe")
    with pytest.raises(LookupError):
        route_path("decision-registry-service", "GET", "s")  # varias rutas terminan en «s»
