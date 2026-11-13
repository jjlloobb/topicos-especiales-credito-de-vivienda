"""Reloj inyectable (U12-T02, P-4; NFR-U12-32). Un solo tipo, con `now()`, `monotonic()` y `sleep()`.

`now()` siempre devuelve una hora con zona UTC (la barrera horaria de `guard.check_decisions` rechaza una sin zona). Lo reciben `simulator`, `driver` y `clients.oidc`:
ningun otro modulo llama a `datetime.now()`, `time.time()` ni `time.sleep()`, salvo esta implementacion real. Las pruebas de ritmo y de la ventana TOTP usan un reloj
falso (`tests/doubles/fake_clock.py`) que avanza sin dormir.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime


class Clock:
    """El reloj real. Las pruebas heredan de esta clase y reemplazan los tres metodos."""

    def now(self) -> datetime:  # pragma: no cover - implementacion real del reloj
        return datetime.now(UTC)

    def monotonic(self) -> float:  # pragma: no cover - implementacion real del reloj
        return time.monotonic()

    def sleep(self, seconds: float) -> None:  # pragma: no cover - implementacion real del reloj
        if seconds > 0:
            time.sleep(seconds)
