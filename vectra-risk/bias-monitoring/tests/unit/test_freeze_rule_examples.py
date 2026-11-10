"""Ejemplos de la regla R4 sobre todos los atributos (BR-U9-11, decision F-03 opcion (b), 2026-11-10; PBT-10).

Conteos construidos en la prueba y la libreria real. La BLM §3 corrige la viñeta del plan: con 2 000 casos por celda y
6 pp el limite R4 es 0,0315 (no congela); con 12 pp si.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from builders import table, with_gap
from support import load_u5_counts
from vectra_bias.freeze_rule import attribute_limits, decide
from vectra_disparity import disparity_by_band, model_aggregate

N_MIN = 30
THRESHOLD = Decimal(5)


def _decide(counts, population="modelo"):
    return decide(population, THRESHOLD, attribute_limits(counts, N_MIN))


def test_40_cases_per_cell_and_6_pp_does_not_freeze():
    assert not _decide(with_gap("region", 0.06, 40)).freeze


def test_2000_cases_per_cell_and_6_pp_does_not_freeze_the_limit_is_0_0315():
    counts = with_gap("region", 0.06, 2000)
    decision = _decide(counts)
    assert not decision.freeze
    assert decision.reason == "bajo_umbral"
    assert attribute_limits(counts, N_MIN)["region"] == Decimal("0.0315")


def test_2000_cases_per_cell_and_12_pp_freezes():
    decision = _decide(with_gap("region", 0.12, 2000))
    assert decision.freeze
    assert decision.reason == "supera_umbral"
    assert [(m.attribute, m.limit) for m in decision.met] == [("region", Decimal("0.0918"))]


def test_f03_masking_case_freezes_through_sexo_although_the_trigger_is_region():
    groups = ["amazonia", "andina", "caribe", "insular", "orinoquia", "pacifica"]
    counts = {
        "region": table("region", {g: 0.5 for g in groups[:-1]} | {groups[-1]: 0.7}, 40),
        "sexo": table("sexo", {"F": 0.5, "M": 0.6}, 3000),
    }
    # Premisa: el disparador (BR-U9-05) es region y su limite R4 no supera el umbral.
    trigger, _ = model_aggregate(disparity_by_band(counts, a, N_MIN) for a in counts)
    limits = attribute_limits(counts, N_MIN)
    assert trigger == "region"
    assert limits["region"] == Decimal("0.0132")
    decision = decide("modelo", THRESHOLD, limits)
    assert decision.freeze
    assert limits["sexo"] == Decimal("0.0768")
    assert [(m.attribute, m.limit) for m in decision.met] == [("sexo", Decimal("0.0768"))]


def test_u5_proxy_variant_freezes_through_region_and_the_base_model_does_not():
    proxy = _decide(load_u5_counts("proxy"))
    assert proxy.freeze
    assert [(m.attribute, m.limit) for m in proxy.met] == [("region", Decimal("0.2282"))]
    base_limits = attribute_limits(load_u5_counts("base"), N_MIN)
    assert not decide("modelo", THRESHOLD, base_limits).freeze
    assert max(v for v in base_limits.values() if v is not None) == Decimal("0.0042")


def test_the_human_population_never_freezes_but_reports_the_rule():
    decision = _decide(with_gap("region", 0.12, 2000), "humana")
    assert not decision.freeze
    assert decision.rule_met


@pytest.mark.parametrize(
    ("limits", "reason"),
    [
        ({}, "muestra_insuficiente"),
        ({"region": None}, "muestra_insuficiente"),
        ({"region": Decimal("-0.0100")}, "intervalo_incluye_cero"),
        ({"region": Decimal("0.0000")}, "intervalo_incluye_cero"),
        ({"region": Decimal("0.0500")}, "bajo_umbral"),
        ({"region": Decimal("0.0501")}, "supera_umbral"),
    ],
)
def test_reasons(limits, reason):
    assert decide("modelo", THRESHOLD, limits).reason == reason


def test_f03_package_has_region_as_trigger_and_implicates_sexo_with_its_limit():
    from datetime import UTC, date, datetime

    from vectra_bias.context import build_context_package, measure
    from vectra_contracts.models.monitoring import AffectedVolume

    groups = ["amazonia", "andina", "caribe", "insular", "orinoquia", "pacifica"]
    counts = {
        "region": table("region", {g: 0.5 for g in groups[:-1]} | {groups[-1]: 0.7}, 40),
        "sexo": table("sexo", {"F": 0.5, "M": 0.6}, 3000),
    }
    after = measure(counts, N_MIN, "modelo", "v1", date(2026, 10, 11), date(2026, 11, 9))
    decision = decide("modelo", THRESHOLD, attribute_limits(counts, N_MIN))
    package = build_context_package(
        model_version_id="v1",
        computed_at=datetime(2026, 11, 9, 12, tzinfo=UTC),
        threshold_pp=THRESHOLD,
        n_min=N_MIN,
        window_days=30,
        schedule="2,17,32,47 * * * *",
        stale_after_s=3600,
        window_start=date(2026, 10, 11),
        before=None,
        after=after,
        last_7_days=None,
        decision=decision,
        affected_volume=AffectedVolume(total=1, favorable=1),
    )
    assert package.trigger_attribute == "region"
    assert [(i["attribute"], i["freeze_lower_limit"]) for i in package.implicated] == [("sexo", "0.0768")]
    assert package.before == "sin_datos"
