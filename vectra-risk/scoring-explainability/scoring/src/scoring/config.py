"""Presupuestos de `scoring-service` como constantes tipadas (INF-U7-04).

Ninguno se lee de variables de entorno: cambiar un valor exige un PR que pase las pruebas de P-U7-01, 02 y 04.
Tiempos en milisegundos, salvo `BREAKER` (segundos, como `BreakerConfig`).
"""

from typing import Final

from vectra_common.deps import BreakerConfig

# P-U7-01: presupuesto previo al registro, contado desde la llegada de la solicitud.
PRE_REGISTRY_BUDGET_MS: Final = 700

# NFR-U7-10: timeouts por llamada. Son maximos: rige el menor entre este y el presupuesto restante.
SERVING_CONFIG_TIMEOUT_MS: Final = 500
PREDICT_TIMEOUT_MS: Final = 300
EXPLAINABILITY_TIMEOUT_MS: Final = 800
REGISTRY_TIMEOUT_MS: Final = 2_500

# P-U7-02: append de `recommendation`, 2 intentos con la misma `idempotency_key`; jitter del reintento de 0 a 100 ms.
APPEND_ATTEMPTS: Final = 2
APPEND_TIMEOUT_MS: Final = 2_500
APPEND_JITTER_MIN_MS: Final = 0
APPEND_JITTER_MAX_MS: Final = 100

# P-U7-02: `fail_closed` es best effort, un solo intento.
FAIL_CLOSED_APPEND_ATTEMPTS: Final = 1
FAIL_CLOSED_APPEND_TIMEOUT_MS: Final = 250

# P-U7-01: margen de proceso sobre `llegada + 700 ms + 250 ms`.
PROCESS_MARGIN_MS: Final = 50
RESPONSE_CEILING_MS: Final = 1_000

# INF-U7-04: `terminationGracePeriodSeconds` del Deployment.
TERMINATION_GRACE_S: Final = 20

# P-U7-04: conexiones maximas por pod, un cliente por dependencia.
PREDICT_POOL: Final = 20
EXPLAINABILITY_POOL: Final = 20
REGISTRY_POOL: Final = 10
SERVING_CONFIG_POOL: Final = 5

# NFR-U7-11: >= 50 % de fallos en las ultimas 20 llamadas dentro de 30 s; semiabierto a los 10 s. Igual para todas las filas.
BREAKER: Final = BreakerConfig(open_for=10.0, window_size=20, failure_ratio=0.5, window_seconds=30.0)

# P-U7-05: cache de `serving-config` por pod, revalidada con `If-None-Match`.
SERVING_CONFIG_CACHE_TTL_MS: Final = 5_000
