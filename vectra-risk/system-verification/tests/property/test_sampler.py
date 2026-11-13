"""PBT-U12-01, `sampler` (U12 Paso 3; BR-U12-01, BR-U12-06; NFR-U12-10, NFR-U12-11) y sus ejemplos.

El oraculo cuenta por definicion, recorriendo la poblacion y la muestra; no reusa funciones de `sampler`.
"""

import random
from collections import Counter

import pytest
from hypothesis import given
from hypothesis import strategies as st

from vectra_verification import sampler
from vectra_verification.sampler import ATTRIBUTES, BANDS, Row

GROUP_NAMES = {
    "sexo": ["F", "M", "otro", "no_informado"],
    "rango_edad": ["18_25", "26_35", "36_50", "51_mas"],
    "region": ["andina", "caribe", "pacifica", "orinoquia", "amazonia"],
    "estrato": ["1", "2", "3", "4", "5", "6"],
}


def make_row(index: int, code: tuple[int, int, int, int, int]) -> Row:
    groups = {a: GROUP_NAMES[a][code[i] % len(GROUP_NAMES[a])] for i, a in enumerate(ATTRIBUTES)}
    return Row(id=f"SYN-{index:05d}", groups=groups, band=BANDS[code[4] % len(BANDS)])


CODES = st.tuples(
    st.integers(0, 3), st.integers(0, 3), st.integers(0, 4), st.integers(0, 5), st.integers(0, 2)
)
# Poblaciones con celdas de todos los tamanos: pocos valores por atributo (celdas grandes), pero tambien cola de celdas chicas y vacias.
POPULATIONS = st.lists(CODES, max_size=400).map(lambda codes: [make_row(i, c) for i, c in enumerate(codes)])
MIN_PER_CELL = st.integers(1, 40)
SEEDS = st.integers(0, 2**32)


def counts(population: list[Row], ids: tuple[str, ...] | list[str]) -> tuple[Counter, Counter]:
    """(disponibles, tomadas) por celda, contando por definicion."""
    chosen = set(ids)
    available: Counter = Counter()
    taken: Counter = Counter()
    for row in population:
        for attribute in ATTRIBUTES:
            cell = (attribute, row.groups[attribute], row.band)
            available[cell] += 1
            if row.id in chosen:
                taken[cell] += 1
    return available, taken


# Poblaciones grandes y concentradas (F-03): de 30 a 400 filas, con codigos sesgados hacia un valor dominante por atributo, asi que hay celdas con 30 filas o mas
# y, a la vez, una cola de celdas chicas y vacias. Un `min_per_cell` de 1 a 40 y volumenes de todo el rango: celdas llenas y cortas en el mismo ejemplo.
SKEWED = st.tuples(
    st.sampled_from([0, 0, 0, 0, 1, 1, 2, 3]),
    st.sampled_from([0, 0, 0, 1, 2, 3]),
    st.sampled_from([0, 0, 0, 1, 2, 3, 4]),
    st.sampled_from([0, 0, 1, 1, 2, 3, 4, 5]),
    st.sampled_from([0, 0, 1, 2]),
)
BIG_POPULATIONS = st.lists(SKEWED, min_size=30, max_size=400).map(
    lambda codes: [make_row(i, c) for i, c in enumerate(codes)]
)
BIG_MIN_PER_CELL = st.one_of(st.integers(1, 40), st.integers(10, 40))


@st.composite
def stratified_inputs(draw):  # type: ignore[no-untyped-def]
    if draw(st.booleans()):
        population = draw(BIG_POPULATIONS)
        minimum = draw(BIG_MIN_PER_CELL)
    else:
        population = draw(POPULATIONS)
        minimum = draw(MIN_PER_CELL)
    volume = draw(
        st.one_of(st.integers(0, len(population)), st.integers(len(population) // 2, len(population)))
    )
    return population, volume, draw(SEEDS), minimum


@given(stratified_inputs())
def test_every_cell_with_enough_data_reaches_the_minimum(args) -> None:  # type: ignore[no-untyped-def]
    population, volume, seed, minimum = args
    sample = sampler.stratified(population, volume, seed, minimum)
    available, taken = counts(population, sample.ids)
    for cell, n in available.items():
        assert taken[cell] >= min(minimum, n)


@given(stratified_inputs())
def test_no_repeated_rows_and_all_from_the_population(args) -> None:  # type: ignore[no-untyped-def]
    population, volume, seed, minimum = args
    sample = sampler.stratified(population, volume, seed, minimum)
    assert len(sample.ids) == len(set(sample.ids))
    assert set(sample.ids) <= {row.id for row in population}
    assert volume <= len(sample.ids) <= len(population)


@given(stratified_inputs())
def test_same_seed_same_sample_in_the_same_order(args) -> None:  # type: ignore[no-untyped-def]
    population, volume, seed, minimum = args
    assert sampler.stratified(population, volume, seed, minimum) == sampler.stratified(
        population, volume, seed, minimum
    )


@given(stratified_inputs())
def test_the_global_random_generator_is_not_used(args) -> None:  # type: ignore[no-untyped-def]
    population, volume, seed, minimum = args
    before = random.getstate()
    sampler.stratified(population, volume, seed, minimum)
    sampler.normal(population, volume, seed)
    assert random.getstate() == before


@given(stratified_inputs())
def test_a_short_cell_is_reported_and_not_filled(args) -> None:  # type: ignore[no-untyped-def]
    population, volume, seed, minimum = args
    sample = sampler.stratified(population, volume, seed, minimum)
    available, taken = counts(population, sample.ids)
    expected_short = {cell for cell, n in available.items() if n < minimum}
    assert {(c.attribute, c.group, c.band) for c in sample.short} == expected_short
    for c in sample.short:
        assert (
            c.taken == c.available == available[(c.attribute, c.group, c.band)]
        )  # toma todas las que hay, sin repetir
    reported = {(c.attribute, c.group, c.band): (c.available, c.taken) for c in sample.cells}
    assert reported == {cell: (n, taken[cell]) for cell, n in available.items()}


@given(POPULATIONS, SEEDS)
def test_the_whole_population_when_the_volume_is_all_of_it(population, seed) -> None:  # type: ignore[no-untyped-def]
    sample = sampler.stratified(population, len(population), seed, 30)
    assert sorted(sample.ids) == sorted(row.id for row in population)
    assert sample.short == tuple(c for c in sample.cells if c.available < 30)


@given(stratified_inputs())
def test_the_sample_is_exactly_the_cover_or_the_volume_whichever_is_larger(args) -> None:  # type: ignore[no-untyped-def]
    """El volumen es un piso (como en U5): `max(volumen, filas que cubren las celdas)`. La cobertura no depende del volumen."""
    population, volume, seed, minimum = args
    cover = sampler.stratified(population, 0, seed, minimum)
    sample = sampler.stratified(population, volume, seed, minimum)
    assert len(sample.ids) == max(volume, len(cover.ids))
    assert sample.ids[: len(cover.ids)] == cover.ids  # primero lo que cubre las celdas, despues el relleno


@given(BIG_POPULATIONS, st.integers(1, 40), st.lists(SEEDS, min_size=3, max_size=3, unique=True))
def test_the_seed_changes_the_sample_and_the_order(population, minimum, seeds) -> None:  # type: ignore[no-untyped-def]
    """Semillas distintas, muestras distintas (F-03: una muestra que ignora la semilla no debe pasar)."""
    volume = len(population) // 2
    strat = {sampler.stratified(population, volume, seed, minimum).ids for seed in seeds}
    norm = {sampler.normal(population, volume, seed) for seed in seeds}
    assert len(strat) > 1 and len(norm) > 1


@given(BIG_POPULATIONS, SEEDS)
def test_normal_is_a_random_draw_and_not_the_front_of_the_population(population, seed) -> None:  # type: ignore[no-untyped-def]
    volume = len(population) // 2
    ids = sampler.normal(population, volume, seed)
    assert list(ids) != [row.id for row in population[:volume]]
    assert set(ids) != {row.id for row in population[:volume]} or len(population) < 40


@st.composite
def normal_inputs(draw):  # type: ignore[no-untyped-def]
    population = draw(st.one_of(POPULATIONS, BIG_POPULATIONS))
    return population, draw(st.integers(0, len(population))), draw(SEEDS)


@given(normal_inputs())
def test_normal_has_the_requested_size_without_repeats(args) -> None:  # type: ignore[no-untyped-def]
    population, volume, seed = args
    ids = sampler.normal(population, volume, seed)
    assert len(ids) == volume == len(set(ids))
    assert set(ids) <= {row.id for row in population}


@given(normal_inputs())
def test_normal_is_deterministic_with_the_seed(args) -> None:  # type: ignore[no-untyped-def]
    population, volume, seed = args
    assert sampler.normal(population, volume, seed) == sampler.normal(population, volume, seed)


@given(POPULATIONS, st.integers(1, 50), SEEDS)
def test_a_volume_larger_than_the_population_is_an_error(population, extra, seed) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(ValueError, match="volume_exceeds_population"):
        sampler.normal(population, len(population) + extra, seed)
    with pytest.raises(ValueError, match="volume_exceeds_population"):
        sampler.stratified(population, len(population) + extra, seed)


# --- ejemplos ---


def test_attributes_and_bands_equal_those_of_u9() -> None:
    from vectra_disparity import counts as u9

    assert sampler.ATTRIBUTES == u9.ATTRIBUTES and sampler.BANDS == u9.BANDS
    assert sampler.MIN_PER_CELL == 30


def test_a_population_with_a_small_cell_is_reported_by_the_sampler() -> None:
    """NFR-U12-11: la celda chica se informa (que `rt2` se niegue es del Paso 8)."""
    rows = [
        Row(
            f"SYN-{i:03d}",
            {"sexo": "F" if i < 60 else "M", "rango_edad": "26_35", "region": "andina", "estrato": "3"},
            "20_30",
        )
        for i in range(80)
    ]
    sample = sampler.stratified(rows, 80, seed=7)
    short = {(c.attribute, c.group, c.band): (c.available, c.taken) for c in sample.short}
    assert short == {("sexo", "M", "20_30"): (20, 20)}
    assert len(sample.ids) == 80


def test_stratified_composes_like_u5_cells_first_then_fills_up_to_the_volume() -> None:
    rows = [
        Row(f"R{i:03d}", {"sexo": "F", "rango_edad": "26_35", "region": "andina", "estrato": "3"}, "gt_30")
        for i in range(200)
    ]
    rows += [
        Row(f"S{i:03d}", {"sexo": "M", "rango_edad": "26_35", "region": "andina", "estrato": "3"}, "gt_30")
        for i in range(35)
    ]
    sample = sampler.stratified(rows, 100, seed=1)
    assert len(sample.ids) == 100 and sample.short == ()
    available, taken = counts(rows, sample.ids)
    assert taken[("sexo", "M", "gt_30")] >= 30 and taken[("sexo", "F", "gt_30")] >= 30


def test_the_volume_is_a_floor_when_covering_the_cells_needs_more_rows() -> None:
    rows = [
        Row(
            f"R{i:03d}",
            {"sexo": f"g{i % 10}", "rango_edad": "26_35", "region": "andina", "estrato": "3"},
            "gt_30",
        )
        for i in range(400)
    ]
    sample = sampler.stratified(rows, 50, seed=3, min_per_cell=30)
    assert len(sample.ids) >= 300  # 10 grupos de `sexo` x 30
    assert sample.short == ()


def test_invalid_inputs_are_errors() -> None:
    good = {"sexo": "F", "rango_edad": "26_35", "region": "andina", "estrato": "3"}
    with pytest.raises(ValueError, match="row_attributes"):
        Row("x", {"sexo": "F"}, "gt_30")
    with pytest.raises(ValueError, match="row_band_unknown"):
        Row("x", good, "40_50")
    rows = [Row("x", good, "gt_30"), Row("x", good, "gt_30")]
    with pytest.raises(ValueError, match="population_duplicate_id"):
        sampler.normal(rows, 1, 0)
    with pytest.raises(ValueError, match="population_duplicate_id"):
        sampler.stratified(rows, 1, 0)
    with pytest.raises(ValueError, match="volume_negative"):
        sampler.normal(rows[:1], -1, 0)
    with pytest.raises(ValueError, match="min_per_cell_below_one"):
        sampler.stratified(rows[:1], 1, 0, 0)


def test_cell_report_counts_available_and_taken() -> None:
    rows = [
        Row(
            f"R{i}",
            {"sexo": "F" if i % 2 else "M", "rango_edad": "a", "region": "r", "estrato": "1"},
            "lt_20",
        )
        for i in range(10)
    ]
    cells, short = sampler.cell_report(rows, ["R0", "R1", "R2"], 3)
    by_cell = {(c.attribute, c.group): (c.available, c.taken) for c in cells}
    assert by_cell[("sexo", "M")] == (5, 2) and by_cell[("sexo", "F")] == (5, 1)
    assert by_cell[("estrato", "1")] == (10, 3)
    assert {(c.attribute, c.group) for c in short} == {("sexo", "M"), ("sexo", "F")}
