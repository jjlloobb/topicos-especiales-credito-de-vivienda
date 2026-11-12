"""Constantes del ciclo (BR-U11-09, 11; NFR-U11-04, 09; P-U11-01, 02).

Sin importar nada de terceros, para que los modulos puros (`model`, `compute`, `noise`) puedan usarla sin E/S. Ninguna sale de una
variable de entorno: son parte del codigo y cambiarlas exige un PR. Los parametros de cumplimiento (F, S, N y
targets) viven en `params.py`, que los lee del `ConfigMap` de `values-product-metrics-policy.yaml`.
"""

from datetime import time, timedelta
from typing import Final

#: Lectura incremental (BR-U11-11, «cada 5 min»).
CYCLE_SECONDS: Final = 5 * 60
#: Pasada completa diaria a las 02:30 UTC mas un desfase aleatorio de 0 a 10 min por replica (NFR-U11-04).
FULL_PASS_AT_UTC: Final = time(2, 30)
FULL_PASS_JITTER_MAX_SECONDS: Final = 10 * 60
#: Plazo de una pasada completa (P-U11-02) y reintentos de la fallida (NFR-U11-09): cada 15 min, hasta 6 veces.
FULL_PASS_DEADLINE_SECONDS: Final = 75 * 60
FULL_PASS_RETRY_SECONDS: Final = 15 * 60
FULL_PASS_RETRIES: Final = 6

#: Una pagina a la vez (P-U11-01, NFR-U11-01): timeout de 5 s, sin reintentos dentro del ciclo (NFR-U11-09), 1 000 entradas.
PAGE_TIMEOUT_SECONDS: Final = 5.0
PAGE_SIZE: Final = 1000
#: Una sola conexion a U3: el pool `projections` tiene una por replica (P-U11-02).
MAX_CONNECTIONS: Final = 1

#: Parametros del breaker de `deps.call` en modo `consecutive_failures` de U0 (NFR-U0-23 (i)): abre con 3 fallos seguidos,
#: semiabierto a los 60 s, cierra con 1 exito. U11 no tiene breaker propio (pendientes consolidados, 2026-10-10). El `reader` los
#: pasa a `vectra_common.deps.BreakerConfig`.
BREAKER_CONSECUTIVE_FAILURES: Final = 3
BREAKER_OPEN_FOR_SECONDS: Final = 60.0
BREAKER_CLOSE_AFTER: Final = 1

#: Dependencia hacia U3 (F28): nombre del servicio en el contrato de rutas y etiqueta de `vectra_circuit_state` (NFR-U11-40).
REGISTRY_SERVICE: Final = "decision-registry-service"
BREAKER_DEPENDENCY: Final = "decision-registry"
#: Un solo scope (NFR-U11-20) y el cliente de Keycloak.
CLIENT_ID: Final = "product-metrics"
SCOPES: Final = ("registry:read:metrics",)

#: Ventanas (BR-U11-08, 11; NFR-U11-10): decisiones de 35 dias en memoria y 6 meses calendario cerrados en contadores,
#: que se publican con `period="month"` y `month="AAAA-MM"`.
STATE_WINDOW_DAYS: Final = 35
CLOSED_MONTHS: Final = 6
#: Margen de la pasada completa (P-U11-01): empieza un dia antes del dia 1 del sexto mes cerrado.
FULL_PASS_MARGIN_DAYS: Final = 1
PERIOD_30D_DAYS: Final = 30
#: Ventana movil de la tasa de consulta (BR-U11-07).
VIEW_WINDOW_DAYS: Final = 7

#: BR-U11-10: `decided_at` puede superar a `recorded_at` en hasta 5 min por desfase de relojes; mas que eso se excluye.
MAX_DECIDED_AHEAD: Final = timedelta(minutes=5)
#: BR-U11-10: con mas del 1 % de excluidas en 30 dias, `degraded = 1`.
DEGRADED_RATIO: Final = 0.01

#: Rangos de los parametros de cumplimiento (BR-U11-09), con nombre para que `params.parse`, sus mensajes y la regla de conftest del
#: chart (Paso 11) compartan una sola fuente: 0 < F < 1, 1 <= S <= 14, N >= 30, targets en 0..1 (`target_north_star` puede ser null).
NOISE_FLOOR_MIN_EXCLUSIVE: Final = 0.0
NOISE_FLOOR_MAX_EXCLUSIVE: Final = 1.0
NOISE_SUSTAIN_DAYS_MIN: Final = 1
NOISE_SUSTAIN_DAYS_MAX: Final = 14
NOISE_MIN_DECISIONS_MIN: Final = 30
TARGET_RATIO_MIN: Final = 0.0
TARGET_RATIO_MAX: Final = 1.0
