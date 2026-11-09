"""Pruebas de ejemplo del Paso 4 (US-301, US-303, BR-U9-01..07). CA-6."""

from decimal import Decimal
from types import SimpleNamespace

import pytest
from support import load_u5_counts
from vectra_contracts.catalog import Decision
from vectra_contracts.models.monitoring import AttributeResult as U0AttributeResult
from vectra_contracts.models.monitoring import CellResult as U0CellResult
from vectra_contracts.models.monitoring import MonitoringMarginalCount
from vectra_disparity import (
    ATTRIBUTES,
    CountCell,
    CountTable,
    aggregate_lower_limit,
    counts_from_marginals,
    counts_from_records,
    disparity_by_band,
    model_aggregate,
    to_dict,
)

N_MIN = 30


def table(attribute, *cells):
    return {attribute: CountTable(attribute, tuple(CountCell(*c) for c in cells))}


def test_insular_band_with_12_cases_is_insufficient_and_outside_the_aggregate():
    # US-301: la banda lt_20 de `insular` tiene 12 casos.
    counts = table(
        "region",
        ("andina", "lt_20", 50, 100),
        ("caribe", "lt_20", 40, 100),
        ("insular", "lt_20", 12, 12),
    )
    result = disparity_by_band(counts, "region", N_MIN)
    insular = next(c for c in result.cells if c.group == "insular")
    assert (insular.n, insular.rate, insular.status) == (12, None, "muestra_insuficiente")
    band = next(b for b in result.bands if b.band == "lt_20")
    assert band.difference == Decimal("0.1000")
    assert band.extreme_pair == ("andina", "caribe")
    assert band.n_band == 200  # los 12 casos no pesan
    assert result.aggregate == Decimal("0.1000")


def test_a_group_with_an_insufficient_cell_has_no_unbanded_rate():
    # BR-U9-06: `c` tiene una celda chica; su tasa sin bandas no se publica y la diferencia es parcial.
    counts = table(
        "estrato",
        ("a", "lt_20", 50, 100), ("a", "20_30", 50, 100),
        ("b", "lt_20", 30, 100), ("b", "20_30", 30, 100),
        ("c", "lt_20", 90, 100), ("c", "20_30", 9, 10),
    )  # fmt: skip
    result = disparity_by_band(counts, "estrato", N_MIN)
    assert result.population_difference_partial is True
    assert result.population_difference == Decimal("0.2000")  # a (0,5) y b (0,3); c queda fuera
    assert next(c for c in result.cells if (c.group, c.band) == ("c", "20_30")).rate is None
    assert next(c for c in result.cells if (c.group, c.band) == ("c", "lt_20")).rate == Decimal("0.9000")


def test_complete_table_is_not_partial_and_no_informado_is_never_extreme():
    counts = table(
        "sexo",
        ("F", "lt_20", 50, 100), ("M", "lt_20", 40, 100), ("no_informado", "lt_20", 1, 100),
        ("F", "20_30", 50, 100), ("M", "20_30", 40, 100), ("no_informado", "20_30", 99, 100),
    )  # fmt: skip
    result = disparity_by_band(counts, "sexo", N_MIN)
    assert result.population_difference_partial is False
    assert result.population_difference == Decimal("0.1000")
    assert all(b.extreme_pair in (None, ("F", "M")) for b in result.bands)
    assert next(b for b in result.bands if b.band == "lt_20").n_band == 200


def test_band_with_one_group_has_no_difference_and_does_not_weigh():
    counts = table("sexo", ("F", "lt_20", 50, 100), ("M", "lt_20", 40, 100), ("F", "gt_30", 90, 100))
    result = disparity_by_band(counts, "sexo", N_MIN)
    gt = next(b for b in result.bands if b.band == "gt_30")
    assert (gt.difference, gt.extreme_pair, gt.ci_95, gt.n_band) == (None, None, None, 100)
    assert result.aggregate == Decimal("0.1000")


def test_ties_choose_two_distinct_groups_by_name_and_all_insufficient_has_no_aggregate():
    counts = table("sexo", ("M", "lt_20", 50, 100), ("F", "lt_20", 50, 100), ("X", "lt_20", 50, 100))
    band = disparity_by_band(counts, "sexo", N_MIN).bands[0]
    assert band.difference == Decimal("0.0000")
    assert band.extreme_pair == ("M", "F")  # mayor: el menor nombre entre los que quedan; menor: F
    tiny = table("sexo", ("F", "lt_20", 1, 10), ("M", "lt_20", 2, 10))
    result = disparity_by_band(tiny, "sexo", N_MIN)
    assert (result.aggregate, result.aggregate_ci_95, result.population_difference) == (None, None, None)
    assert result.population_difference_partial is True


def test_missing_attribute_is_an_empty_result_and_n_min_must_be_positive():
    result = disparity_by_band({}, "region", N_MIN)
    assert (result.cells, result.aggregate, result.population_difference_partial) == ((), None, False)
    assert all(b.difference is None and b.n_band == 0 for b in result.bands)
    with pytest.raises(ValueError, match="n_min_invalid"):
        disparity_by_band({}, "region", 0)


def test_repeated_cells_are_summed():
    counts = table("sexo", ("F", "lt_20", 10, 20), ("F", "lt_20", 20, 30), ("M", "lt_20", 10, 50))
    result = disparity_by_band(counts, "sexo", N_MIN)
    assert next(c for c in result.cells if c.group == "F").n == 50
    assert next(c for c in result.cells if c.group == "F").rate == Decimal("0.6000")


def test_count_cells_are_validated():
    with pytest.raises(ValueError, match="band_unknown"):
        CountCell("a", "xx", 0, 1)
    with pytest.raises(ValueError, match="invalid_cell"):
        CountCell("a", "lt_20", 2, 1)
    with pytest.raises(ValueError, match="invalid_cell"):
        CountCell("a", "lt_20", -1, 1)


def test_model_aggregate_is_the_largest_and_names_its_trigger_attribute():
    results = [
        disparity_by_band(table(a, ("g1", "lt_20", int(100 * r), 100), ("g2", "lt_20", 10, 100)), a, N_MIN)
        for a, r in [("sexo", 0.2), ("rango_edad", 0.5), ("region", 0.5), ("estrato", 0.3)]
    ]
    assert model_aggregate(results) == ("rango_edad", Decimal("0.4000"))  # empate: gana el primero
    empty = disparity_by_band({}, "sexo", N_MIN)
    assert model_aggregate([empty]) is None
    assert model_aggregate([]) is None


# BR-U9-01 -------------------------------------------------------------------------------------------------------------


def _record(outcome, group="F"):
    return {
        "sexo": group,
        "rango_edad": "26_40",
        "region": "andina",
        "estrato": "3",
        "banda": "lt_20",
        "outcome": outcome,
    }


def test_revision_requerida_and_desfavorable_are_not_favorable():
    records = (
        [_record("favorable")] * 10 + [_record("revision_requerida")] * 10 + [_record("desfavorable")] * 10
    )
    cell = counts_from_records(records)["sexo"].cells[0]
    assert (cell.favorable, cell.total) == (10, 30)
    assert counts_from_records([])["sexo"].cells == ()


def test_counts_from_marginals_accepts_mappings_and_objects():
    marginals = [
        {"attribute": "sexo", "group": "F", "band": "lt_20", "result": "favorable", "decision": None, "count": 4},
        SimpleNamespace(attribute="sexo", group="F", band="lt_20", result="desfavorable", decision="sigue", count=6),
        MonitoringMarginalCount(
            population="humana", model_version_id="mv-1", range_id="r", attribute="sexo", group="F", band="lt_20",
            result="revision_requerida", decision=Decision.SE_APARTA, count=5,
        ),
    ]  # fmt: skip
    cell = counts_from_marginals(marginals)["sexo"].cells[0]
    assert (cell.favorable, cell.total) == (4, 15)


# Conteos de U5 (RT-2, US-303) -------------------------------------------------------------------------------------------


def _model_level(variant):
    counts = load_u5_counts(variant)
    results = [disparity_by_band(counts, a, N_MIN) for a in ATTRIBUTES]
    return results, model_aggregate(results)


def test_u5_proxy_variant_reaches_10_pp_and_the_base_model_stays_under_5_pp():
    _, proxy = _model_level("proxy")
    _, base = _model_level("base")
    assert proxy is not None and base is not None
    assert proxy[1] >= Decimal("0.10")
    assert base[1] < Decimal("0.05")
    # Contraste con el doble de U5 (4,61 pp la base y 11,66 pp la variante; CANDIDATAS.md): ver la bitacora.
    assert abs(float(base[1]) * 100 - 4.61) < 0.05
    assert abs(float(proxy[1]) * 100 - 11.66) < 0.05


def test_u5_freeze_limit_rt2_proxy_is_above_the_threshold_and_the_base_model_is_not():
    """RT-2 con la regla R4: el limite de la agregada del atributo disparador (`region` en las dos)."""
    limits = {}
    for variant in ("base", "proxy"):
        counts = load_u5_counts(variant)
        trigger, _ = _model_level(variant)[1]
        limits[variant] = aggregate_lower_limit(counts, trigger, N_MIN)
    assert limits["proxy"] > Decimal("0.05")
    assert limits["base"] <= Decimal("0.05")


@pytest.mark.parametrize("variant", ["base", "proxy"])
def test_library_output_validates_against_the_u0_models(variant):
    results, _ = _model_level(variant)
    for result in results:
        payload = to_dict(result)
        validated = U0AttributeResult.model_validate(payload)
        assert validated.attribute == result.attribute
        for cell in payload["cells"]:
            parsed = U0CellResult.model_validate(cell)
            if parsed.status == "muestra_insuficiente":
                assert parsed.rate is None


def test_u0_rejects_an_insufficient_cell_with_a_rate():
    with pytest.raises(ValueError, match="insufficient_cell_with_rate"):
        U0CellResult.model_validate(
            {"group": "a", "band": "lt_20", "n": 3, "rate": "0.5000", "status": "muestra_insuficiente"}
        )


# Intervalo (BLM §3) ------------------------------------------------------------------------------------------------------


def _pair_table(n, favorable_b):
    cells = [
        (g, band, f, n)
        for band in ("lt_20", "20_30", "gt_30")
        for g, f in (("a", n // 2), ("b", favorable_b))
    ]
    return table("sexo", *cells)


def test_interval_with_few_cases_includes_zero_and_with_many_does_not():
    few = disparity_by_band(_pair_table(50, 28), "sexo", N_MIN)  # 6 pp con 50 casos por celda
    many = disparity_by_band(_pair_table(2000, 1120), "sexo", N_MIN)  # 6 pp con 2 000 casos por celda
    assert few.aggregate == many.aggregate == Decimal("0.0600")
    assert few.aggregate_ci_95[0] <= 0
    assert many.aggregate_ci_95[0] > 0


def test_freeze_limit_uses_bonferroni_z_and_only_changes_the_z():
    """BR-U9-11 (regla R4): el limite es `D_a - 3,14 * sqrt(Var)`; el intervalo de 95 % publicado no cambia."""
    counts = _pair_table(2000, 1120)
    result = disparity_by_band(counts, "sexo", N_MIN)
    half_95 = (result.aggregate_ci_95[1] - result.aggregate_ci_95[0]) / 2  # = 1,96 sigma
    sigma = half_95 / Decimal("1.96")
    assert aggregate_lower_limit(counts, "sexo", N_MIN) == (
        result.aggregate - Decimal("3.14") * sigma
    ).quantize(Decimal("0.0001"), rounding="ROUND_HALF_UP")
    assert aggregate_lower_limit(counts, "sexo", N_MIN, z=1.96) == result.aggregate_ci_95[0]


def test_freeze_limit_with_few_cases_or_a_small_gap_does_not_exceed_the_threshold():
    """BLM §3 (regla R4): 40 casos por celda y 6 pp, 2 000 casos y 6 pp, y 2 000 casos y 12 pp."""
    assert aggregate_lower_limit(_pair_table(40, 22), "sexo", N_MIN) <= Decimal("0.05")  # 6 pp con 40 casos
    assert aggregate_lower_limit(_pair_table(2000, 1120), "sexo", N_MIN) <= Decimal("0.05")  # 6 pp con 2 000
    assert aggregate_lower_limit(_pair_table(2000, 1240), "sexo", N_MIN) > Decimal("0.05")  # 12 pp con 2 000


def test_freeze_limit_is_none_without_an_aggregate_and_validates_n_min():
    assert aggregate_lower_limit({}, "region", N_MIN) is None
    assert aggregate_lower_limit(_pair_table(10, 5), "sexo", N_MIN) is None  # todas las celdas insuficientes
    with pytest.raises(ValueError, match="n_min_invalid"):
        aggregate_lower_limit({}, "region", 0)
