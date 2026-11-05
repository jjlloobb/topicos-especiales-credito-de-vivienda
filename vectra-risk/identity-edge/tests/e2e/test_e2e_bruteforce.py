"""Fuerza bruta (BR-U2-05, BR-U2-16; US-601): el bloqueo, su evento en Loki y PBT-U2-08. Se ejecutan en el Paso 16.

H9: el tipo de evento del bloqueo temporal se fija contra el código de Keycloak 26.8.1:
- `services/src/main/java/org/keycloak/services/managers/DefaultBruteForceProtector.java`, línea 142: `sendEvent(..., EventType.USER_DISABLED_BY_TEMPORARY_LOCKOUT)`;
- el permanente, línea 180: `EventType.USER_DISABLED_BY_PERMANENT_LOCKOUT`;
- `server-spi-private/src/main/java/org/keycloak/events/EventType.java`, líneas 177 y 180, los declara.
El evento se construye con `.user(userId)` y sin `username` ni `email` (líneas 191-195 del mismo archivo): BR-U2-16.
"""

import os
import re
import secrets
import time
from typing import Any

import bruteforce_model
import e2e_support as support
from bruteforce_model import BruteForceModel, Params
from e2e_support import Flow
from hypothesis import settings
from hypothesis.stateful import (
    RuleBasedStateMachine,
    invariant,
    precondition,
    rule,
    run_state_machine_as_test,
)

TEMPORARY_LOCKOUT_EVENT = "USER_DISABLED_BY_TEMPORARY_LOCKOUT"
BRUTE_FORCE = support.brute_force()
FAILURE_FACTOR = BRUTE_FORCE["failureFactor"]


def attempt(username: str, password: str) -> support.Step:
    """Un intento de login con un flujo nuevo; devuelve la respuesta de Keycloak."""
    flow = Flow()
    try:
        return flow.password(flow.start(), username, password)
    finally:
        flow.close()


def wrong_password() -> str:
    return secrets.token_urlsafe(24)


def lock(account: support.Account, admin: support.Admin) -> None:
    """`failureFactor` fallos separados más que `quickLoginCheckMilliSeconds`: si no, Keycloak aplica el bloqueo rápido
    (`DefaultBruteForceProtector.java`, líneas 121-127) en el 2.o fallo y los demás no cuentan (F-01a)."""
    for i in range(FAILURE_FACTOR):
        if i:
            time.sleep(PARAMS.quick_login_check_milliseconds / 1000 + bruteforce_model.QUICK_MARGIN_SECONDS)
        step = attempt(account.username, wrong_password())
        assert step.code is None
    status = admin.settled_status(account.user_id, lambda s: bool(s["disabled"]))
    assert status["disabled"], f"el usuario no quedó bloqueado tras {FAILURE_FACTOR} fallos: {status}"


def test_five_failures_lock_the_user(ephemeral_user: Any, admin: support.Admin) -> None:
    """`failureFactor` fallos consecutivos -> bloqueo temporal: ni la contraseña correcta obtiene código."""
    account = ephemeral_user()
    lock(account, admin)
    status = admin.brute_force_status(account.user_id)
    assert status["numFailures"] == FAILURE_FACTOR
    assert status["numTemporaryLockouts"] == 1, "el bloqueo de `failureFactor` fallos es el primero de la serie, y no uno rápido"
    assert attempt(account.username, account.password).code is None, "con el usuario bloqueado, la contraseña correcta obtuvo un código"


def test_lockout_event_has_user_id_and_no_username(ephemeral_user: Any, admin: support.Admin, loki: support.Loki) -> None:
    """H6: el evento del bloqueo, consultado en Loki con LogQL, lleva `userId` y no lleva `username` ni `email` (BR-U2-16)."""
    account = ephemeral_user()
    since = time.time_ns() - 5_000_000_000
    lock(account, admin)
    query = f'{support.KEYCLOAK_STREAM} |= "{TEMPORARY_LOCKOUT_EVENT}" |= "{account.user_id}"'
    lines = loki.wait_for(query, since)
    assert lines, f"Loki no tiene el evento {TEMPORARY_LOCKOUT_EVENT} de {account.user_id}"
    for line in lines:
        assert re.search(rf'userId="?{account.user_id}', line), line
        assert "username=" not in line and "email=" not in line, line
        assert account.username not in line, line


# --- PBT-U2-08 --------------------------------------------------------------------------------------------------

# Una espera de Keycloak se espera de verdad: el modelo solo la cruza si dura a lo sumo esto (por defecto, los tres primeros
# bloqueos: 60, 120 y 180 s). La serie completa (hasta el fallo 19 de 900 s y el permanente del 20) la cubre la prueba
# unitaria `test_bruteforce_model.py`; con `VECTRA_E2E_BRUTEFORCE_MAX_WAIT_SECONDS=900` la máquina también la recorre.
MAX_WAIT_SECONDS = int(os.environ.get("VECTRA_E2E_BRUTEFORCE_MAX_WAIT_SECONDS") or 3 * BRUTE_FORCE["waitIncrementSeconds"])
MARGIN_SECONDS = 3.0  # cerca del fin de un bloqueo el reloj de Keycloak y el del modelo no coinciden: se espera a que pase
PARAMS = Params.from_realm(BRUTE_FORCE)


class BruteForceMachine(RuleBasedStateMachine):
    """Modelo completo de BR-U2-05 con H10 contra el Keycloak de kind, con un usuario efímero por ejemplo (H8).

    Los parámetros salen del realm (`failureFactor`, `waitIncrementSeconds`, `maxFailureWaitSeconds`, `maxTemporaryLockouts`,
    `bruteForceStrategy`) y el modelo es `bruteforce_model.BruteForceModel`: desde el fallo `failureFactor` cada fallo es un
    bloqueo temporal creciente, durante un bloqueo ni la contraseña correcta obtiene código y los intentos no cuentan, un acierto
    pone todo a cero y el bloqueo número `maxTemporaryLockouts + 1` es permanente. La regla `wait_out_lockout` deja pasar el
    tiempo real (hasta `MAX_WAIT_SECONDS`).
    """

    admin: support.Admin
    make_user: Any

    def __init__(self) -> None:
        super().__init__()
        self.account = self.make_user()
        self.model = BruteForceModel(PARAMS)
        self.started = time.monotonic()

    def teardown(self) -> None:
        self.admin.delete_user(self.account.user_id)

    def now(self) -> float:
        return time.monotonic() - self.started

    def steady(self) -> float:
        """El instante actual, después de esperar si un bloqueo está a punto de terminar (la frontera es ambigua)."""
        remaining = self.model.remaining(self.now())
        if 0 < remaining <= MARGIN_SECONDS:
            time.sleep(remaining + MARGIN_SECONDS)
        return self.now()

    @rule()
    def wrong_password_attempt(self) -> None:
        at = self.steady()
        if not self.model.locked(at) and self.model.quiet_until() > at:
            # F-01a: dos fallos a menos de `quickLoginCheckMilliSeconds` serían un bloqueo rápido, que el modelo no busca aquí
            time.sleep(self.model.quiet_until() - at)
            at = self.steady()
        step = attempt(self.account.username, wrong_password())
        assert step.code is None
        # F-12: Keycloak fecha el fallo al procesar el POST, no antes de enviarlo: se toma el instante después del intento
        at = self.now()
        self.model.wrong(at)
        self.settle()

    @rule()
    def right_password_attempt(self) -> None:
        at = self.steady()
        step = attempt(self.account.username, self.account.password)
        if self.model.right(at):
            assert step.code, "sin bloqueo, la contraseña correcta no obtuvo un código"
        else:
            assert step.code is None, "bloqueado, la contraseña correcta obtuvo un código"
        self.settle()

    @precondition(lambda self: 0 < self.model.remaining(self.now()) <= MAX_WAIT_SECONDS)
    @rule()
    def wait_out_lockout(self) -> None:
        time.sleep(self.model.remaining(self.now()) + MARGIN_SECONDS)
        self.settle()

    def settle(self) -> None:
        at = self.steady()
        self.admin.settled_status(
            self.account.user_id,
            lambda s: s["numFailures"] == self.model.failures
            and s["numTemporaryLockouts"] == self.model.temporary_lockouts
            and bool(s["disabled"]) == self.model.locked(at),
        )

    @invariant()
    def keycloak_agrees_with_the_model(self) -> None:
        at = self.steady()
        status = self.admin.brute_force_status(self.account.user_id)
        assert status["numFailures"] == self.model.failures, f"fallos: Keycloak {status}, modelo {self.model.failures}"
        assert status["numTemporaryLockouts"] == self.model.temporary_lockouts, f"bloqueos temporales: Keycloak {status}, modelo {self.model.temporary_lockouts}"
        assert bool(status["disabled"]) == self.model.locked(at), f"bloqueo: Keycloak {status}, modelo en {at:.0f} s"


def test_pbt_u2_08_bruteforce_state_machine(admin: support.Admin, ephemeral_user: Any) -> None:
    """PBT-U2-08: secuencias generadas de aciertos, fallos y esperas contra Keycloak, con el perfil `kind-e2e`."""

    class Machine(BruteForceMachine):
        pass

    Machine.admin = admin
    Machine.make_user = staticmethod(ephemeral_user)
    run_state_machine_as_test(Machine, settings=settings.get_profile("kind-e2e"))
