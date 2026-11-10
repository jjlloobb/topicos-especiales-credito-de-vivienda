"""PBT-U9-03, clausula de `publish`: ninguna serie publica la tasa de una celda insuficiente, y `band = sin_bandas` sigue
BR-U9-06 (sin la tasa de un grupo con alguna celda insuficiente; diferencia solo con celdas suficientes y `partial`)."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from fractions import Fraction

from builders import batch_client, population_report, small_tables, table, uniform
from hypothesis import example, given
from vectra_bias.publish import RunReport, VersionReport, publish
from vectra_disparity import UNINFORMED, quantize4
from world import PUSHGATEWAY_URL, World

N_MIN = 30
T0 = datetime(2026, 11, 9, 12, 0, tzinfo=UTC)
BANDS_AND_AGGREGATES = {"lt_20", "20_30", "gt_30", "agregada", "sin_bandas"}


def _sin_bandas_oracle(table) -> tuple[str | None, bool]:
    totals: dict[str, list[int]] = {}
    excluded: set[str] = set()
    for cell in table.cells:
        if cell.group == UNINFORMED:
            continue
        if cell.total < N_MIN:
            excluded.add(cell.group)
        acc = totals.setdefault(cell.group, [0, 0])
        acc[0] += cell.favorable
        acc[1] += cell.total
    rates = [Fraction(f, n) for g, (f, n) in totals.items() if g not in excluded and n > 0]
    if len(rates) < 2:
        return None, bool(excluded)
    return str(quantize4(max(rates) - min(rates))), bool(excluded)


def _rounding_tie() -> dict:
    """La diferencia sin bandas de `sexo` es 9/480 = 0,01875 exacto: mitad hacia arriba da 0,0188 (la libreria usa fracciones)."""
    counts = uniform(0.5, 100)
    counts["sexo"] = table("sexo", {"F": 3 / 160, "M": 0.0}, 160)
    return counts


@example(counts=_rounding_tie())
@given(counts=small_tables())
def test_no_series_publishes_the_rate_of_an_insufficient_cell(counts):
    world = World()
    population = population_report(counts, "modelo", "v1")
    report = RunReport(
        T0,
        T0,
        True,
        None,
        True,
        (VersionReport("v1", population, population_report(uniform(0.5, 100), "humana", "v1")),),
        0,
        1,
    )
    client = batch_client("pushgateway", PUSHGATEWAY_URL, world.pushgateway.transport())
    assert asyncio.run(publish(client, report)).ok
    series = [
        (n, lab, v)
        for n, lab, v in world.pushgateway.group("bias-monitoring", "run")
        if lab.get("population") == "modelo"
    ]

    # Solo `cell_size` lleva el grupo de la celda: ninguna otra serie puede ser la tasa de una celda.
    assert all("group" not in lab for n, lab, _ in series if n != "vectra_bias_cell_size")
    assert {lab["band"] for n, lab, _ in series if n == "vectra_bias_disparity"} <= BANDS_AND_AGGREGATES
    sizes = {
        (lab["attribute"], lab["group"], lab["band"]): int(v)
        for n, lab, v in series
        if n == "vectra_bias_cell_size"
    }
    for attribute, table in counts.items():
        for cell in table.cells:
            assert (
                sizes[(attribute, cell.group, cell.band)] == cell.total
            )  # el tamano se publica siempre, insuficiente o no
    assert {n for n, _, _ in series} <= {
        "vectra_bias_disparity", "vectra_bias_aggregate_lower", "vectra_bias_rule_met", "vectra_bias_cell_size",
    }  # fmt: skip

    for attribute, table in counts.items():
        expected, partial = _sin_bandas_oracle(table)
        published = [
            (lab, v)
            for n, lab, v in series
            if n == "vectra_bias_disparity" and lab["attribute"] == attribute and lab["band"] == "sin_bandas"
        ]
        if expected is None:
            assert published == []
        else:
            assert [(lab["partial"], v) for lab, v in published] == [
                ("true" if partial else "false", expected)
            ]
