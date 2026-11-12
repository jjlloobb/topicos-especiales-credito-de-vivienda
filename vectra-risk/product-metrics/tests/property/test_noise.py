"""PBT-U11-04: `days_below_floor` contra un oraculo que recorre los dias (BR-U11-07)."""

from decimal import Decimal

from hypothesis import given
from hypothesis import strategies as st
from vectra_product.noise import DayWindow, days_below_floor


@st.composite
def series(draw: st.DrawFn) -> list[DayWindow]:
    """Series diarias de vistas y decisiones, con dias sin muestra (decisiones bajo N o cero)."""
    out = []
    for _ in range(draw(st.integers(0, 40))):
        decisions = draw(st.one_of(st.integers(0, 29), st.integers(30, 120), st.just(50), st.just(49)))
        out.append(DayWindow(draw(st.integers(0, decisions)), decisions))
    return out


floors = st.one_of(
    st.sampled_from([0.6, 0.5, 0.25, 0.9, 0.99, 0.01]),
    st.floats(min_value=0.001, max_value=0.999, allow_nan=False),
)


def oracle(windows: list[DayWindow], floor: float, minimum: int) -> int:
    """Recorre los dias de ayer hacia atras con aritmetica decimal exacta del valor que declara el archivo."""
    limit = Decimal(repr(floor))
    count = 0
    day = len(windows) - 1
    while day >= 0:
        window = windows[day]
        if window.decisions >= minimum:
            if Decimal(window.viewed) < limit * window.decisions:  # viewed / decisions < F
                count += 1
            else:
                return count
        day -= 1
    return count


@given(windows=series(), floor=floors, minimum=st.integers(30, 60))
def test_pbt_u11_04_matches_the_day_walking_oracle(
    windows: list[DayWindow], floor: float, minimum: int
) -> None:
    result = days_below_floor(windows, floor, minimum)
    assert result == oracle(windows, floor, minimum)
    # La cuenta nunca supera los dias con muestra.
    assert 0 <= result <= sum(1 for w in windows if w.decisions >= minimum)


@given(windows=series(), floor=floors, minimum=st.integers(30, 60), extra=st.integers(0, 29))
def test_pbt_u11_04_a_day_below_n_neither_adds_nor_resets(
    windows: list[DayWindow], floor: float, minimum: int, extra: int
) -> None:
    """Insertar un dia sin muestra (menos de N decisiones) en cualquier lugar no cambia la cuenta."""
    base = days_below_floor(windows, floor, minimum)
    sample = DayWindow(extra // 2, min(extra, minimum - 1))
    for position in range(len(windows) + 1):
        assert days_below_floor([*windows[:position], sample, *windows[position:]], floor, minimum) == base


@given(floor=floors, minimum=st.integers(30, 60))
def test_pbt_u11_04_a_rate_of_exactly_f_stops_the_count(floor: float, minimum: int) -> None:
    exact = Decimal(repr(floor))
    decisions = int(minimum * 1000)
    viewed = exact * decisions
    if viewed != viewed.to_integral_value():  # el piso no es una fraccion exacta de este tamano de muestra
        return
    window = DayWindow(int(viewed), decisions)
    assert days_below_floor([window], floor, minimum) == 0
