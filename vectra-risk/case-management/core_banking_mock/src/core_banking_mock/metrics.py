"""Metricas del mock (Paso 17; P-U8-06; NFR-U8-45). Sin etiquetas: `vectra_core_write_attempts_total` nace en 0 al importar el modulo."""

from typing import Final

from prometheus_client import Counter
from vectra_common.metrics import REGISTRY

WRITE_ATTEMPTS: Final = Counter(
    "vectra_core_write_attempts_total",
    "Intentos de escritura al core rechazados con 403 (RT-5; alerta CoreWriteAttempt)",
    registry=REGISTRY,
)
