"""Soporte de las pruebas del Bloque D (Pasos 8 y 9): reloj simulado, doble del registro de U3, doble del Job y fabricas.

El **doble del registro** reproduce la semantica de `POST /v1/entries` de U3 (`decision-registry/src/vectra_registry/append.py`),
sin copiar su codigo: la misma llave con el mismo contenido (los campos de negocio de BR-U3-06) devuelve el ack original; la
misma llave con otro contenido da 409; el actor de gobierno se valida como BR-U3-16; y puede fallar al azar, antes de escribir
(`down`) o despues de escribir con el ack perdido (`lost_ack`).
"""

import hashlib
import json
import random
import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any

import psycopg
from governance_pg import Db, admin_url, create_database, drop_database, url
from psycopg.rows import dict_row
from pydantic import ValidationError
from vectra_contracts.catalog import Role
from vectra_contracts.models.explanation import RegistryAck
from vectra_contracts.models.governance import (
    ModelRegistration,
    NormativeParams,
    PolicyDraft,
    ValidationReport,
)
from vectra_contracts.models.monitoring import (
    AffectedVolume,
    DisparityResult,
    FreezeContext,
    InitialDisparity,
)
from vectra_contracts.models.registry import RegistryEntryIn
from vectra_governance.background import Background
from vectra_governance.evidence import Evidence, NewModel, RegistryConflict, RegistryUnavailable
from vectra_governance.k8s_jobs import JobInfo
from vectra_governance.model_fsm import Actor
from vectra_governance.pools import Pools

START = datetime(2026, 11, 9, 15, 0, tzinfo=UTC)  # 10:00 en Bogota

ING = Actor("user", "ing-1", Role.INGENIERO_RIESGO, "mfa")
CRO1 = Actor("user", "cro-1", Role.CRO, "mfa")
CRO2 = Actor("user", "cro-2", Role.CRO, "mfa")
CUM = Actor("user", "cum-1", Role.CUMPLIMIENTO, "mfa")
BIAS = Actor("service", "bias-monitoring-job")
VALIDATION_JOB = Actor("service", "model-validation-job")


class SimClock:
    """Reloj simulado: las pruebas lo adelantan (24 h de abandono, plazos de 2 h, medianoche de Bogota)."""

    def __init__(self, now: datetime = START) -> None:
        self.current = now

    def __call__(self) -> datetime:
        return self.current

    def advance(self, **delta: float) -> None:
        self.current += timedelta(**delta)


# --- doble del registro (semantica de U3) ---------------------------------------------------------------------------------


MAX_ENTRY_BYTES = 64 * 1024  # BR-U3-07: el registro rechaza mas de 64 KiB
BUSINESS_FIELDS = ("entry_type", "idempotency_key", "actor", "case_id", "model_version_id", "policy_version_id", "payload")


@dataclass
class Written:
    seq: int
    key: str
    entry: dict[str, Any]
    recorded_at: datetime


class FakeRegistry:
    """`append(entry)` como el de U3. `mode`: `up`, `down` (no escribe) o `lost_ack` (escribe y falla). Hilo-seguro."""

    def __init__(self, clock: SimClock) -> None:
        self.clock = clock
        self.mode = "up"
        self.chain: list[Written] = []
        self.calls = 0
        self.script: list[str] = []  # modos para las proximas llamadas (se consume uno por llamada)
        self.latency = 0.0  # segundos que tarda cada llamada (fuera del lock del doble)
        self.rng: random.Random | None = None
        self.p_down = 0.0
        self.p_lost = 0.0
        self.largest = 0  # el cuerpo mas grande que recibio (BR-U4-15: nunca mas de 64 KiB)
        self._by_key: dict[str, Written] = {}
        self._lock = threading.Lock()

    def flaky(self, seed: int, p_down: float, p_lost: float) -> None:
        """Falla al azar (con semilla): `p_down` antes de escribir y `p_lost` despues de escribir (ack perdido)."""
        self.rng = random.Random(seed)  # noqa: S311
        self.p_down, self.p_lost = p_down, p_lost

    def _business(self, entry: dict[str, Any]) -> str:
        return json.dumps({k: entry[k] for k in BUSINESS_FIELDS if entry.get(k) is not None}, sort_keys=True)

    @staticmethod
    def _check_actor(entry: dict[str, Any]) -> None:
        """BR-U3-16 (la misma regla de `check_governance_actor` de U3): un evento de gobierno lo escribe una persona con rol o, por excepcion, un servicio o el sistema."""
        actor = entry["actor"]
        if actor["kind"] == "user":
            assert actor.get("role") is not None and actor.get("acr") and actor.get("auth_time"), actor
            return
        payload = entry["payload"]
        event = payload.get("event")
        allowed: set[tuple[str, str]] = set()
        if entry["entry_type"] == "freeze":
            allowed.add(("system", "bias-monitoring-job"))
        elif entry["entry_type"] == "model_event":
            if event in ("informe_validacion", "validacion_fallida"):
                allowed.add(("service", "model-validation-job"))
            if event in ("validacion_fallida", "transicion_descartada"):
                allowed.add(("system", "governance-service"))
        assert (actor["kind"], actor["id"]) in allowed, f"actor no permitido por BR-U3-16: {actor} en {entry['entry_type']}"

    def _validate(self, entry: dict[str, Any]) -> None:
        self._check_actor(entry)
        size = len(json.dumps(entry).encode())
        self.largest = max(self.largest, size)
        assert size <= MAX_ENTRY_BYTES, f"el registro rechazaria {size} bytes (BR-U3-07: {MAX_ENTRY_BYTES})"
        try:
            RegistryEntryIn.model_validate_json(json.dumps(entry))
        except ValidationError as error:  # un defecto del servicio, no un 4xx esperado
            raise AssertionError(f"el servicio envio una entrada invalida: {error}") from error

    def append(self, entry: dict[str, Any]) -> RegistryAck:
        if self.latency:
            time.sleep(self.latency)
        with self._lock:
            self.calls += 1
            self._validate(entry)
            mode = self.script.pop(0) if self.script else self.mode
            if mode == "up" and self.rng is not None:
                roll = self.rng.random()
                mode = "down" if roll < self.p_down else "lost_ack" if roll < self.p_down + self.p_lost else "up"
            if mode == "down":
                raise RegistryUnavailable()
            key = entry["idempotency_key"]
            held = self._by_key.get(key)
            if held is None:
                held = Written(len(self.chain), key, entry, self.clock())
                self.chain.append(held)
                self._by_key[key] = held
            elif self._business(held.entry) != self._business(entry):
                raise RegistryConflict()  # BR-U3-06
            if mode == "lost_ack":
                raise RegistryUnavailable()
            return RegistryAck(registry_entry_id=str(held.seq), seq=held.seq, recorded_at=held.recorded_at)

    # --- lectura de la cadena ---
    def events(self, entity_id: str | None = None) -> list[Written]:
        return [
            w
            for w in self.chain
            if entity_id is None or entity_id in (w.entry.get("model_version_id"), w.entry.get("policy_version_id"))
        ]

    def names(self, entity_id: str) -> list[str]:
        return [
            str(w.entry["payload"].get("event") or w.entry["entry_type"]) for w in self.events(entity_id)
        ]


class FakeJobs:
    """Doble de la lectura del Job (K01 `get`): lo que el barrido consulta para registrar el motivo."""

    def __init__(self) -> None:
        self.infos: dict[str, JobInfo | None] = {}

    def get(self, job_name: str) -> JobInfo | None:
        return self.infos.get(job_name)


# --- fabricas --------------------------------------------------------------------------------------------------------------


def new_model(model_id: str) -> NewModel:
    return NewModel(
        model_version_id=model_id,
        registration=ModelRegistration(
            artifact_uri=f"s3://model-store/{model_id}/model.onnx",
            artifact_format="onnx",
            artifact_sha256="a" * 64,
            explainer_uri=f"s3://model-store/{model_id}/explainer.json",
            explainer_sha256="b" * 64,
            manifest_uri=f"s3://model-store/{model_id}/manifest.json",
            manifest_sha256="c" * 64,
        ),
        inference_service="isvc-" + hashlib.sha256(model_id.encode()).hexdigest()[:8],
        feature_dictionary_version="fd-1",
        feature_dictionary={"features": []},
        feature_spec={"features": []},
    )


def report(passed: bool = True) -> ValidationReport:
    return ValidationReport.model_validate(
        {
            "auc_roc": "0.9000",
            "auc_target": "0.8500",
            "auc_meets_target": True,
            "initial_disparity": InitialDisparity(attributes=[]).model_dump(mode="json"),
            "sync_check": {
                "passed": passed,
                "predictor_version": "p",
                "explainer_version": "p" if passed else "q",
                "samples_checked": 10,
                "failure_reason": None if passed else "version_mismatch",
            },
            "dataset_ref": "s3://model-store/validation.csv",
            "disclaimer": "El monitoreo mide disparidad y no certifica ausencia de discriminacion",
        }
    )


def freeze_context(model_id: str, now: datetime = START) -> FreezeContext:
    after = DisparityResult(
        population="modelo",
        model_version_id=model_id,
        window_from=date(2026, 11, 1),
        window_to=date(2026, 11, 8),
        attributes=[],
    )
    return FreezeContext(
        model_version_id=model_id,
        computed_at=now,
        threshold_pp="5.0000",
        n_min=30,
        window_days=30,
        schedule="daily",
        stale_after_s=86400,
        library_version="1",
        window_start=date(2026, 10, 10),
        before="sin_datos",
        after=after,
        last_7_days="sin_datos",
        trigger_attribute="sexo",
        implicated=[],
        affected_volume=AffectedVolume(total=10, favorable=5),
        truncated=False,
    )


def policy_draft(*, cutoff: str = "0.5000", normative: list[NormativeParams] | None = None) -> PolicyDraft:
    return PolicyDraft(
        cutoff=cutoff, low_confidence_threshold="0.2000", channel_rules=[], normative=normative or []
    )


def normative(start: date, end: date | None = None) -> NormativeParams:
    return NormativeParams(
        vis_max_property_value=150_000_000,
        usury_cap_ea="0.2500",
        effective_from=start,
        effective_to=end,
        source_ref="Resolucion 1",
    )


# --- servicio --------------------------------------------------------------------------------------------------------------


def service_dsn(db: Db) -> str:
    return url(db.pg, db.name, "gov_app", "gov_app")


def make_service(
    db: Db, registry: FakeRegistry, clock: SimClock, replica: str = "a", *, warm: bool = True
) -> Evidence:
    pools = Pools(service_dsn(db), replica)
    if warm:
        pools.warm()
    return Evidence(pools, registry, clock)


def to_aprobado(svc: Evidence, model_id: str) -> None:
    svc.register(ING, new_model(model_id))
    svc.start_validation(ING, model_id, job_name=f"job-{model_id}")
    run_id = str(_one(svc, "SELECT run_id FROM validation_runs WHERE model_version_id = %s", model_id))
    svc.receive_report(VALIDATION_JOB, model_id, run_id, report(True))
    svc.approve(CRO1, model_id)


def to_activo(svc: Evidence, model_id: str) -> None:
    to_aprobado(svc, model_id)
    svc.mark_active(ING, model_id)


def with_active_policy(svc: Evidence, policy_id: str = "p-1", draft: PolicyDraft | None = None) -> None:
    svc.propose_policy(CRO1, policy_id, draft or policy_draft())
    svc.approve_policy(CRO2, policy_id)


def _one(svc: Evidence, statement: str, *params: object) -> object:
    with svc.pools.read() as conn:
        row = conn.execute(statement, params).fetchone()  # type: ignore[arg-type]
        conn.rollback()
    assert row is not None
    return next(iter(row.values()))


def sql(svc: Evidence, statement: str, *params: object) -> list[dict[str, Any]]:
    """Lectura de vuelta con SQL real sobre la base de la replica."""
    with svc.pools.read() as conn:
        rows = conn.execute(statement, params).fetchall()  # type: ignore[arg-type]
        conn.rollback()
    return rows


def state_of(svc: Evidence, model_id: str) -> str | None:
    rows = sql(svc, "SELECT state FROM model_versions WHERE model_version_id = %s", model_id)
    return None if not rows else str(rows[0]["state"])


def rows_of(svc: Evidence, entity_id: str) -> list[dict[str, Any]]:
    return sql(
        svc,
        "SELECT transition_number AS n, status, kind, from_state, to_state, unit_id, registry_entry_id, transition_id, "
        "idempotency_key FROM transitions WHERE entity_id = %s ORDER BY transition_number, created_at",
        entity_id,
    )


def wait_for(condition: Callable[[], bool], timeout: float) -> float | None:
    """Los segundos que tardo la condicion, o `None` si no se cumplio en `timeout`."""
    start = time.monotonic()
    while time.monotonic() - start < timeout:
        if condition():
            return time.monotonic() - start
        time.sleep(0.005)
    return None


class Harness:
    """Una base por ejemplo (copia de la plantilla migrada), 2 replicas, el doble del registro y el reloj simulado."""

    def __init__(self, pg: Any, template: str) -> None:
        self.pg = pg
        self.name = "p_" + uuid.uuid4().hex[:12]
        create_database(pg, self.name, template)
        self.db = Db(pg, self.name)
        self.clock = SimClock()
        self.registry = FakeRegistry(self.clock)
        self.jobs = FakeJobs()
        self.services = {
            "a": make_service(self.db, self.registry, self.clock, "a", warm=False),
            "b": make_service(self.db, self.registry, self.clock, "b", warm=False),
        }
        self.background = {name: Background(svc, self.jobs) for name, svc in self.services.items()}
        self.admin = psycopg.connect(admin_url(pg, self.name), row_factory=dict_row, autocommit=True)

    def snapshot(self) -> dict[str, Any]:
        """Lectura de vuelta con SQL real: filas de `transitions`, estados de las entidades y la cadena del doble."""
        q = self.admin.execute
        return {
            "transitions": q(
                "SELECT * FROM transitions ORDER BY entity_type, entity_id, transition_number, created_at, transition_id"
            ).fetchall(),
            "models": {r["model_version_id"]: r for r in q("SELECT * FROM model_versions").fetchall()},
            "policies": {r["policy_version_id"]: r for r in q("SELECT * FROM policies").fetchall()},
            "chain": list(self.registry.chain),
        }

    def close(self) -> None:
        self.admin.close()
        for svc in self.services.values():
            svc.pools.close()
        drop_database(self.pg, self.name)
