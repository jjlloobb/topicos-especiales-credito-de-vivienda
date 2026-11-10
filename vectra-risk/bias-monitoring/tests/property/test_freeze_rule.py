"""PBT-U9-04: `freeze` <=> poblacion `modelo` y algun atributo con limite R4 > umbral (BR-U9-11, F-03 opcion (b)).

Dos capas contra un oraculo por tabla de verdad: (1) `decide` con limites alrededor de los bordes (4,99 / 5,00 / 5,01 pp) en
cualquier atributo; (2) `attribute_limits` + `decide` sobre tablas de conteo reales, donde el atributo con el mayor limite
puede no ser el de la mayor agregada (el enmascaramiento de F-03).
"""

from __future__ import annotations

from decimal import Decimal

from hypothesis import given
from hypothesis import strategies as st
from support import GROUP_NAMES
from vectra_bias.freeze_rule import attribute_limits, decide
from vectra_disparity import ATTRIBUTES, BANDS, CountCell, CountTable, aggregate_lower_limit

N_MIN = 30
THRESHOLD = Decimal(5)
EDGES = [
    None,
    Decimal("-0.0100"),
    Decimal("0.0000"),
    Decimal("0.0499"),
    Decimal("0.0500"),
    Decimal("0.0501"),
    Decimal("0.3000"),
]
limit_strategy = st.one_of(st.sampled_from(EDGES), st.decimals(Decimal("-0.5"), Decimal("0.6"), places=4))
limits_strategy = st.fixed_dictionaries({a: limit_strategy for a in ATTRIBUTES})


def _truth_table(population: str, limits: dict[str, Decimal | None]) -> tuple[bool, bool]:
    """(freeze, rule_met) por definicion: algun atributo con agregada y limite > 5 pp; solo `modelo` congela."""
    met = any(v is not None and v > Decimal("0.05") for v in limits.values())
    return population == "modelo" and met, met


@given(population=st.sampled_from(["modelo", "humana"]), limits=limits_strategy)
def test_decide_matches_the_truth_table_for_any_attribute(population, limits):
    expected_freeze, expected_met = _truth_table(population, limits)
    decision = decide(population, THRESHOLD, limits)
    assert decision.freeze is expected_freeze
    assert decision.rule_met is expected_met
    assert (decision.reason == "supera_umbral") is expected_met
    assert [m.attribute for m in decision.met] == [
        a
        for a, _ in sorted(
            ((a, v) for a, v in limits.items() if v is not None and v > Decimal("0.05")),
            key=lambda kv: (-kv[1], kv[0]),
        )
    ]
    assert all(a.limit > Decimal("0.05") for a in decision.met)


@given(population=st.sampled_from(["modelo", "humana"]), limits=limits_strategy)
def test_all_insufficient_never_freezes(population, limits):
    decision = decide(population, THRESHOLD, dict.fromkeys(limits))
    assert not decision.freeze
    assert not decision.rule_met
    assert decision.reason == "muestra_insuficiente"


@given(limits=limits_strategy)
def test_the_human_population_never_freezes(limits):
    assert not decide("humana", THRESHOLD, limits).freeze


@given(
    limits=limits_strategy, threshold=st.sampled_from([Decimal(1), Decimal(5), Decimal("7.5"), Decimal(20)])
)
def test_the_threshold_is_in_percentage_points(limits, threshold):
    decision = decide("modelo", threshold, limits)
    assert decision.freeze is any(v is not None and v > threshold / 100 for v in limits.values())


@st.composite
def _attribute_table(draw, attribute):
    """2 a 6 grupos con un tamano de celda comun (chico o grande) y tasas con una brecha elegida: asi unos atributos quedan
    con limite alto y otros no, y el de la mayor agregada no siempre es el de mayor limite."""
    groups = GROUP_NAMES[: draw(st.integers(2, 6))]
    n = draw(st.sampled_from([30, 40, 100, 500, 3000]))
    gap = draw(st.sampled_from([0.0, 0.02, 0.06, 0.1, 0.2, 0.3]))
    cells = []
    for i, group in enumerate(groups):
        favorable = round(n * (0.5 + (gap if i == len(groups) - 1 else 0.0)))
        cells += [CountCell(group, band, favorable, n) for band in BANDS]
    return CountTable(attribute, tuple(cells))


@st.composite
def four_attributes(draw):
    return {a: draw(_attribute_table(a)) for a in ATTRIBUTES}


@given(counts=four_attributes())
def test_the_rule_over_real_counts_looks_at_every_attribute(counts):
    """Oraculo independiente: el limite R4 de cada atributo con la libreria, sin pasar por `attribute_limits`."""
    expected = {a: aggregate_lower_limit(counts, a, N_MIN) for a in ATTRIBUTES}
    decision = decide("modelo", THRESHOLD, attribute_limits(counts, N_MIN))
    assert decision.freeze is any(v is not None and v > Decimal("0.05") for v in expected.values())
    assert {m.attribute: m.limit for m in decision.met} == {
        a: v for a, v in expected.items() if v is not None and v > Decimal("0.05")
    }
