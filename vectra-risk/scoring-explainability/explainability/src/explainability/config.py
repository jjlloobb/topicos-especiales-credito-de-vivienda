"""Presupuestos de `explainability-service` como constantes tipadas (INF-U7-04).

Ninguno se lee de variables de entorno. Tiempos en milisegundos, salvo `BREAKER` (segundos, como `BreakerConfig`).
"""

from typing import Final

from vectra_common.deps import BreakerConfig

# P-U7-01: tope propio contado desde la llegada, y margen sobre la cabecera `x-vectra-deadline`.
# Corta en `min(deadline - 50 ms, llegada + 700 ms)`; una cabecera manipulada no extiende el presupuesto.
OWN_CEILING_MS: Final = 700
DEADLINE_MARGIN_MS: Final = 50

# NFR-U7-10: timeouts por llamada (maximos; rige el menor con el tiempo restante).
EXPLAIN_TIMEOUT_MS: Final = 500
DICTIONARY_TIMEOUT_MS: Final = 500
REGISTRY_TIMEOUT_MS: Final = 2_500

# P-U7-04: conexiones maximas por pod, un cliente por dependencia.
EXPLAIN_POOL: Final = 20
DICTIONARY_POOL: Final = 5
REGISTRY_POOL: Final = 5

# NFR-U7-11: iguales a los de scoring.
BREAKER: Final = BreakerConfig(open_for=10.0, window_size=20, failure_ratio=0.5, window_seconds=30.0)

# P-U7-05: `serving-config` <= 5 s; diccionario por version, sin expiracion, LRU de 4 versiones.
SERVING_CONFIG_CACHE_TTL_MS: Final = 5_000
DICTIONARY_LRU_VERSIONS: Final = 4
