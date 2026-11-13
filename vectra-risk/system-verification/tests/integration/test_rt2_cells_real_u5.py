"""CA-9 (U12-T03, P-10): la regla de las celdas, atada a los datos reales de U5.

Genera la particion `test` con el **generador real y la configuracion completa** de U5 (`vectra_reference.generate.generate` con `load_config()`, sin `with_overrides`; solo datos, sin entrenar), en una carpeta del worktree, y la lee
con `simulator.read_delivery` y una fecha de evaluacion **fija** (el conteo de `56-65/lt_20` depende de ella). Compara el **conjunto** de celdas, no conteos escritos a mano.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from u5_delivery import SCRATCH, make_delivery, remove
from vectra_verification import sampler
from vectra_verification.scenarios import rt2
from vectra_verification.simulator import Population, Simulator, read_delivery

pytestmark = pytest.mark.integration

EVALUATED_ON = datetime(2026, 11, 13, tzinfo=UTC)
UNREACHABLE = {
    ("estrato", "6", "lt_20"),
    ("rango_edad", "56-65", "lt_20"),
    ("rango_edad", "66+", "20_30"),
    ("rango_edad", "66+", "gt_30"),
}
SEEDS = (3, 17, 2026)


@pytest.fixture(scope="module")
def population() -> Iterator[Population]:
    directory: Path = SCRATCH / f"real-u5-{os.getpid()}"
    make_delivery(directory, n_rows=None)
    try:
        yield read_delivery(directory, EVALUATED_ON)
    finally:
        remove(directory)


def simulator(population: Population) -> Simulator:
    return Simulator(None, None, None, population, "3fa9c2d1")  # type: ignore[arg-type]  # `select` solo mira la poblacion


def test_rt2_cells_real_u5_test_has_18000_rows_and_65_cells(population: Population) -> None:
    assert population.test_rows == 18000
    cells, _ = sampler.cell_report(population.rows, [], sampler.MIN_PER_CELL)
    assert len(cells) == 65


def test_rt2_cells_real_u5_the_cells_with_fewer_than_30_available_are_exactly_the_four_of_u9(population: Population) -> None:
    cells, _ = sampler.cell_report(population.rows, [], sampler.MIN_PER_CELL)
    short = {(c.attribute, c.group, c.band) for c in cells if c.available < sampler.MIN_PER_CELL}
    assert short == UNREACHABLE, f"con la fecha {EVALUATED_ON.date()} el conjunto cambio: {sorted(short ^ UNREACHABLE)}"


@pytest.mark.parametrize("seed", SEEDS)
def test_rt2_cells_real_u5_the_rule_runs_and_reports_those_four_and_the_other_61_have_30_or_more_taken(population: Population, seed: int) -> None:
    ids, short = simulator(population).select("stratified", 1500, seed)
    check = rt2.check_cells(short)  # no se niega
    assert {(c.attribute, c.group, c.band) for c in check.unreachable_short} == UNREACHABLE and check.reachable_short == ()
    cells, _ = sampler.cell_report(population.rows, [str(i) for i in ids], sampler.MIN_PER_CELL)
    others = [c for c in cells if (c.attribute, c.group, c.band) not in UNREACHABLE]
    assert len(others) == 61 and all(c.taken >= sampler.MIN_PER_CELL for c in others)
    assert len(ids) >= 1500  # el volumen es un piso (CANDIDATAS.md): se registra el pedido y el enviado, sin tope
