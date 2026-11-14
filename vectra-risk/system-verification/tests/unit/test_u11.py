"""La seccion `u11` y la evidencia `dashboard` (U12-T04, CA-12; BR-U12-06)."""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from product_prom import Prom
from vectra_verification import guard
from vectra_verification.clients.prom import PromClient
from vectra_verification.guard import GuardError
from vectra_verification.scenarios import u11

PRODUCT = (
    Path(__file__).resolve().parents[3] / "product-metrics" / "observability" / "dashboards" / "product.json"
)
D = datetime(2026, 11, 13, 22, 30, tzinfo=UTC)  # `decisions` termino el dia D
AFTER_PASS = datetime(2026, 11, 14, 3, 30, tzinfo=UTC)  # D + 1, despues de las 02:40 y del plazo de la pasada
BEFORE_PASS = datetime(2026, 11, 14, 2, 35, tzinfo=UTC)


def run(transport: Prom, now: datetime = AFTER_PASS, finished: datetime | None = D) -> u11.Outcome:
    return u11.u11(guard.KIND, PromClient("http://prom.test", transport=transport), now, finished)


def test_the_expressions_are_the_ones_of_the_panels_of_product_json() -> None:
    document = json.loads(PRODUCT.read_text(encoding="utf-8"))
    by_title = {p["title"]: tuple(t["expr"] for t in p["targets"]) for p in document["panels"]}
    for title, expressions in u11.PANELS.items():
        assert by_title[title] == expressions, title
    assert len(u11.PANELS) == 4


def test_with_value_in_the_four_panels_and_no_stale_alert_it_passes() -> None:
    transport = Prom()
    outcome = run(transport)
    assert outcome.result == "pasa" and outcome.missing == ()
    assert len(outcome.queries) == 7 and set(transport.queries) >= {
        e for es in u11.PANELS.values() for e in es
    }
    assert (
        "RuidoExplicacion" in outcome.readings["not_verified"]
        and "promtool" in outcome.readings["not_verified"]
    )


def test_the_same_utc_day_as_decisions_is_not_executed() -> None:
    transport = Prom()
    outcome = run(transport, now=D + timedelta(hours=1))
    assert outcome.result == "no ejecutado" and outcome.missing == ("u11_antes_de_d_mas_1",)
    assert transport.queries == []  # ninguna solicitud


def test_without_decisions_in_the_manifest_it_is_not_executed() -> None:
    outcome = run(Prom(), finished=None)
    assert outcome.result == "no ejecutado" and outcome.missing == ("u11_decisions_no_corrio",)


def test_a_missing_series_after_the_pass_is_a_failure_that_names_it() -> None:
    outcome = run(Prom(absent=("noise_days_below_floor",)))
    assert outcome.result == "falla"
    assert outcome.missing == (
        "u11_serie_ausente:Días bajo el piso (vectra:product_noise_days_below_floor:dedup)",
    )


def test_an_empty_series_is_never_a_pass() -> None:
    """Rojo: aceptar un vector vacio como `pasa`."""
    outcome = run(Prom(absent=("north_star_ratio",)))
    assert outcome.result != "pasa" and "North Star de ayer" in outcome.obtained


def test_a_nan_value_is_not_a_value() -> None:
    assert run(Prom(value="NaN")).result == "falla"


def test_a_missing_series_before_the_pass_is_not_executed_not_a_failure() -> None:
    outcome = run(Prom(absent=("north_star_ratio",)), now=BEFORE_PASS)
    assert outcome.result == "no ejecutado" and outcome.missing == ("u11_pasada_pendiente",)


def test_the_stale_alert_firing_is_a_failure() -> None:
    outcome = run(Prom(stale=True))
    assert outcome.result == "falla" and outcome.missing == ("u11_product_metrics_stale_firing",)


def test_missing_and_stale_are_both_reported() -> None:
    outcome = run(Prom(stale=True, absent=("explanation_view_ratio",)))
    assert (
        outcome.result == "falla" and len(outcome.missing) == 2 and "ProductMetricsStale" in outcome.obtained
    )


def test_prometheus_that_does_not_answer_is_not_executed() -> None:
    outcome = run(Prom(down=True))
    assert outcome.result == "no ejecutado" and outcome.missing == ("u11_prometheus_no_responde",)


def test_the_guard_runs_before_any_request() -> None:
    transport = Prom()
    with pytest.raises(GuardError):
        u11.u11(
            guard.Environment("kind", "x", "y"),
            PromClient("http://prom.test", transport=transport),
            AFTER_PASS,
            D,
        )
    assert transport.queries == []


def test_the_deadline_is_0240_utc_of_d_plus_1_plus_the_window() -> None:
    assert u11.pass_deadline(D) == datetime(2026, 11, 14, 2, 50, tzinfo=UTC)
    assert u11.pass_deadline(datetime(2026, 11, 13, 23, 59, tzinfo=UTC), timedelta(0)) == datetime(
        2026, 11, 14, 2, 40, tzinfo=UTC
    )
