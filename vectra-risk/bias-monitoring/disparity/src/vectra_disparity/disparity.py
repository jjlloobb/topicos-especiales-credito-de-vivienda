"""Disparidad por grupo, banda y atributo (BR-U9-01..06; P-U9-04; NFR-U9-31).

Los tipos de resultado llevan los mismos nombres de campo que los de U0 §9.4 (`CellResult`, `BandResult`,
`AttributeResult`), con cifras en `Decimal` de 4 decimales; `to_dict` los pasa a la forma JSON de U0 (cadenas `Decimal4`).
Las cifras (tasas, diferencias, agregadas e intervalos) son proporciones, la misma escala que `rate`: 5 pp = 0,05.

La supresion de celdas chicas esta siempre aplicada: una celda con `n < n_min` nunca lleva `rate`, nunca entra en una
diferencia, y la diferencia sin bandas excluye a todo grupo que tenga alguna celda insuficiente.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, fields, is_dataclass
from decimal import Decimal
from fractions import Fraction
from typing import Any

from vectra_disparity.counts import ATTRIBUTES, BANDS, UNINFORMED, CountTable
from vectra_disparity.stats import (
    Z_FREEZE,
    band_variance,
    combined_variance,
    newcombe_float,
    normal_interval,
    quantize4,
)

SUFFICIENT = "suficiente"
INSUFFICIENT = "muestra_insuficiente"


@dataclass(frozen=True)
class CellResult:
    group: str
    band: str
    n: int
    rate: Decimal | None
    status: str


@dataclass(frozen=True)
class BandResult:
    band: str
    difference: Decimal | None
    extreme_pair: tuple[str, str] | None
    ci_95: tuple[Decimal, Decimal] | None
    n_band: int


@dataclass(frozen=True)
class AttributeResult:
    attribute: str
    cells: tuple[CellResult, ...]
    bands: tuple[BandResult, ...]
    aggregate: Decimal | None
    aggregate_ci_95: tuple[Decimal, Decimal] | None
    population_difference: Decimal | None
    population_difference_partial: bool


@dataclass(frozen=True)
class _Cell:
    group: str
    band: str
    favorable: int
    n: int

    @property
    def rate(self) -> Fraction:
        return Fraction(self.favorable, self.n)


def _merged(table: CountTable | None) -> list[_Cell]:
    """Las celdas de la tabla, sumando las repetidas, ordenadas por (grupo, banda)."""
    sums: dict[tuple[str, str], list[int]] = {}
    for cell in () if table is None else table.cells:
        acc = sums.setdefault((cell.group, cell.band), [0, 0])
        acc[0] += cell.favorable
        acc[1] += cell.total
    return [
        _Cell(group, band, favorable, n)
        for (group, band), (favorable, n) in sorted(
            sums.items(), key=lambda kv: (kv[0][0], BANDS.index(kv[0][1]))
        )
    ]


def _extremes(eligible: list[_Cell]) -> tuple[_Cell, _Cell]:
    """(mayor, menor) por tasa; en empate, el de menor nombre de grupo (no depende del orden de entrada).

    Siempre son dos grupos distintos: con todas las tasas iguales, el menor es el primero por nombre y el mayor, el segundo.
    """
    ordered = sorted(eligible, key=lambda c: (c.rate, c.group))
    lowest = ordered[0]
    top = ordered[-1].rate
    highest = next(c for c in ordered[1:] if c.rate == top)
    return highest, lowest


def _bands(
    cells: list[_Cell], sufficient: Mapping[tuple[str, str], bool]
) -> tuple[tuple[BandResult, ...], tuple[Fraction, float] | None]:
    """Diferencia por banda y, si alguna banda la tiene, la agregada exacta con su varianza (BR-U9-02, 04)."""
    band_results: list[BandResult] = []
    weighted: list[tuple[int, Fraction, float]] = []  # (n_b, d_b, v_b) de las bandas con diferencia
    for band in BANDS:
        eligible = [
            c for c in cells if c.band == band and sufficient[(c.group, band)] and c.group != UNINFORMED
        ]
        n_band = sum(c.n for c in eligible)
        if len(eligible) < 2:
            band_results.append(BandResult(band, None, None, None, n_band))
            continue
        highest, lowest = _extremes(eligible)
        _, lower, upper = newcombe_float(highest.favorable, highest.n, lowest.favorable, lowest.n)
        difference = highest.rate - lowest.rate
        band_results.append(
            BandResult(
                band,
                quantize4(difference),
                (highest.group, lowest.group),
                (quantize4(lower), quantize4(upper)),
                n_band,
            )
        )
        weighted.append((n_band, difference, band_variance(lower, upper)))
    if not weighted:
        return tuple(band_results), None
    total = sum(n for n, _, _ in weighted)
    exact = sum((Fraction(n, total) * d for n, d, _ in weighted), Fraction(0))
    variance = combined_variance([n / total for n, _, _ in weighted], [v for _, _, v in weighted])
    return tuple(band_results), (exact, variance)


def disparity_by_band(counts: Mapping[str, CountTable], attribute: str, n_min: int) -> AttributeResult:
    """Resultado de un atributo: celdas, diferencia por banda, agregada ponderada y diferencia sin bandas.

    `counts` es lo que devuelven `counts_from_records` o `counts_from_marginals`. `n_min` es el de
    `values-monitoring-policy.yaml` (30 hoy); no es una constante de la libreria.
    """
    if n_min < 1:
        raise ValueError(f"n_min_invalid:{n_min}")
    cells = _merged(counts.get(attribute))
    sufficient = {(c.group, c.band): c.n >= n_min for c in cells}
    cell_results = tuple(
        CellResult(
            c.group,
            c.band,
            c.n,
            quantize4(c.rate) if sufficient[(c.group, c.band)] else None,
            SUFFICIENT if sufficient[(c.group, c.band)] else INSUFFICIENT,
        )
        for c in cells
    )

    band_results, aggregate_parts = _bands(cells, sufficient)
    aggregate: Decimal | None = None
    aggregate_ci: tuple[Decimal, Decimal] | None = None
    if aggregate_parts is not None:
        exact, variance = aggregate_parts
        low, high = normal_interval(float(exact), variance)
        aggregate, aggregate_ci = quantize4(exact), (quantize4(low), quantize4(high))

    population_difference, partial = _population_difference(cells, sufficient)
    return AttributeResult(
        attribute, cell_results, band_results, aggregate, aggregate_ci, population_difference, partial
    )


def _population_difference(
    cells: list[_Cell], sufficient: Mapping[tuple[str, str], bool]
) -> tuple[Decimal | None, bool]:
    """BR-U9-06: diferencia sin bandas, sin la tasa de un grupo con alguna celda insuficiente (sin inferencia por resta)."""
    totals: dict[str, list[int]] = {}
    excluded: set[str] = set()
    for c in cells:
        if c.group == UNINFORMED:
            continue
        if not sufficient[(c.group, c.band)]:
            excluded.add(c.group)
        acc = totals.setdefault(c.group, [0, 0])
        acc[0] += c.favorable
        acc[1] += c.n
    rates = [Fraction(f, n) for group, (f, n) in totals.items() if group not in excluded]
    difference = quantize4(max(rates) - min(rates)) if len(rates) >= 2 else None
    return difference, bool(excluded)


def aggregate_lower_limit(
    counts: Mapping[str, CountTable], attribute: str, n_min: int, z: float = Z_FREEZE
) -> Decimal | None:
    """Limite inferior de la agregada del atributo con la `z` de Bonferroni de BR-U9-11 (regla R4); `None` si es insuficiente.

    Es `D_a - z * sqrt(Var(D_a))` con la misma `Var(D_a)` de BR-U9-04; solo cambia la `z` (3,14 en vez de 1,96). El
    intervalo de 95 % que se publica (`aggregate_ci_95`) no cambia. `freeze_rule` congela si este limite, del atributo
    disparador (BR-U9-05), es mayor que el umbral; `z` es un argumento solo para las pruebas.
    """
    if n_min < 1:
        raise ValueError(f"n_min_invalid:{n_min}")
    cells = _merged(counts.get(attribute))
    sufficient = {(c.group, c.band): c.n >= n_min for c in cells}
    _, parts = _bands(cells, sufficient)
    if parts is None:
        return None
    exact, variance = parts
    return quantize4(normal_interval(float(exact), variance, z)[0])


def model_aggregate(results: Iterable[AttributeResult]) -> tuple[str, Decimal] | None:
    """BR-U9-05: la mayor agregada con valor y el atributo que la produce; `None` si todas son insuficientes.

    En empate gana el primero de la secuencia recibida.
    """
    best: tuple[str, Decimal] | None = None
    for result in results:
        if result.aggregate is not None and (best is None or result.aggregate > best[1]):
            best = (result.attribute, result.aggregate)
    return best


def to_dict(value: Any) -> Any:
    """Forma JSON de U0: dataclases a mapeos, tuplas a listas y `Decimal` a cadena (`Decimal4`)."""
    if is_dataclass(value) and not isinstance(value, type):
        return {f.name: to_dict(getattr(value, f.name)) for f in fields(value)}
    if isinstance(value, tuple | list):
        return [to_dict(v) for v in value]
    if isinstance(value, Decimal):
        return str(value)
    return value


__all__ = [
    "ATTRIBUTES",
    "AttributeResult",
    "BandResult",
    "CellResult",
    "aggregate_lower_limit",
    "disparity_by_band",
    "model_aggregate",
    "to_dict",
]
