"""Metricas propias del BFF (P-U10-09, 11; NFR-U10-34). Etiquetas de conjunto cerrado: nunca un identificador.

- `vectra_console_client_errors_total{error_code}`: una serie por cada `error_code` del catalogo de `ClientErrorReport`,
  creadas en 0 al importar este modulo (tercera revision del Infrastructure Design de U10): sin eso `increase()` no
  tiene un punto anterior y `ConsoleChunkOrCspError` no dispararia con el primer error.
- `vectra_bff_dependency_duration_seconds{dependency, route}`: el sobrecosto del BFF = la duracion de la ruta (`vectra_http_request_duration_seconds`,
  que U0 ya emite por plantilla de ruta) menos la de sus dependencias.
"""

from typing import Final, get_args

from prometheus_client import Counter
from vectra_common.metrics import HTTP_BUCKETS, REGISTRY, histogram
from vectra_contracts.models.api import ClientErrorReport

CLIENT_ERROR_CODES: Final[tuple[str, ...]] = get_args(ClientErrorReport.model_fields["error_code"].annotation)

CLIENT_ERRORS: Final = Counter(
    "vectra_console_client_errors_total",
    "Errores del navegador reportados por la SPA",
    ["error_code"],
    registry=REGISTRY,
)
for _code in CLIENT_ERROR_CODES:
    CLIENT_ERRORS.labels(error_code=_code)

DEPENDENCY_DURATION: Final = histogram(
    "vectra_bff_dependency_duration_seconds",
    "Duracion de cada llamada del BFF a un destino",
    ["dependency", "route"],
    HTTP_BUCKETS,
)
