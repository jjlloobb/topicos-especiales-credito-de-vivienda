"""Fuerza bruta (BR-U2-05, BR-U2-16; US-601): el bloqueo, su evento en Loki y PBT-U2-08. Se ejecutan en el Paso 16.

H9: el tipo de evento del bloqueo temporal se fija contra el código de Keycloak 26.8.1:
- `services/src/main/java/org/keycloak/services/managers/DefaultBruteForceProtector.java`, línea 142: `sendEvent(..., EventType.USER_DISABLED_BY_TEMPORARY_LOCKOUT)`;
- el permanente, línea 180: `EventType.USER_DISABLED_BY_PERMANENT_LOCKOUT`;
- `server-spi-private/src/main/java/org/keycloak/events/EventType.java`, líneas 177 y 180, los declara.
El evento se construye con `.user(userId)` y sin `username` ni `email` (líneas 191-195 del mismo archivo): BR-U2-16.
"""

import re
import secrets
import time
from typing import Any

import e2e_support as support
from e2e_support import Flow
from hypothesis import settings
from hypothesis.stateful import RuleBasedStateMachine, invariant, rule, run_state_machine_as_test

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
    for _ in range(FAILURE_FACTOR):
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


class BruteForceMachine(RuleBasedStateMachine):
    """Modelo de BR-U2-05 contra el Keycloak de kind, con un usuario efímero por ejemplo (H8).

    Los contadores salen del realm (`BRUTE_FORCE`). El modelo cubre la primera serie: `failureFactor` fallos consecutivos bloquean
    de forma temporal, un acierto antes de eso reinicia la cuenta y, bloqueado, ni la contraseña correcta obtiene código y los
    intentos no cuentan. Las series siguientes (espera 60/120/180 s y bloqueo permanente) NO están modeladas: el código de
    Keycloak 26.8.1 no se comporta como BR-U2-05 las describe (bitácora de U02-T14, bloqueo B-1).
    """

    admin: support.Admin
    make_user: Any

    def __init__(self) -> None:
        super().__init__()
        self.account = self.make_user()
        self.failures = 0
        self.locked = False

    def teardown(self) -> None:
        self.admin.delete_user(self.account.user_id)

    @rule()
    def wrong_password_attempt(self) -> None:
        step = attempt(self.account.username, wrong_password())
        assert step.code is None
        if not self.locked:
            self.failures += 1
            self.locked = self.failures >= FAILURE_FACTOR
        self.settle()

    @rule()
    def right_password_attempt(self) -> None:
        step = attempt(self.account.username, self.account.password)
        if self.locked:
            assert step.code is None, "bloqueado, la contraseña correcta obtuvo un código"
        else:
            assert step.code, "sin bloqueo, la contraseña correcta no obtuvo un código"
            self.failures = 0
        self.settle()

    def settle(self) -> None:
        self.admin.settled_status(self.account.user_id, lambda s: s["numFailures"] == self.failures and bool(s["disabled"]) == self.locked)

    @invariant()
    def keycloak_agrees_with_the_model(self) -> None:
        status = self.admin.brute_force_status(self.account.user_id)
        assert status["numFailures"] == self.failures
        assert bool(status["disabled"]) == self.locked


def test_pbt_u2_08_bruteforce_state_machine(admin: support.Admin, ephemeral_user: Any) -> None:
    """PBT-U2-08: secuencias generadas de aciertos y fallos contra Keycloak, con el perfil `kind-e2e`."""

    class Machine(BruteForceMachine):
        pass

    Machine.admin = admin
    Machine.make_user = staticmethod(ephemeral_user)
    run_state_machine_as_test(Machine, settings=settings.get_profile("kind-e2e"))
