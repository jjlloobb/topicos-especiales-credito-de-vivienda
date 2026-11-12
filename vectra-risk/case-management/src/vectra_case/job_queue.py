"""Cola de evaluacion con `FOR UPDATE SKIP LOCKED` (Paso 15; BR-U8-07; P-U8-01; NFR-U8-02, 03, 04).

`take` es una transaccion corta: elige un trabajo debido (`run_at <= ahora` y sin arrendamiento vigente), le pone `locked_until = ahora +
30 s`, incrementa `evaluation_jobs.attempt` y copia el numero a `cases.attempts`, tambien en la retoma tras un arrendamiento vencido
(el intento perdido con el worker cuenta como uno de los 6). La decision se toma con el `attempt` **leido**: si ya vale 6, el caso escala
en esa misma transaccion con `local_cause = scoring_unreachable`, sin incrementar (el `CHECK` rechazaria 7) y sin llamar a scoring.
La conexion vuelve al pool antes de la llamada a scoring: `take` entrega una fila (`Taken`) y termina.

El reloj es inyectado: `run_at`, `locked_until` y los comparativos viajan como parametros, no salen de `now()` de la base.
"""

from datetime import timedelta

from vectra_contracts.catalog import CaseState, LocalCause

from vectra_case.case_fsm import CaseEvent
from vectra_case.config import LEASE, MAX_ATTEMPTS
from vectra_case.db import Database
from vectra_case.evaluation import IN_FLIGHT, Clock, Taken, escalate, utc_now

_DUE = (
    "SELECT case_id, attempt FROM evaluation_jobs WHERE run_at <= %s AND (locked_until IS NULL OR locked_until <= %s) "
    "ORDER BY run_at LIMIT 1 FOR UPDATE SKIP LOCKED"
)
_CASE = (
    "SELECT c.state, c.created_at, c.ever_degraded, c.application, to_jsonb(i) - 'case_id' AS identifiers "
    "FROM cases c LEFT JOIN case_identifiers i USING (case_id) WHERE c.case_id = %s"
)


class JobQueue:
    def __init__(self, db: Database, clock: Clock = utc_now) -> None:
        self.db = db
        self.clock = clock

    async def take(self) -> Taken | None:
        """Un trabajo para evaluar, o `None` si no hay (o si la toma lo escalo o lo descarto sin que haya nada que evaluar)."""
        now = self.clock()
        async with self.db.tx() as conn:
            cur = await conn.execute(_DUE, (now, now))
            job = await cur.fetchone()
            if job is None:
                return None
            case_id, read = job["case_id"], job["attempt"]
            cur = await conn.execute(_CASE, (case_id,))
            case = await cur.fetchone()
            assert case is not None  # `evaluation_jobs.case_id` referencia `cases`
            state = CaseState(case["state"])
            if (
                state.value not in IN_FLIGHT
            ):  # el caso ya salio del bucle (p. ej. `decidido`, `vencido`): el trabajo sobra
                await conn.execute("DELETE FROM evaluation_jobs WHERE case_id = %s", (case_id,))
                return None
            if (
                read >= MAX_ATTEMPTS
            ):  # worker perdido en el intento 6: escala sin incrementar y sin llamar (BR-U8-07)
                escalated = await escalate(
                    conn,
                    case_id=case_id,
                    state=state,
                    attempt=read,
                    leased_until=None,  # la propia toma tiene la fila bloqueada
                    now=now,
                    cause=None,
                    local_cause=LocalCause.SCORING_UNREACHABLE,
                    event=CaseEvent.ATTEMPT_6_FAILED,
                )
                if (
                    not escalated
                ):  # el caso ya no esta en el bucle: el trabajo sobra y no debe volver a tomarse
                    await conn.execute("DELETE FROM evaluation_jobs WHERE case_id = %s", (case_id,))
                return None
            leased_until = now + timedelta(seconds=LEASE)
            attempt = read + 1  # el valor leido, no `attempt + 1` en SQL: nunca se escribe un 7
            await conn.execute(
                "UPDATE evaluation_jobs SET attempt = %s, locked_until = %s WHERE case_id = %s",
                (attempt, leased_until, case_id),
            )
            cur = await conn.execute(
                "UPDATE cases SET attempts = %s, updated_at = %s WHERE case_id = %s "
                "AND state IN ('en_evaluacion', 'en_sincronizacion')",
                (attempt, now, case_id),
            )
            if (
                cur.rowcount != 1
            ):  # otro proceso cambio el caso entre la lectura y la guarda: el trabajo sobra
                await conn.execute("DELETE FROM evaluation_jobs WHERE case_id = %s", (case_id,))
                return None
            return Taken(
                case_id,
                attempt,
                leased_until,
                state,
                case["created_at"],
                case["ever_degraded"],
                case["application"],
                case["identifiers"],
            )
