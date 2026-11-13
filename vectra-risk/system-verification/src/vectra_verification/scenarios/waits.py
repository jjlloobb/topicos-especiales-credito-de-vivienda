"""Esperas con el reloj inyectado (U12-T03, P-4 (a); NFR-U12-42). Una sola funcion de sondeo: condicion, intervalo y plazo, con `Clock.sleep`.

Ningun modulo de `scenarios/` duerme ni lee la hora del sistema por su cuenta (solo el reloj inyectado): las esperas largas (15 min de la ventana de RT-5, 12 a 19 min de `no_disponible`, 1 800 s de RT-2,
45 min de bias, 300 s del barrido) se prueban con el reloj falso, sin dormir.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from vectra_verification.clock import Clock


@dataclass(frozen=True)
class Waited[T]:
    """`value` es lo ultimo que devolvio la condicion; `met`, si se cumplio antes del plazo; `elapsed`, los segundos esperados (nunca mas que el plazo); `attempts`, las lecturas."""

    met: bool
    value: T
    elapsed: float
    attempts: int


def poll[T](
    clock: Clock, condition: Callable[[], tuple[bool, T]], *, interval: float, timeout: float
) -> Waited[T]:
    """Lee `condition` ahora y cada `interval` segundos hasta que se cumpla o pasen `timeout`. La ultima lectura se hace justo en el plazo: si se cumple ahi, `met`."""
    if interval <= 0 or timeout < 0:
        raise ValueError("poll_interval_or_timeout_invalid")
    start = clock.monotonic()
    attempts = 0
    while True:
        attempts += 1
        done, value = condition()
        elapsed = clock.monotonic() - start
        if done:
            return Waited(True, value, elapsed, attempts)
        remaining = timeout - elapsed
        if remaining <= 0:
            return Waited(False, value, min(elapsed, timeout), attempts)
        clock.sleep(min(interval, remaining))
