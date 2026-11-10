"""Constructores de conteos para las pruebas del Bloque C: tablas por tasa y tamano de celda, y marginales de U3."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date

from vectra_contracts.models.monitoring import MonitoringMarginalCount
from hypothesis import strategies as st
from vectra_disparity import ATTRIBUTES, BANDS, UNINFORMED, CountCell, CountTable

#: Grupos informados por atributo en el catalogo de U0 (`no_informado` aparte).
CATALOG = {
    "sexo": ["F", "M"],
    "rango_edad": ["18-25", "26-35", "36-45", "46-55", "56-65", "66+"],
    "region": ["amazonia", "andina", "caribe", "insular", "orinoquia", "pacifica"],
    "estrato": ["1", "2", "3", "4", "5", "6"],
}


def table(attribute: str, rates: Mapping[str, float], n: int | Mapping[str, int]) -> CountTable:
    """Una celda por (grupo, banda) con `n` casos (o `n[grupo]`) y `round(rate * n)` favorables, igual en las tres bandas."""
    cells = []
    for group, rate in rates.items():
        size = n[group] if isinstance(n, Mapping) else n
        for band in BANDS:
            cells.append(CountCell(group, band, round(rate * size), size))
    return CountTable(attribute, tuple(cells))


def uniform(rate: float, n: int) -> dict[str, CountTable]:
    """Los cuatro atributos con todas las tasas iguales (disparidad 0)."""
    return {a: table(a, dict.fromkeys(CATALOG[a], rate), n) for a in ATTRIBUTES}


def with_gap(attribute: str, gap: float, n: int, base: float = 0.5) -> dict[str, CountTable]:
    """Disparidad `gap` en `attribute` (un grupo a `base + gap`, los demas a `base`) y 0 en los otros tres."""
    counts = uniform(base, n)
    rates = dict.fromkeys(CATALOG[attribute], base)
    rates[CATALOG[attribute][-1]] = base + gap
    counts[attribute] = table(attribute, rates, n)
    return counts


def marginals_of(
    counts: Mapping[str, CountTable],
    *,
    population: str,
    version: str,
    range_id: str,
    decisions: bool = False,
) -> list[MonitoringMarginalCount]:
    """`MonitoringMarginalCount` de U3 (favorable / no favorable por celda) a partir de tablas de conteo."""
    rows = []
    for attribute, tbl in counts.items():
        for cell in tbl.cells:
            for result, count in (("favorable", cell.favorable), ("desfavorable", cell.total - cell.favorable)):
                if count:
                    rows.append(
                        MonitoringMarginalCount(
                            population=population,  # type: ignore[arg-type]
                            model_version_id=version,
                            range_id=range_id,
                            attribute=attribute,  # type: ignore[arg-type]
                            group=cell.group,
                            band=cell.band,  # type: ignore[arg-type]
                            result=result,
                            decision=("sigue" if result == "favorable" else "se_aparta") if decisions else None,
                            count=count,
                        )
                    )
    return rows


def day(offset: int, today: date) -> date:
    from datetime import timedelta

    return today - timedelta(days=offset)


@st.composite
def small_tables(draw: st.DrawFn) -> dict[str, CountTable]:
    """Los cuatro atributos con 2 a 4 grupos, `no_informado` presente o no, y celdas en torno a `n_min = 30`."""
    counts = {}
    for attribute in ATTRIBUTES:
        groups = CATALOG[attribute][: draw(st.integers(2, 4))]
        if draw(st.booleans()):
            groups = [*groups, UNINFORMED]
        cells = []
        for group in groups:
            for band in BANDS:
                total = draw(st.sampled_from([0, 10, 29, 30, 31, 100, 2000]))
                cells.append(CountCell(group, band, draw(st.integers(0, total)), total))
        counts[attribute] = CountTable(attribute, tuple(cells))
    return counts


def full_catalog(rate_gap: float = 0.1, n: int = 500) -> dict[str, CountTable]:
    """Los catalogos completos de U0: 22 grupos (los 20 informados y `no_informado` en sexo y estrato) por 3 bandas."""
    counts = {}
    for attribute in ATTRIBUTES:
        rates = {g: 0.5 + (rate_gap if i == 0 else 0.0) for i, g in enumerate(CATALOG[attribute])}
        if attribute in ("sexo", "estrato"):
            rates[UNINFORMED] = 0.5
        counts[attribute] = table(attribute, rates, n)
    return counts
