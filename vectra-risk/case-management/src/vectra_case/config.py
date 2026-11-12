"""Constantes tipadas de U8 (Paso 2; INF-U8-07; P-U8-01, 02; NFR-U8-30, 31).

Ninguna se lee de variables de entorno ni de values de Helm: son decisiones de diseno y cambiarlas es un cambio de codigo.
Lo que si es configuracion llega por values al chart (Paso 20) y no vive aqui: URLs y audiencias, telemetria,
`allowTestScenarios`, `core.enabled`, `coreMock.enabled` y `retention.*` (esta ultima, ademas, por `retention_settings`).
Tiempos en segundos (`float`) y tamanos en unidades.
"""

from typing import Final

# --- Timeouts por llamada (NFR-U8-30), todos con `vectra_common.deps.call` ---
SERVING_CONFIG_TIMEOUT: Final[float] = 0.5
FEATURE_SPEC_TIMEOUT: Final[float] = 1.0
SCORING_TIMEOUT: Final[float] = 7.0
REGISTRY_TIMEOUT: Final[float] = 2.5
CORE_TIMEOUT: Final[float] = 0.5

# --- Pools por dependencia (P-U8-02) y de la base ---
SCORING_POOL: Final[int] = 16
GOVERNANCE_WORKER_POOL: Final[int] = 4  # case-worker -> governance (F104)
GOVERNANCE_SERVICE_POOL: Final[int] = 2  # case-service -> governance, barrido (F104)
REGISTRY_POOL: Final[int] = 10
CORE_POOL: Final[int] = 10
# Envios simultaneos del reconciliador por replica: deja >= 6 de las 10 conexiones del registro a la decision (NFR-U8-01).
RECONCILER_CONCURRENCY: Final[int] = 4
CASE_DB_POOL_MAX: Final[int] = 5  # pool de `case-db` por proceso (<= 5)

# --- Circuit breaker (NFR-U8-31): los umbrales de U7, los aplica `vectra_common.deps` ---
BREAKER_FAILURE_RATIO: Final[float] = 0.5
BREAKER_WINDOW_CALLS: Final[int] = 20
BREAKER_WINDOW_SECONDS: Final[float] = 30.0
BREAKER_HALF_OPEN_AFTER: Final[float] = 10.0

# --- Backoff de la evaluacion (BR-U8-07): 30 s * 2^(n-1) con jitter de +-20 %, maximo 6 intentos ---
BACKOFF_BASE: Final[float] = 30.0
BACKOFF_FACTOR: Final[int] = 2
BACKOFF_JITTER: Final[float] = 0.2
MAX_ATTEMPTS: Final[int] = 6

# --- Cola de evaluacion (P-U8-01) ---
LEASE: Final[float] = 30.0  # arrendamiento (`locked_until`)
POLL_INTERVAL: Final[float] = 0.4  # sondeo con la cola vacia: 400 ms ...
POLL_JITTER: Final[float] = 0.1  # ... +- 100 ms (<= 500 ms, NFR-U8-04)
WORKER_CONCURRENCY: Final[int] = 16  # semaforo de trabajos en vuelo por replica

# Peor caso de un intento, con el reintento por 401 (BR-U8-08): serving-config + feature_spec + scoring + scoring = 15,5 s.
# Se calcula, no se escribe a mano (P-U8-01).
WORKER_WORST_CASE: Final[float] = (
    SERVING_CONFIG_TIMEOUT + FEATURE_SPEC_TIMEOUT + SCORING_TIMEOUT + SCORING_TIMEOUT
)

# --- Apagado ordenado del worker (INF-U8-06) ---
WORKER_SHUTDOWN_GRACE: Final[float] = 20.0  # espera de las llamadas en vuelo tras SIGTERM
# `terminationGracePeriodSeconds` del Deployment de `case-worker`: es un campo del chart (Paso 20, U08-T05), que debe usar
# este valor; aqui es la constante documentada contra la que se comparan las demas.
WORKER_TERMINATION_GRACE: Final[float] = 30.0

# --- Lotes (P-U8-01, 07; NFR-U8-13) ---
BATCH_SIZE: Final[int] = 100  # barridos y reconciliador
RETENTION_BATCH_SIZE: Final[int] = 500  # `case-retention`

# --- Evidencia en dos fases (BR-U8-18) ---
EVIDENCE_ABANDON_AFTER: Final[float] = 24 * 60 * 60.0  # 24 h sin confirmar -> `abandonada`
RECONCILER_BACKOFF_MIN: Final[float] = 1.0  # reintentos del reconciliador: de 1 s ...
RECONCILER_BACKOFF_MAX: Final[float] = 300.0  # ... a 5 min

# --- case-service (U08-T03): reconciliador, barridos, gauges, cliente de governance y pool de `case-db` ---
# Los del reconciliador llevan el prefijo `RECONCILER_`: no son los del worker (`LEASE`, `BACKOFF_*` de arriba).
RECONCILER_INTERVAL: Final[float] = 1.0  # un ciclo cada 1 s (P-U8-04)
RECONCILER_BACKOFF_JITTER: Final[float] = 0.2  # +-20 % sobre el backoff de 1 s a 5 min
# Arrendamiento de una evidencia reclamada: cubre el peor lote, no un envio. Un lote son BATCH_SIZE / RECONCILER_CONCURRENCY
# turnos de hasta REGISTRY_TIMEOUT, el doble con el reintento por 401: 25 * 2,5 s * 2 = 125 s. Si una replica muere, sus filas
# vuelven a ser elegibles al vencer. Tambien es el `next_attempt_at` inicial del envio inmediato de la decision y de la consulta.
RECONCILER_LEASE: Final[float] = float(BATCH_SIZE // RECONCILER_CONCURRENCY) * REGISTRY_TIMEOUT * 2
SWEEP_INTERVAL: Final[float] = 300.0  # barrido de `modelo_congelado` cada 5 min (BR-U8-10)
GAUGE_INTERVAL: Final[float] = 30.0  # `db_gauges` cada 30 s (P-U8-04, 08)
JOBS_OVERDUE_AFTER: Final[int] = (
    30  # un trabajo sin tomar con `run_at` mas viejo que esto esta vencido (segundos)
)
SERVING_CONFIG_CACHE_TTL: Final[float] = 5.0  # cache de `serving-config` <= 5 s (NFR-U8-15)
DB_ACQUIRE_TIMEOUT: Final[float] = 2.0  # esperar una conexion libre del pool de `case-db`
DB_CONNECT_TIMEOUT: Final[int] = 2  # conexion nueva a `case-db`
