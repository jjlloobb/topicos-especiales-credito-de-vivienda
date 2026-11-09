"""Paso 8 (U04-T03): evidencia en dos fases, reconciliador y barridos, contra PostgreSQL real (Testcontainers), con 2 replicas.

Un caso por viñeta de la aceptacion del Paso 8 del plan (salvo la rama `source_comparison` del barrido, diferida con US-306).
La lectura de vuelta es con SQL sobre `transitions`, `model_versions`, `validation_runs` y `serving_config`, y sobre la cadena
del doble del registro (`FakeRegistry`), no con los valores de retorno.
"""

import threading
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date, timedelta

import pytest
from evidence_support import (
    BIAS,
    CRO1,
    CRO2,
    CUM,
    ING,
    START,
    FakeJobs,
    FakeRegistry,
    SimClock,
    freeze_context,
    make_service,
    new_model,
    normative,
    policy_draft,
    rows_of,
    sql,
    state_of,
    to_activo,
    to_aprobado,
    with_active_policy,
)
from governance_pg import Db
from vectra_common.metrics import REGISTRY
from vectra_contracts.catalog import Role
from vectra_governance.background import Background
from vectra_governance.evidence import Evidence, RegistryUnavailable
from vectra_governance.k8s_jobs import JobInfo
from vectra_governance.model_fsm import Actor, ConflictState

pytestmark = pytest.mark.integration


@dataclass
class World:
    clock: SimClock
    registry: FakeRegistry
    jobs: FakeJobs
    a: Evidence
    b: Evidence
    bg_a: Background
    bg_b: Background

    def reconcile(self, times: int = 3) -> None:
        for _ in range(times):
            self.bg_a.reconcile_once()
            self.bg_b.reconcile_once()


@pytest.fixture
def world(db: Db) -> Iterator[World]:
    clock = SimClock()
    registry = FakeRegistry(clock)
    jobs = FakeJobs()
    a = make_service(db, registry, clock, "a")
    b = make_service(db, registry, clock, "b")
    yield World(clock, registry, jobs, a, b, Background(a, jobs), Background(b, jobs))
    a.pools.close()
    b.pools.close()


def statuses(svc: Evidence, entity_id: str) -> list[tuple[int, str, str]]:
    return [(r["n"], r["kind"], r["status"]) for r in rows_of(svc, entity_id)]


def gauge(name: str) -> float:
    value = REGISTRY.get_sample_value(name)
    assert value is not None
    return value


# --- ninguna transicion cambia el estado sin ack ----------------------------------------------------------------------------


def test_sin_ack_no_hay_efecto_y_el_reconciliador_la_confirma(world: World) -> None:
    world.registry.mode = "down"
    with pytest.raises(RegistryUnavailable):
        world.a.register(ING, new_model("mv-1"))
    # Lectura de vuelta: ninguna fila de la version, la transicion pendiente y la cadena vacia.
    assert state_of(world.a, "mv-1") is None
    assert statuses(world.a, "mv-1") == [(1, "cambio_estado", "pendiente_registro")]
    assert world.registry.chain == []

    world.registry.mode = "up"
    world.reconcile()
    assert state_of(world.b, "mv-1") == "registrado"
    row = rows_of(world.b, "mv-1")[0]
    assert row["status"] == "confirmada" and row["registry_entry_id"] == "0"
    assert world.registry.names("mv-1") == ["registrado"]


def test_ningun_evento_se_duplica_con_el_ack_perdido_y_los_reintentos(world: World) -> None:
    world.registry.mode = "lost_ack"  # escribe y falla: el servicio no sabe que se escribio
    with pytest.raises(RegistryUnavailable):
        world.a.register(ING, new_model("mv-1"))
    assert state_of(world.a, "mv-1") is None  # sin ack, sin efecto
    assert len(world.registry.chain) == 1
    for _ in range(3):
        world.reconcile(1)  # el registro sigue perdiendo el ack: se reintenta con la misma llave
    assert len(world.registry.chain) == 1 and state_of(world.a, "mv-1") is None
    world.registry.mode = "up"
    world.reconcile()
    assert len(world.registry.chain) == 1  # el reintento devuelve el ack original
    assert state_of(world.b, "mv-1") == "registrado"
    assert statuses(world.a, "mv-1") == [(1, "cambio_estado", "confirmada")]


# --- abandono + transicion nueva con la abandonada ya escrita ----------------------------------------------------------------


def test_abandono_y_transicion_nueva_con_la_abandonada_ya_escrita_da_un_solo_evento(world: World) -> None:
    world.a.register(ING, new_model("mv-1"))
    world.registry.mode = "lost_ack"
    with pytest.raises(RegistryUnavailable):
        world.a.start_validation(ING, "mv-1", job_name="job-1")
    assert world.registry.names("mv-1") == ["registrado", "validacion_iniciada"]  # se escribio; el ack se perdio
    world.clock.advance(hours=25)
    world.registry.mode = "up"
    world.reconcile(1)  # a las 24 h la pendiente queda `abandonada` (BR-U4-17)
    assert statuses(world.a, "mv-1") == [(1, "cambio_estado", "confirmada"), (2, "cambio_estado", "abandonada")]
    assert state_of(world.a, "mv-1") == "registrado"

    other = Actor("user", "ing-2", Role.INGENIERO_RIESGO, "mfa")  # otro contenido, misma `n` y misma llave
    with pytest.raises(ConflictState) as error:
        world.b.start_validation(other, "mv-1", job_name="job-2")
    assert error.value.reason == "abandoned_transition_recovered"

    # Un solo evento para esa `n` y el estado es el de la abandonada (se reenvio con su llave y se confirmo).
    assert world.registry.names("mv-1") == ["registrado", "validacion_iniciada"]
    assert state_of(world.a, "mv-1") == "en_validacion"
    assert statuses(world.a, "mv-1") == [
        (1, "cambio_estado", "confirmada"),
        (2, "cambio_estado", "confirmada"),  # la abandonada, recuperada
        (2, "cambio_estado", "abandonada"),  # la nueva, rechazada
    ]
    runs = sql(world.a, "SELECT job_name, state FROM validation_runs")
    assert [(r["job_name"], r["state"]) for r in runs] == [("job-1", "lanzado")]
    keys = [w.key for w in world.registry.chain]
    assert len(keys) == len(set(keys))


# --- frozen_resolution con el freeze pendiente --------------------------------------------------------------------------------


def test_frozen_resolution_con_el_freeze_pendiente_da_transition_pending(world: World) -> None:
    to_activo(world.a, "mv-1")
    with_active_policy(world.a)
    world.registry.mode = "down"
    result = world.b.freeze(BIAS, "mv-1", freeze_context("mv-1"))
    assert result.event_written is False
    assert state_of(world.a, "mv-1") == "congelado"  # la excepcion de BR-U4-17: aplica sin ack
    before = rows_of(world.a, "mv-1")
    with pytest.raises(ConflictState) as error:
        world.a.frozen_resolution(CUM, "mv-1", "reactivar", "cumple")
    assert error.value.reason == "transition_pending"
    assert rows_of(world.a, "mv-1") == before  # el intento no dejo ninguna fila
    assert state_of(world.a, "mv-1") == "congelado"

    world.registry.mode = "up"
    world.reconcile()
    world.a.frozen_resolution(CUM, "mv-1", "reactivar", "cumple")
    assert state_of(world.a, "mv-1") == "activo"
    # nunca una frozen_resolution antes de su freeze
    assert world.registry.names("mv-1")[-2:] == ["freeze", "frozen_resolution"]


# --- freeze con un mark_active pendiente --------------------------------------------------------------------------------------


def setup_mark_active_in_flight(world: World, mode: str) -> None:
    to_activo(world.a, "mv-1")
    with_active_policy(world.a)
    to_aprobado(world.a, "mv-2")
    world.registry.mode = mode
    with pytest.raises(RegistryUnavailable):
        world.a.mark_active(ING, "mv-2")


def test_freeze_con_un_mark_active_pendiente_descarta_el_par_aunque_llegue_el_ack(world: World) -> None:
    setup_mark_active_in_flight(world, "lost_ack")  # los dos eventos se escribieron, sin ack
    pair = [r for r in rows_of(world.a, "mv-1") + rows_of(world.a, "mv-2") if r["unit_id"] is not None]
    assert [r["status"] for r in pair] == ["pendiente_registro"] * 2
    world.registry.mode = "up"
    world.b.freeze(BIAS, "mv-1", freeze_context("mv-1"))

    assert state_of(world.a, "mv-1") == "congelado"
    assert state_of(world.a, "mv-2") == "aprobado"  # la destino no pasa a `activo`
    assert [r["status"] for r in rows_of(world.a, "mv-2") if r["unit_id"] is not None] == ["descartada"]
    live = sql(world.a, "SELECT model_version_id, state FROM serving_config")
    assert live == [{"model_version_id": "mv-1", "state": "congelado"}]

    world.reconcile()
    world.registry.mode = "lost_ack"
    world.reconcile(1)  # una escritura mas con el ack perdido no cambia nada
    world.registry.mode = "up"
    world.a.finish(pair[0]["transition_id"], world.a.pools.tx)  # y un ack tardio tampoco aplica una descartada
    assert state_of(world.a, "mv-2") == "aprobado"
    assert {r["status"] for r in rows_of(world.a, "mv-2") if r["unit_id"] is not None} == {"descartada"}

    # La cadena: el freeze y despues los `transicion_descartada` (uno por mitad).
    mv1, mv2 = world.registry.names("mv-1"), world.registry.names("mv-2")
    assert mv1[-3:] == ["inactivado", "freeze", "transicion_descartada"]
    assert mv2[-2:] == ["activado", "transicion_descartada"]
    seq = {w.entry["payload"].get("event") or w.entry["entry_type"]: w.seq for w in world.registry.events("mv-1")}
    freeze_seq = seq["freeze"]
    discarded = [w for w in world.registry.chain if w.entry["payload"].get("event") == "transicion_descartada"]
    assert len(discarded) == 2 and all(w.seq > freeze_seq for w in discarded)
    keys = {str(r["idempotency_key"]) for r in pair}
    assert {w.entry["payload"]["details"]["discarded_idempotency_key"] for w in discarded} == keys
    assert {w.entry["payload"]["details"]["reason"] for w in discarded} == {"freeze"}


def test_el_ack_llega_durante_el_freeze_y_la_descartada_no_aplica(world: World) -> None:
    """Carrera: el append de `mark_active` tarda; el `freeze` entra antes de que el ack se guarde y se confirme."""
    to_activo(world.a, "mv-1")
    with_active_policy(world.a)
    to_aprobado(world.a, "mv-2")
    world.registry.latency = 0.5
    outcome: list[BaseException] = []

    def mark_active() -> None:
        try:
            world.a.mark_active(ING, "mv-2")
        except BaseException as error:  # noqa: BLE001
            outcome.append(error)

    thread = threading.Thread(target=mark_active)
    thread.start()
    deadline = START  # espera a que A tenga las dos filas pendientes y este escribiendo
    while not [r for r in rows_of(world.b, "mv-2") if r["status"] == "pendiente_registro"]:
        pass
    world.b.freeze(BIAS, "mv-1", freeze_context("mv-1"))
    thread.join(timeout=30)
    del deadline
    assert len(outcome) == 1 and isinstance(outcome[0], ConflictState)
    assert outcome[0].reason == "transition_discarded"
    assert state_of(world.a, "mv-1") == "congelado" and state_of(world.a, "mv-2") == "aprobado"
    unit = [r for r in rows_of(world.a, "mv-2") if r["unit_id"] is not None]
    assert [r["status"] for r in unit] == ["descartada"]
    assert unit[0]["registry_entry_id"] is not None  # el ack si llego; no aplico nada


# --- una compensacion pendiente mas de 24 h ----------------------------------------------------------------------------------


def test_compensacion_pendiente_mas_de_24_h_no_se_abandona_y_bloquea_la_resolucion(world: World) -> None:
    setup_mark_active_in_flight(world, "lost_ack")
    world.registry.mode = "down"
    world.b.freeze(BIAS, "mv-1", freeze_context("mv-1"))  # el evento freeze tampoco se escribe
    world.clock.advance(hours=30)
    world.reconcile()
    for entity in ("mv-1", "mv-2"):
        assert "abandonada" not in [r["status"] for r in rows_of(world.a, entity)], entity
    comps = sql(world.a, "SELECT status FROM transitions WHERE kind = 'compensacion'")
    assert [c["status"] for c in comps] == ["pendiente_registro"] * 2  # siguen pendientes tras 30 h
    assert gauge("vectra_governance_compensation_events_pending") == 2  # la regla `CompensationEventPending`
    assert gauge("vectra_governance_freeze_events_pending") == 1  # y `FreezeEventPending`
    with pytest.raises(ConflictState) as error:
        world.a.frozen_resolution(CUM, "mv-1", "reactivar", "cumple")
    assert error.value.reason == "transition_pending"

    world.registry.mode = "up"
    world.reconcile()
    assert gauge("vectra_governance_compensation_events_pending") == 0
    assert gauge("vectra_governance_freeze_events_pending") == 0
    world.a.frozen_resolution(CUM, "mv-1", "reactivar", "cumple")  # ahora si: la compensacion ya esta escrita
    assert state_of(world.a, "mv-1") == "activo"
    mv1 = world.registry.names("mv-1")
    assert mv1.index("freeze") < mv1.index("transicion_descartada") < mv1.index("frozen_resolution")


# --- barrido de validaciones vencidas -----------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("info", "reason", "run_state"),
    [
        (JobInfo(deadline_exceeded=True), "deadline", "timeout"),
        (JobInfo(failed=True), "failed", "fallido"),
        (None, "sin informe", "timeout"),
    ],
)
def test_validacion_vencida_pasa_a_validacion_fallida_con_el_motivo_del_job(
    world: World, info: JobInfo | None, reason: str, run_state: str
) -> None:
    world.a.register(ING, new_model("mv-1"))
    world.a.start_validation(ING, "mv-1", job_name="job-1")
    world.jobs.infos["job-1"] = info
    assert world.bg_a.sweep_validations_once() == 0  # todavia dentro del plazo de 2 h
    assert state_of(world.a, "mv-1") == "en_validacion"

    world.clock.advance(hours=2, minutes=1)
    assert world.bg_a.sweep_validations_once() == 1
    assert world.bg_b.sweep_validations_once() == 0  # la otra replica no la procesa otra vez
    assert state_of(world.b, "mv-1") == "validacion_fallida"
    assert sql(world.a, "SELECT state FROM validation_runs") == [{"state": run_state}]
    event = world.registry.events("mv-1")[-1]
    assert event.entry["payload"]["event"] == "validacion_fallida"
    assert event.entry["payload"]["details"]["reason"] == reason
    assert event.entry["actor"] == {"kind": "system", "id": "governance-service"}
    assert world.registry.names("mv-1").count("validacion_fallida") == 1


def test_el_barrido_ignora_las_corridas_source_comparison(world: World) -> None:
    """La rama `source_comparison` queda diferida con US-306 (Q-6): el barrido no toca esas corridas."""
    world.a.register(ING, new_model("mv-1"))
    world.a.register(ING, new_model("mv-2"))
    world.a.start_validation(ING, "mv-1", job_name="job-1")
    with world.a.pools.tx() as conn, conn.transaction():
        conn.execute(
            "INSERT INTO data_sources (ds_id, name, owner, proposed_by, state) VALUES ('ds-1', 'n', 'o', 'p', 'en_evaluacion')"
        )
        conn.execute(
            "INSERT INTO validation_runs (run_id, model_version_id, job_name, state, mode, source_id, baseline_version_id, "
            "started_at, deadline_at) VALUES (%s, 'mv-2', 'job-sc', 'lanzado', 'source_comparison', 'ds-1', 'mv-1', %s, %s)",
            (uuid.uuid4(), START, START + timedelta(hours=2)),
        )
    world.clock.advance(hours=3)
    assert world.bg_a.sweep_validations_once() == 1  # solo la de `validacion`
    runs = {r["job_name"]: r["state"] for r in sql(world.a, "SELECT job_name, state FROM validation_runs")}
    assert runs == {"job-1": "timeout", "job-sc": "lanzado"}
    assert state_of(world.a, "mv-2") == "registrado"


# --- politica: la activacion es una sola unidad -------------------------------------------------------------------------------


def test_activacion_de_politica_es_una_unidad_y_sin_ack_no_cambia_nada(world: World) -> None:
    with_active_policy(world.a, "p-1")
    to_activo(world.a, "mv-1")
    world.a.propose_policy(CRO1, "p-2", policy_draft(cutoff="0.6000"))
    etag = sql(world.a, "SELECT etag FROM serving_config")
    world.registry.mode = "down"
    with pytest.raises(RegistryUnavailable):
        world.a.approve_policy(CRO2, "p-2")
    states = {r["policy_version_id"]: r["state"] for r in sql(world.a, "SELECT policy_version_id, state FROM policies")}
    assert states == {"p-1": "activa", "p-2": "propuesta"}
    assert sql(world.a, "SELECT etag FROM serving_config") == etag
    with pytest.raises(ConflictState) as error:  # una sola pendiente por entidad
        world.b.reject_policy(CRO2, "p-2", "no")
    assert error.value.reason == "transition_pending"

    world.registry.mode = "up"
    world.reconcile()
    states = {r["policy_version_id"]: r["state"] for r in sql(world.a, "SELECT policy_version_id, state FROM policies")}
    assert states == {"p-1": "historica", "p-2": "activa"}  # las dos mitades, juntas
    assert sql(world.a, "SELECT policy_version_id FROM serving_config") == [{"policy_version_id": "p-2"}]
    assert world.registry.names("p-2") == ["propuesta", "activada"]
    assert world.registry.names("p-1")[-1] == "historica"


def test_la_unidad_de_politica_se_abandona_completa(world: World) -> None:
    with_active_policy(world.a, "p-1")
    to_activo(world.a, "mv-1")
    world.a.propose_policy(CRO1, "p-2", policy_draft())
    world.registry.mode = "down"
    with pytest.raises(RegistryUnavailable):
        world.a.approve_policy(CRO2, "p-2")
    world.clock.advance(hours=25)
    world.reconcile(1)
    pending = sql(world.a, "SELECT entity_id, status FROM transitions WHERE unit_id IS NOT NULL ORDER BY entity_id")
    assert pending == [{"entity_id": "p-1", "status": "abandonada"}, {"entity_id": "p-2", "status": "abandonada"}]
    states = {r["policy_version_id"]: r["state"] for r in sql(world.a, "SELECT policy_version_id, state FROM policies")}
    assert states == {"p-1": "activa", "p-2": "propuesta"}
    world.registry.mode = "up"
    world.a.approve_policy(CRO2, "p-2")  # la repite: `n` libre otra vez
    assert sql(world.a, "SELECT policy_version_id FROM serving_config") == [{"policy_version_id": "p-2"}]


def test_mark_active_abandonado_con_una_mitad_con_ack_deja_esa_mitad_descartada_con_su_compensacion(
    world: World,
) -> None:
    to_activo(world.a, "mv-1")
    with_active_policy(world.a)
    to_aprobado(world.a, "mv-2")
    world.registry.script = ["up", "down"]  # la mitad de mv-2 tiene ack; la de mv-1 no
    with pytest.raises(RegistryUnavailable):
        world.a.mark_active(ING, "mv-2")
    half2 = [r for r in rows_of(world.a, "mv-2") if r["unit_id"] is not None][0]
    half1 = [r for r in rows_of(world.a, "mv-1") if r["unit_id"] is not None][0]
    assert half2["registry_entry_id"] is not None and half1["registry_entry_id"] is None
    assert state_of(world.a, "mv-2") == "aprobado" and state_of(world.a, "mv-1") == "activo"  # una mitad con ack no aplica sola

    world.clock.advance(hours=25)
    world.reconcile(2)
    assert [r["status"] for r in rows_of(world.a, "mv-1") if r["unit_id"] is not None] == ["abandonada"]
    mv2 = [(r["kind"], r["status"]) for r in rows_of(world.a, "mv-2") if r["n"] >= 5]
    assert mv2 == [("cambio_estado", "descartada"), ("compensacion", "confirmada")]
    assert state_of(world.a, "mv-2") == "aprobado" and state_of(world.a, "mv-1") == "activo"
    last = world.registry.events("mv-2")[-1]
    assert last.entry["payload"]["event"] == "transicion_descartada"
    assert last.entry["payload"]["details"]["reason"] == "abandono"


# --- serving-config sigue a las transiciones confirmadas -------------------------------------------------------------------------


def test_serving_config_se_recalcula_con_mark_active_y_freeze(world: World) -> None:
    with_active_policy(world.a, draft=policy_draft(normative=[normative(date(2026, 1, 1))]))
    assert sql(world.a, "SELECT model_version_id FROM serving_config") == [{"model_version_id": None}]  # sin version servible
    to_activo(world.a, "mv-1")
    first = sql(world.a, "SELECT model_version_id, state, etag FROM serving_config")[0]
    assert (first["model_version_id"], first["state"]) == ("mv-1", "activo")
    to_aprobado(world.a, "mv-2")
    world.a.mark_active(ING, "mv-2")
    second = sql(world.a, "SELECT model_version_id, state, etag FROM serving_config")[0]
    assert (second["model_version_id"], second["state"]) == ("mv-2", "activo") and second["etag"] != first["etag"]
    assert state_of(world.a, "mv-1") == "inactivo"
    world.b.freeze(BIAS, "mv-2", freeze_context("mv-2"))
    third = sql(world.a, "SELECT model_version_id, state, etag FROM serving_config")[0]
    assert (third["model_version_id"], third["state"]) == ("mv-2", "congelado") and third["etag"] != second["etag"]
    with pytest.raises(ConflictState) as error:
        world.a.mark_active(ING, "mv-1")  # BR-U4-02: un modelo congelado no se reemplaza por promocion
    assert error.value.reason == "active_version_frozen"
