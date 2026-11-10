"""Backoff de la evaluacion (puro; Paso 5; BR-U8-07; US-112).

`schedule(attempt, rng)` es el retraso antes del intento `attempt + 1`, para `attempt` de 1 a 5: 30 s, 1, 2, 4 y 8 min con un
jitter uniforme de +-20 %. Tras el intento 6 no hay mas intentos (el caso escala, BR-U8-09): `schedule(6, ...)` y cualquier valor
fuera de 1..5 lanzan `ValueError`. El `rng` es un parametro para que la propiedad sea reproducible.
"""

from random import Random

from vectra_case.config import BACKOFF_BASE, BACKOFF_FACTOR, BACKOFF_JITTER, MAX_ATTEMPTS


def schedule(attempt: int, rng: Random) -> float:
    """Segundos de espera antes del intento `attempt + 1`."""
    if not 1 <= attempt < MAX_ATTEMPTS:
        raise ValueError(f"attempt fuera de 1..{MAX_ATTEMPTS - 1}: {attempt}")
    nominal: float = BACKOFF_BASE * float(BACKOFF_FACTOR) ** (attempt - 1)
    return nominal * rng.uniform(1.0 - BACKOFF_JITTER, 1.0 + BACKOFF_JITTER)
