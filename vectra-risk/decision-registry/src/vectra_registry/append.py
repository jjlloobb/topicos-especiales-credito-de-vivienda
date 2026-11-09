"""Append (Paso 7 del plan; BR-U3-03..07, 16; P-U3-02; NFR-U3-20; US-401, US-404).

Una escritura es: autorizacion (scope, tipo, forma del `fail_closed`, actor de gobierno) -> tamano -> transaccion con el
*advisory lock* -> busqueda de la llave (idempotencia, solo campos de negocio) -> para una llave nueva, ventana de `occurred_at`
y `check_business_time` -> cabeza -> `recorded_at` no decreciente -> `canonical` (JCS) -> `hash` -> `INSERT` -> `COMMIT` con
`synchronous_commit = remote_apply`. El ack sale **solo** despues del commit confirmado por el standby sincrono; sin el
(el commit se cancela por `statement_timeout`) la respuesta es 503 `dependency_unavailable` y el llamador reintenta con la
misma llave (el reintento resuelve el ack original, BR-U3-06).

La unicidad de `idempotency_key` no depende del nombre de ninguna restriccion: se detecta con la busqueda de la llave dentro
del lock (BR-U3-04, paso 0) y, si aun asi una escritura ajena al lock la gana, se repite esa busqueda una vez.
"""

import asyncio
import contextlib
import time
from collections.abc import Callable, Collection, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Final, cast
from uuid import UUID

import psycopg
import vectra_contracts
from psycopg import errors
from vectra_common.errors import (
    ConflictState,
    DependencyUnavailable,
    Forbidden,
    PayloadTooLarge,
    ValidationFailed,
)
from vectra_common.metrics import histogram
from vectra_contracts.catalog import EntryType, Scope
from vectra_contracts.models.api import InvalidParam
from vectra_contracts.models.explanation import RegistryAck
from vectra_contracts.models.registry import RegistryEntryIn
from vectra_contracts.validation import BUSINESS_TIME_FIELDS, check_business_time

from vectra_registry.chain import canonicalize, decode, link
from vectra_registry.locks import APPEND_LOCK
from vectra_registry.pools import Connection, Pools

#: BR-U3-07: `canonical` de hasta 64 KiB; por encima de 48 KiB la metrica cruza el umbral de la alerta `RegistryEntryLarge`.
MAX_CANONICAL = 64 * 1024
#: BR-U3-05: `occurred_at` se acepta si `|occurred_at - now| <= 5 min`.
WINDOW = timedelta(seconds=300)
#: P-U3-02: limites del append, sin reintento interno.
LOCK_TIMEOUT_MS = 1000
STATEMENT_TIMEOUT_MS = 2000
HANDLER_TIMEOUT = 2.5
#: Una cota inferior del tamano, antes de tomar el lock (el `seq` real tiene al menos un digito); la exacta se comprueba dentro del lock.
_SEQ_PLACEHOLDER = 0

ENTRY_SIZE = histogram(
    "vectra_registry_entry_size_bytes",
    "Tamano de canonical de las entradas escritas (BR-U3-07)",
    [],
    (1024, 4096, 16384, 32768, 49152, 57344, 65536),
)

#: BR-U3-03: los tipos que cada scope puede escribir. `genesis` y `checkpoint` solo los escribe el propio registro.
SCOPE_TYPES: Final[dict[Scope, frozenset[str]]] = {
    Scope.REGISTRY_APPEND_SCORING: frozenset({EntryType.RECOMMENDATION, EntryType.FAIL_CLOSED}),
    Scope.REGISTRY_APPEND_CASE: frozenset(
        {EntryType.HUMAN_DECISION, EntryType.EXPLANATION_VIEW, EntryType.FAIL_CLOSED}
    ),
    Scope.REGISTRY_APPEND_GOVERNANCE: frozenset(
        {
            EntryType.MODEL_EVENT,
            EntryType.POLICY_EVENT,
            EntryType.DATA_SOURCE_EVENT,
            EntryType.FREEZE,
            EntryType.FROZEN_RESOLUTION,
        }
    ),
}
#: BR-U3-16: las cinco entradas de gobierno (US-404).
GOVERNANCE_TYPES: Final = SCOPE_TYPES[Scope.REGISTRY_APPEND_GOVERNANCE]
#: Los campos de negocio de BR-U3-06; no entran `seq`, `recorded_at`, `occurred_at`, `correlation_id` ni `contract_version`.
BUSINESS_FIELDS: Final = (
    "entry_type",
    "idempotency_key",
    "actor",
    "case_id",
    "model_version_id",
    "policy_version_id",
    "payload",
)
#: BR-U3-16: los actores de servicio o de sistema que pueden escribir eventos de gobierno; el resto exige un usuario con rol.
FREEZE_ACTOR: Final = ("system", "bias-monitoring-job")
VALIDATION_JOB: Final = ("service", "model-validation-job")
GOVERNANCE_SYSTEM: Final = ("system", "governance-service")


def _utc_now() -> datetime:
    return datetime.now(UTC)


# --- Autorizacion (BR-U3-03, 16) ------------------------------------------------------------------------------------------


def scope_permits(scope: Scope, entry: RegistryEntryIn) -> bool:
    """BR-U3-03: el tipo es de ese scope y, en `fail_closed`, la forma del payload es la de ese scope (regla simetrica)."""
    if entry.entry_type not in SCOPE_TYPES.get(scope, frozenset()):
        return False
    if entry.entry_type == EntryType.FAIL_CLOSED:
        payload: Any = entry.payload
        if scope is Scope.REGISTRY_APPEND_SCORING:
            # Una entrada por intento (BR-U7-16): sin `local_cause` ni `escalated_at`.
            return bool(payload.local_cause is None and payload.escalated_at is None)
        return bool(payload.escalated_at is not None)  # el escalamiento de case (BR-U8-09)
    return True


def authorize(scopes: Collection[Scope], entry: RegistryEntryIn) -> None:
    """`403 forbidden` si ningun scope del llamador permite esa entrada (BR-U3-03). `genesis` y `checkpoint` nunca."""
    if not any(scope_permits(scope, entry) for scope in scopes):
        raise Forbidden()


def check_governance_actor(entry: RegistryEntryIn) -> None:
    """BR-U3-16: un evento de gobierno que provoca una persona lleva `actor` de usuario con rol; los de servicio o sistema son
    solo las excepciones del diseno (el CronJob de sesgo, el Job de validacion y `governance-service`)."""
    if entry.entry_type not in GOVERNANCE_TYPES:
        return
    actor = entry.actor
    if actor.kind == "user":
        if actor.role is None:
            raise ValidationFailed(invalid_params=[InvalidParam(name="actor.role", reason_code="role_required")])
        return
    payload: Any = entry.payload
    event = getattr(payload, "event", None)
    allowed: set[tuple[str, str]] = set()
    if entry.entry_type == EntryType.FREEZE:
        allowed.add(FREEZE_ACTOR)
    elif entry.entry_type == EntryType.MODEL_EVENT:
        if event in ("informe_validacion", "validacion_fallida"):
            allowed.add(VALIDATION_JOB)
        if event in ("validacion_fallida", "transicion_descartada"):
            allowed.add(GOVERNANCE_SYSTEM)
    if (actor.kind, actor.id) not in allowed:
        raise Forbidden()


# --- Tiempos (BR-U3-05) ---------------------------------------------------------------------------------------------------


def check_window(occurred_at: datetime, now: datetime) -> None:
    """BR-U3-05: `|occurred_at - now| <= 5 min`; si no, 422. Solo para una llave nueva."""
    if abs(occurred_at - now) > WINDOW:
        raise ValidationFailed(invalid_params=[InvalidParam(name="occurred_at", reason_code="outside_window")])


def check_business(entry: RegistryEntryIn) -> None:
    """BR-U0-37 (`check_business_time` de U0): los momentos de negocio son <= `occurred_at` y de hace como mucho 7 dias.

    `received_at` no es un momento de negocio y no entra. Solo para una llave nueva (BR-U3-05).
    """
    moments = {name: getattr(entry.payload, name, None) for name in BUSINESS_TIME_FIELDS}
    error = check_business_time(moments, entry.occurred_at)
    if error is not None:
        raise ValidationFailed(invalid_params=[InvalidParam(name=f"payload.{error.field}", reason_code=error.reason_code)])


def next_recorded_at(clock_now: datetime, head_recorded_at: datetime) -> datetime:
    """BR-U3-05: `recorded_at = max(reloj de la base, recorded_at de la cabeza)`, no decreciente en `seq` aunque el reloj retroceda."""
    return max(clock_now, head_recorded_at)


# --- Contenido de `canonical` (domain-entities §1.1) ----------------------------------------------------------------------


def entry_body(entry: RegistryEntryIn, seq: int, recorded_at: datetime) -> dict[str, Any]:
    """Los campos de domain-entities §1.1. Los opcionales ausentes no se escriben (`case_id?`); los del payload se conservan tal cual."""
    body = entry.model_dump(mode="python")
    for name in ("case_id", "model_version_id", "policy_version_id"):
        if body[name] is None:
            del body[name]
    body["actor"] = {key: value for key, value in body["actor"].items() if value is not None}
    body["seq"] = seq
    body["recorded_at"] = recorded_at
    body["contract_version"] = vectra_contracts.__version__
    return body


def build_canonical(entry: RegistryEntryIn, seq: int, recorded_at: datetime) -> bytes:
    return canonicalize(entry_body(entry, seq, recorded_at))


def business_of(body: Mapping[str, Any]) -> bytes:
    """Los campos de negocio (BR-U3-06) en JCS; un campo ausente y uno nulo son lo mismo."""
    return canonicalize({name: body[name] for name in BUSINESS_FIELDS if body.get(name) is not None})


def same_business(entry: RegistryEntryIn, stored: bytes) -> bool:
    """Si la solicitud tiene los mismos campos de negocio que la entrada guardada (BR-U3-06)."""
    return business_of(decode(build_canonical(entry, 0, datetime(2000, 1, 1, tzinfo=UTC)))) == business_of(decode(stored))


# --- Escritura ------------------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class AppendOutcome:
    """`created` es `False` en un reintento idempotente (ack original, sin escribir)."""

    ack: RegistryAck
    created: bool


def _ack(seq: int, recorded_at: datetime) -> RegistryAck:
    return RegistryAck(registry_entry_id=str(seq), seq=seq, recorded_at=recorded_at.astimezone(UTC))


async def _find(conn: Connection, key: UUID) -> tuple[int, datetime, bytes] | None:
    """BR-U3-04, paso 0: la entrada con esa llave, por el indice de `idempotency_key` (no por una restriccion de unicidad)."""
    cursor = await conn.execute(
        "SELECT seq, recorded_at, canonical FROM registry_entries WHERE idempotency_key = %s", (key,)
    )
    row = await cursor.fetchone()
    if row is None:
        return None
    seq, recorded_at, canonical = cast(tuple[int, datetime, bytes], row)
    return int(seq), recorded_at, bytes(canonical)


async def _commit(conn: Connection, budget: float) -> None:
    """`COMMIT` con `remote_apply`, con un tope de `budget` segundos.

    `statement_timeout` **no** cubre la espera del commit sincrono (PostgreSQL lo desactiva antes de confirmar), asi que el tope
    es nuestro: al vencer se le pide al servidor cancelar esa espera (`cancel_safe`), que confirma en local con un WARNING y suelta
    el lock; `_once` convierte ese WARNING en 503. La fila queda escrita y el reintento con la misma llave la resuelve.
    """
    task = asyncio.ensure_future(conn.commit())
    try:
        done, _ = await asyncio.wait({task}, timeout=max(budget, 0.05))
        if not done:
            await conn.cancel_safe()
        await task
    except BaseException:
        task.cancel()
        raise


async def _transaction(
    conn: Connection,
    entry: RegistryEntryIn,
    clock: Callable[[], datetime],
    db_clock: Callable[[], datetime] | None,
) -> AppendOutcome:
    started = time.monotonic()
    try:
        outcome = await _work(conn, entry, clock, db_clock)
    except asyncio.CancelledError:
        raise
    except BaseException:
        with contextlib.suppress(psycopg.Error):  # la conexion puede estar rota: el pool la descarta
            await conn.rollback()
        raise
    await _commit(conn, STATEMENT_TIMEOUT_MS / 1000 - (time.monotonic() - started))
    return outcome


async def _work(
    conn: Connection,
    entry: RegistryEntryIn,
    clock: Callable[[], datetime],
    db_clock: Callable[[], datetime] | None,
) -> AppendOutcome:
    await conn.execute(f"SET LOCAL lock_timeout = {LOCK_TIMEOUT_MS}")  # noqa: S608 - constantes
    await conn.execute(f"SET LOCAL statement_timeout = {STATEMENT_TIMEOUT_MS}")  # noqa: S608
    await conn.execute("SET LOCAL synchronous_commit = 'remote_apply'")
    await conn.execute("SELECT pg_advisory_xact_lock(%s)", (APPEND_LOCK,))
    existing = await _find(conn, entry.idempotency_key)
    if existing is not None:
        seq, recorded_at, stored = existing
        if not same_business(entry, stored):
            raise ConflictState()
        # Un reintento no escribe, pero el ack solo se da si la fila ya esta en el standby sincrono: un mensaje
        # transaccional en el WAL hace que este commit espere (remote_apply) hasta pasar por la fila original.
        await conn.execute("SELECT pg_logical_emit_message(true, 'registry', 'ack')")
        return AppendOutcome(_ack(seq, recorded_at), created=False)
    # Llave nueva: la ventana y la cota de los momentos de negocio (BR-U3-05).
    check_window(entry.occurred_at, clock())
    check_business(entry)
    cursor = await conn.execute("SELECT seq, hash, recorded_at, clock_timestamp() FROM registry_head")
    head = await cursor.fetchone()
    assert head is not None, "el registro siempre tiene la genesis"  # noqa: S101
    head_seq, head_hash, head_recorded, db_now = cast(tuple[int, bytes, datetime, datetime], head)
    recorded_at = next_recorded_at(db_clock() if db_clock else db_now, head_recorded)
    head_hash = bytes(head_hash)
    seq = head_seq + 1
    canonical = build_canonical(entry, seq, recorded_at)
    if len(canonical) > MAX_CANONICAL:
        raise PayloadTooLarge()
    actor = entry.actor
    await conn.execute(
        "INSERT INTO registry_entries (seq, idempotency_key, entry_type, case_id, model_version_id, policy_version_id, "
        "actor_kind, actor_id, actor_role, occurred_at, recorded_at, correlation_id, contract_version, canonical, "
        "prev_hash, hash) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
        (
            seq, entry.idempotency_key, str(entry.entry_type), entry.case_id, entry.model_version_id,
            entry.policy_version_id, actor.kind, actor.id, str(actor.role) if actor.role else None,
            entry.occurred_at, recorded_at, entry.correlation_id, vectra_contracts.__version__, canonical,
            head_hash, link(head_hash, canonical),
        ),
    )  # fmt: skip
    ENTRY_SIZE.observe(len(canonical))
    return AppendOutcome(_ack(seq, recorded_at), created=True)


def _commit_unconfirmed(severities: list[str | None]) -> bool:
    """Al cancelar la espera de la replica sincrona, PostgreSQL **confirma igual en local** y avisa con un WARNING."""
    return "WARNING" in severities


async def append_entry(
    pools: Pools,
    entry: RegistryEntryIn,
    *,
    clock: Callable[[], datetime] = _utc_now,
    db_clock: Callable[[], datetime] | None = None,
) -> AppendOutcome:
    """Escribe una entrada (BR-U3-04) o resuelve el reintento. Sin autorizacion: eso es de `append_authorized`.

    `clock` es el reloj del servicio (la ventana de `occurred_at`); `db_clock` reemplaza a `clock_timestamp()` solo en las pruebas.
    Errores: 413, 422, 409 y 503 (`DependencyUnavailable`: sin pool, sin lock, sin commit confirmado, o 2,5 s agotados).
    """
    estimate = build_canonical(entry, _SEQ_PLACEHOLDER, clock())
    if len(estimate) > MAX_CANONICAL:
        raise PayloadTooLarge()
    try:
        async with asyncio.timeout(HANDLER_TIMEOUT):
            try:
                return await _once(pools, entry, clock, db_clock)
            except errors.UniqueViolation:
                # Otra escritura gano la llave sin pasar por el lock: se repite la busqueda una vez (sin depender del
                # nombre de la restriccion). Ahora la fila existe y se resuelve por BR-U3-06.
                return await _once(pools, entry, clock, db_clock)
    except TimeoutError as error:
        raise DependencyUnavailable() from error
    except (errors.LockNotAvailable, errors.QueryCanceled, psycopg.OperationalError) as error:
        raise DependencyUnavailable() from error


async def _once(
    pools: Pools,
    entry: RegistryEntryIn,
    clock: Callable[[], datetime],
    db_clock: Callable[[], datetime] | None,
) -> AppendOutcome:
    severities: list[str | None] = []

    def on_notice(diagnostic: psycopg.errors.Diagnostic) -> None:
        severities.append(diagnostic.severity)  # el `Diagnostic` solo vale dentro del manejador

    async with pools.append.connection() as conn:
        conn.add_notice_handler(on_notice)
        try:
            outcome = await _transaction(conn, entry, clock, db_clock)
        finally:
            conn.remove_notice_handler(on_notice)
    if _commit_unconfirmed(severities):
        # La fila quedo escrita en local, pero el standby no la confirmo a tiempo: el llamador reintenta con la misma llave.
        raise DependencyUnavailable()
    return outcome


async def append_authorized(
    pools: Pools,
    entry: RegistryEntryIn,
    scopes: Collection[Scope],
    *,
    clock: Callable[[], datetime] = _utc_now,
    db_clock: Callable[[], datetime] | None = None,
) -> AppendOutcome:
    """El camino de `POST /v1/entries`: scope y forma (403), actor de gobierno (BR-U3-16) y despues el append."""
    authorize(scopes, entry)
    check_governance_actor(entry)
    return await append_entry(pools, entry, clock=clock, db_clock=db_clock)
