"""Apoyo de las pruebas de la libreria: generadores de tablas (BLM §3), expansion a filas y conteos de U5."""

from __future__ import annotations

import json
from pathlib import Path

from hypothesis import strategies as st
from vectra_disparity import BANDS, UNINFORMED, CountCell, CountTable

U5_COUNTS = Path(__file__).with_name("u5_counts.json")
N_MIN = 30


def load_u5_counts(variant: str) -> dict[str, CountTable]:
    """Las `CountTable` de U5 (`base` o `proxy`) del archivo generado una vez por `generate_u5_counts.py`."""
    raw = json.loads(U5_COUNTS.read_text(encoding="utf-8"))[variant]
    return {
        attribute: CountTable(
            attribute, tuple(CountCell(c["group"], c["band"], c["favorable"], c["total"]) for c in cells)
        )
        for attribute, cells in raw.items()
    }


def rows_of(table: CountTable) -> list[tuple[str, str, int]]:
    """Expande una tabla a filas `(grupo, banda, favorable 0/1)`: la inversa de contar."""
    rows: list[tuple[str, str, int]] = []
    for cell in table.cells:
        rows += [(cell.group, cell.band, 1)] * cell.favorable
        rows += [(cell.group, cell.band, 0)] * (cell.total - cell.favorable)
    return rows


def table_from_rows(attribute: str, rows: list[tuple[str, str, int]]) -> CountTable:
    sums: dict[tuple[str, str], list[int]] = {}
    for group, band, favorable in rows:
        acc = sums.setdefault((group, band), [0, 0])
        acc[0] += favorable
        acc[1] += 1
    return CountTable(
        attribute,
        tuple(
            CountCell(g, b, f, n)
            for (g, b), (f, n) in sorted(sums.items(), key=lambda kv: (kv[0][0], BANDS.index(kv[0][1])))
        ),
    )


GROUP_NAMES = ["g1", "g2", "g3", "g4", "g5", "g6", "g7"]


@st.composite
def _cell_total(draw: st.DrawFn) -> int:
    """Conteos de 0 a 5 000 con muchas celdas alrededor de `n_min`."""
    return draw(
        st.one_of(
            st.integers(0, 5000),
            st.integers(N_MIN - 3, N_MIN + 3),
            st.integers(0, 2 * N_MIN),
        )
    )


@st.composite
def count_tables(
    draw: st.DrawFn, attribute: str = "region", with_uninformed: bool | None = None
) -> CountTable:
    """1 a 7 grupos, 3 bandas, `no_informado` presente o ausente."""
    groups = draw(st.integers(1, 7))
    names = GROUP_NAMES[:groups]
    present = draw(st.booleans()) if with_uninformed is None else with_uninformed
    if present:
        names = [*names, UNINFORMED]
    cells = []
    for group in names:
        for band in BANDS:
            total = draw(_cell_total())
            favorable = draw(st.integers(0, total))
            cells.append(CountCell(group, band, favorable, total))
    return CountTable(attribute, tuple(draw(st.permutations(cells))))


def scale(table: CountTable, k: int) -> CountTable:
    return CountTable(
        table.attribute, tuple(CountCell(c.group, c.band, c.favorable * k, c.total * k) for c in table.cells)
    )


def states(table: CountTable, n_min: int = N_MIN) -> list[bool]:
    return [c.total >= n_min for c in table.cells]
