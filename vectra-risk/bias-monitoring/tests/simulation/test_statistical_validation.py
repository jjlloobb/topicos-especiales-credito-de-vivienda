"""Validacion estadistica (no PBT; BLM §3, NFR-U9-53): cobertura de Newcombe y las tres condiciones de BR-U9-11.

La regla que se mide es la de produccion, `vectra_bias.freeze_rule` (regla R4 sobre **todos** los atributos, F-03 opcion (b),
decision del usuario del 2026-11-10): la simulacion no la reimplementa.

Condicion 1: con disparidad real 0 y >= 500 casos por celda, congelamientos falsos <= 5 %.
Condicion 2: el modelo base de U5 (4,61 pp reales) congela <= 5 % con celdas de 50 a 100 casos (en 30, <= 6 %).
Condicion 3 (reformulada en el arbitraje de la ronda 2): con el lote `stratified` de BR-U12-06, la variante proxy actual de U5
(t = 1) congela >= 95 %, y una variante con disparidad real >= D* tambien. D* sale de `revisiones/U09-T02/busqueda-dstar.py`.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import numpy as np
import pytest
from vectra_bias.freeze_rule import attribute_limits, decide
from vectra_disparity import BANDS, CountCell, CountTable
from vectra_disparity.stats import newcombe_float

pytestmark = pytest.mark.simulation

REPETITIONS = 10_000
SEED = 20261109
N_MIN = 30
THRESHOLD = Decimal("0.05")  # 5 pp, expresado como proporcion
# Grupos informados por atributo en el catalogo de U0 (sexo F/M, rango_edad 6, region 6, estrato 1 a 6; `no_informado` no es extremo).
GROUPS = {"sexo": 2, "rango_edad": 6, "region": 6, "estrato": 6}
CELL_SIZES = (30, 100, 500, 2000)
BASE_CELL_SIZES = (30, 50, 100)
U5_COUNTS = Path(__file__).parents[1] / "doubles" / "u5_counts.json"
DSTAR_T = None  # se fija con `revisiones/U09-T02/busqueda-dstar.py`
STRATIFIED_BATCH = (
    1500  # ~1 500 casos `stratified` (BR-U12-06), repartidos en partes iguales por atributo, grupo y banda
)


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


def _stratified_cell(groups: int) -> int:
    return max(N_MIN, STRATIFIED_BATCH // (len(BANDS) * groups))


def _truth(variant: str) -> dict[str, np.ndarray]:
    """Tasas reales por atributo (grupo x banda) de U5; una celda de < 30 casos toma la tasa agrupada de su banda."""
    raw = json.loads(U5_COUNTS.read_text(encoding="utf-8"))[variant]
    truth: dict[str, np.ndarray] = {}
    for attribute, cells in raw.items():
        cells = [c for c in cells if c["group"] != "no_informado"]
        groups = sorted({c["group"] for c in cells})
        rates = np.zeros((len(groups), len(BANDS)))
        for b, band in enumerate(BANDS):
            in_band = [c for c in cells if c["band"] == band]
            pooled = sum(c["favorable"] for c in in_band) / sum(c["total"] for c in in_band)
            for c in in_band:
                rates[groups.index(c["group"]), b] = (
                    c["favorable"] / c["total"] if c["total"] >= N_MIN else pooled
                )
        truth[attribute] = rates
    return truth


def synthetic_variant(t: float) -> dict[str, np.ndarray]:
    """Variante sintetica entre el modelo base (t = 0) y el proxy de U5 (t = 1; mas alla, extrapola), tasas en [0, 1]."""
    base, proxy = _truth("base"), _truth("proxy")
    return {a: np.clip(base[a] + t * (proxy[a] - base[a]), 0.0, 1.0) for a in base}


def true_model_disparity(truth: dict[str, np.ndarray]) -> float:
    """Disparidad real del modelo: la mayor, entre atributos, de la media por banda de (tasa maxima - tasa minima)."""
    return max(float((rates.max(0) - rates.min(0)).mean()) for rates in truth.values())


def _freezes(counts: dict[str, CountTable]) -> bool:
    """BR-U9-11 (regla R4 sobre todos los atributos) con `vectra_bias.freeze_rule`, la misma que usa el CronJob."""
    return decide("modelo", Decimal(5), attribute_limits(counts, N_MIN)).freeze


def freeze_rate(truth: dict[str, np.ndarray], cell_size, repetitions: int, rng: np.random.Generator) -> float:
    """Proporcion de corridas que congelan cuando las tasas reales son `truth` y cada celda trae `cell_size(grupos)` casos."""
    freezes = 0
    for _ in range(repetitions):
        counts: dict[str, CountTable] = {}
        for attribute, rates in truth.items():
            groups = rates.shape[0]
            n = cell_size(groups)
            favorable = rng.binomial(n, rates)
            counts[attribute] = CountTable(
                attribute,
                tuple(
                    CountCell(f"g{g}", band, int(favorable[g, b]), n)
                    for g in range(groups)
                    for b, band in enumerate(BANDS)
                ),
            )
        freezes += _freezes(counts)
    return freezes / repetitions


NULL_TRUTH = {attribute: np.full((groups, len(BANDS)), 0.5) for attribute, groups in GROUPS.items()}


@pytest.fixture(scope="module")
def false_freeze_rates() -> dict[int, float]:
    rng = np.random.default_rng(SEED + 1)
    rates = {n: freeze_rate(NULL_TRUTH, lambda _g, n=n: n, REPETITIONS, rng) for n in CELL_SIZES}
    print("false_freeze_rate=" + json.dumps({str(n): r for n, r in rates.items()}))
    return rates


@pytest.fixture(scope="module")
def base_freeze_rates() -> dict[int, float]:
    rng = np.random.default_rng(SEED + 2)
    truth = _truth("base")
    print(f"base_true_disparity={true_model_disparity(truth):.4f}")
    rates = {n: freeze_rate(truth, lambda _g, n=n: n, REPETITIONS, rng) for n in BASE_CELL_SIZES}
    print("base_freeze_rate=" + json.dumps({str(n): r for n, r in rates.items()}))
    return rates


def test_false_freeze_rate_is_small_with_2000_cases_per_cell(false_freeze_rates):
    assert false_freeze_rates[2000] <= 0.05


def test_false_freeze_rate_is_at_most_5_percent_with_500_cases_per_cell(false_freeze_rates):
    assert false_freeze_rates[500] <= 0.05


def test_the_base_model_does_not_freeze_with_50_to_100_cases_per_cell(base_freeze_rates):
    assert base_freeze_rates[50] <= 0.05
    assert base_freeze_rates[100] <= 0.05


def test_the_base_model_freezes_at_most_6_percent_with_30_cases_per_cell(base_freeze_rates):
    assert base_freeze_rates[30] <= 0.06  # el margen documentado en `library.md`


def test_a_proxy_variant_with_the_minimum_disparity_freezes_at_least_95_percent_with_the_stratified_batch():
    truth = synthetic_variant(DSTAR_T)
    rate = freeze_rate(truth, _stratified_cell, REPETITIONS, np.random.default_rng(SEED + 3))
    print(f"dstar={true_model_disparity(truth):.4f} freeze_rate_stratified={rate:.4f}")
    assert rate >= 0.95
