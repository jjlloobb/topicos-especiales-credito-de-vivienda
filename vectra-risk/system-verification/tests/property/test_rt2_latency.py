"""PBT-U12-04, `rt2_latency` (U12 Paso 3; BR-U12-07; INF-U12-03) y los ejemplos de la latencia."""

import random
from datetime import UTC, datetime, timedelta, timezone

import pytest
from hypothesis import given
from hypothesis import strategies as st

from vectra_verification import rt2_latency
from vectra_verification.rt2_latency import measure

BASE = datetime(2026, 11, 12, 10, 0, tzinfo=UTC)
LIMIT = timedelta(seconds=1800)

# Lotes de 1 a 2 000 `recorded_at` en UTC, desordenados y con empates (microsegundos sobre una ventana de 3 minutos); y un `freeze`
# alrededor del limite de 1 800 s respecto del inicio del lote. El tamano se sortea aparte (F-05: `st.lists` casi nunca pasa de unas decenas) y las marcas
# salen de un generador con semilla: unas veces todas distintas, otras de un conjunto chico de valores (muchos empates, tambien en el minimo).
WINDOW_US = 180_000_000


@st.composite
def batches(draw):  # type: ignore[no-untyped-def]
    size = draw(st.one_of(st.integers(1, 5), st.integers(1, 100), st.integers(1, 2000), st.just(2000)))
    rnd = random.Random(draw(st.integers(0, 2**32)))
    pool = (
        [rnd.randrange(WINDOW_US + 1) for _ in range(draw(st.integers(1, 6)))]
        if draw(st.booleans())
        else None
    )
    values = [rnd.choice(pool) if pool else rnd.randrange(WINDOW_US + 1) for _ in range(size)]
    return [BASE + timedelta(microseconds=us) for us in values]


BATCHES = batches()
AROUND_LIMIT = st.one_of(
    st.integers(-1_000_000, 4_000_000_000).map(lambda us: timedelta(microseconds=us)),
    st.integers(-5, 5).map(lambda us: LIMIT + timedelta(microseconds=us)),
    st.sampled_from([timedelta(0), LIMIT, LIMIT + timedelta(milliseconds=1)]),
)


@given(BATCHES, AROUND_LIMIT, st.sampled_from(rt2_latency.RUNS))
def test_latency_is_freeze_minus_the_minimum_recorded_at_of_the_batch(batch, offset, run) -> None:  # type: ignore[no-untyped-def]
    first = min(batch)
    freeze = first + offset
    if offset < timedelta(0):
        with pytest.raises(ValueError, match="freeze_before_batch"):
            measure(run, batch, freeze)
        return
    result = measure(run, batch, freeze)
    assert (
        result.batch_first_recorded_at == first and result.freeze_recorded_at == freeze and result.run == run
    )
    assert result.latency_seconds == (freeze - first).total_seconds()


@given(BATCHES, AROUND_LIMIT)
def test_latency_is_never_less_than_the_one_measured_from_any_other_entry(batch, offset) -> None:  # type: ignore[no-untyped-def]
    freeze = min(batch) + max(offset, timedelta(0))
    result = measure(1, batch, freeze)
    for entry in batch:
        assert result.latency_seconds >= (freeze - entry).total_seconds()


@given(BATCHES, AROUND_LIMIT)
def test_a_run_over_1800_seconds_is_not_passed_and_the_limit_itself_passes(batch, offset) -> None:  # type: ignore[no-untyped-def]
    freeze = min(batch) + max(offset, timedelta(0))
    result = measure(2, batch, freeze)
    assert result.passed == (freeze - min(batch) <= LIMIT)
    if result.latency_seconds > 1800:
        assert result.passed is False


@given(BATCHES, st.randoms())
def test_the_order_of_the_batch_does_not_matter(batch, rnd) -> None:  # type: ignore[no-untyped-def]
    shuffled = list(batch)
    rnd.shuffle(shuffled)
    freeze = min(batch) + timedelta(minutes=10)
    assert measure(3, batch, freeze) == measure(3, shuffled, freeze)


# --- ejemplos ---


def test_a_run_of_31_minutes_fails_and_the_measurement_is_recorded() -> None:
    result = measure(1, [BASE + timedelta(seconds=30), BASE], BASE + timedelta(minutes=31))
    assert result.passed is False and result.latency_seconds == 1860.0
    assert result.batch_first_recorded_at == BASE and result.freeze_recorded_at == BASE + timedelta(
        minutes=31
    )


def test_exactly_1800_seconds_passes_and_1800_001_does_not() -> None:
    assert measure(1, [BASE], BASE + timedelta(seconds=1800)).passed is True
    over = measure(1, [BASE], BASE + timedelta(seconds=1800, milliseconds=1))
    assert over.passed is False and over.latency_seconds == 1800.001


def test_typical_27_minutes_passes_and_zero_latency_is_a_measurement() -> None:
    assert measure(5, [BASE], BASE + timedelta(minutes=27)).passed is True
    assert measure(4, [BASE], BASE).latency_seconds == 0.0


def test_an_empty_batch_is_an_error_not_a_measurement() -> None:
    with pytest.raises(ValueError, match="empty_batch"):
        measure(1, [], BASE)


def test_a_freeze_before_the_start_is_an_error() -> None:
    with pytest.raises(ValueError, match="freeze_before_batch"):
        measure(1, [BASE, BASE + timedelta(seconds=5)], BASE - timedelta(microseconds=1))


def test_the_run_must_be_between_1_and_5() -> None:
    for run in (0, 6, -1):
        with pytest.raises(ValueError, match="run_out_of_range"):
            measure(run, [BASE], BASE)


def test_times_must_be_utc() -> None:
    naive = datetime(2026, 11, 12, 10, 0)
    bogota = timezone(timedelta(hours=-5))
    with pytest.raises(ValueError, match="not_utc:recommendation"):
        measure(1, [naive], BASE)
    with pytest.raises(ValueError, match="not_utc:freeze"):
        measure(1, [BASE], naive)
    with pytest.raises(ValueError, match="not_utc:freeze"):
        measure(1, [BASE], BASE.astimezone(bogota))


@given(BATCHES)
def test_the_batches_cover_the_range_of_1_to_2000_entries_with_ties(batch) -> None:  # type: ignore[no-untyped-def]
    assert 1 <= len(batch) <= 2000
