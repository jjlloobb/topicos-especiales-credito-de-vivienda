"""Paso 9: ejemplos a mano de `compare_source` (BR-U9-17; US-306; BLM §3). Los oraculos estan escritos en la prueba."""

from __future__ import annotations

import pytest
from builders import CATALOG, compare_request, table, uniform
from scenario import POLICY
from vectra_bias.compare import CATALOG as COMPARE_CATALOG
from vectra_bias.compare import compare_source
from vectra_common.errors import ValidationFailed
from vectra_contracts.canonical import canonicalize
from vectra_contracts.models.monitoring import CountCell, CountTable
from vectra_disparity import BANDS, UNINFORMED

ATTRIBUTES = ("sexo", "rango_edad", "region", "estrato")


def sex_counts(female: float, male: float):
    """`sexo` con F y M (1 000 casos por celda y banda); los otros tres atributos, sin disparidad."""
    counts = uniform(0.5, 1000)
    counts["sexo"] = table("sexo", {"F": female, "M": male}, 1000)
    return counts


def test_the_example_of_the_blm_gives_a_delta_of_minus_0_0500_for_sexo():
    # pre: F 0,50 y M 0,60 -> diferencia 0,10 en las 3 bandas, agregada 0,1000. post: 0,50 y 0,55 -> 0,0500.
    report = compare_source(compare_request("fuente-1", sex_counts(0.5, 0.6), sex_counts(0.5, 0.55)), POLICY)
    assert report.source_id == "fuente-1"
    assert {a.attribute: a.aggregate for a in report.pre.attributes}["sexo"] == "0.1000"
    assert {a.attribute: a.aggregate for a in report.post.attributes}["sexo"] == "0.0500"
    deltas = {a.attribute: a.delta for a in report.delta.attributes}
    assert deltas == {"sexo": "-0.0500", "rango_edad": "0.0000", "region": "0.0000", "estrato": "0.0000"}
    assert report.delta.model_aggregate == "-0.0500"  # la mayor agregada: 0,1000 antes y 0,0500 despues
    assert (report.threshold_pp, report.n_min, report.truncated) == ("5.0000", 30, False)
    assert report.disclaimer == "mide y alerta, no certifica"


def test_the_delta_is_post_minus_pre_and_is_positive_when_the_gap_widens():
    report = compare_source(compare_request("f", sex_counts(0.5, 0.55), sex_counts(0.5, 0.6)), POLICY)
    assert {a.attribute: a.delta for a in report.delta.attributes}["sexo"] == "0.0500"


def test_a_delta_is_null_when_one_of_the_two_aggregates_is_missing():
    thin = sex_counts(0.5, 0.6)
    thin["sexo"] = table(
        "sexo", {"F": 0.5, "M": 0.6}, 10
    )  # 10 < n_min: todas las celdas insuficientes, sin agregada
    report = compare_source(compare_request("f", thin, sex_counts(0.5, 0.55)), POLICY)
    assert {a.attribute: a.aggregate for a in report.pre.attributes}["sexo"] is None
    deltas = {a.attribute: a.delta for a in report.delta.attributes}
    assert deltas["sexo"] is None and deltas["region"] == "0.0000"
    # la mayor agregada de `pre` pasa a ser la de otro atributo (0,0000); la de `post` es 0,0500: 0,0500 - 0,0000
    assert report.delta.model_aggregate == "0.0500"


def test_every_delta_is_null_when_every_aggregate_of_pre_is_missing():
    thin = uniform(0.5, 10)  # 10 < n_min en todas las celdas
    report = compare_source(compare_request("f", thin, sex_counts(0.5, 0.55)), POLICY)
    assert [a.delta for a in report.delta.attributes] == [None, None, None, None]
    assert report.delta.model_aggregate is None


def full_catalog_counts(gap: float):
    """Los catalogos completos de U0 (22 grupos: `no_informado` solo en sexo y estrato) por 3 bandas."""
    counts = {}
    for attribute in ATTRIBUTES:
        groups = [*CATALOG[attribute], *([UNINFORMED] if attribute in ("sexo", "estrato") else [])]
        rates = {g: 0.5 + (gap if i == 0 else 0.0) for i, g in enumerate(groups)}
        counts[attribute] = table(attribute, rates, 500)
    return counts


def test_the_catalog_of_u0_has_22_groups():
    assert sum(len(groups) for groups in COMPARE_CATALOG.values()) == 22


def test_a_report_with_the_full_catalogs_fits_in_48_kib():
    report = compare_source(compare_request("f", full_catalog_counts(0.1), full_catalog_counts(0.05)), POLICY)
    assert len(canonicalize(report.model_dump(mode="json"))) <= 48 * 1024
    assert report.truncated is False
    assert sum(len(a.cells) for a in report.pre.attributes) == 22 * 3


def test_when_the_report_does_not_fit_the_cells_of_pre_go_first_then_those_of_post():
    request = compare_request("f", full_catalog_counts(0.1), full_catalog_counts(0.05))
    full = compare_source(request, POLICY)
    size = len(canonicalize(full.model_dump(mode="json")))

    no_pre = compare_source(request, POLICY, max_bytes=size - 1)  # solo cabe sin las celdas de `pre`
    assert no_pre.truncated is True
    assert all(a.cells == [] for a in no_pre.pre.attributes)
    assert [a.cells for a in no_pre.post.attributes] == [a.cells for a in full.post.attributes]

    neither = compare_source(request, POLICY, max_bytes=1)
    assert neither.truncated is True
    assert all(a.cells == [] for a in neither.pre.attributes + neither.post.attributes)
    for cut in (no_pre, neither):  # agregadas, bandas y `delta` quedan intactos (BLM §3)
        for side in ("pre", "post"):
            kept, whole = getattr(cut, side), getattr(full, side)
            assert [
                (a.attribute, a.aggregate, a.aggregate_ci_95, a.population_difference)
                for a in kept.attributes
            ] == [
                (a.attribute, a.aggregate, a.aggregate_ci_95, a.population_difference)
                for a in whole.attributes
            ]
            assert [a.bands for a in kept.attributes] == [a.bands for a in whole.attributes]
            assert kept.model_aggregate == whole.model_aggregate
        assert cut.delta == full.delta


def _with_cell(counts, attribute: str, group: str, band: str):
    request = compare_request("f", counts, counts)
    table_ = next(t for t in request.pre if t.attribute == attribute)
    table_.cells.append(CountCell(group=group, band=band, favorable=1, total=2))  # type: ignore[arg-type]
    return request


def test_a_group_outside_the_catalog_is_a_422_without_partial_calculation():
    with pytest.raises(ValidationFailed) as error:
        compare_source(_with_cell(uniform(0.5, 100), "region", "Bogota", "lt_20"), POLICY)
    assert [(p.name, p.reason_code) for p in error.value.invalid_params] == [
        ("pre.2.cells.18.group", "group_not_in_catalog")
    ]


def test_a_band_outside_the_catalog_is_a_422():
    request = compare_request("f", uniform(0.5, 100), uniform(0.5, 100))
    cell = request.post[0].cells[0]
    request.post[0].cells[0] = CountCell.model_construct(group=cell.group, band="lt_99", favorable=1, total=2)
    with pytest.raises(ValidationFailed) as error:
        compare_source(request, POLICY)
    assert [p.reason_code for p in error.value.invalid_params] == ["band_not_in_catalog"]


def test_a_repeated_cell_is_a_422():
    request = _with_cell(uniform(0.5, 100), "sexo", "F", "lt_20")  # `uniform` ya trae F en lt_20
    with pytest.raises(ValidationFailed) as error:
        compare_source(request, POLICY)
    assert [p.reason_code for p in error.value.invalid_params] == ["duplicate_cell"]


def test_the_bands_of_the_catalog_are_the_three_of_the_library():
    from vectra_bias.compare import BANDS as COMPARE_BANDS

    assert COMPARE_BANDS == frozenset(BANDS)


def test_the_models_of_u0_reject_negative_counts_and_repeated_attributes_before_compare():
    with pytest.raises(ValueError):
        CountCell(group="F", band="lt_20", favorable=-1, total=5)  # type: ignore[arg-type]
    request = compare_request("f", uniform(0.5, 100), uniform(0.5, 100))
    with pytest.raises(ValueError):
        type(request).model_validate(
            {**request.model_dump(), "pre": [t.model_dump() for t in request.pre[:3]]}
        )
    assert CountTable  # el modelo de U0 es el que valida atributos y conteos
