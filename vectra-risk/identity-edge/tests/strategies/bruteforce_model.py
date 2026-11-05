"""Modelo puro de la fuerza bruta de BR-U2-05 (enmienda H10) para PBT-U2-08. Sin red, sin reloj propio, sin Keycloak.

Semántica de Keycloak 26.8.1 (`DefaultBruteForceProtector.java`, líneas 109-143 y 161-164; ver `test_bruteforce_model.py`):
- cada fallo desde `failureFactor` es un bloqueo temporal de `espera(n)` segundos, con tope `maxFailureWaitSeconds`:
  LINEAR `waitIncrement * (1 + n - failureFactor)`, MULTIPLE `waitIncrement * (n // failureFactor)`;
- cada bloqueo suma uno al contador; con `numTemporaryLockouts > maxTemporaryLockouts` el bloqueo es permanente;
- un intento durante un bloqueo no cuenta; un acierto fuera del bloqueo pone todo a cero (también `lastFailure`);
- bloqueo rápido (líneas 121-127 y 130-136): un fallo sin espera por serie que llega a menos de `quickLoginCheckMilliSeconds`
  del fallo anterior bloquea `minimumQuickLoginWaitSeconds` (con el tope `maxFailureWaitSeconds`), cuenta como fallo y NO suma
  un bloqueo temporal.
El tiempo lo aporta quien llama (`at`, en segundos): el modelo no duerme.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

# El realm de Git no fija `quickLoginCheckMilliSeconds` ni `minimumQuickLoginWaitSeconds`: rigen los valores por defecto del
# realm que crea Keycloak 26.8.1 (`services/.../managers/RealmManager.java`, línea 278: 60 s; línea 280: 1000 ms).
KEYCLOAK_DEFAULT_MINIMUM_QUICK_LOGIN_WAIT_SECONDS = 60
KEYCLOAK_DEFAULT_QUICK_LOGIN_CHECK_MILLISECONDS = 1000

QUICK_MARGIN_SECONDS = 0.5  # lo que se deja de más sobre `quickLoginCheckMilliSeconds` entre dos fallos


@dataclass(frozen=True)
class Params:
    failure_factor: int
    wait_increment_seconds: int
    max_failure_wait_seconds: int
    max_temporary_lockouts: int
    strategy: str
    quick_login_check_milliseconds: int = KEYCLOAK_DEFAULT_QUICK_LOGIN_CHECK_MILLISECONDS
    minimum_quick_login_wait_seconds: int = KEYCLOAK_DEFAULT_MINIMUM_QUICK_LOGIN_WAIT_SECONDS

    @classmethod
    def from_realm(cls, realm: Mapping[str, Any]) -> "Params":
        return cls(
            failure_factor=realm["failureFactor"],
            wait_increment_seconds=realm["waitIncrementSeconds"],
            max_failure_wait_seconds=realm["maxFailureWaitSeconds"],
            max_temporary_lockouts=realm["maxTemporaryLockouts"],
            strategy=realm["bruteForceStrategy"],
            quick_login_check_milliseconds=realm.get("quickLoginCheckMilliSeconds", KEYCLOAK_DEFAULT_QUICK_LOGIN_CHECK_MILLISECONDS),
            minimum_quick_login_wait_seconds=realm.get("minimumQuickLoginWaitSeconds", KEYCLOAK_DEFAULT_MINIMUM_QUICK_LOGIN_WAIT_SECONDS),
        )


def lockout_seconds(params: Params, failures: int) -> int:
    """Segundos de bloqueo temporal que produce el fallo número `failures` (0 si todavía no hay bloqueo)."""
    if params.strategy == "MULTIPLE":
        wait = params.wait_increment_seconds * (failures // params.failure_factor)
    else:
        wait = params.wait_increment_seconds * (1 + failures - params.failure_factor)
    return min(params.max_failure_wait_seconds, wait) if wait > 0 else 0


class BruteForceModel:
    def __init__(self, params: Params) -> None:
        self.params = params
        self.failures = 0
        self.permanent = False
        self.last_failure_at: float | None = None
        self.temporary_lockouts = 0
        self.locked_until = 0.0

    def locked(self, at: float) -> bool:
        return self.permanent or at < self.locked_until

    def remaining(self, at: float) -> float:
        """Segundos que faltan para el fin del bloqueo temporal (0 si no hay)."""
        return 0.0 if self.permanent else max(0.0, self.locked_until - at)

    def quiet_until(self) -> float:
        """El instante a partir del cual un fallo ya no es rápido: `quickLoginCheckMilliSeconds` (más un margen) después del último."""
        if self.last_failure_at is None:
            return 0.0
        return self.last_failure_at + self.params.quick_login_check_milliseconds / 1000 + QUICK_MARGIN_SECONDS

    def next_free_time(self) -> float:
        """El primer instante en que se puede intentar de nuevo sin caer en un bloqueo rápido: fuera del bloqueo y en silencio."""
        return max(self.locked_until, self.quiet_until())

    def wrong(self, at: float) -> bool:
        """Un fallo de contraseña. Devuelve si Keycloak lo cuenta (durante un bloqueo, no)."""
        if self.locked(at):
            return False
        previous = self.last_failure_at
        self.failures += 1
        self.last_failure_at = at
        wait = lockout_seconds(self.params, self.failures)
        quick = False
        if wait <= 0 and previous is not None and (at - previous) * 1000 < self.params.quick_login_check_milliseconds:
            wait, quick = self.params.minimum_quick_login_wait_seconds, True
        if wait > 0:
            wait = min(self.params.max_failure_wait_seconds, wait)
            if not quick:
                self.temporary_lockouts += 1
            if quick or self.temporary_lockouts <= self.params.max_temporary_lockouts:
                self.locked_until = at + wait
        if self.temporary_lockouts > self.params.max_temporary_lockouts:
            self.permanent = True
        return True

    def right(self, at: float) -> bool:
        """Un acierto. Devuelve si obtiene código (durante un bloqueo, no); si lo obtiene, todo vuelve a cero."""
        if self.locked(at):
            return False
        self.failures = 0
        self.temporary_lockouts = 0
        self.locked_until = 0.0
        self.last_failure_at = None
        return True
