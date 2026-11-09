"""Metricas de U6 en el 8081 (P-U6-05, P-U6-06), sobre el registro de `vectra_common`.

U6 no pasa por `create_app` ni lleva el servidor de KServe, asi que declara sus propias series. Etiqueta `component`:
`predictor` o `explainer`.
"""

from typing import Final

from prometheus_client import Counter
from vectra_common.metrics import HTTP_BUCKETS, REGISTRY, histogram

PREDICTOR: Final = "predictor"
EXPLAINER: Final = "explainer"

REJECTED: Final = Counter(
    "vectra_serving_rejected_total",
    "Solicitudes rechazadas con 503 por el limite de concurrencia del pod",
    ["component"],
    registry=REGISTRY,
)
INTEGRITY_FAILED: Final = Counter(
    "vectra_serving_package_integrity_failed_total",
    "Paquetes del modelo que no pasaron la verificacion al cargar (ModelPackageIntegrityFailed)",
    ["component"],
    registry=REGISTRY,
)
DURATION: Final = histogram(
    "vectra_serving_request_duration_seconds",
    "Duracion de :predict y :explain",
    ["component"],
    HTTP_BUCKETS,
)
