"""Limite de concurrencia por pod (P-U6-05, NFR-U6-41; RESILIENCY-10, bulkhead).

El predictor atiende 16 solicitudes a la vez y el explicador 8. Por encima, `try_acquire` falla **de inmediato**, sin cola
ni espera: el llamador responde 503 y la solicitud cuenta en `vectra_serving_rejected_total{component}`.
"""

import threading
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Final

from vectra_serving_common.metrics import EXPLAINER, PREDICTOR, REJECTED

PREDICTOR_LIMIT: Final = 16
EXPLAINER_LIMIT: Final = 8


class Saturated(Exception):  # noqa: N818 - el nombre es el del patron P-U6-05
    """El pod ya atiende su maximo de solicitudes concurrentes."""


class ConcurrencyLimiter:
    """Semaforo no bloqueante: `limit` solicitudes en curso como maximo."""

    def __init__(self, component: str, limit: int) -> None:
        if limit < 1:
            raise ValueError("limit_must_be_positive")
        self.component = component
        self.limit = limit
        self._in_flight = 0
        self._lock = threading.Lock()

    @property
    def in_flight(self) -> int:
        return self._in_flight

    def try_acquire(self) -> bool:
        with self._lock:
            if self._in_flight >= self.limit:
                REJECTED.labels(component=self.component).inc()
                return False
            self._in_flight += 1
            return True

    def release(self) -> None:
        with self._lock:
            self._in_flight -= 1

    @contextmanager
    def slot(self) -> Iterator[None]:
        """Ocupa un lugar mientras dura el bloque; si no hay, `Saturated` sin esperar."""
        if not self.try_acquire():
            raise Saturated(self.component)
        try:
            yield
        finally:
            self.release()


def predictor_limiter() -> ConcurrencyLimiter:
    return ConcurrencyLimiter(PREDICTOR, PREDICTOR_LIMIT)


def explainer_limiter() -> ConcurrencyLimiter:
    return ConcurrencyLimiter(EXPLAINER, EXPLAINER_LIMIT)
