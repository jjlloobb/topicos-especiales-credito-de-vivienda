"""Muestreo `normal` y `stratified` (U12 Paso 3; BR-U12-01, BR-U12-06; NFR-U12-10, NFR-U12-11). Logica pura: sin E/S.

La poblacion llega en memoria; derivar las etiquetas de monitoreo y leer la particion `test` de U5 es del `simulator` (Paso 6).
El azar es `random.Random(seed)` de la biblioteca estandar: sin `numpy` y sin el generador global.

`stratified` sigue el procedimiento de `stratified_sample` de U5 (el que midio que la variante proxy congela): orden al azar; se toma una fila si alguna
de sus celdas aun no llega a `min(min_per_cell, disponibles)`; despues se completa al azar hasta el volumen. El volumen es un piso: si las filas
tomadas para cubrir las celdas ya lo superan, la muestra es mas grande, como en U5. Una celda que no alcanza `min_per_cell` toma todas las filas que hay
y **no se rellena** con repetidas; el informe de celdas la nombra. Negarse a correr es de la seccion `rt2` (Paso 8), no del `sampler` (P-8).
"""

from __future__ import annotations

import random
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final

# Los mismos de `vectra_disparity.counts` (U9); U12 no depende de esa libreria y una prueba los compara.
ATTRIBUTES: Final = ("sexo", "rango_edad", "region", "estrato")
BANDS: Final = ("lt_20", "20_30", "gt_30")
MIN_PER_CELL: Final = 30

Cell = tuple[str, str, str]  # (atributo, grupo, banda)


@dataclass(frozen=True)
class Row:
    """Una fila de la poblacion: su identificador y las etiquetas de monitoreo (un grupo por atributo, y la banda)."""

    id: str
    groups: Mapping[str, str]
    band: str

    def __post_init__(self) -> None:
        if set(self.groups) != set(ATTRIBUTES):
            raise ValueError(f"row_attributes:{self.id}")
        if self.band not in BANDS:
            raise ValueError(f"row_band_unknown:{self.band}")

    @property
    def cells(self) -> tuple[Cell, ...]:
        return tuple((attribute, self.groups[attribute], self.band) for attribute in ATTRIBUTES)


@dataclass(frozen=True)
class CellReport:
    attribute: str
    group: str
    band: str
    available: int
    taken: int


@dataclass(frozen=True)
class StratifiedSample:
    """Los identificadores muestreados (en el orden en que se tomaron), el informe de cada celda y las celdas que no alcanzan."""

    ids: tuple[str, ...]
    cells: tuple[CellReport, ...]
    short: tuple[CellReport, ...]


def _check_population(population: Sequence[Row]) -> None:
    if len({row.id for row in population}) != len(population):
        raise ValueError("population_duplicate_id")


def _check_volume(population: Sequence[Row], volume: int) -> None:
    if volume < 0:
        raise ValueError("volume_negative")
    if volume > len(population):
        raise ValueError(f"volume_exceeds_population:{volume}>{len(population)}")


def normal(population: Sequence[Row], volume: int, seed: int) -> tuple[str, ...]:
    """Muestra al azar, sin repeticion, de `volume` filas (BR-U12-01, escenario `normal`). Un volumen mayor que la poblacion es un error."""
    _check_population(population)
    _check_volume(population, volume)
    order = list(range(len(population)))
    random.Random(seed).shuffle(order)  # noqa: S311 - muestreo reproducible con semilla, no criptografia
    return tuple(population[i].id for i in order[:volume])


def cell_report(
    population: Sequence[Row], ids: Sequence[str], min_per_cell: int
) -> tuple[tuple[CellReport, ...], tuple[CellReport, ...]]:
    """Por cada celda de la poblacion, `disponibles` y `tomadas` en `ids`; y las que quedan por debajo de `min_per_cell`."""
    chosen = set(ids)
    available: Counter[Cell] = Counter()
    taken: Counter[Cell] = Counter()
    for row in population:
        available.update(row.cells)
        if row.id in chosen:
            taken.update(row.cells)
    cells = tuple(CellReport(*cell, available[cell], taken[cell]) for cell in sorted(available))
    return cells, tuple(c for c in cells if c.taken < min_per_cell)


def stratified(
    population: Sequence[Row], volume: int, seed: int, min_per_cell: int = MIN_PER_CELL
) -> StratifiedSample:
    """Muestra `stratified` (BR-U12-01, BR-U12-06): >= `min_per_cell` en cada celda que lo permita, hasta `volume` filas (como minimo)."""
    if min_per_cell < 1:
        raise ValueError("min_per_cell_below_one")
    _check_population(population)
    _check_volume(population, volume)
    available: Counter[Cell] = Counter(cell for row in population for cell in row.cells)
    order = list(range(len(population)))
    random.Random(seed).shuffle(order)  # noqa: S311 - muestreo reproducible con semilla, no criptografia
    taken: Counter[Cell] = Counter()
    chosen: list[int] = []
    skipped: list[int] = []
    for i in order:
        cells = population[i].cells
        if any(taken[c] < min(min_per_cell, available[c]) for c in cells):
            chosen.append(i)
            taken.update(cells)
        else:
            skipped.append(i)
    chosen += skipped[: max(0, volume - len(chosen))]
    ids = tuple(population[i].id for i in chosen)
    cells_report, short = cell_report(population, ids, min_per_cell)
    return StratifiedSample(ids=ids, cells=cells_report, short=short)
