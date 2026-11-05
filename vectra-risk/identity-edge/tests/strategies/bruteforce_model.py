"""Modelo puro de la fuerza bruta de BR-U2-05 (enmienda H10) para PBT-U2-08. Sin red, sin reloj propio, sin Keycloak.

Semántica de Keycloak 26.8.1 (`DefaultBruteForceProtector.java`, líneas 109-143 y 161-164; ver `test_bruteforce_model.py`):
- cada fallo desde `failureFactor` es un bloqueo temporal de `espera(n)` segundos, con tope `maxFailureWaitSeconds`:
  LINEAR `waitIncrement * (1 + n - failureFactor)`, MULTIPLE `waitIncrement * (n // failureFactor)`;
- cada bloqueo suma uno al contador; con `numTemporaryLockouts > maxTemporaryLockouts` el bloqueo es permanente;
- un intento durante un bloqueo no cuenta; un acierto fuera del bloqueo pone todo a cero.
El tiempo lo aporta quien llama (`at`, en segundos): el modelo no duerme.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Params:
    failure_factor: int
    wait_increment_seconds: int
    max_failure_wait_seconds: int
    max_temporary_lockouts: int
    strategy: str

    @classmethod
    def from_realm(cls, realm: Mapping[str, Any]) -> "Params":
        return cls(
            failure_factor=realm["failureFactor"],
            wait_increment_seconds=realm["waitIncrementSeconds"],
            max_failure_wait_seconds=realm["maxFailureWaitSeconds"],
            max_temporary_lockouts=realm["maxTemporaryLockouts"],
            strategy=realm["bruteForceStrategy"],
        )


def lockout_seconds(params: Params, failures: int) -> int:
    """Segundos de bloqueo temporal que produce el fallo número `failures` (0 si todavía no hay bloqueo)."""
    if params.strategy == "MULTIPLE":
        wait = params.wait_increment_seconds * (failures // params.failure_factor)
    else:
        wait = params.wait_increment_seconds * (1 + failures - params.failure_factor)
    return min(params.max_failure_wait_seconds, wait) if wait > 0 else 0


def temporary_lockouts(params: Params, failures: int) -> int:
    """Bloqueos acumulados tras `failures` fallos: cada fallo con espera positiva suma uno."""
    return sum(1 for n in range(1, failures + 1) if lockout_seconds(params, n) > 0)


class BruteForceModel:
    def __init__(self, params: Params) -> None:
        self.params = params
        self.failures = 0
        self.permanent = False
        self.last_failure_at = 0.0
        self.locked_until = 0.0

    def locked(self, at: float) -> bool:
        return self.permanent or at < self.locked_until

    def remaining(self, at: float) -> float:
        """Segundos que faltan para el fin del bloqueo temporal (0 si no hay)."""
        return 0.0 if self.permanent else max(0.0, self.locked_until - at)

    def next_free_time(self) -> float:
        """El primer instante en que se puede intentar de nuevo."""
        return self.locked_until

    def wrong(self, at: float) -> bool:
        """Un fallo de contraseña. Devuelve si Keycloak lo cuenta (durante un bloqueo, no)."""
        if self.locked(at):
            return False
        self.failures += 1
        self.last_failure_at = at
        wait = lockout_seconds(self.params, self.failures)
        if wait > 0:
            if temporary_lockouts(self.params, self.failures) > self.params.max_temporary_lockouts:
                self.permanent = True
            else:
                self.locked_until = at + wait
        return True

    def right(self, at: float) -> bool:
        """Un acierto. Devuelve si obtiene código (durante un bloqueo, no); si lo obtiene, todo vuelve a cero."""
        if self.locked(at):
            return False
        self.failures = 0
        self.locked_until = 0.0
        return True
