"""Metricas de `scoring-service` (P-U7-08). Etiquetas solo de la allowlist de P-U7-07; nunca `case_id`, versiones ni `idempotency_key`."""

import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Final

from prometheus_client import Counter, Histogram
from vectra_common.metrics import REGISTRY, histogram

LABEL_ALLOWLIST: Final = frozenset({"outcome", "cause", "reason", "dependency", "result", "attempt", "stage"})
OUTCOMES: Final = ("favorable", "desfavorable", "revision_requerida", "fail_closed")
DURATION_BUCKETS: Final = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 0.8, 1.0, 2.5)


def _counter(name: str, documentation: str, labels: list[str]) -> Counter:
    """Los dos servicios comparten algunos nombres (`vectra_deadline_exhausted_total`): en un solo proceso de pruebas se reutiliza."""
    try:
        return Counter(name, documentation, labels, registry=REGISTRY)
    except ValueError:
        return REGISTRY._names_to_collectors[name]  # type: ignore[return-value]  # noqa: SLF001


def _histogram(name: str, documentation: str, labels: list[str]) -> Histogram:
    try:
        return histogram(name, documentation, labels, DURATION_BUCKETS)
    except ValueError:
        return REGISTRY._names_to_collectors[name]  # type: ignore[return-value]  # noqa: SLF001


RECOMMENDATIONS: Final = _counter(
    "vectra_recommendations_total", "Recomendaciones por resultado", ["outcome"]
)
#: BR-U7-03: la que lee `PromotionMismatchPersistent` de U4 con `cause="version_mismatch"`.
FAILCLOSED: Final = _counter("vectra_scoring_failclosed_total", "FailClosed por causa", ["cause"])
REGISTRY_ATTEMPTS: Final = _counter(
    "vectra_registry_append_attempts_total", "Intentos de append de la recommendation", ["attempt", "result"]
)
#: P-U7-03: cada abandono puede dejar una entrada `recommendation` escrita y no entregada.
REGISTRY_ABANDONED: Final = _counter(
    "vectra_registry_append_abandoned_total", "Appends abandonados tras agotar los intentos", []
)
DEADLINE_EXHAUSTED: Final = _counter(
    "vectra_deadline_exhausted_total", "Llamadas no hechas o cortadas por el presupuesto", ["stage"]
)
DEPENDENCY_DURATION: Final = _histogram(
    "vectra_dependency_duration_seconds", "Duracion de las llamadas a dependencias", ["dependency"]
)
ALL: Final = (
    RECOMMENDATIONS,
    FAILCLOSED,
    REGISTRY_ATTEMPTS,
    REGISTRY_ABANDONED,
    DEADLINE_EXHAUSTED,
    DEPENDENCY_DURATION,
)


@asynccontextmanager
async def timed(dependency: str) -> AsyncIterator[None]:
    started = time.perf_counter()
    try:
        yield
    finally:
        DEPENDENCY_DURATION.labels(dependency=dependency).observe(time.perf_counter() - started)
