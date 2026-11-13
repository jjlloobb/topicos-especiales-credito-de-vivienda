"""Reloj falso (U12-T02): `now()`, `monotonic()` y `sleep()` avanzan juntos sin dormir. Cada `sleep` queda anotado para las pruebas de ritmo y de la ventana TOTP."""

from datetime import UTC, datetime, timedelta

from vectra_verification.clock import Clock

START = datetime(2026, 11, 13, 10, 0, 0, tzinfo=UTC)


class FakeClock(Clock):
    def __init__(self, start: datetime = START) -> None:
        self._now = start
        self._mono = 1000.0
        self.sleeps: list[float] = []

    def now(self) -> datetime:
        return self._now

    def monotonic(self) -> float:
        return self._mono

    def sleep(self, seconds: float) -> None:
        if seconds > 0:
            self.sleeps.append(seconds)
            self.advance(seconds)

    def advance(self, seconds: float) -> None:
        self._now += timedelta(seconds=seconds)
        self._mono += seconds


class NaiveClock(FakeClock):
    """Un reloj que devuelve la hora sin zona (`utcnow`): la barrera horaria lo rechaza (`clock_without_timezone`)."""

    def now(self) -> datetime:
        return self._now.replace(tzinfo=None)
