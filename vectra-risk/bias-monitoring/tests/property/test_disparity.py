"""PBT-U9-01 (oraculo de Fairlearn), PBT-U9-02 (invariantes de la agregada) y PBT-U9-03 (supresion). CA-6."""

from decimal import Decimal

import numpy as np
from fairlearn.metrics import MetricFrame, demographic_parity_difference, selection_rate
from hypothesis import assume, given
from hypothesis import strategies as st
from support import N_MIN, count_tables, scale, states
from vectra_disparity import (
    BANDS,
    UNINFORMED,
    CountCell,
    CountTable,
    aggregate_lower_limit,
    disparity_by_band,
    to_dict,
)

HALF_ULP = (
    5e-5 + 1e-9
)  # la libreria publica 4 decimales: la tolerancia de 1e-9 se aplica despues de ese redondeo


def _run(table: CountTable, n_min: int = N_MIN):
    return disparity_by_band({table.attribute: table}, table.attribute, n_min)


def _frame(cells: list[CountCell]):
    y = np.concatenate([np.r_[np.ones(c.favorable), np.zeros(c.total - c.favorable)] for c in cells])
    groups = np.concatenate([np.full(c.total, c.group) for c in cells])
    return y, groups


@given(count_tables())
def test_pbt_u9_01_matches_fairlearn_oracle(table):
    result = _run(table)
    by_band = {b.band: b for b in result.bands}
    cell_results = {(c.group, c.band): c for c in result.cells}
    for band in BANDS:
        sufficient = [c for c in table.cells if c.band == band and c.total >= N_MIN]
        if sufficient:
            y, groups = _frame(sufficient)
            rates = MetricFrame(
                metrics=selection_rate, y_true=y, y_pred=y, sensitive_features=groups
            ).by_group
            for group, rate in rates.items():
                assert abs(float(cell_results[(group, band)].rate) - float(rate)) <= HALF_ULP
        comparable = [c for c in sufficient if c.group != UNINFORMED]
        if len(comparable) < 2:
            assert by_band[band].difference is None
            continue
        y, groups = _frame(comparable)
        expected = demographic_parity_difference(y, y, sensitive_features=groups)
        assert abs(float(by_band[band].difference) - float(expected)) <= HALF_ULP


@given(count_tables())
def test_pbt_u9_02_aggregate_is_between_band_differences(table):
    result = _run(table)
    differences = [b.difference for b in result.bands if b.difference is not None]
    if not differences:
        assert result.aggregate is None and result.aggregate_ci_95 is None
        return
    assert min(differences) <= result.aggregate <= max(differences)
    if len(differences) == 1:
        assert result.aggregate == differences[0]
    low, high = result.aggregate_ci_95
    assert low <= result.aggregate <= high


@given(count_tables(), st.data())
def test_pbt_u9_02_does_not_change_with_permutations(table, data):
    shuffled = CountTable(table.attribute, tuple(data.draw(st.permutations(table.cells))))
    assert _run(shuffled) == _run(table)
    # Renombrar los grupos no cambia ninguna cifra (solo los nombres del par extremo).
    renamed = CountTable(
        table.attribute,
        tuple(
            CountCell(c.group if c.group == UNINFORMED else f"z-{c.group}", c.band, c.favorable, c.total)
            for c in table.cells
        ),
    )
    a, b = _run(table), _run(renamed)
    assert (a.aggregate, a.aggregate_ci_95, a.population_difference) == (
        b.aggregate,
        b.aggregate_ci_95,
        b.population_difference,
    )
    assert [(x.difference, x.ci_95, x.n_band) for x in a.bands] == [
        (x.difference, x.ci_95, x.n_band) for x in b.bands
    ]


@given(count_tables(), st.integers(1, 6))
def test_pbt_u9_02_scaling_keeps_values_and_never_widens_the_interval(table, k):
    scaled = scale(table, k)
    assume(states(scaled) == states(table))  # si una celda cruza n_min la propiedad no aplica (revision H9)
    a, b = _run(table), _run(scaled)
    assert a.aggregate == b.aggregate
    assert [x.difference for x in a.bands] == [x.difference for x in b.bands]
    if a.aggregate is not None:
        width_a = a.aggregate_ci_95[1] - a.aggregate_ci_95[0]
        width_b = b.aggregate_ci_95[1] - b.aggregate_ci_95[0]
        assert width_b <= width_a + Decimal("0.0001")  # 4 decimales: el redondeo de cada extremo cuenta
    for x, y in zip(a.bands, b.bands, strict=True):
        if x.ci_95 is not None:
            assert y.ci_95[1] - y.ci_95[0] <= x.ci_95[1] - x.ci_95[0] + Decimal("0.0001")


@given(count_tables())
def test_pbt_u9_02_freeze_limit_is_below_the_95_interval_and_exists_with_the_aggregate(table):
    """BR-U9-11 (R4): el limite con z = 3,14 existe cuando existe la agregada y nunca queda sobre el limite de 95 %."""
    result = _run(table)
    limit = aggregate_lower_limit({table.attribute: table}, table.attribute, N_MIN)
    assert (limit is None) == (result.aggregate is None)
    if limit is not None:
        assert limit <= result.aggregate_ci_95[0] <= result.aggregate
        assert (
            aggregate_lower_limit({table.attribute: table}, table.attribute, N_MIN, z=1.96)
            == result.aggregate_ci_95[0]
        )


@given(count_tables(), st.integers(1, 6))
def test_pbt_u9_02_scaling_never_lowers_the_freeze_limit(table, k):
    scaled = scale(table, k)
    assume(states(scaled) == states(table))
    a = aggregate_lower_limit({table.attribute: table}, table.attribute, N_MIN)
    b = aggregate_lower_limit({table.attribute: scaled}, table.attribute, N_MIN)
    assert (a is None) == (b is None)
    if a is not None:
        assert b >= a - Decimal("0.0001")  # 4 decimales


@given(count_tables(), st.integers(0, 29), st.integers(0, 29))
# BR-U9-04: los pesos de la agregada cuentan solo las celdas suficientes (el valor y el intervalo usan los mismos pesos).
def test_pbt_u9_02_weights_only_count_sufficient_cells(table, total, favorable):
    tiny = CountCell("tiny", BANDS[0], min(favorable, total), total)
    extended = CountTable(table.attribute, (*table.cells, tiny))
    a, b = _run(table), _run(extended)
    assert (a.aggregate, a.aggregate_ci_95) == (b.aggregate, b.aggregate_ci_95)
    assert [(x.difference, x.n_band) for x in a.bands] == [(x.difference, x.n_band) for x in b.bands]


@given(count_tables())
def test_pbt_u9_03_small_cells_never_leak(table):
    result = _run(table)
    sufficient_group_band = {(c.group, c.band) for c in table.cells if c.total >= N_MIN}
    for cell in result.cells:
        if cell.n < N_MIN:
            assert cell.rate is None and cell.status == "muestra_insuficiente"
        else:
            assert cell.rate is not None and cell.status == "suficiente"
    for band in result.bands:
        if band.extreme_pair is not None:
            assert UNINFORMED not in band.extreme_pair
            assert all((g, band.band) in sufficient_group_band for g in band.extreme_pair)
    # La diferencia sin bandas se rehace con un oraculo independiente: solo grupos con todas sus celdas suficientes.
    groups = {c.group for c in table.cells if c.group != UNINFORMED}
    excluded = {g for g in groups if any(c.total < N_MIN for c in table.cells if c.group == g)}
    rates = [
        sum(c.favorable for c in table.cells if c.group == g)
        / sum(c.total for c in table.cells if c.group == g)
        for g in groups - excluded
    ]
    assert result.population_difference_partial == bool(excluded)
    if len(rates) >= 2:
        assert abs(float(result.population_difference) - (max(rates) - min(rates))) <= HALF_ULP
    else:
        assert result.population_difference is None


@given(count_tables(), st.data())
def test_pbt_u9_03_an_insufficient_cell_cannot_be_recovered_by_subtraction(table, data):
    """El resultado no depende de los favorables de una celda insuficiente: solo se publica su tamano."""
    small = [i for i, c in enumerate(table.cells) if c.total < N_MIN and c.total > 0]
    assume(small)
    index = data.draw(st.sampled_from(small))
    cell = table.cells[index]
    other = CountCell(cell.group, cell.band, data.draw(st.integers(0, cell.total)), cell.total)
    changed = CountTable(table.attribute, (*table.cells[:index], other, *table.cells[index + 1 :]))
    assert to_dict(_run(changed)) == to_dict(_run(table))
