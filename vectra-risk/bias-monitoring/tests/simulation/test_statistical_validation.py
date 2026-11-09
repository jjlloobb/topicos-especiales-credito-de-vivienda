"""Validacion estadistica (no PBT; BLM §3, NFR-U9-53): cobertura de Newcombe y congelamientos falsos de BR-U9-11."""

from __future__ import annotations

import json
from decimal import Decimal

import numpy as np
import pytest
from vectra_disparity import BANDS, CountCell, CountTable, disparity_by_band
from vectra_disparity.stats import newcombe_float

pytestmark = pytest.mark.simulation

REPETITIONS = 10_000
SEED = 20261109
N_MIN = 30
THRESHOLD = Decimal("0.05")  # 5 pp, expresado como proporcion
# Grupos informados por atributo en el catalogo de U0 (sexo F/M, rango_edad 6, region 6, estrato 1 a 6; `no_informado` no es extremo).
GROUPS = {"sexo": 2, "rango_edad": 6, "region": 6, "estrato": 6}
CELL_SIZES = (30, 100, 500, 2000)


def test_newcombe_interval_covers_the_true_difference_in_at_least_93_percent():
    rng = np.random.default_rng(SEED)
    p1, p2, n1, n2 = 0.55, 0.45, 100, 100
    true_difference = p1 - p2
    x1 = rng.binomial(n1, p1, REPETITIONS)
    x2 = rng.binomial(n2, p2, REPETITIONS)
    covered = 0
    for a, b in zip(x1.tolist(), x2.tolist(), strict=True):
        _, lower, upper = newcombe_float(a, n1, b, n2)
        covered += lower <= true_difference <= upper
    coverage = covered / REPETITIONS
    print(f"newcombe_coverage={coverage:.4f}")
    assert coverage >= 0.93


def _false_freeze_rate(n_cell: int, repetitions: int, rng: np.random.Generator) -> float:
    """Con disparidad real 0 (todos los grupos con la misma tasa 0,5): proporcion de corridas en que BR-U9-11 congela.

    Condicion de BR-U9-11 evaluada sobre la salida de la libreria: agregada del modelo > umbral Y limite inferior del
    intervalo de esa agregada > 0. `freeze_rule` llega en el Bloque C; aqui no existe todavia.
    """
    freezes = 0
    for _ in range(repetitions):
        counts: dict[str, CountTable] = {}
        for attribute, groups in GROUPS.items():
            favorable = rng.binomial(n_cell, 0.5, (groups, len(BANDS)))
            counts[attribute] = CountTable(
                attribute,
                tuple(
                    CountCell(f"g{g}", band, int(favorable[g, b]), n_cell)
                    for g in range(groups)
                    for b, band in enumerate(BANDS)
                ),
            )
        best: tuple[Decimal, Decimal] | None = None
        for attribute in GROUPS:
            result = disparity_by_band(counts, attribute, N_MIN)
            if result.aggregate is not None and (best is None or result.aggregate > best[0]):
                best = (result.aggregate, result.aggregate_ci_95[0])  # type: ignore[index]
        freezes += best is not None and best[0] > THRESHOLD and best[1] > 0
    return freezes / repetitions


@pytest.fixture(scope="module")
def false_freeze_rates() -> dict[int, float]:
    rng = np.random.default_rng(SEED + 1)
    rates = {n: _false_freeze_rate(n, REPETITIONS, rng) for n in CELL_SIZES}
    print("false_freeze_rate=" + json.dumps({str(n): r for n, r in rates.items()}))
    return rates


def test_false_freeze_rate_is_small_with_2000_cases_per_cell(false_freeze_rates):
    assert false_freeze_rates[2000] <= 0.05


@pytest.mark.xfail(
    strict=True,
    reason=(
        "HALLAZGO (U09-T01): el diseno exige <= 5 % con >= 500 casos por celda, pero con disparidad real 0 y los cuatro "
        "atributos (hasta 6 grupos) la condicion de BR-U9-11 congela en ~96 % de las corridas con 500 casos por celda: "
        "el intervalo trata el par extremo como si se hubiera fijado de antemano. Ver library.md y la bitacora."
    ),
)
def test_false_freeze_rate_is_at_most_5_percent_with_500_cases_per_cell(false_freeze_rates):
    assert false_freeze_rates[500] <= 0.05
