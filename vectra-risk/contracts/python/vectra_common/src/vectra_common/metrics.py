"""Metricas que emite U0 (logical-components §2). Sin identificadores en las etiquetas."""

from collections.abc import Sequence
from typing import Final

from prometheus_client import (
    CollectorRegistry,
    Counter,
    Gauge,
    GCCollector,
    Histogram,
    PlatformCollector,
    ProcessCollector,
)
from vectra_contracts.errors import ContractViolation

REGISTRY: Final = CollectorRegistry()
ProcessCollector(registry=REGISTRY)  # series estandar que usa U11
PlatformCollector(registry=REGISTRY)
GCCollector(registry=REGISTRY)

#: Incluyen los umbrales de los SLO y de las alertas.
HTTP_BUCKETS: Final = (
    0.005,
    0.01,
    0.025,
    0.03,
    0.05,
    0.1,
    0.15,
    0.25,
    0.3,
    0.4,
    0.5,
    0.7,
    0.8,
    1.0,
    1.5,
    2.0,
    2.5,
    5.0,
    10.0,
)

AUTHZ_DENIED: Final = Counter(
    "vectra_authz_denied_total", "Denegaciones 401/403", ["code", "route_template"], registry=REGISTRY
)
JWKS_REFRESH: Final = Counter("vectra_jwks_refresh_total", "Refrescos de JWKS", ["result"], registry=REGISTRY)
LOG_FIELDS_DROPPED: Final = Counter(
    "vectra_log_fields_dropped_total", "Campos descartados", ["service", "event"], registry=REGISTRY
)
CIRCUIT_STATE: Final = Gauge(
    "vectra_circuit_state", "0 cerrado, 1 semiabierto, 2 abierto", ["dependency"], registry=REGISTRY
)


def histogram(name: str, documentation: str, labels: Sequence[str], buckets: Sequence[float]) -> Histogram:
    """Todo histograma declara sus buckets al registrarse."""
    if not buckets:
        raise ContractViolation(f"el histograma {name} necesita buckets")
    return Histogram(name, documentation, list(labels), buckets=tuple(buckets), registry=REGISTRY)


HTTP_DURATION: Final = histogram(
    "vectra_http_request_duration_seconds",
    "Duracion de las solicitudes HTTP",
    ["service", "route_template", "method", "status"],
    HTTP_BUCKETS,
)
