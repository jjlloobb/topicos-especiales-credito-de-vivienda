"""PBT-U9-06: `counts_from_records` y la expansion a filas son inversas; la tabla de un rango suma las de su particion."""

from collections import defaultdict

from hypothesis import given
from hypothesis import strategies as st
from support import rows_of, table_from_rows
from vectra_disparity import ATTRIBUTES, BANDS, counts_from_marginals, counts_from_records

OUTCOMES = ["favorable", "desfavorable", "revision_requerida"]


@st.composite
def labelled_records(draw: st.DrawFn):
    """Filas etiquetadas con grupos de pocos valores (para que las celdas se repitan) y el `outcome` de U7."""
    groups = {
        "sexo": ["F", "M", "no_informado"],
        "rango_edad": ["18_25", "26_40", "no_informado"],
        "region": ["andina", "insular", "caribe"],
        "estrato": ["1", "2", "3"],
    }
    record = st.fixed_dictionaries(
        {
            **{a: st.sampled_from(groups[a]) for a in ATTRIBUTES},
            "banda": st.sampled_from(BANDS),
            "outcome": st.sampled_from(OUTCOMES),
        }
    )
    return draw(st.lists(record, max_size=80))


@given(labelled_records())
def test_pbt_u9_06_counting_and_expanding_are_inverse(records):
    tables = counts_from_records(records)
    assert set(tables) == set(ATTRIBUTES)
    for attribute, table in tables.items():
        rows = rows_of(table)
        assert table_from_rows(attribute, rows) == table
        assert len(rows) == len(records)
        assert sum(r[2] for r in rows) == sum(r["outcome"] == "favorable" for r in records)  # BR-U9-01


def _marginals(records, day):
    """Lo que el agregador de U3 entrega por dia: marginales por atributo, con `result` y, en humana, `decision`."""
    counts: dict[tuple[str, str, str, str], int] = defaultdict(int)
    for r in records:
        for attribute in ATTRIBUTES:
            counts[(attribute, r[attribute], r["banda"], r["outcome"])] += 1
    return [
        {"population": "modelo", "model_version_id": "mv-1", "range_id": f"day-{day}", "attribute": a, "group": g,
         "band": b, "result": result, "decision": None, "count": n}
        for (a, g, b, result), n in counts.items()
    ]  # fmt: skip


@given(labelled_records(), st.lists(st.integers(0, 29), min_size=80, max_size=80))
def test_pbt_u9_06_range_table_is_the_sum_of_any_30_day_partition(records, days):
    by_day: dict[int, list] = defaultdict(list)
    for record, day in zip(records, days, strict=False):
        by_day[day].append(record)
    marginals = [m for day, rs in by_day.items() for m in _marginals(rs, day)]
    assert counts_from_marginals(marginals) == counts_from_records(records)
