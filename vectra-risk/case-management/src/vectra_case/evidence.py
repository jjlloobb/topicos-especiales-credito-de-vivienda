"""Evidencia en dos fases, consulta de la explicacion y reconciliador (Paso 10; BR-U8-09, 15..19; P-U8-02, 04, 09).

- Decision (BR-U8-15..18): se valida (`validate_decision`), se inserta `decisions` + `evidence_outbox` (llave `UUIDv5(case_id,
  "human_decision")`) en una transaccion y se envia al registro; con el ack, una segunda transaccion confirma evidencia, decision y
  caso `decidido`. Sin ack: 503 y la decision queda `pendiente_registro`.
- Conflicto tras un abandono: se reenvia la abandonada (misma llave) y, con su ack, se intercambian los estados (la nueva primero:
  los indices unicos parciales admiten una sola fila viva) y se responde 409 `decision_already_recorded`.
- Consulta (BR-U8-19): primera vez por (caso, usuario) con llave `UUIDv5(case_id, user_id)`; siguientes -> sin entrada nueva.
- Reconciliador (P-U8-04): cada 1 s, lotes de 100 con `SKIP LOCKED`, <= 4 envios en vuelo. Reclama con un arrendamiento
  (`next_attempt_at`), asi dos replicas no reintentan la misma evidencia en un ciclo. Reenvia con la misma llave, el mismo payload y
  el mismo `correlation_id`, y un `occurred_at` nuevo.
- `outbox.payload` es la entrada completa del registro (`RegistryEntryIn` en JSON); `case-worker` (U08-T04) inserta `fail_closed` igual.
- Todos los tiempos salen del reloj inyectado, no de `now()` de la base, para poder simular horas y dias.
"""

import asyncio
import json
import time
import uuid
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from random import Random
from typing import Any, Final, Literal

from psycopg import errors
from psycopg.types.json import Jsonb
from vectra_common import deps
from vectra_common import logging as vlog
from vectra_common.errors import (
    ConflictState,
    DependencyUnavailable,
    NotFound,
    Unauthenticated,
    ValidationFailed,
    VectraError,
)
from vectra_contracts.catalog import CaseState, ProblemCode, ProblemReason
from vectra_contracts.models.api import DecisionIn, DecisionRef, Principal
from vectra_contracts.models.explanation import RegistryAck
from vectra_contracts.models.registry import RegistryEntryIn
from vectra_contracts.outcome import Recommendation, read_wire

from vectra_case import metrics
from vectra_case.config import (
    BATCH_SIZE,
    BREAKER_FAILURE_RATIO,
    BREAKER_HALF_OPEN_AFTER,
    BREAKER_WINDOW_CALLS,
    BREAKER_WINDOW_SECONDS,
    EVIDENCE_ABANDON_AFTER,
    RECONCILER_BACKOFF_MAX,
    RECONCILER_BACKOFF_MIN,
    RECONCILER_CONCURRENCY,
    REGISTRY_POOL,
    REGISTRY_TIMEOUT,
)
from vectra_case.db import Database
from vectra_case.decision import validate_decision

Clock = Callable[[], datetime]
Row = dict[str, Any]
LEASE: Final = timedelta(seconds=30)
RECONCILER_INTERVAL: Final[float] = 1.0
BACKOFF_JITTER: Final[float] = 0.2


def _utc_now() -> datetime:
    return datetime.now(UTC)


def backoff_seconds(attempts: int, rng: Random) -> float:
    """1 s * 2^(n-1) hasta 5 min, con jitter de +-20 % (sin pasar de 5 min)."""
    nominal = min(RECONCILER_BACKOFF_MAX, RECONCILER_BACKOFF_MIN * 2.0 ** max(attempts - 1, 0))
    return min(RECONCILER_BACKOFF_MAX, nominal * rng.uniform(1 - BACKOFF_JITTER, 1 + BACKOFF_JITTER))


@dataclass(frozen=True)
class AppendResult:
    kind: Literal["ack", "conflict", "rejected", "unavailable"]
    ack: RegistryAck | None = None


class RegistryClient:
    """`POST /v1/entries` con scope `registry:append:case`; un pool de 10 y un breaker propios (P-U8-02)."""

    def __init__(
        self,
        base_url: str,
        token_source: deps.TokenSource | None,
        *,
        transport: Any = None,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self._client = deps.DependencyClient(
            "decision-registry",
            base_url,
            deps.BreakerConfig(
                open_for=BREAKER_HALF_OPEN_AFTER,
                window_size=BREAKER_WINDOW_CALLS,
                failure_ratio=BREAKER_FAILURE_RATIO,
                window_seconds=BREAKER_WINDOW_SECONDS,
            ),
            REGISTRY_POOL,
            clock=monotonic,
            transport=transport,
            token_source=token_source,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def append(self, entry: dict[str, Any]) -> AppendResult:
        content = json.dumps(entry, ensure_ascii=False).encode("utf-8")
        try:
            response = await deps.call(
                self._client,
                "POST",
                "/v1/entries",
                timeout=REGISTRY_TIMEOUT,
                headers={"content-type": "application/json"},
                content=content,
            )
        except VectraError:
            return AppendResult("unavailable")
        if response.status_code in (200, 201):
            try:
                return AppendResult("ack", RegistryAck.model_validate_json(response.content))
            except ValueError:
                return AppendResult("unavailable")
        if response.status_code == 409:  # noqa: PLR2004
            return AppendResult("conflict")
        if response.status_code == 422:  # noqa: PLR2004
            return AppendResult("rejected")
        return AppendResult("unavailable")


def entry_json(
    *,
    entry_type: str,
    case_id: uuid.UUID,
    model_version_id: str | None,
    policy_version_id: str | None,
    actor: dict[str, Any],
    occurred_at: datetime,
    correlation_id: str,
    idempotency_key: uuid.UUID,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Arma y valida (U0) la entrada del registro; devuelve su JSON."""
    data = {
        "entry_type": entry_type,
        "case_id": str(case_id),
        "model_version_id": model_version_id,
        "policy_version_id": policy_version_id,
        "actor": actor,
        "occurred_at": occurred_at.isoformat(),
        "correlation_id": correlation_id,
        "idempotency_key": str(idempotency_key),
        "payload": payload,
    }
    RegistryEntryIn.model_validate_json(json.dumps(data, ensure_ascii=False))
    return data


def _correlation(explicit: str | None) -> str:
    return explicit or vlog.correlation_id_var.get() or uuid.uuid4().hex


def _actor(principal: Principal, role: str) -> dict[str, Any]:
    if principal.acr is None or principal.auth_time is None:
        raise Unauthenticated()  # la evidencia necesita el nivel de autenticacion del token (US-108)
    return {
        "kind": "user",
        "id": principal.subject,
        "role": role,
        "acr": principal.acr,
        "auth_time": principal.auth_time.isoformat(),
    }


class Evidence:
    def __init__(
        self, db: Database, registry: RegistryClient, clock: Clock = _utc_now, rng: Random | None = None
    ) -> None:
        self.db = db
        self.registry = registry
        self.clock = clock
        self.rng = rng or Random()  # noqa: S311

    # ------------------------------------------------------------------ envio
    async def deliver(self, row: Row) -> AppendResult:
        """Un intento: misma llave, payload y `correlation_id`; `occurred_at` nuevo (BR-U3-05)."""
        entry = {
            **row["payload"],
            "entry_type": row["entry_type"],
            "case_id": str(row["case_id"]),
            "idempotency_key": str(row["idempotency_key"]),
            "occurred_at": self.clock().isoformat(),
        }
        return await self.registry.append(entry)

    async def _fail(self, row: Row) -> None:
        async with self.db.tx() as conn:
            cur = await conn.execute(
                "SELECT attempts FROM evidence_outbox WHERE evidence_id = %s", (row["evidence_id"],)
            )
            current = await cur.fetchone()
            attempts = (current["attempts"] if current else 0) + 1
            nxt = self.clock() + timedelta(seconds=backoff_seconds(attempts, self.rng))
            await conn.execute(
                "UPDATE evidence_outbox SET attempts = %s, next_attempt_at = %s "
                "WHERE evidence_id = %s AND state = 'pendiente_registro'",
                (attempts, nxt, row["evidence_id"]),
            )

    async def _confirm(self, row: Row, ack: RegistryAck) -> bool:
        """Con el ack: evidencia (y, si es decision, decision y caso `decidido`) en una transaccion."""
        async with self.db.tx() as conn:
            cur = await conn.execute(
                "UPDATE evidence_outbox SET state = 'confirmada', registry_entry_id = %s "
                "WHERE evidence_id = %s AND state = 'pendiente_registro'",
                (ack.registry_entry_id, row["evidence_id"]),
            )
            if cur.rowcount == 0:
                return False
            if row["entry_type"] == "human_decision":
                await conn.execute(
                    "UPDATE decisions SET state = 'confirmada' WHERE evidence_id = %s AND state = 'pendiente_registro'",
                    (row["evidence_id"],),
                )
                await conn.execute(
                    "UPDATE cases SET state = 'decidido', updated_at = %s WHERE case_id = %s AND state = 'listo'",
                    (self.clock(), row["case_id"]),
                )
        return True

    async def _discard(self, row: Row) -> None:
        async with self.db.tx() as conn:
            cur = await conn.execute(
                "UPDATE evidence_outbox SET state = 'descartada' WHERE evidence_id = %s AND state = 'pendiente_registro'",
                (row["evidence_id"],),
            )
        if cur.rowcount:
            metrics.EVIDENCE_DISCARDED.inc()

    async def _resolve_conflict(self, new: Row) -> bool:
        """BR-U8-18: reenvia la abandonada que el registro si escribio. `True` si hubo intercambio de estados."""
        async with self.db.tx() as conn:
            cur = await conn.execute(
                "SELECT * FROM evidence_outbox WHERE case_id = %s AND entry_type = 'human_decision' "
                "AND state = 'abandonada' AND evidence_id <> %s ORDER BY created_at DESC",
                (new["case_id"], new["evidence_id"]),
            )
            abandoned = await cur.fetchall()
        for old in abandoned:
            result = await self.deliver(old)
            if result.kind == "conflict":
                continue
            if result.kind != "ack" or result.ack is None:
                return False
            async with self.db.tx() as conn:
                # Orden: la nueva primero (indices unicos parciales sobre filas vivas, BR-U8-18).
                await conn.execute(
                    "UPDATE evidence_outbox SET state = 'abandonada' WHERE evidence_id = %s",
                    (new["evidence_id"],),
                )
                await conn.execute(
                    "UPDATE decisions SET state = 'abandonada' WHERE evidence_id = %s", (new["evidence_id"],)
                )
                await conn.execute(
                    "UPDATE evidence_outbox SET state = 'confirmada', registry_entry_id = %s WHERE evidence_id = %s",
                    (result.ack.registry_entry_id, old["evidence_id"]),
                )
                await conn.execute(
                    "UPDATE decisions SET state = 'confirmada' WHERE evidence_id = %s", (old["evidence_id"],)
                )
                await conn.execute(
                    "UPDATE cases SET state = 'decidido', updated_at = %s WHERE case_id = %s AND state = 'listo'",
                    (self.clock(), new["case_id"]),
                )
            return True
        return False

    async def settle(self, row: Row) -> tuple[AppendResult, bool]:
        """Envia una evidencia y aplica el resultado. Devuelve (resultado, hubo_conflicto_resuelto)."""
        result = await self.deliver(row)
        if result.kind == "ack" and result.ack is not None:
            await self._confirm(row, result.ack)
        elif result.kind == "conflict" and row["entry_type"] == "human_decision":
            if await self._resolve_conflict(row):
                return result, True
            await self._fail(row)
        elif result.kind == "rejected" and row["entry_type"] == "explanation_view":
            await self._discard(row)
        else:
            await self._fail(row)
        return result, False

    # --------------------------------------------------------------- decision
    async def record_decision(
        self, principal: Principal, case_id: uuid.UUID, body: DecisionIn, correlation_id: str | None = None
    ) -> DecisionRef:
        actor = _actor(principal, "analista")
        now = self.clock()
        async with self.db.tx() as conn:
            cur = await conn.execute(
                "SELECT state, recommendation::text AS rec, recommendation_entry_id FROM cases "
                "WHERE case_id = %s FOR UPDATE",
                (case_id,),
            )
            case = await cur.fetchone()
            if case is None:
                raise NotFound()
            if case["state"] != CaseState.LISTO or case["rec"] is None:
                raise ConflictState()
            cur = await conn.execute(
                "SELECT 1 FROM decisions WHERE case_id = %s AND state IN ('pendiente_registro', 'confirmada')",
                (case_id,),
            )
            if await cur.fetchone() is not None:
                raise ConflictState()
            rec = read_wire(Recommendation, case["rec"])
            rejected = validate_decision(body, rec)
            if rejected is not None:
                # P-3 (a): solo el `code`; la razon interna no sale a la red ni a los logs.
                raise ValidationFailed() if rejected.code is ProblemCode.VALIDATION_ERROR else ConflictState()
            cur = await conn.execute(
                "SELECT 1 FROM explanation_views v JOIN evidence_outbox e ON e.evidence_id = v.evidence_id "
                "WHERE v.case_id = %s AND v.user_id = %s AND v.first_viewed_at < %s AND e.state = 'confirmada'",
                (case_id, principal.subject, now),
            )
            viewed = await cur.fetchone() is not None
            key = uuid.uuid5(case_id, "human_decision")
            entry = entry_json(
                entry_type="human_decision",
                case_id=case_id,
                model_version_id=rec.model_version_id,
                policy_version_id=rec.policy_version_id,
                actor=actor,
                occurred_at=now,
                correlation_id=_correlation(correlation_id),
                idempotency_key=key,
                payload={
                    **body.model_dump(mode="json"),
                    "explanation_viewed_before": viewed,
                    "decided_at": now.isoformat(),
                    "recommendation_entry_id": case["recommendation_entry_id"],
                },
            )
            evidence_id = uuid.uuid4()
            try:
                cur = await conn.execute(
                    "INSERT INTO evidence_outbox (evidence_id, case_id, entry_type, idempotency_key, payload, "
                    "created_at, next_attempt_at) VALUES (%s, %s, 'human_decision', %s, %s, %s, %s) RETURNING *",
                    (evidence_id, case_id, key, Jsonb(entry), now, now),
                )
                row = await cur.fetchone()
                await conn.execute(
                    "INSERT INTO decisions (case_id, decision, final_outcome, used_factors, justification, "
                    "explanation_viewed_before, decided_by, decided_at, evidence_id) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (
                        case_id,
                        body.decision.value,
                        body.final_outcome.value,
                        Jsonb(body.used_factors),
                        body.justification,
                        viewed,
                        Jsonb({"kind": "user", "id": principal.subject, "role": "analista"}),
                        now,
                        evidence_id,
                    ),
                )
            except errors.UniqueViolation as exc:
                raise ConflictState() from exc
        assert row is not None  # noqa: S101
        result, swapped = await self.settle(row)
        if swapped:
            raise ConflictState(ProblemReason.DECISION_ALREADY_RECORDED)
        if result.kind != "ack" or result.ack is None:
            raise DependencyUnavailable()
        return DecisionRef(
            case_id=case_id,
            registry_entry_id=result.ack.registry_entry_id,
            recorded_at=result.ack.recorded_at,
        )

    # ------------------------------------------------------------- consulta
    async def record_view(
        self, principal: Principal, case_id: uuid.UUID, correlation_id: str | None = None
    ) -> None:
        actor = _actor(principal, "analista")
        now = self.clock()
        to_send: Row | None = None
        async with self.db.tx() as conn:
            await conn.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                (f"view:{case_id}:{principal.subject}",),
            )
            cur = await conn.execute(
                "SELECT state, recommendation_entry_id, recommendation->>'model_version_id' AS mv, "
                "recommendation->>'policy_version_id' AS pv FROM cases WHERE case_id = %s",
                (case_id,),
            )
            case = await cur.fetchone()
            if case is None:
                raise NotFound()
            if case["state"] not in (CaseState.LISTO, CaseState.DECIDIDO):
                raise ConflictState()
            cur = await conn.execute(
                "SELECT e.* FROM explanation_views v JOIN evidence_outbox e ON e.evidence_id = v.evidence_id "
                "WHERE v.case_id = %s AND v.user_id = %s",
                (case_id, principal.subject),
            )
            existing = await cur.fetchone()
            if existing is not None:
                if existing["state"] != "abandonada":
                    return
                # Recuperacion (BR-U8-19): el payload original, la misma llave y un plazo de 24 h nuevo.
                cur = await conn.execute(
                    "UPDATE evidence_outbox SET state = 'pendiente_registro', attempts = 0, created_at = %s, "
                    "next_attempt_at = %s WHERE evidence_id = %s RETURNING *",
                    (now, now, existing["evidence_id"]),
                )
                to_send = await cur.fetchone()
            else:
                key = uuid.uuid5(case_id, principal.subject)
                entry = entry_json(
                    entry_type="explanation_view",
                    case_id=case_id,
                    model_version_id=case["mv"],
                    policy_version_id=case["pv"],
                    actor=actor,
                    occurred_at=now,
                    correlation_id=_correlation(correlation_id),
                    idempotency_key=key,
                    payload={
                        "viewed_at": now.isoformat(),
                        "recommendation_entry_id": case["recommendation_entry_id"],
                    },
                )
                evidence_id = uuid.uuid4()
                cur = await conn.execute(
                    "INSERT INTO evidence_outbox (evidence_id, case_id, entry_type, idempotency_key, payload, "
                    "created_at, next_attempt_at) VALUES (%s, %s, 'explanation_view', %s, %s, %s, %s) RETURNING *",
                    (evidence_id, case_id, key, Jsonb(entry), now, now),
                )
                to_send = await cur.fetchone()
                await conn.execute(
                    "INSERT INTO explanation_views (case_id, user_id, first_viewed_at, evidence_id) "
                    "VALUES (%s, %s, %s, %s)",
                    (case_id, principal.subject, now, evidence_id),
                )
        if to_send is not None:
            # Un intento inmediato; si falla queda pendiente y sigue el reconciliador (siempre 204).
            await self.settle(to_send)


class Reconciler:
    """Reconciliador de evidencia (P-U8-04): `run_once` es un ciclo; `run_forever` repite cada 1 s hasta `stop()`."""

    def __init__(self, evidence: Evidence) -> None:
        self.evidence = evidence
        self._stop = asyncio.Event()
        self.in_flight = 0
        self.max_in_flight = 0

    def stop(self) -> None:
        self._stop.set()

    async def abandon_overdue(self) -> int:
        cutoff = self.evidence.clock() - timedelta(seconds=EVIDENCE_ABANDON_AFTER)
        async with self.evidence.db.tx() as conn:
            cur = await conn.execute(
                "UPDATE evidence_outbox SET state = 'abandonada' WHERE state = 'pendiente_registro' "
                "AND created_at <= %s RETURNING evidence_id, entry_type",
                (cutoff,),
            )
            rows = await cur.fetchall()
            if rows:
                await conn.execute(
                    "UPDATE decisions SET state = 'abandonada' WHERE state = 'pendiente_registro' "
                    "AND evidence_id = ANY(%s)",
                    ([r["evidence_id"] for r in rows],),
                )
        for r in rows:
            metrics.EVIDENCE_ABANDONED.labels(entry_type=r["entry_type"]).inc()
        return len(rows)

    async def _claim(self) -> list[Row]:
        now = self.evidence.clock()
        async with self.evidence.db.tx() as conn:
            cur = await conn.execute(
                "SELECT evidence_id FROM evidence_outbox WHERE state = 'pendiente_registro' AND next_attempt_at <= %s "
                "ORDER BY next_attempt_at LIMIT %s FOR UPDATE SKIP LOCKED",
                (now, BATCH_SIZE),
            )
            ids = [r["evidence_id"] for r in await cur.fetchall()]
            if not ids:
                return []
            cur = await conn.execute(
                "UPDATE evidence_outbox SET next_attempt_at = %s WHERE evidence_id = ANY(%s) RETURNING *",
                (now + LEASE, ids),
            )
            return await cur.fetchall()

    async def _one(self, sem: asyncio.Semaphore, row: Row) -> None:
        async with sem:
            self.in_flight += 1
            self.max_in_flight = max(self.max_in_flight, self.in_flight)
            try:
                with suppress(
                    Exception
                ):  # un envio fallido no detiene el lote; el arrendamiento lo reintenta
                    await self.evidence.settle(row)
            finally:
                self.in_flight -= 1

    async def run_once(self) -> int:
        """Un ciclo: abandona lo vencido, reclama un lote y lo envia con <= 4 en vuelo. El lote termina aunque llegue `stop()`."""
        if self._stop.is_set():
            return 0
        await self.abandon_overdue()
        rows = await self._claim()
        sem = asyncio.Semaphore(RECONCILER_CONCURRENCY)
        await asyncio.gather(*(self._one(sem, r) for r in rows))
        return len(rows)

    async def run_forever(self) -> None:
        while not self._stop.is_set():
            with suppress(Exception):  # la base caida no mata el bucle
                await self.run_once()
            try:
                await asyncio.wait_for(self._stop.wait(), RECONCILER_INTERVAL)
            except TimeoutError:
                pass
