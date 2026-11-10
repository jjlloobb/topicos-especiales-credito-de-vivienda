"""PBT-U9-07 (BLM §3): `compare_source(pre, pre)` da `delta = 0` y intercambiar `pre` y `post` invierte el signo de cada `delta`.

Tablas con 1 a 7 grupos del catalogo de U0 y 3 bandas, conteos de 0 a 5 000 y celdas alrededor de `n_min`. Los `null` siguen
`null` al intercambiar. Los ejemplos con oraculo a mano (que fijan el signo de `post - pre`) estan en
`tests/unit/test_compare_examples.py`: las dos invariantes de aqui las cumple tambien un signo invertido.
"""

from __future__ import annotations

from decimal import Decimal

from builders import compare_request
from hypothesis import given
from hypothesis import strategies as st
from scenario import POLICY
from vectra_bias.compare import CATALOG, compare_source
from vectra_disparity import ATTRIBUTES, BANDS, CountCell, CountTable

N_MIN = POLICY.n_min


@st.composite
def _total(draw: st.DrawFn) -> int:
    return draw(st.one_of(st.integers(0, 5000), st.integers(N_MIN - 3, N_MIN + 3), st.integers(0, 2 * N_MIN)))


@st.composite
def catalog_tables(draw: st.DrawFn) -> dict[str, CountTable]:
    """Los cuatro atributos, cada uno con 1 a 7 grupos del catalogo (los que tenga) y las tres bandas."""
    counts = {}
    for attribute in ATTRIBUTES:
        groups = sorted(CATALOG[attribute])
        chosen = draw(
            st.lists(st.sampled_from(groups), min_size=1, max_size=min(7, len(groups)), unique=True)
        )
        cells = []
        for group in chosen:
            for band in BANDS:
                total = draw(_total())
                cells.append(CountCell(group, band, draw(st.integers(0, total)), total))
        counts[attribute] = CountTable(attribute, tuple(cells))
    return counts


def _deltas(report) -> list[str | None]:
    return [*(a.delta for a in report.delta.attributes), report.delta.model_aggregate]


@given(pre=catalog_tables())
def test_pbt_u9_07_comparing_a_table_with_itself_gives_zero_everywhere(pre):
    report = compare_source(compare_request("fuente", pre, pre), POLICY)
    for pre_side, delta in zip(
        [*(a.aggregate for a in report.pre.attributes), report.pre.model_aggregate],
        _deltas(report),
        strict=True,
    ):
        assert delta == (None if pre_side is None else "0.0000")


@given(pre=catalog_tables(), post=catalog_tables())
def test_pbt_u9_07_swapping_pre_and_post_inverts_the_sign_of_every_delta(pre, post):
    forward = _deltas(compare_source(compare_request("fuente", pre, post), POLICY))
    backward = _deltas(compare_source(compare_request("fuente", post, pre), POLICY))
    assert len(forward) == len(backward) == 5
    for a, b in zip(forward, backward, strict=True):
        if a is None or b is None:
            assert a is None and b is None
        else:
            assert Decimal(a) == -Decimal(b)
