"""Metricas de `explainability-service` (P-U7-08). Etiquetas solo de la allowlist de P-U7-07; nunca `case_id` ni versiones."""

import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Final

from prometheus_client import Counter, Histogram
from vectra_common.metrics import REGISTRY, histogram

#: P-U7-07: las unicas etiquetas que una metrica de U7 puede llevar.
LABEL_ALLOWLIST: Final = frozenset({"outcome", "cause", "reason", "dependency", "result", "attempt", "stage"})
RESULTS: Final = (
    "ok",
    "version_mismatch",
    "feature_dictionary_incomplete",
    "factuality_failed",
    "timeout",
    "unavailable",
    "error",
)
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


EXPLANATIONS: Final = _counter("vectra_explanations_total", "Explicaciones por resultado", ["result"])
DEPENDENCY_DURATION: Final = _histogram(
    "vectra_dependency_duration_seconds", "Duracion de las llamadas a dependencias", ["dependency"]
)
DEADLINE_EXHAUSTED: Final = _counter(
    "vectra_deadline_exhausted_total", "Llamadas no hechas o cortadas por el presupuesto", ["stage"]
)
ALL: Final = (EXPLANATIONS, DEPENDENCY_DURATION, DEADLINE_EXHAUSTED)


@asynccontextmanager
async def timed(dependency: str) -> AsyncIterator[None]:
    started = time.perf_counter()
    try:
        yield
    finally:
        DEPENDENCY_DURATION.labels(dependency=dependency).observe(time.perf_counter() - started)
