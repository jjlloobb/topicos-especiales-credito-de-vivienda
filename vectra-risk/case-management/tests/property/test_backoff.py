"""Paso 5: PBT-U8-02 (BR-U8-07; US-112)."""

import random

import pytest
from hypothesis import given
from hypothesis import strategies as st

from vectra_case.backoff import schedule

BASE = 30.0
seeds = st.integers(0, 2**63)


@given(attempt=st.integers(1, 5), seed=seeds)
def test_delay_is_within_the_jitter_band(attempt, seed):
    delay = schedule(attempt, random.Random(seed))
    nominal = BASE * 2 ** (attempt - 1)
    assert 0.8 * nominal <= delay <= 1.2 * nominal


@given(seed=seeds)
def test_the_five_delays_sum_within_930_s_band(seed):
    rng = random.Random(seed)
    total = sum(schedule(n, rng) for n in range(1, 6))
    assert 0.8 * 930 <= total <= 1.2 * 930


def test_nominal_delays_are_30s_1_2_4_8_min_without_jitter():
    class Mid(random.Random):
        def uniform(self, a: float, b: float) -> float:
            return (a + b) / 2

    assert [schedule(n, Mid()) for n in range(1, 6)] == [30, 60, 120, 240, 480]


def test_the_same_seed_gives_the_same_delay():
    assert schedule(3, random.Random(7)) == schedule(3, random.Random(7))


@pytest.mark.parametrize("attempt", [-1, 0, 6, 7, 100])
def test_outside_1_to_5_there_is_no_next_attempt(attempt):
    """Tras el intento 6 el caso escala (BR-U8-09): no hay retraso que calcular."""
    with pytest.raises(ValueError, match="fuera de 1..5"):
        schedule(attempt, random.Random(0))
