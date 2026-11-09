"""Evidencia en dos fases (BR-U4-17), excepcion de `freeze` (BR-U4-15) y operaciones de la capa de servicio (Paso 8).

**Dos fases.** Toda operacion hace: TX1 inserta la `Transition` en `pendiente_registro` (el estado no cambia) -> append al
registro con la `idempotency_key` -> TX2 (`_finish`) con el ack: **revalida** que la transicion siga pendiente y que el
estado de la entidad sea su `from_state`; si es asi la confirma, aplica el estado y recalcula `serving-config`; si no, la
deja `descartada` y escribe su compensacion `transicion_descartada` (modelos). Sin ack no hay efecto: `register` y
`propose_policy` ni siquiera crean la fila de la entidad antes del ack (viaja en `event_payload.effect`).

**Sobre de `event_payload`.** `{"entry": <lo que se reenvia al registro, sin `occurred_at`>, "effect": <lo que se aplica al
confirmar>, "depends_on": <transition_id | null>}`. El `correlation_id` y el sobre se guardan al crear la transicion y se
reenvian sin cambios; cada intento lleva un `occurred_at` nuevo (BR-U3-05).

**Una escritura a la vez.** Toda transaccion que escribe estado toma el *advisory lock* de governance (`GLOBAL_LOCK`): son
transiciones de personas, de bajo volumen, y asi las operaciones multi-entidad (`mark_active`, la activacion de politica,
`freeze`) no se cruzan nunca ni se bloquean entre si. El reconciliador (`background.py`) usa `SKIP LOCKED` solo para
reclamar la menor `n` pendiente de cada entidad mientras escribe en el registro; no toma ese lock hasta confirmar.

**Decisiones que el diseno no fija** (registradas en la bitacora de U04-T03):
- Un ack parcial de una unidad se guarda en `registry_entry_id` de la fila, que sigue `pendiente_registro`; la unidad se
  confirma cuando todas sus mitades lo tienen.
- Un `freeze` tiene el actor `service` de `model_fsm`, pero U3 (BR-U3-16) exige `{kind: system, id: bias-monitoring-job}`:
  al armar la entrada del registro, el actor del `freeze` viaja como `system`.
- El `freeze` lleva aqui el `FreezeContext` tal cual (`data_sources` e `initial_disparity` y la reduccion por tamano son del
  Paso 10); el cliente real del registro lo rechazaria hasta entonces (el tipo de U0 exige `FreezeContextPackage`).
- Una descartada de **politica** no tiene compensacion (el `CHECK` de `0001` solo admite `compensacion` en modelos).
"""

import json
import uuid
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any, Final, Literal, Protocol

import httpx
from psycopg import errors as pg_errors
from psycopg.types.json import Jsonb
from vectra_common.errors import DependencyUnavailable
from vectra_contracts.catalog import Role
from vectra_contracts.models.explanation import RegistryAck
from vectra_contracts.models.governance import (
    ModelRegistration,
    ModelVersion,
    PolicyDraft,
    PolicyVersion,
    ValidationReport,
)
from vectra_contracts.models.monitoring import FreezeContext

from vectra_governance.model_fsm import (
    BIAS_JOB,
    MFA,
    Action,
    Actor,
    ConflictState,
    Forbidden,
    ModelContext,
    transition,
)
from vectra_governance.policy import approve_policy
from vectra_governance.pools import Connection, Pools
from vectra_governance.serving_config import compose

Row = dict[str, Any]
Clock = Callable[[], datetime]
PoolFactory = Callable[[], AbstractContextManager[Connection]]

ENTITY_MODEL: Final = "model_version"
ENTITY_POLICY: Final = "policy"
ENTITY_SOURCE: Final = "data_source"
PENDING: Final = "pendiente_registro"
NO_STATE: Final = "-"  # `from_state` de una transicion que crea la entidad (`register`, `propose_policy`)
#: Una sola escritura de estado a la vez en toda governance (ver el docstring del modulo).
GLOBAL_LOCK: Final = 0x56454354_52410004
ABANDON_AFTER: Final = timedelta(hours=24)  # BR-U4-17
VALIDATION_DEADLINE: Final = timedelta(hours=2)  # BR-U4-05
GOVERNANCE_SYSTEM: Final = Actor("system", "governance-service")
REASON_TRANSITION_PENDING: Final = "transition_pending"  # ProblemReason.TRANSITION_PENDING (U0)
LIVE_STATES: Final = ("activo", "congelado")


def utc_now() -> datetime:
    return datetime.now(UTC)


def idempotency_key(entity_type: str, entity_id: str, n: int) -> uuid.UUID:
    """BR-U4-17 (precisado el 2026-11-09, Q-3): la **unica** funcion de la llave. La usan el servicio y las pruebas."""
    return uuid.uuid5(uuid.NAMESPACE_URL, f"urn:vectra:governance:{entity_type}:{entity_id}:{n}")


# --- Errores y cliente del registro ----------------------------------------------------------------------------------------


class RegistryUnavailable(DependencyUnavailable):
    """El registro no respondio (red, timeout, 5xx, 4xx permanente): 503. La transicion queda `pendiente_registro`."""

    def __init__(self, transition_ids: tuple[uuid.UUID, ...] = ()) -> None:
        super().__init__()
        self.transition_ids = transition_ids


class RegistryConflict(Exception):
    """409 del registro: la misma llave con otro contenido (BR-U3-06)."""


class RegistryClient(Protocol):
    def append(self, entry: dict[str, Any]) -> RegistryAck: ...


class HttpRegistryClient:
    """`POST /v1/entries` de `decision-registry-service` (U3) con timeouts (NFR-U4-25). La autenticacion es del llamador."""

    def __init__(
        self,
        base_url: str,
        token: Callable[[], str],
        *,
        timeout: float = 2.5,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._token = token
        self._client = httpx.Client(
            base_url=base_url, timeout=httpx.Timeout(timeout, connect=1.0), transport=transport
        )

    def append(self, entry: dict[str, Any]) -> RegistryAck:
        try:
            response = self._client.post(
                "/v1/entries", json=entry, headers={"Authorization": f"Bearer {self._token()}"}
            )
        except httpx.HTTPError as error:
            raise RegistryUnavailable() from error
        if response.status_code == 409:
            raise RegistryConflict()
        if response.status_code not in (200, 201):
            raise RegistryUnavailable()
        return RegistryAck.model_validate_json(response.content)

    def close(self) -> None:
        self._client.close()


# --- Entradas del registro --------------------------------------------------------------------------------------------------


def _jsonable(value: Any) -> Any:
    return json.loads(json.dumps(value, default=_default))


def _default(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat()
    if isinstance(value, uuid.UUID | Decimal):
        return str(value)
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    raise TypeError(f"no serializable: {type(value)}")


def actor_json(actor: Actor, now: datetime, auth_time: datetime | None = None) -> dict[str, Any]:
    """`{kind, sub, role?, acr?, auth_time?}` (domain-entities §1.3). El `auth_time` real lo trae el endpoint (Paso 10)."""
    out: dict[str, Any] = {"kind": actor.kind, "sub": actor.id}
    if actor.kind == "user":
        out["role"] = actor.role.value if actor.role else None
        out["acr"] = actor.acr
        out["auth_time"] = (auth_time or now).astimezone(UTC).isoformat()
    return {key: value for key, value in out.items() if value is not None}


def _model_event(model_id: str, event: str, **details: Any) -> dict[str, Any]:
    return {
        "entry_type": "model_event",
        "model_version_id": model_id,
        "payload": {"event": event, "details": _jsonable(details)},
    }


def _policy_event(policy_id: str, event: str) -> dict[str, Any]:
    return {
        "entry_type": "policy_event",
        "policy_version_id": policy_id,
        "payload": {"event": event, "policy_version_id": policy_id},
    }


def build_entry(row: Row, now: datetime) -> dict[str, Any]:
    """La entrada `RegistryEntryIn` (JSON) de una transicion: el sobre guardado, con `occurred_at` nuevo (BR-U3-05)."""
    entry = dict(row["event_payload"]["entry"])
    actor = row["actor"]
    registry_actor: dict[str, Any] = {"kind": actor["kind"], "id": actor["sub"]}
    for name in ("role", "acr", "auth_time"):
        if name in actor:
            registry_actor[name] = actor[name]
    if entry["entry_type"] == "freeze":  # BR-U3-16: el CronJob de sesgo escribe como `system`
        registry_actor["kind"] = "system"
    entry.update(
        actor=registry_actor,
        occurred_at=now.astimezone(UTC).isoformat(),
        correlation_id=row["correlation_id"],
        idempotency_key=str(row["idempotency_key"]),
    )
    return entry


# --- Filas ----------------------------------------------------------------------------------------------------------------


@dataclass
class NewTransition:
    entity_type: str
    entity_id: str
    from_state: str
    to_state: str
    actor: dict[str, Any]
    entry: dict[str, Any]
    effect: dict[str, Any]
    justification: str | None = None
    kind: Literal["cambio_estado", "compensacion"] = "cambio_estado"
    unit_id: uuid.UUID | None = None
    depends_on: uuid.UUID | None = None
    transition_id: uuid.UUID | None = None


def _lock(conn: Connection) -> None:
    conn.execute("SELECT pg_advisory_xact_lock(%s)", (GLOBAL_LOCK,))


_ENTITY_TABLES = {
    ENTITY_MODEL: ("model_versions", "model_version_id"),
    ENTITY_POLICY: ("policies", "policy_version_id"),
    ENTITY_SOURCE: ("data_sources", "ds_id"),
}


def entity_state(conn: Connection, entity_type: str, entity_id: str) -> str | None:
    table, column = _ENTITY_TABLES[entity_type]
    row = conn.execute(f"SELECT state FROM {table} WHERE {column} = %s", (entity_id,)).fetchone()  # noqa: S608
    return None if row is None else str(row["state"])


def _model_row(conn: Connection, model_id: str) -> Row | None:
    return conn.execute("SELECT * FROM model_versions WHERE model_version_id = %s", (model_id,)).fetchone()


def _policy_row(conn: Connection, policy_id: str) -> Row | None:
    return conn.execute("SELECT * FROM policies WHERE policy_version_id = %s", (policy_id,)).fetchone()


def is_freeze(row: Row) -> bool:
    return bool(
        row["entity_type"] == ENTITY_MODEL
        and row["kind"] == "cambio_estado"
        and row["from_state"] == "activo"
        and row["to_state"] == "congelado"
    )


def _has_pending(conn: Connection, entity_type: str, entity_id: str) -> bool:
    return (
        conn.execute(
            "SELECT 1 FROM transitions WHERE entity_type = %s AND entity_id = %s AND status = %s LIMIT 1",
            (entity_type, entity_id, PENDING),
        ).fetchone()
        is not None
    )


def _ensure_free(conn: Connection, entity_type: str, entity_id: str) -> None:
    """BR-U4-17: una sola transicion pendiente por entidad (la compensacion y el `freeze` pendientes cuentan)."""
    if _has_pending(conn, entity_type, entity_id):
        raise ConflictState(REASON_TRANSITION_PENDING)


def _insert(conn: Connection, nt: NewTransition, now: datetime, correlation_id: str) -> Row:
    """`n` = transiciones no abandonadas + 1 (BR-U4-17), como el maximo `n` no abandonado + 1.

    El `freeze` y las compensaciones toman, en cambio, el maximo de **todas** (tambien las abandonadas) + 1: nunca reusan
    la llave de una abandonada que el registro pudo haber escrito, porque no se pueden rechazar con un 409 (el `freeze` ya
    aplico y una compensacion nunca se abandona) y quedarian bloqueados para siempre.
    """
    fresh = nt.kind == "compensacion" or (
        nt.entity_type == ENTITY_MODEL and nt.from_state == "activo" and nt.to_state == "congelado"
    )
    top = conn.execute(
        "SELECT COALESCE(max(transition_number) FILTER (WHERE %s OR status <> 'abandonada'), 0) AS n FROM transitions "
        "WHERE entity_type = %s AND entity_id = %s",
        (fresh, nt.entity_type, nt.entity_id),
    ).fetchone()
    assert top is not None
    n = int(top["n"]) + 1
    envelope = {
        "entry": _jsonable(nt.entry),
        "effect": _jsonable(nt.effect),
        "depends_on": None if nt.depends_on is None else str(nt.depends_on),
    }
    try:
        row = conn.execute(
            "INSERT INTO transitions (transition_id, entity_type, entity_id, transition_number, idempotency_key, "
            "from_state, to_state, actor, justification, kind, status, unit_id, event_payload, correlation_id, created_at) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'pendiente_registro', %s, %s, %s, %s) RETURNING *",
            (
                nt.transition_id or uuid.uuid4(),
                nt.entity_type,
                nt.entity_id,
                n,
                idempotency_key(nt.entity_type, nt.entity_id, n),
                nt.from_state,
                nt.to_state,
                Jsonb(nt.actor),
                nt.justification,
                nt.kind,
                nt.unit_id,
                Jsonb(envelope),
                correlation_id,
                now,
            ),
        ).fetchone()
    except pg_errors.UniqueViolation as error:
        raise ConflictState(REASON_TRANSITION_PENDING) from error
    assert row is not None
    return row


def _fetch(conn: Connection, ids: list[uuid.UUID]) -> list[Row]:
    return conn.execute(
        "SELECT * FROM transitions WHERE transition_id = ANY(%s) ORDER BY transition_id FOR UPDATE", (ids,)
    ).fetchall()


# --- Entidades como tipos de U0 ---------------------------------------------------------------------------------------------


def _aware(value: datetime | None) -> datetime | None:
    return None if value is None else value.astimezone(UTC)


def model_version_of(row: Row) -> ModelVersion:
    return ModelVersion.model_validate_json(
        json.dumps(
            {
                **{k: row[k] for k in ModelVersion.model_fields if k in row},
                "created_at": _aware(row["created_at"]),
                "updated_at": _aware(row["updated_at"]),
                "archived_at": _aware(row["archived_at"]),
            },
            default=_default,
        )
    )


def policy_version_of(row: Row) -> PolicyVersion:
    data = {k: row[k] for k in PolicyVersion.model_fields if k in row}
    data["cutoff"] = format(row["cutoff"], ".4f")
    data["low_confidence_threshold"] = format(row["low_confidence_threshold"], ".4f")
    data["created_at"] = _aware(row["created_at"])
    return PolicyVersion.model_validate_json(json.dumps(data, default=_default))


def recompute_serving_config(conn: Connection, now: datetime) -> None:
    """Escribe la fila unica de `serving_config` (domain-entities §5). El trigger notifica solo si cambia el `etag`."""
    model = conn.execute(
        "SELECT * FROM model_versions WHERE state IN ('activo', 'congelado')"
    ).fetchone()
    policy = conn.execute("SELECT * FROM policies WHERE state = 'activa'").fetchone()
    config = (
        compose(model_version_of(model), policy_version_of(policy), now, now)
        if model is not None and policy is not None
        else None
    )
    if config is None:
        conn.execute(
            "UPDATE serving_config SET model_version_id = NULL, state = NULL, policy_version_id = NULL, "
            "feature_dictionary_version = NULL, inference_service = NULL, normative_current = NULL, "
            "effective_from = NULL, etag = NULL WHERE id = 1"
        )
        return
    normative = None if config.normative_current is None else Jsonb(config.normative_current.model_dump(mode="json"))
    conn.execute(
        "UPDATE serving_config SET model_version_id = %s, state = %s, policy_version_id = %s, "
        "feature_dictionary_version = %s, inference_service = %s, normative_current = %s, effective_from = %s, etag = %s "
        "WHERE id = 1",
        (
            config.model_version_id,
            config.state,
            config.policy_version_id,
            config.feature_dictionary_version,
            config.inference_service,
            normative,
            now,
            config.etag,
        ),
    )


# --- Efectos (TX2) ---------------------------------------------------------------------------------------------------------


def _touches_serving(row: Row) -> bool:
    if row["from_state"] == row["to_state"]:
        return False
    if row["entity_type"] == ENTITY_MODEL:
        return row["from_state"] in LIVE_STATES or row["to_state"] in LIVE_STATES
    if row["entity_type"] == ENTITY_POLICY:
        return "activa" in (row["from_state"], row["to_state"])
    return False


_MODEL_COLUMNS: Final = (
    "model_version_id",
    "artifact_uri",
    "artifact_format",
    "artifact_sha256",
    "explainer_uri",
    "explainer_sha256",
    "inference_service",
    "manifest_uri",
    "manifest_sha256",
    "feature_dictionary_version",
    "feature_dictionary",
    "feature_spec",
    "data_sources",
    "source_candidate_for",
    "registered_by",
)


def _set_model_state(conn: Connection, row: Row, now: datetime, **extra: Any) -> None:
    sets = ["state = %s", "updated_at = %s"] + [f"{column} = %s" for column in extra]
    conn.execute(
        f"UPDATE model_versions SET {', '.join(sets)} WHERE model_version_id = %s",  # noqa: S608
        (row["to_state"], now, *extra.values(), row["entity_id"]),
    )


def _apply(conn: Connection, row: Row, now: datetime) -> None:
    """Aplica el efecto de una transicion ya `confirmada` (el trigger `guard_unfreeze` lo exige asi)."""
    effect = row["event_payload"]["effect"]
    op = effect["op"]
    entity_id = row["entity_id"]
    if op == "register":
        data = effect["model"]
        values = [Jsonb(data[c]) if c in ("feature_dictionary", "feature_spec") else data[c] for c in _MODEL_COLUMNS]
        conn.execute(
            f"INSERT INTO model_versions ({', '.join(_MODEL_COLUMNS)}, created_at, updated_at) "  # noqa: S608
            f"VALUES ({', '.join(['%s'] * len(_MODEL_COLUMNS))}, %s, %s)",
            (*values, now, now),
        )
    elif op == "state":
        extra = {"approved_by": effect["approved_by"]} if "approved_by" in effect else {}
        _set_model_state(conn, row, now, **extra)
    elif op == "start_validation":
        _set_model_state(conn, row, now)
        run = effect["run"]
        conn.execute(
            "INSERT INTO validation_runs (run_id, model_version_id, job_name, state, mode, started_at, deadline_at) "
            "VALUES (%s, %s, %s, 'lanzado', 'validacion', %s, %s)",
            (run["run_id"], entity_id, run["job_name"], now, run["deadline_at"]),
        )
    elif op == "run_result":
        _set_model_state(conn, row, now)
        conn.execute(
            "UPDATE validation_runs SET state = %s, report = %s, finished_at = %s WHERE run_id = %s",
            (
                effect["run_state"],
                None if effect.get("report") is None else Jsonb(effect["report"]),
                now,
                effect["run_id"],
            ),
        )
    elif op == "resolution":
        conn.execute("SELECT set_config('vectra.frozen_resolution', %s, true)", (str(row["transition_id"]),))
        if effect["action"] == "investigar":
            conn.execute(
                "UPDATE model_versions SET investigation = true, updated_at = %s WHERE model_version_id = %s",
                (now, entity_id),
            )
        else:
            _set_model_state(conn, row, now)
    elif op == "policy_propose":
        draft = effect["policy"]
        conn.execute(
            "INSERT INTO policies (policy_version_id, cutoff, low_confidence_threshold, channel_rules, normative, state, "
            "proposed_by, created_at) VALUES (%s, %s, %s, %s, %s, 'propuesta', %s, %s)",
            (
                entity_id,
                draft["cutoff"],
                draft["low_confidence_threshold"],
                Jsonb(draft["channel_rules"]),
                Jsonb(draft["normative"]),
                effect["proposed_by"],
                now,
            ),
        )
    elif op == "policy_activate":
        conn.execute(
            "UPDATE policies SET state = 'activa', approved_by = %s, activated_at = %s WHERE policy_version_id = %s",
            (effect["approved_by"], now, entity_id),
        )
    elif op == "policy_supersede":
        conn.execute(
            "UPDATE policies SET state = 'historica', superseded_at = %s WHERE policy_version_id = %s", (now, entity_id)
        )
    elif op == "policy_reject":
        conn.execute(
            "UPDATE policies SET state = 'rechazada', rejection_justification = %s WHERE policy_version_id = %s",
            (effect.get("justification"), entity_id),
        )
    elif op != "none":  # `none`: freeze y compensacion no aplican estado al confirmarse
        raise ValueError(f"efecto desconocido: {op}")


# --- Resultado ---------------------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Result:
    """La operacion se confirmo (`confirmada`). `event_written` solo importa en `freeze`."""

    transition_ids: tuple[uuid.UUID, ...]
    status: str = "confirmada"
    event_written: bool = True


@dataclass(frozen=True)
class NewModel:
    """Lo que `register` guarda al confirmarse. La validacion de bytes (BR-U4-06) y `inference_service` son del Paso 10."""

    model_version_id: str
    registration: ModelRegistration
    inference_service: str
    feature_dictionary_version: str
    feature_dictionary: dict[str, Any]
    feature_spec: dict[str, Any]


class Evidence:
    """La capa de servicio sin HTTP: las operaciones de modelo y de politica con evidencia en dos fases."""

    def __init__(self, pools: Pools, registry: RegistryClient, clock: Clock = utc_now) -> None:
        self.pools = pools
        self.registry = registry
        self.clock = clock

    # --- fase 1 y 2 -------------------------------------------------------------------------------------------------------

    def _begin(
        self,
        build: Callable[[Connection, datetime], list[NewTransition]],
        *,
        conn: Connection | None = None,
    ) -> list[Row]:
        """TX1: arma las transiciones (con las verificaciones de `model_fsm`), exige una sola pendiente por entidad e inserta.

        Con `conn`, corre dentro de la transaccion de quien llama (el barrido, que reclama la corrida con `SKIP LOCKED`).
        """
        if conn is not None:
            with conn.transaction():
                return self._begin_in(conn, build)
        with self.pools.tx() as own, own.transaction():
            return self._begin_in(own, build)

    def _begin_in(
        self, conn: Connection, build: Callable[[Connection, datetime], list[NewTransition]]
    ) -> list[Row]:
        _lock(conn)
        now = self.clock()
        plan = build(conn, now)
        for nt in plan:
            _ensure_free(conn, nt.entity_type, nt.entity_id)
        cid = uuid.uuid4().hex
        return [_insert(conn, nt, now, cid) for nt in plan]

    def publish(self, rows: list[Row], pool: PoolFactory) -> str:
        """Fase 2 de transiciones ya insertadas (el barrido las crea en su propia transaccion): su estado final."""
        return self._drive([r["transition_id"] for r in rows], pool)

    def _drive(self, ids: list[uuid.UUID], pool: PoolFactory) -> str:
        """Fase 2 de un grupo (una transicion o una unidad): appends, ack guardado y TX2. Devuelve el estado de la primera."""
        for transition_id in ids:
            self.send(transition_id, pool)
        return self.finish(ids[0], pool)

    def _complete(self, rows: list[Row]) -> Result:
        ids = [r["transition_id"] for r in rows]
        status = self._drive(ids, self.pools.tx)
        if status == "confirmada":
            return Result(tuple(ids))
        if status == PENDING:
            raise RegistryUnavailable(tuple(ids))
        if status == "abandonada":
            raise ConflictState("abandoned_transition_recovered")
        raise ConflictState("transition_discarded")

    def send(self, transition_id: uuid.UUID, pool: PoolFactory) -> str:
        """Reclama la fila (`SKIP LOCKED`), escribe en el registro y guarda el ack. `skipped`, `unavailable` o `acked`.

        Un 409 del registro (llave de una abandonada ya escrita) termina en `ConflictState` (ver `_recover`).

        Respeta el orden de `n`: no escribe una fila mientras la entidad tenga una pendiente con menor `n`, ni una que
        dependa (`depends_on`) de otra todavia sin confirmar.
        """
        with pool() as conn, conn.transaction():
            row = conn.execute(
                "SELECT * FROM transitions t WHERE transition_id = %s AND status = 'pendiente_registro' "
                "AND NOT EXISTS (SELECT 1 FROM transitions o WHERE o.entity_type = t.entity_type AND o.entity_id = t.entity_id "
                "AND o.status = 'pendiente_registro' AND o.transition_number < t.transition_number) "
                "FOR UPDATE SKIP LOCKED",
                (transition_id,),
            ).fetchone()
            if row is None:
                return "skipped"
            dep = row["event_payload"].get("depends_on")
            if dep is not None:
                done = conn.execute(
                    "SELECT 1 FROM transitions WHERE transition_id = %s AND status = 'confirmada'", (dep,)
                ).fetchone()
                if done is None:
                    return "skipped"
            try:
                ack = self.registry.append(build_entry(row, self.clock()))
            except RegistryUnavailable:
                return "unavailable"
            except RegistryConflict:
                if is_freeze(row) or row["kind"] == "compensacion":
                    return "unavailable"  # nunca se abandonan ni se rechazan: siguen pendientes (y alertan)
                conflict_row = row
            else:
                conn.execute(
                    "UPDATE transitions SET registry_entry_id = %s WHERE transition_id = %s",
                    (ack.registry_entry_id, transition_id),
                )
                return "acked"
        self._recover(conflict_row, pool)  # `conflict`: siempre termina en `ConflictState`
        raise AssertionError("unreachable")

    def finish(self, transition_id: uuid.UUID, pool: PoolFactory) -> str:
        """TX2 (BR-U4-17, paso 3): revalida, confirma y aplica la transicion (o su unidad completa), o la descarta."""
        with pool() as conn, conn.transaction():
            _lock(conn)
            now = self.clock()
            first = conn.execute("SELECT * FROM transitions WHERE transition_id = %s", (transition_id,)).fetchone()
            if first is None:
                return "desconocida"
            if first["unit_id"] is None:
                rows = _fetch(conn, [transition_id])
            else:
                ids = [
                    r["transition_id"]
                    for r in conn.execute(
                        "SELECT transition_id FROM transitions WHERE unit_id = %s AND status <> 'abandonada' "
                        "OR transition_id = %s",
                        (first["unit_id"], transition_id),
                    ).fetchall()
                ]
                rows = _fetch(conn, ids)
            self._finish_locked(conn, rows, now)
            current = conn.execute(
                "SELECT status FROM transitions WHERE transition_id = %s", (transition_id,)
            ).fetchone()
            assert current is not None
            return str(current["status"])

    def _finish_locked(self, conn: Connection, rows: list[Row], now: datetime) -> None:
        pending = [r for r in rows if r["status"] == PENDING]
        if not pending:
            return
        if len(pending) != len(rows):  # una mitad ya no esta pendiente: la unidad no se confirma (BR-U4-17)
            self._discard(conn, pending, "unidad_incompleta", now)
            return
        if any(r["registry_entry_id"] is None for r in pending):
            return  # espera el ack de las demas mitades
        if not all(self._still_valid(conn, r) for r in pending):
            self._discard(conn, pending, "estado_cambio", now)
            return
        self._confirm(conn, pending, now)

    @staticmethod
    def _still_valid(conn: Connection, row: Row) -> bool:
        if row["kind"] == "compensacion" or is_freeze(row):
            return True
        state = entity_state(conn, row["entity_type"], row["entity_id"])
        return (state is None) if row["from_state"] == NO_STATE else (state == row["from_state"])

    @staticmethod
    def _confirm(conn: Connection, rows: list[Row], now: datetime) -> None:
        # Primero las salidas (`activo -> inactivo`, `activa -> historica`): el indice de una sola viva/activa lo exige.
        ordered = sorted(rows, key=lambda r: r["to_state"] not in ("inactivo", "historica"))
        touches = False
        for row in ordered:
            conn.execute(
                "UPDATE transitions SET status = 'confirmada', confirmed_at = %s WHERE transition_id = %s",
                (now, row["transition_id"]),
            )
            if row["kind"] == "compensacion" or is_freeze(row):
                continue
            _apply(conn, row, now)
            touches = touches or _touches_serving(row)
        if touches:
            recompute_serving_config(conn, now)

    def _discard(
        self,
        conn: Connection,
        rows: list[Row],
        reason: str,
        now: datetime,
        *,
        depends_on: uuid.UUID | None = None,
    ) -> None:
        """Descarta transiciones pendientes (su `n` queda reservado) y escribe la compensacion de las de modelo."""
        for row in rows:
            conn.execute(
                "UPDATE transitions SET status = 'descartada' WHERE transition_id = %s AND status = 'pendiente_registro'",
                (row["transition_id"],),
            )
            if row["entity_type"] != ENTITY_MODEL or row["kind"] != "cambio_estado":
                continue  # el `CHECK` de `0001` solo admite `compensacion` en versiones de modelo
            state = entity_state(conn, ENTITY_MODEL, row["entity_id"]) or row["from_state"]
            comp = NewTransition(
                ENTITY_MODEL,
                row["entity_id"],
                state,
                state,
                {"kind": "system", "sub": GOVERNANCE_SYSTEM.id},
                _model_event(
                    row["entity_id"],
                    "transicion_descartada",
                    discarded_idempotency_key=str(row["idempotency_key"]),
                    reason=reason,
                ),
                {"op": "none"},
                kind="compensacion",
                depends_on=depends_on,
            )
            _insert(conn, comp, now, uuid.uuid4().hex)

    # --- recuperacion tras un abandono ------------------------------------------------------------------------------------

    def _recover(self, row: Row, pool: PoolFactory) -> None:
        """409 del registro: la transicion `row` repite la llave de una abandonada que si se escribio (BR-U4-17).

        Reenvia la abandonada (y las demas mitades de su unidad) con su llave, obtiene el ack original, la revalida y, si
        procede, la confirma y aplica **ese** estado; la nueva se rechaza (409). Una unidad solo se confirma completa.
        """
        with pool() as conn:
            candidates = conn.execute(
                "SELECT * FROM transitions WHERE entity_type = %s AND entity_id = %s AND transition_number = %s "
                "AND status = 'abandonada' AND transition_id <> %s ORDER BY created_at DESC",
                (row["entity_type"], row["entity_id"], row["transition_number"], row["transition_id"]),
            ).fetchall()
            conn.rollback()
        recovered: dict[uuid.UUID, RegistryAck] | None = None
        group: list[Row] = []
        for candidate in candidates:
            group = self._abandoned_group(pool, candidate)
            try:
                acks = {m["transition_id"]: self.registry.append(build_entry(m, self.clock())) for m in group}
            except RegistryConflict:
                continue
            recovered = acks
            break
        with pool() as conn, conn.transaction():
            _lock(conn)
            now = self.clock()
            mine = conn.execute(
                "SELECT * FROM transitions WHERE (transition_id = %s OR (unit_id IS NOT NULL AND unit_id = %s)) "
                "AND status = 'pendiente_registro'",
                (row["transition_id"], row["unit_id"]),
            ).fetchall()
            mine_ids = [m["transition_id"] for m in mine]
            # La unidad abandonada solo vuelve si todas sus `n` siguen libres; si otra transicion ya ocupo alguna, no se
            # puede reanimar: la nueva queda `descartada` (reserva su `n`, para que no vuelva a chocar con esa llave) y su
            # `transicion_descartada` marca el evento escrito sin efecto.
            blocked = recovered is not None and any(
                conn.execute(
                    "SELECT 1 FROM transitions WHERE entity_type = %s AND entity_id = %s AND transition_number = %s "
                    "AND status <> 'abandonada' AND transition_id <> ALL(%s) LIMIT 1",
                    (m["entity_type"], m["entity_id"], m["transition_number"], mine_ids),
                ).fetchone()
                for m in group
            )
            if blocked:
                self._discard(conn, mine, "abandono", now)
            else:
                conn.execute(
                    "UPDATE transitions SET status = 'abandonada' WHERE transition_id = ANY(%s)", (mine_ids,)
                )
                if recovered is not None:
                    self._settle_recovered(conn, group, recovered, now)
        raise ConflictState("abandoned_transition_recovered" if recovered is not None else "idempotency_conflict")

    @staticmethod
    def _abandoned_group(pool: PoolFactory, candidate: Row) -> list[Row]:
        if candidate["unit_id"] is None:
            return [candidate]
        with pool() as conn:
            rows = conn.execute(
                "SELECT * FROM transitions WHERE unit_id = %s AND status = 'abandonada' ORDER BY transition_id",
                (candidate["unit_id"],),
            ).fetchall()
            conn.rollback()
        return rows

    def _settle_recovered(
        self, conn: Connection, group: list[Row], acks: dict[uuid.UUID, RegistryAck], now: datetime
    ) -> None:
        unit_id = group[0]["unit_id"]
        broken = unit_id is not None and (
            conn.execute(
                "SELECT 1 FROM transitions WHERE unit_id = %s AND status NOT IN ('abandonada', 'confirmada') "
                "AND transition_id <> ALL(%s) LIMIT 1",
                (unit_id, [m["transition_id"] for m in group]),
            ).fetchone()
            is not None
        )
        revived = [
            conn.execute(
                "UPDATE transitions SET status = 'pendiente_registro', registry_entry_id = %s WHERE transition_id = %s "
                "RETURNING *",
                (acks[m["transition_id"]].registry_entry_id, m["transition_id"]),
            ).fetchone()
            for m in group
        ]
        pending = [r for r in revived if r is not None]
        if broken:
            self._discard(conn, pending, "abandono", now)
        elif all(self._still_valid(conn, r) for r in pending):
            self._confirm(conn, pending, now)
        else:
            self._discard(conn, pending, "estado_cambio", now)

    # --- abandono a las 24 h (lo llama el reconciliador) -------------------------------------------------------------------

    def abandon(self, transition_id: uuid.UUID, pool: PoolFactory) -> str:
        """24 h sin confirmar (BR-U4-17): `abandonada`; una mitad con ack de una unidad rota queda `descartada` + compensacion.

        Nunca abandona un `freeze` ni una compensacion. Devuelve `abandonada`, `descartada` o `nada`.
        """
        with pool() as conn, conn.transaction():
            _lock(conn)
            now = self.clock()
            row = conn.execute("SELECT * FROM transitions WHERE transition_id = %s", (transition_id,)).fetchone()
            if row is None or row["status"] != PENDING or row["kind"] != "cambio_estado" or is_freeze(row):
                return "nada"
            if row["unit_id"] is None:
                rows = _fetch(conn, [transition_id])
            else:
                rows = _fetch(
                    conn,
                    [
                        r["transition_id"]
                        for r in conn.execute(
                            "SELECT transition_id FROM transitions WHERE unit_id = %s AND status = 'pendiente_registro'",
                            (row["unit_id"],),
                        ).fetchall()
                    ],
                )
            rows = [r for r in rows if r["status"] == PENDING]
            if row["unit_id"] is None and row["registry_entry_id"] is not None:
                self._finish_locked(conn, rows, now)  # ya tiene ack: se confirma, no se abandona
                return "nada"
            if all(r["registry_entry_id"] is not None for r in rows):
                self._finish_locked(conn, rows, now)
                return "nada"
            without = [r for r in rows if r["registry_entry_id"] is None]
            with_ack = [r for r in rows if r["registry_entry_id"] is not None]
            conn.execute(
                "UPDATE transitions SET status = 'abandonada' WHERE transition_id = ANY(%s)",
                ([r["transition_id"] for r in without],),
            )
            self._discard(conn, with_ack, "abandono", now)
            return "descartada" if with_ack else "abandonada"

    # --- helpers de las operaciones ---------------------------------------------------------------------------------------

    def _context(self, conn: Connection, row: Row | None, model_id: str) -> ModelContext:
        other = conn.execute(
            "SELECT model_version_id, state FROM model_versions WHERE state IN ('activo', 'congelado') "
            "AND model_version_id <> %s",
            (model_id,),
        ).fetchone()
        source_state = None
        if row is not None and row["source_candidate_for"] is not None:
            source_state = entity_state(conn, ENTITY_SOURCE, row["source_candidate_for"])
        return ModelContext(
            registered_by=None if row is None else row["registered_by"],
            source_candidate_for=None if row is None else row["source_candidate_for"],
            source_state=source_state,
            other_servable=None if other is None else other["state"],
        )

    def _checked(
        self, conn: Connection, model_id: str, action: Action, actor: Actor
    ) -> tuple[Row | None, str, Row | None]:
        """`model_fsm.transition` sobre la fila actual. Si la accion no cabe y hay una pendiente: `transition_pending`."""
        row = _model_row(conn, model_id)
        context = self._context(conn, row, model_id)
        try:
            target = transition(None if row is None else row["state"], action, actor, context)
        except ConflictState:
            if row is not None and _has_pending(conn, ENTITY_MODEL, model_id):
                raise ConflictState(REASON_TRANSITION_PENDING) from None
            raise
        other = conn.execute(
            "SELECT * FROM model_versions WHERE state IN ('activo', 'congelado') AND model_version_id <> %s",
            (model_id,),
        ).fetchone()
        return row, target, other

    def _simple_build(
        self,
        model_id: str,
        action: Action,
        actor: Actor,
        event: str,
        *,
        auth_time: datetime | None = None,
        effect: dict[str, Any] | None = None,
        details: dict[str, Any] | None = None,
        justification: str | None = None,
        after_check: Callable[[Connection], None] | None = None,
    ) -> Callable[[Connection, datetime], list[NewTransition]]:
        def build(conn: Connection, now: datetime) -> list[NewTransition]:
            row, target, _ = self._checked(conn, model_id, action, actor)
            if after_check is not None:
                after_check(conn)
            state = NO_STATE if row is None else row["state"]
            return [
                NewTransition(
                    ENTITY_MODEL,
                    model_id,
                    state,
                    target,
                    actor_json(actor, now, auth_time),
                    _model_event(model_id, event, from_state=state, to_state=target, **(details or {})),
                    effect or {"op": "state"},
                    justification=justification,
                )
            ]

        return build

    def _simple(self, model_id: str, action: Action, actor: Actor, event: str, **kwargs: Any) -> Result:
        return self._complete(self._begin(self._simple_build(model_id, action, actor, event, **kwargs)))

    # --- operaciones de modelo -----------------------------------------------------------------------------------------------

    def register(self, actor: Actor, new: NewModel, *, auth_time: datetime | None = None) -> Result:
        """`register` (BR-U4-01): la fila de la version se crea al confirmarse, no antes."""
        registration = new.registration
        model = {
            "model_version_id": new.model_version_id,
            "artifact_uri": registration.artifact_uri,
            "artifact_format": registration.artifact_format,
            "artifact_sha256": registration.artifact_sha256,
            "explainer_uri": registration.explainer_uri,
            "explainer_sha256": registration.explainer_sha256,
            "inference_service": new.inference_service,
            "manifest_uri": registration.manifest_uri,
            "manifest_sha256": registration.manifest_sha256,
            "feature_dictionary_version": new.feature_dictionary_version,
            "feature_dictionary": new.feature_dictionary,
            "feature_spec": new.feature_spec,
            "data_sources": registration.data_sources,
            "source_candidate_for": registration.source_candidate_for,
            "registered_by": actor.id,
        }
        return self._simple(
            new.model_version_id,
            "register",
            actor,
            "registrado",
            auth_time=auth_time,
            effect={"op": "register", "model": model},
            details={"artifact_sha256": registration.artifact_sha256},
        )

    def start_validation(
        self, actor: Actor, model_id: str, *, job_name: str, auth_time: datetime | None = None
    ) -> Result:
        """`registrado -> en_validacion` y la `ValidationRun` con plazo de 2 h (BR-U4-05). El lanzador del Job es del Paso 10."""
        return self._validation(actor, model_id, "start_validation", job_name, auth_time)

    def retry_validation(
        self, actor: Actor, model_id: str, *, job_name: str, auth_time: datetime | None = None
    ) -> Result:
        return self._validation(actor, model_id, "retry_validation", job_name, auth_time)

    def _validation(
        self, actor: Actor, model_id: str, action: Action, job_name: str, auth_time: datetime | None
    ) -> Result:
        run = {"run_id": str(uuid.uuid4()), "job_name": job_name, "deadline_at": self.clock() + VALIDATION_DEADLINE}
        return self._simple(
            model_id,
            action,
            actor,
            "validacion_iniciada",
            auth_time=auth_time,
            effect={"op": "start_validation", "run": _jsonable(run)},
            details={"run_id": run["run_id"]},
        )

    def receive_report(
        self, actor: Actor, model_id: str, run_id: str, report: ValidationReport, *, auth_time: datetime | None = None
    ) -> Result:
        """F32: la sincronia decide (BR-U4-07): `sync_check.passed` -> `lista_para_aprobacion`; si no, `validacion_fallida`."""
        passed = report.sync_check.passed
        action: Action = "validation_passed" if passed else "validation_failed"
        return self._simple(
            model_id,
            action,
            actor,
            "informe_validacion" if passed else "validacion_fallida",
            auth_time=auth_time,
            effect={
                "op": "run_result",
                "run_id": run_id,
                "run_state": "informe_recibido",
                "report": report.model_dump(mode="json"),
            },
            details={"run_id": run_id, "sync_passed": passed, "auc_roc": report.auc_roc}
            if passed
            else {"run_id": run_id, "reason": report.sync_check.failure_reason or "sync_check"},
            after_check=lambda conn: self._require_run(conn, model_id, run_id),
        )

    def _fail_validation_build(
        self, model_id: str, run_id: str, reason: str, run_state: str
    ) -> Callable[[Connection, datetime], list[NewTransition]]:
        return self._simple_build(
            model_id,
            "validation_failed",
            GOVERNANCE_SYSTEM,
            "validacion_fallida",
            effect={"op": "run_result", "run_id": run_id, "run_state": run_state},
            details={"run_id": run_id, "reason": reason},
        )

    def fail_validation(self, model_id: str, run_id: str, reason: str, *, run_state: str = "timeout") -> Result:
        """El sistema pasa una validacion vencida a `validacion_fallida` con su motivo (barrido de P-U4-02)."""
        return self._complete(self._begin(self._fail_validation_build(model_id, run_id, reason, run_state)))

    def begin_fail_validation(
        self, conn: Connection, model_id: str, run_id: str, reason: str, *, run_state: str = "timeout"
    ) -> list[Row]:
        """TX1 de `fail_validation` dentro de la transaccion `conn` del barrido; la fase 2 es `publish`."""
        return self._begin(self._fail_validation_build(model_id, run_id, reason, run_state), conn=conn)

    @staticmethod
    def _require_run(conn: Connection, model_id: str, run_id: str) -> None:
        run = conn.execute(
            "SELECT state, mode FROM validation_runs WHERE run_id = %s AND model_version_id = %s", (run_id, model_id)
        ).fetchone()
        if run is None or run["state"] != "lanzado" or run["mode"] != "validacion":
            raise ConflictState("validation_run_not_open")

    def approve(self, actor: Actor, model_id: str, *, auth_time: datetime | None = None) -> Result:
        return self._simple(
            model_id, "approve", actor, "aprobado", auth_time=auth_time, effect={"op": "state", "approved_by": actor.id}
        )

    def reject(self, actor: Actor, model_id: str, justification: str, *, auth_time: datetime | None = None) -> Result:
        return self._simple(
            model_id,
            "reject",
            actor,
            "rechazado",
            auth_time=auth_time,
            details={"justification": justification},
            justification=justification,
        )

    def retire(self, actor: Actor, model_id: str, *, auth_time: datetime | None = None) -> Result:
        return self._simple(model_id, "retire", actor, "retirado", auth_time=auth_time)

    def mark_active(self, actor: Actor, model_id: str, *, auth_time: datetime | None = None) -> Result:
        """BR-U4-08: la destino pasa a `activo` y la que estaba `activo` a `inactivo`, una sola unidad de evidencia."""

        def build(conn: Connection, now: datetime) -> list[NewTransition]:
            row, target, other = self._checked(conn, model_id, "mark_active", actor)
            assert row is not None
            who = actor_json(actor, now, auth_time)
            unit = uuid.uuid4() if other is not None and other["state"] == "activo" else None
            plan = [
                NewTransition(
                    ENTITY_MODEL,
                    model_id,
                    row["state"],
                    target,
                    who,
                    _model_event(model_id, "activado", from_state=row["state"], to_state=target),
                    {"op": "state"},
                    unit_id=unit,
                )
            ]
            if unit is not None:
                assert other is not None
                transition(other["state"], "deactivate", GOVERNANCE_SYSTEM)  # BR-U4-01: lo hace el sistema
                plan.append(
                    NewTransition(
                        ENTITY_MODEL,
                        other["model_version_id"],
                        "activo",
                        "inactivo",
                        who,  # el evento `inactivado` lleva el actor de este `mark_active` (BR-U3-16)
                        _model_event(other["model_version_id"], "inactivado", from_state="activo", to_state="inactivo"),
                        {"op": "state"},
                        unit_id=unit,
                    )
                )
            return plan

        return self._complete(self._begin(build))

    def frozen_resolution(
        self,
        actor: Actor,
        model_id: str,
        action: Literal["reactivar", "descartar", "investigar"],
        justification: str,
        *,
        auth_time: datetime | None = None,
    ) -> Result:
        """US-305: solo `cumplimiento` con MFA saca de `congelado` (la cuarta barrera es `guard_unfreeze`)."""

        def build(conn: Connection, now: datetime) -> list[NewTransition]:
            row, target, _ = self._checked(conn, model_id, action, actor)
            assert row is not None
            return [
                NewTransition(
                    ENTITY_MODEL,
                    model_id,
                    row["state"],
                    target,
                    actor_json(actor, now, auth_time),
                    {
                        "entry_type": "frozen_resolution",
                        "model_version_id": model_id,
                        "payload": {"action": action, "justification": justification},
                    },
                    {"op": "resolution", "action": action},
                    justification=justification,
                )
            ]

        return self._complete(self._begin(build))

    def freeze(self, actor: Actor, model_id: str, context: FreezeContext) -> Result:
        """BR-U4-15: aplica `congelado` y recalcula `serving-config` en la misma transaccion, antes del evento.

        Descarta, en esa misma transaccion, las transiciones pendientes de la version y su unidad completa, con su
        `transicion_descartada` (despues del `freeze` en la cadena). El evento se escribe despues: si el registro cae, el
        modelo queda congelado igual y el reconciliador lo reintenta (`FreezeEventPending`).
        """
        with self.pools.tx() as conn, conn.transaction():
            _lock(conn)
            now = self.clock()
            row, _, _ = self._checked(conn, model_id, "freeze", actor)
            assert row is not None
            if context.model_version_id != model_id:
                raise ConflictState("freeze_context_mismatch")
            freeze_id = uuid.uuid4()
            entry = {
                "entry_type": "freeze",
                "model_version_id": model_id,
                "payload": {
                    "freeze_id": str(freeze_id),
                    "frozen_at": now,
                    "context_package": context,
                },
            }
            doomed = conn.execute(
                "SELECT * FROM transitions WHERE entity_type = %s AND entity_id = %s AND status = 'pendiente_registro' "
                "AND kind = 'cambio_estado'",
                (ENTITY_MODEL, model_id),
            ).fetchall()
            units = [r["unit_id"] for r in doomed if r["unit_id"] is not None]
            if units:
                doomed = conn.execute(
                    "SELECT * FROM transitions WHERE status = 'pendiente_registro' AND kind = 'cambio_estado' AND "
                    "(unit_id = ANY(%s) OR (entity_type = %s AND entity_id = %s)) ORDER BY transition_id",
                    (units, ENTITY_MODEL, model_id),
                ).fetchall()
            frozen = NewTransition(
                ENTITY_MODEL,
                model_id,
                "activo",
                "congelado",
                actor_json(actor, now),
                entry,
                {"op": "none"},
                transition_id=freeze_id,
            )
            _insert(conn, frozen, now, uuid.uuid4().hex)
            conn.execute("SELECT set_config('vectra.freeze', %s, true)", (str(freeze_id),))
            conn.execute(
                "UPDATE model_versions SET state = 'congelado', updated_at = %s WHERE model_version_id = %s",
                (now, model_id),
            )
            self._discard(conn, doomed, "freeze", now, depends_on=freeze_id)
            recompute_serving_config(conn, now)
        written = False
        try:
            self.send(freeze_id, self.pools.tx)
            written = self.finish(freeze_id, self.pools.tx) == "confirmada"
        except (DependencyUnavailable, ConflictState):
            pass  # el modelo queda congelado igual; el reconciliador reintenta el evento
        return Result((freeze_id,), "congelado", event_written=written)

    # --- operaciones de politica (BR-U4-10, 11) -------------------------------------------------------------------------------

    @staticmethod
    def _require_cro(actor: Actor) -> None:
        if actor.kind != "user" or actor.role != Role.CRO or actor.acr != MFA:
            raise Forbidden("actor_not_allowed")

    def propose_policy(
        self, actor: Actor, policy_version_id: str, draft: PolicyDraft, *, auth_time: datetime | None = None
    ) -> Result:
        self._require_cro(actor)

        def build(conn: Connection, now: datetime) -> list[NewTransition]:
            if _policy_row(conn, policy_version_id) is not None:
                raise ConflictState("policy_exists")
            return [
                NewTransition(
                    ENTITY_POLICY,
                    policy_version_id,
                    NO_STATE,
                    "propuesta",
                    actor_json(actor, now, auth_time),
                    _policy_event(policy_version_id, "propuesta"),
                    {"op": "policy_propose", "policy": draft.model_dump(mode="json"), "proposed_by": actor.id},
                )
            ]

        return self._complete(self._begin(build))

    def approve_policy(self, actor: Actor, policy_version_id: str, *, auth_time: datetime | None = None) -> Result:
        """Cuatro ojos y activacion como una sola unidad: la nueva `activa` y la anterior `historica` (BR-U4-11)."""

        def build(conn: Connection, now: datetime) -> list[NewTransition]:
            proposed = _policy_row(conn, policy_version_id)
            if proposed is None:
                raise ConflictState("policy_not_found")
            active = conn.execute("SELECT * FROM policies WHERE state = 'activa'").fetchone()
            try:
                activation = approve_policy(
                    policy_version_of(proposed), actor, None if active is None else policy_version_of(active)
                )
            except ConflictState:
                if _has_pending(conn, ENTITY_POLICY, policy_version_id):
                    raise ConflictState(REASON_TRANSITION_PENDING) from None
                raise
            who = actor_json(actor, now, auth_time)
            unit = uuid.uuid4() if activation.superseded is not None else None
            plan = [
                NewTransition(
                    ENTITY_POLICY,
                    policy_version_id,
                    "propuesta",
                    "activa",
                    who,
                    _policy_event(policy_version_id, "activada"),
                    {"op": "policy_activate", "approved_by": actor.id},
                    unit_id=unit,
                )
            ]
            if activation.superseded is not None:
                old = activation.superseded.policy_version_id
                plan.append(
                    NewTransition(
                        ENTITY_POLICY,
                        old,
                        "activa",
                        "historica",
                        who,
                        _policy_event(old, "historica"),
                        {"op": "policy_supersede"},
                        unit_id=unit,
                    )
                )
            return plan

        return self._complete(self._begin(build))

    def reject_policy(
        self, actor: Actor, policy_version_id: str, justification: str, *, auth_time: datetime | None = None
    ) -> Result:
        self._require_cro(actor)

        def build(conn: Connection, now: datetime) -> list[NewTransition]:
            state = entity_state(conn, ENTITY_POLICY, policy_version_id)
            if state != "propuesta":
                if state is not None and _has_pending(conn, ENTITY_POLICY, policy_version_id):
                    raise ConflictState(REASON_TRANSITION_PENDING)
                raise ConflictState("policy_not_proposed")
            return [
                NewTransition(
                    ENTITY_POLICY,
                    policy_version_id,
                    "propuesta",
                    "rechazada",
                    actor_json(actor, now, auth_time),
                    _policy_event(policy_version_id, "rechazada"),
                    {"op": "policy_reject", "justification": justification},
                    justification=justification,
                )
            ]

        return self._complete(self._begin(build))


def bias_actor() -> Actor:
    """La identidad que puede `freeze` (BR-U4-04)."""
    return Actor("service", BIAS_JOB)
