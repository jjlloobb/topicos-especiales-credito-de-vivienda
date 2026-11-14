"""CA-17 (U12-T03): el sondeo con el reloj inyectado (NFR-U12-42): ni un `sleep` real."""

import time

from fake_clock import FakeClock
from vectra_verification.scenarios import waits


def test_a_condition_true_at_the_first_attempt_waits_nothing() -> None:
    clock = FakeClock()
    waited = waits.poll(clock, lambda: (True, "x"), interval=15, timeout=900)
    assert (
        waited.met
        and waited.attempts == 1
        and clock.sleeps == []
        and waited.elapsed == 0
        and waited.value == "x"
    )


def test_a_condition_true_at_attempt_n_waits_n_minus_one_intervals() -> None:
    clock = FakeClock()
    calls = []

    def condition() -> tuple[bool, int]:
        calls.append(1)
        return len(calls) == 5, len(calls)

    waited = waits.poll(clock, condition, interval=15, timeout=900)
    assert waited.met and waited.attempts == 5 and clock.sleeps == [15, 15, 15, 15] and waited.elapsed == 60


def test_an_expired_deadline_returns_vencido_and_never_waits_more_than_the_timeout() -> None:
    clock = FakeClock()
    waited = waits.poll(clock, lambda: (False, None), interval=400, timeout=900)
    assert (
        not waited.met
        and waited.elapsed == 900
        and sum(clock.sleeps) == 900
        and clock.sleeps == [400, 400, 100]
    )


def test_a_condition_that_becomes_true_exactly_at_the_deadline_is_met() -> None:
    clock = FakeClock()
    waited = waits.poll(clock, lambda: (clock.monotonic() - 1000.0 >= 60, None), interval=15, timeout=60)
    assert waited.met and waited.elapsed == 60


def test_zero_timeout_reads_once() -> None:
    clock = FakeClock()
    waited = waits.poll(clock, lambda: (False, 1), interval=15, timeout=0)
    assert not waited.met and waited.attempts == 1 and clock.sleeps == []


def test_a_two_hour_wait_takes_no_real_time() -> None:
    clock = FakeClock()
    started = time.monotonic()
    waited = waits.poll(clock, lambda: (False, None), interval=15, timeout=7200)
    assert not waited.met and sum(clock.sleeps) == 7200 and time.monotonic() - started < 2.0


def test_invalid_interval_or_timeout_is_an_error() -> None:
    import pytest

    for interval, timeout in ((0, 10), (-1, 10), (5, -1)):
        with pytest.raises(ValueError, match="poll_interval_or_timeout_invalid"):
            waits.poll(FakeClock(), lambda: (True, None), interval=interval, timeout=timeout)


def test_a_deadline_that_float_arithmetic_leaves_a_hair_short_still_ends_with_the_fake_clock() -> None:
    """F-08 (ronda 2): con un reloj falso cuyo `monotonic` acumula error de coma flotante, `elapsed` quedaba en `timeout - 1e-12`, el ultimo `sleep` era de 1e-12 (no mueve el reloj) y el sondeo no terminaba nunca: la suite se colgaba al 100 % de CPU."""
    clock = FakeClock()
    clock._mono = 1000.1  # noqa: SLF001
    reads: list[int] = []

    def never() -> tuple[bool, None]:
        reads.append(1)
        assert len(reads) < 5000, "el sondeo no termina: el plazo nunca se alcanza"
        return False, None

    waited = waits.poll(clock, never, interval=30.0, timeout=600.0)
    assert not waited.met and waited.elapsed <= 600.0 and len(reads) < 5000
