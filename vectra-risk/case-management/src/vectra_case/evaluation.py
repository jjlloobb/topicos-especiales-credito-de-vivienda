"""Evaluacion de un caso (Paso 15; BR-U8-05..09, 12; P-U8-01, 08, 09; US-109, US-112).

Un intento (BR-U8-05): `serving-config` -> `feature_spec` de esa version -> `derive` -> `ScoringRequest` -> scoring. Despues se aplica el
resultado (BR-U8-08) en **una** transaccion, con la guarda `UPDATE ... WHERE state IN (en_evaluacion, en_sincronizacion) AND attempts
= :attempt` (el numero que devolvio esa toma). Si ninguna fila cambia (el caso ya esta `vencido`, `listo` o lo retomo otro worker) el
resultado se descarta con el log `evaluation.result_discarded` y el trabajo vivo no se toca.

- `build_request` no hace E/S: PBT-U8-05 lo prueba sin base. Nunca lleva identificadores, `free_text` ni `test_scenario_id`.
- Cada cambio de estado sale de `case_fsm.transition`; los triggers de la base (`guard_transition`) son la segunda defensa.
- Al entrar en `en_sincronizacion`, `no_disponible` o `modelo_congelado`, la misma transaccion pone `ever_degraded = true`.
- Escalamiento (BR-U8-09): `no_disponible`, `escalation_count + 1` y una entrada `fail_closed` en `evidence_outbox` con
  `UUIDv5(case_id, "fail_closed:<ciclo>")`, `INSERT` simple dentro de un `SAVEPOINT` (el rol `case_worker` no tiene `SELECT`;
  `unique_violation` de la llave = exito). Lo envia el reconciliador de `case-service`.
- Todo tiempo sale del reloj inyectado, no de `now()` de la base.
- Clientes: `ScoringClient` vive aqui (no en `governance_client`) porque solo lo usa la evaluacion; es el cliente de F15.
"""

import asyncio
import json
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from random import Random
from typing import Any, ClassVar, Final

from psycopg import errors
from psycopg.types.json import Jsonb
from vectra_common import deps
from vectra_common import logging as vlog
from vectra_common.errors import VectraError
from vectra_contracts.catalog import CaseState, FailClosedCause, LocalCause, LogEvent
from vectra_contracts.labels import derive, derive_monitoring_labels
from vectra_contracts.models.api import PolicyInputs, ScoringRequest
from vectra_contracts.models.application import ApplicationIn
from vectra_contracts.models.explanation import FailClosed
from vectra_contracts.models.features import FeatureSpec
from vectra_contracts.models.registry import FailClosedPayload
from vectra_contracts.outcome import Recommendation, RecommendResult

from vectra_case import backoff, metrics
from vectra_case.case_fsm import CaseEvent, Rechazo, transition
from vectra_case.config import (
    BREAKER_FAILURE_RATIO,
    BREAKER_HALF_OPEN_AFTER,
    BREAKER_WINDOW_CALLS,
    BREAKER_WINDOW_SECONDS,
    MAX_ATTEMPTS,
    SCORING_POOL,
    SCORING_TIMEOUT,
)
from vectra_case.db import Conn, Database
from vectra_case.evidence import entry_json
from vectra_case.governance_client import ServingConfigClient, ServingConfigInvalid

Clock = Callable[[], datetime]
OK = 200
CLIENT_ERROR = 400  # 4xx: defecto o configuracion (BR-U8-08); un 401 repetido tambien llega aqui
SERVER_ERROR = 500
IN_FLIGHT: Final = ("en_evaluacion", "en_sincronizacion")
# Cada `UPDATE` sobre `cases` lleva la guarda de BR-U8-08 y fija `updated_at` (P-4 de U08-T03). La guarda identifica **la toma**: el
# trabajo vivo del caso lleva el `locked_until` que fijo esa toma (los dos ultimos parametros); `attempts` solo la acompana, porque vuelve a 0
# al congelar y con el `retry` del CRO y un numero igual no prueba que sea la misma toma. parametro `NULL` = sin comprobar (la propia toma, que ya
# tiene el trabajo bloqueado).
_READY: Final = (
    "UPDATE cases SET state = %s, recommendation = %s::jsonb, recommendation_entry_id = %s, updated_at = %s "
    "WHERE case_id = %s AND state IN ('en_evaluacion', 'en_sincronizacion') AND attempts = %s "
    "AND (%s::timestamptz IS NULL OR EXISTS (SELECT 1 FROM evaluation_jobs j WHERE j.case_id = cases.case_id "
    "AND j.locked_until = %s::timestamptz))"
)
_FROZEN: Final = (
    "UPDATE cases SET state = %s, attempts = 0, last_cause = %s, ever_degraded = true, updated_at = %s "
    "WHERE case_id = %s AND state IN ('en_evaluacion', 'en_sincronizacion') AND attempts = %s "
    "AND (%s::timestamptz IS NULL OR EXISTS (SELECT 1 FROM evaluation_jobs j WHERE j.case_id = cases.case_id "
    "AND j.locked_until = %s::timestamptz))"
)
_RETRY: Final = (
    "UPDATE cases SET state = %s, last_cause = %s, ever_degraded = true, updated_at = %s "
    "WHERE case_id = %s AND state IN ('en_evaluacion', 'en_sincronizacion') AND attempts = %s "
    "AND (%s::timestamptz IS NULL OR EXISTS (SELECT 1 FROM evaluation_jobs j WHERE j.case_id = cases.case_id "
    "AND j.locked_until = %s::timestamptz))"
)
_ESCALATE: Final = (
    "UPDATE cases SET state = %s, escalation_count = escalation_count + 1, last_cause = %s, ever_degraded = true, updated_at = %s "
    "WHERE case_id = %s AND state IN ('en_evaluacion', 'en_sincronizacion') AND attempts = %s "
    "AND (%s::timestamptz IS NULL OR EXISTS (SELECT 1 FROM evaluation_jobs j WHERE j.case_id = cases.case_id "
    "AND j.locked_until = %s::timestamptz))"
    " RETURNING escalation_count"
)
ACTOR: Final = {"kind": "service", "id": "case-worker"}


def utc_now() -> datetime:
    return datetime.now(UTC)


# --- La toma ------------------------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Taken:
    """Lo que la toma entrega al intento: el numero **nuevo** de intento y la fila del caso (leida en la misma transaccion corta)."""

    case_id: uuid.UUID
    attempt: int
    leased_until: datetime  # el `locked_until` que fijo esta toma: la identifica (BR-U8-08)
    state: CaseState
    created_at: datetime
    ever_degraded: bool
    application: Mapping[str, Any]  # `cases.application`: sin el grupo de identificacion, con `sex` y estrato
    identifiers: (
        Mapping[str, Any] | None
    )  # `case_identifiers` (el worker no los envia: solo `derive` los lee)


# --- Cliente de scoring (F15) -------------------------------------------------------------------------------------------------


class ScoringRejected(Exception):  # noqa: N818
    """4xx de scoring tras el reintento por 401 que ya hace `deps.call`: defecto o configuracion, no se reintenta (BR-U8-08)."""


class ScoringUnreachable(Exception):  # noqa: N818
    """Timeout, conexion, circuito abierto, 5xx o una respuesta que no es un `RecommendResult` (reintentable)."""


class ScoringClient:
    """`POST /v1/recommendations`: 16 conexiones, 7 s, el breaker de NFR-U8-31 y el token `case:recommend` (P-U8-02)."""

    def __init__(
        self,
        base_url: str,
        token_source: deps.TokenSource | None,
        *,
        transport: Any = None,
        timeout: float = SCORING_TIMEOUT,
    ) -> None:
        self._timeout = timeout
        self._client = deps.DependencyClient(
            "scoring",
            base_url,
            deps.BreakerConfig(
                open_for=BREAKER_HALF_OPEN_AFTER,
                window_size=BREAKER_WINDOW_CALLS,
                failure_ratio=BREAKER_FAILURE_RATIO,
                window_seconds=BREAKER_WINDOW_SECONDS,
            ),
            SCORING_POOL,
            transport=transport,
            token_source=token_source,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def recommend(self, request: ScoringRequest) -> Recommendation | FailClosed:
        content = request.model_dump_json().encode()
        try:
            # El tope duro cubre las dos llamadas del reintento por 401 (WORKER_WORST_CASE cuenta scoring dos veces).
            async with asyncio.timeout(2 * self._timeout):
                response = await deps.call(
                    self._client,
                    "POST",
                    "/v1/recommendations",
                    timeout=self._timeout,
                    headers={"content-type": "application/json"},
                    content=content,
                )
        except (VectraError, TimeoutError) as exc:
            raise ScoringUnreachable from exc
        if response.status_code >= SERVER_ERROR:
            raise ScoringUnreachable
        if response.status_code >= CLIENT_ERROR:
            raise ScoringRejected
        if response.status_code != OK:
            raise ScoringUnreachable
        try:
            return RecommendResult.from_wire(response.content)
        except ValueError as exc:  # `ValidationError` es un `ValueError`
            raise ScoringUnreachable from exc


# --- Construccion del ScoringRequest (sin E/S; PBT-U8-05) ---------------------------------------------------------------------


def build_request(
    taken: Taken, spec: FeatureSpec, model_version_id: str, evaluated_at: datetime
) -> ScoringRequest:
    """BR-U8-05, 06. `derive` necesita la solicitud completa (`cases.application` mas `case_identifiers`); el `ScoringRequest` no lleva
    ningun identificador, `free_text` ni `test_scenario_id`: solo features, etiquetas de monitoreo, entradas de la politica y el intento."""
    application = ApplicationIn.model_validate_json(
        json.dumps({**taken.application, **(taken.identifiers or {})})
    )
    evaluated_on = evaluated_at.date()
    return ScoringRequest(
        case_id=taken.case_id,
        features=derive(application, evaluated_on, spec),
        monitoring_labels=derive_monitoring_labels(application, evaluated_on),
        policy_inputs=PolicyInputs(
            property_value=application.property_value,
            proposed_rate_ea=application.proposed_rate_ea,
            channel=application.channel,
        ),
        attempt=taken.attempt,
        model_version_id=model_version_id,
        received_at=taken.created_at,
        first_evaluation=not taken.ever_degraded and taken.attempt == 1,
    )


# --- Resultado de un intento (BR-U8-08) ---------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Success:
    result: ClassVar[str] = "recommendation"  # etiqueta `result` de `vectra_case_attempts_total`
    recommendation: Recommendation


@dataclass(frozen=True)
class Frozen:
    """`FailClosed(model_frozen)`: el caso espera al barrido de `case-service` (BR-U8-10)."""

    result: ClassVar[str] = "model_frozen"


@dataclass(frozen=True)
class Failure:
    """Reintentable (`escalate_now = False`) o 4xx no reintentable (`scoring_rejected`: escala de inmediato)."""

    result: str  # etiqueta `result` de `vectra_case_attempts_total`
    cause: FailClosedCause | None = None
    local_cause: LocalCause | None = None
    escalate_now: bool = False

    @property
    def last_cause(self) -> str:
        return self.cause.value if self.cause is not None else str(self.local_cause)


Outcome = Success | Frozen | Failure
CONFIG_UNAVAILABLE: Final = Failure(
    "serving_config_unavailable", local_cause=LocalCause.SERVING_CONFIG_UNAVAILABLE
)
UNREACHABLE: Final = Failure("scoring_unreachable", local_cause=LocalCause.SCORING_UNREACHABLE)
REJECTED: Final = Failure("scoring_rejected", local_cause=LocalCause.SCORING_REJECTED, escalate_now=True)


def _target(state: CaseState, event: CaseEvent) -> CaseState:
    target = transition(state, event)
    assert not isinstance(target, Rechazo), f"{state} + {event} fuera de BR-U8-12"
    return target


# --- Escalamiento (BR-U8-09) --------------------------------------------------------------------------------------------------


def fail_closed_key(case_id: uuid.UUID, cycle: int) -> uuid.UUID:
    """`UUIDv5(case_id, "fail_closed", ciclo)`: `ciclo` es `escalation_count` ya incrementado (1, 2, ... tras cada `retry` del CRO)."""
    return uuid.uuid5(case_id, f"fail_closed:{cycle}")


async def escalate(
    conn: Conn,
    *,
    case_id: uuid.UUID,
    state: CaseState,
    attempt: int,
    leased_until: datetime | None,
    now: datetime,
    cause: FailClosedCause | None,
    local_cause: LocalCause | None,
    event: CaseEvent,
) -> bool:
    """`no_disponible` + `fail_closed` en la **misma** transaccion que el llamador. `False` si la guarda no deja cambiar el caso."""
    last_cause = cause.value if cause is not None else str(local_cause)
    cur = await conn.execute(
        _ESCALATE,
        (_target(state, event).value, last_cause, now, case_id, attempt, leased_until, leased_until),
    )
    row = await cur.fetchone()
    if row is None:
        return False
    await conn.execute("DELETE FROM evaluation_jobs WHERE case_id = %s", (case_id,))
    retryable = (
        cause is not FailClosedCause.MODEL_FROZEN
        if cause is not None
        else local_cause is not LocalCause.SCORING_REJECTED
    )
    payload = FailClosedPayload(
        cause=cause, local_cause=local_cause, retryable=retryable, attempt=attempt, escalated_at=now
    )
    key = fail_closed_key(case_id, row["escalation_count"])
    entry = entry_json(
        entry_type="fail_closed",
        case_id=case_id,
        model_version_id=None,
        policy_version_id=None,
        actor=dict(ACTOR),
        occurred_at=now,
        correlation_id=vlog.correlation_id_var.get() or uuid.uuid4().hex,
        idempotency_key=key,
        payload=json.loads(payload.model_dump_json(exclude_none=True)),
    )
    try:
        async with (
            conn.transaction()
        ):  # SAVEPOINT: un `unique_violation` no aborta la transaccion del cambio de estado
            await conn.execute(
                "INSERT INTO evidence_outbox (evidence_id, case_id, entry_type, idempotency_key, payload) "
                "VALUES (%s, %s, 'fail_closed', %s, %s)",
                (uuid.uuid4(), case_id, key, Jsonb(entry)),
            )
    except errors.UniqueViolation:
        pass  # la misma llave es el mismo escalamiento (commit incierto): exito
    return True


# --- El intento ---------------------------------------------------------------------------------------------------------------


class Evaluator:
    def __init__(
        self,
        db: Database,
        governance: ServingConfigClient,
        scoring: ScoringClient,
        clock: Clock = utc_now,
        rng: Random | None = None,
    ) -> None:
        self.db = db
        self.governance = governance
        self.scoring = scoring
        self.clock = clock
        self.rng = rng or Random()  # noqa: S311 (jitter del backoff, no criptografia)

    async def run(self, taken: Taken) -> bool:
        """Un intento completo y la aplicacion de su resultado. `False` si el resultado se descarto."""
        outcome = await self.attempt(taken)
        return await self.apply(taken, outcome)

    async def attempt(self, taken: Taken) -> Outcome:
        try:
            config = await self.governance.get()
            spec = await self.governance.feature_spec(config.model_version_id)
            request = build_request(taken, spec, config.model_version_id, self.clock())
        except (
            VectraError,
            ServingConfigInvalid,
            ValueError,
        ):  # `ValidationError` y los `ValueError` de `derive`
            return CONFIG_UNAVAILABLE  # sin llamar a scoring: falla cerrado
        try:
            result = await self.scoring.recommend(request)
        except ScoringRejected:
            return REJECTED
        except ScoringUnreachable:
            return UNREACHABLE
        if isinstance(result, Recommendation):
            return Success(result)
        if result.cause is FailClosedCause.MODEL_FROZEN:
            return Frozen()
        return Failure("failclosed", cause=result.cause)

    async def apply(self, taken: Taken, outcome: Outcome) -> bool:
        now = self.clock()
        async with self.db.tx() as conn:
            applied = await self._apply(conn, taken, outcome, now)
        if not applied:
            vlog.log_event(
                LogEvent.EVALUATION_RESULT_DISCARDED, case_id=str(taken.case_id), attempt=taken.attempt
            )
            return False
        metrics.CASE_ATTEMPTS.labels(result=outcome.result, attempt=str(taken.attempt)).inc()
        if isinstance(outcome, Success) and taken.attempt == 1 and not taken.ever_degraded:
            metrics.TIME_TO_READY.observe(max((now - taken.created_at).total_seconds(), 0.0))
        return True

    async def _apply(self, conn: Conn, taken: Taken, outcome: Outcome, now: datetime) -> bool:
        case_id, state = taken.case_id, taken.state
        if isinstance(outcome, Success):
            cur = await conn.execute(
                _READY,
                (
                    _target(state, CaseEvent.RECOMMENDATION).value,
                    outcome.recommendation.model_dump_json(),
                    outcome.recommendation.registry_entry_id,
                    now,
                    case_id,
                    taken.attempt,
                    taken.leased_until,
                    taken.leased_until,
                ),
            )
        elif isinstance(outcome, Frozen):
            cur = await conn.execute(
                _FROZEN,
                (
                    _target(state, CaseEvent.MODEL_FROZEN).value,
                    FailClosedCause.MODEL_FROZEN.value,
                    now,
                    case_id,
                    taken.attempt,
                    taken.leased_until,
                    taken.leased_until,
                ),
            )
        elif outcome.escalate_now or taken.attempt >= MAX_ATTEMPTS:
            event = CaseEvent.SCORING_REJECTED if outcome.escalate_now else CaseEvent.ATTEMPT_6_FAILED
            return await escalate(
                conn,
                case_id=case_id,
                state=state,
                attempt=taken.attempt,
                leased_until=taken.leased_until,
                now=now,
                cause=outcome.cause,
                local_cause=outcome.local_cause,
                event=event,
            )
        else:
            cur = await conn.execute(
                _RETRY,
                (
                    _target(state, CaseEvent.RETRYABLE_FAILURE).value,
                    outcome.last_cause,
                    now,
                    case_id,
                    taken.attempt,
                    taken.leased_until,
                    taken.leased_until,
                ),
            )
            if cur.rowcount != 1:
                return False
            # Reprogramar: `run_at` y `locked_until = NULL` (el numero de intento sube en la toma siguiente, BR-U8-07).
            await conn.execute(
                "UPDATE evaluation_jobs SET run_at = %s, locked_until = NULL WHERE case_id = %s",
                (now + timedelta(seconds=backoff.schedule(taken.attempt, self.rng)), case_id),
            )
            return True
        if cur.rowcount != 1:
            return False
        await conn.execute(
            "DELETE FROM evaluation_jobs WHERE case_id = %s", (case_id,)
        )  # el trabajo se borra al terminar
        return True
