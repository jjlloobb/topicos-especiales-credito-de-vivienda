"""Tasa de congelamiento de la regla R4 (BR-U9-11) sobre muestras `stratified` REALES de `test` (BR-U5-14, U05-T05).

Cada muestra sale del dataset `test` de U5 con la composicion de BR-U12-06: se elige al azar (semilla fija) hasta que
cada celda de U9 (atributo, grupo, banda) de los cuatro atributos tenga >= 30 casos, y se completa al azar hasta
~1 500 casos. El reparto por celda es el del muestreo, no el de celdas iguales. R4 se aplica con la libreria real: el
atributo disparador de `model_aggregate` y `aggregate_lower_limit` con `Z_FREEZE` contra el umbral de 5 pp.

La variante debe congelar en >= 95 % de las muestras y el modelo base en <= 5 %.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import date
from decimal import Decimal
from typing import Any

import numpy as np
import pytest
from vectra_disparity import ATTRIBUTES, CountTable, aggregate_lower_limit, counts_from_records
from vectra_reference import proxy as px
from vectra_reference.generate import load_config
from vectra_reference.release import ProxyRelease, Release, partition_outcomes

pytestmark = pytest.mark.simulation

SEED = 20261109
SAMPLES = 2_000  # N >= 2 000
BATCH = 1_500  # ~1 500 casos `stratified` (BR-U12-06)
N_MIN = px.N_MIN  # 30 por celda de U9
THRESHOLD = Decimal("0.05")  # umbral de congelamiento: 5 pp como proporcion
FREEZE_MIN = 0.95  # variante
FREEZE_MAX = 0.05  # modelo base


def labelled(
    rows: Sequence[Mapping[str, Any]], outcomes: Sequence[str], evaluated_on: date
) -> list[dict[str, str]]:
    return [
        {**px.monitoring_labels(row, evaluated_on), "outcome": outcome}
        for row, outcome in zip(rows, outcomes, strict=True)
    ]


def _cells(record: Mapping[str, str]) -> list[tuple[str, str, str]]:
    return [(a, record[a], record["banda"]) for a in ATTRIBUTES]


def stratified_sample(
    records: Sequence[Mapping[str, str]], rng: np.random.Generator, batch: int = BATCH, n_min: int = N_MIN
) -> list[int]:
    """Indices de una muestra `stratified` (BR-U12-06): >= `n_min` en cada celda alcanzable y ~`batch` casos en total.

    Recorre `records` en orden aleatorio y toma un caso si alguna de sus celdas aun no llega a `n_min`; despues completa
    al azar hasta `batch`. Una celda con menos de `n_min` casos en todo `test` toma todos los que hay.
    """
    available = Counter(cell for record in records for cell in _cells(record))
    order = [int(i) for i in rng.permutation(len(records))]
    taken: Counter[tuple[str, str, str]] = Counter()
    chosen: list[int] = []
    skipped: list[int] = []
    for i in order:
        cells = _cells(records[i])
        if any(taken[c] < min(n_min, available[c]) for c in cells):
            chosen.append(i)
            taken.update(cells)
        else:
            skipped.append(i)
    chosen += skipped[: max(0, batch - len(chosen))]
    return chosen


def r4_freezes(counts: Mapping[str, CountTable]) -> bool:
    """BR-U9-11 (regla R4): el limite inferior de la agregada del atributo disparador, con `Z_FREEZE`, supera 5 pp."""
    trigger, _ = px.model_trigger(counts)
    limit = aggregate_lower_limit(counts, trigger, N_MIN)
    return limit is not None and limit > THRESHOLD


def freeze_rate(records: Sequence[Mapping[str, str]], samples: int, seed: int) -> tuple[float, int]:
    """(proporcion de muestras `stratified` que R4 congela, tamano medio de la muestra)."""
    rng = np.random.default_rng(seed)
    frozen, total = 0, 0
    for _ in range(samples):
        chosen = stratified_sample(records, rng)
        total += len(chosen)
        frozen += r4_freezes(counts_from_records(records[i] for i in chosen))
    return frozen / samples, round(total / samples)


@pytest.fixture(scope="module")
def evaluated_on() -> date:
    return date.fromisoformat(str(load_config()["reference_date"]))


def test_r4_freezes_the_proxy_variant_in_at_least_95_percent_and_the_base_in_at_most_5_percent_of_stratified_samples(
    reference_release: Release, reference_proxy: ProxyRelease, evaluated_on: date
) -> None:
    base_records = labelled(*partition_outcomes(reference_release), evaluated_on)
    proxy_records = labelled(*partition_outcomes(reference_release, reference_proxy), evaluated_on)
    cell_sizes = Counter(
        cell
        for i in stratified_sample(proxy_records, np.random.default_rng(SEED))
        for cell in _cells(proxy_records[i])
    )
    base_rate, base_size = freeze_rate(base_records, SAMPLES, SEED + 1)
    proxy_rate, proxy_size = freeze_rate(proxy_records, SAMPLES, SEED + 2)
    print(  # noqa: T201
        f"\nsamples={SAMPLES} seed={SEED} batch~{BATCH} (media base={base_size}, variante={proxy_size}); "
        f"celdas de la primera muestra: {len(cell_sizes)}, minima={min(cell_sizes.values())}"
    )
    print(f"freeze_rate_proxy={proxy_rate:.4f} freeze_rate_base={base_rate:.4f}")  # noqa: T201
    assert SAMPLES >= 2_000
    assert proxy_rate >= FREEZE_MIN
    assert base_rate <= FREEZE_MAX


def test_a_stratified_sample_reaches_30_cases_in_every_reachable_cell(
    reference_release: Release, evaluated_on: date
) -> None:
    records = labelled(*partition_outcomes(reference_release), evaluated_on)
    available = Counter(cell for record in records for cell in _cells(record))
    chosen = stratified_sample(records, np.random.default_rng(SEED))
    got = Counter(cell for i in chosen for cell in _cells(records[i]))
    assert all(got[cell] >= min(N_MIN, n) for cell, n in available.items())
    assert len(chosen) == len(set(chosen)) >= BATCH
