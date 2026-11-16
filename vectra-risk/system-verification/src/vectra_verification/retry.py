"""Lecturas que aguantan un error transitorio (U12-T09; NFR-U12-42). Una sola funcion: `retry_read`.

Las lecturas de `decisions` (la espera de `sim_normal.read_cases` y la bandeja del conductor, `driver._ready`) caian con un solo 429, 503, 504 o tiempo agotado y dejaban la seccion `interrumpida` con los 2 000 casos ya
enviados. Se reintentan el estado 0 (fallo de transporte o tiempo agotado: `ApiClient._send`), 429, 502, 503 y 504, con espera creciente (2 s, 4 s, ... hasta 30 s; el `Retry-After` del servidor manda si es mayor) y un
tope de `READ_BUDGET` segundos que mide el reloj inyectado. Agotado el tope: `ReadUnavailable`, con la causa estable `lectura_agotada` y el ultimo estado; nunca la traza del ultimo `ApiError`. Otro estado (401, 403, 404, 500, ...)
no se reintenta: lo trata quien llama. Solo para **lecturas**: una escritura no pasa por aqui.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Final

from vectra_verification.clients._api import ApiError
from vectra_verification.clock import Clock

READ_RETRY_STATUSES: Final = (0, 429, 502, 503, 504)
READ_BASE: Final = 2.0
READ_MAX_PAUSE: Final = 30.0
READ_BUDGET: Final = 300.0


class ReadUnavailable(Exception):
    """El BFF siguio sin responder bien durante todo el tope: la causa es `lectura_agotada` (el codigo del mensaje) y `status` es el ultimo estado visto (0: transporte)."""

    code = "lectura_agotada"

    def __init__(self, what: str, status: int, attempts: int) -> None:
        super().__init__(f"{self.code}:{what}:http_{status}:intentos_{attempts}")
        self.what = what
        self.status = status
        self.attempts = attempts


def retry_read[T](
    clock: Clock, call: Callable[[], T], *, what: str, budget: float = READ_BUDGET, base: float = READ_BASE
) -> T:
    """`call()` con reintentos ante un error transitorio; `what` nombra la lectura en la causa (`decisions_espera`, `decisions_bandeja`)."""
    start = clock.monotonic()
    pause = base
    attempts = 0
    while True:
        attempts += 1
        try:
            return call()
        except ApiError as error:
            if error.status not in READ_RETRY_STATUSES:
                raise
            wait = max(pause, error.retry_after or 0.0)
            if clock.monotonic() - start + wait > budget:
                raise ReadUnavailable(what, error.status, attempts) from None
            clock.sleep(wait)
            pause = min(pause * 2, READ_MAX_PAUSE)
