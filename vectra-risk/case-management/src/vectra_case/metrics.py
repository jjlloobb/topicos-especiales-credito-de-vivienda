"""Metricas de U8 (Paso 11, 13 y 15; P-U8-04, 06, 08; NFR-U8-13, 45).

Etiquetas permitidas (P-U8-06): `result`, `cause`, `state`, `entry_type`, `dependency`, `code`, `route_template`, `attempt`.
Los contadores de conjunto cerrado crean todas sus combinaciones en 0 al importar el modulo (`increase()` no pierde el primer evento).
"""

from typing import Final

from prometheus_client import Counter, Gauge, Histogram
from vectra_common.metrics import REGISTRY

ENTRY_TYPES: Final = ("human_decision", "explanation_view", "fail_closed")
ATTEMPT_RESULTS: Final = (
    "recommendation",
    "failclosed",
    "model_frozen",
    "scoring_unreachable",
    "serving_config_unavailable",
    "scoring_rejected",
)
ATTEMPTS: Final = tuple(str(n) for n in range(1, 7))
ALLOWED_LABELS: Final = frozenset(
    {"result", "cause", "state", "entry_type", "dependency", "code", "route_template", "attempt"}
)

EVIDENCE_PENDING_OLDEST: Final = Gauge(
    "vectra_case_evidence_pending_oldest_seconds",
    "Antiguedad de la evidencia pendiente mas vieja",
    ["entry_type"],
    registry=REGISTRY,
)
EVIDENCE_ABANDONED: Final = Counter(
    "vectra_case_evidence_abandoned_total",
    "Evidencias abandonadas a las 24 h",
    ["entry_type"],
    registry=REGISTRY,
)
EVIDENCE_DISCARDED: Final = Counter(
    "vectra_case_evidence_discarded_total", "Consultas descartadas por BR-U0-37", registry=REGISTRY
)
CASE_RETRIES: Final = Counter("vectra_case_retries_total", "retry del CRO", registry=REGISTRY)
CASE_ATTEMPTS: Final = Counter(
    "vectra_case_attempts_total", "Intentos de evaluacion", ["result", "attempt"], registry=REGISTRY
)
# Solo los casos `listo` al primer intento (U11 BR-U11-05; quinta revision de coherencia, 2026-10-31). Sin etiquetas.
TIME_TO_READY_BUCKETS: Final = (0.5, 1.0, 2.0, 3.0, 5.0, 10.0, 30.0, 60.0)
TIME_TO_READY: Final = Histogram(
    "vectra_case_time_to_ready_seconds",
    "Segundos de la creacion del caso a listo, solo al primer intento",
    registry=REGISTRY,
    buckets=TIME_TO_READY_BUCKETS,
)
JOBS_OVERDUE: Final = Gauge("vectra_case_jobs_overdue", "Trabajos vencidos sin tomar", registry=REGISTRY)
FAILCLOSED_PERSISTENT: Final = Gauge(
    "vectra_cases_failclosed_persistent", "Casos en no_disponible", registry=REGISTRY
)


def init_series() -> None:
    """Crea en 0 cada combinacion de los contadores y gauges de conjunto cerrado."""
    for entry_type in ENTRY_TYPES:
        EVIDENCE_ABANDONED.labels(entry_type=entry_type)
        EVIDENCE_PENDING_OLDEST.labels(entry_type=entry_type).set(0)
    for result in ATTEMPT_RESULTS:
        for attempt in ATTEMPTS:
            CASE_ATTEMPTS.labels(result=result, attempt=attempt)
    JOBS_OVERDUE.set(0)
    FAILCLOSED_PERSISTENT.set(0)


init_series()
