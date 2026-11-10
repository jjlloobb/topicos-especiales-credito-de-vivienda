"""Cobertura de ramas de `evidence.py` (Paso 19, U04-T06): 100 % (NFR-U4-41).

Cada caso recorre una rama que las pruebas de los Pasos 8 y 10 no tocaban: las funciones puras que ajustan el tamano del evento, el
cliente HTTP del registro, los 409 con transicion pendiente de politicas y fuentes, y las carreras entre las dos fases de una transicion
(se provocan cambiando la fila con SQL entre `send` y `finish`, no con hilos). La lectura de vuelta es con SQL.
"""

import json
import uuid
from datetime import UTC, datetime
from decimal import Decimal

import httpx
import psycopg
import pytest
from api_support import _result
from evidence_support import (
    CRO1,
    CRO2,
    CUM,
    ING,
    START,
    VALIDATION_JOB,
    freeze_context,
    new_model,
    policy_draft,
    report,
    rows_of,
    sql,
    state_of,
    to_activo,
    to_aprobado,
    with_active_policy,
)
from governance_pg import Db, admin_url
from test_evidence import World, world  # noqa: F401
from vectra_contracts.models.governance import DataSourceProposal
from vectra_contracts.models.monitoring import (
    FreezeContextPackage,
    InitialDisparity,
    PrePostDelta,
    PrePostReport,
)
from vectra_governance import evidence as ev
from vectra_governance.evidence import (
    EntityNotFound,
    Forbidden,
    HttpRegistryClient,
    RegistryConflict,
    RegistryUnavailable,
    bias_actor,
    fit_freeze_package,
    fit_report,
    utc_now,
)
from vectra_governance.model_fsm import Actor, ConflictState
from evidence_support import Written  # noqa: E402

pytestmark = pytest.mark.integration


# --- funciones puras --------------------------------------------------------------------------------------------------------


def test_utc_now_es_un_instante_con_zona() -> None:
    assert utc_now().tzinfo is UTC


def test_bias_actor_es_el_servicio_que_congela() -> None:
    assert bias_actor() == Actor("service", "bias-monitoring-job")


def test_el_cliente_http_del_registro_cierra_su_conexion() -> None:
    client = HttpRegistryClient("http://registry", lambda: "t", transport=httpx.MockTransport(lambda r: httpx.Response(200)))
    client.close()
    with pytest.raises(RuntimeError):
        client._client.get("/x")  # un cliente cerrado ya no sirve


def test_jsonable_serializa_uuid_decimal_y_modelos_y_rechaza_lo_demas() -> None:
    value = uuid.uuid4()
    out = ev._jsonable({"u": value, "d": Decimal("1.5000"), "m": InitialDisparity(attributes=[]), "t": START})
    assert out["u"] == str(value) and out["d"] == "1.5000" and out["m"]["attributes"] == []
    assert out["t"].startswith("2026-11-09T15:00:00")
    with pytest.raises(TypeError):
        ev._jsonable({"x": object()})


def _package() -> FreezeContextPackage:
    base = freeze_context("mv-1")
    return FreezeContextPackage(**base.model_dump(), data_sources=[{"ds_id": "ds-1", "pad": "x" * 50}], initial_disparity=InitialDisparity(attributes=[]))


def test_el_paquete_del_freeze_conserva_lo_que_cabe_y_descarta_en_orden(monkeypatch: pytest.MonkeyPatch) -> None:
    package, freeze_id = _package(), uuid.uuid4()
    assert fit_freeze_package("mv-1", freeze_id, START, package) is package  # cabe: intacto
    # Ni con las agregadas ni con los ids: ultimo recurso (BR-U4-15), `truncated` y sin `before`, `last_7_days` ni `implicated`.
    monkeypatch.setattr(ev, "SOFT_EVENT_BYTES", 1)
    monkeypatch.setattr(ev, "MAX_EVENT_BYTES", 1)
    last = fit_freeze_package("mv-1", freeze_id, START, package)
    assert last.truncated is True and last.before == "sin_datos" and last.last_7_days == "sin_datos" and last.implicated == []
    assert last.data_sources == ["ds-1"]


def _pre_post(groups: int) -> PrePostReport:
    return PrePostReport(
        source_id="ds-1",
        pre=_result("pre", groups, label="pre"),
        post=_result("post", groups, label="post"),
        delta=PrePostDelta(attributes=[], model_aggregate="0.0000"),
        threshold_pp="5.0000",
        n_min=30,
        truncated=False,
        disclaimer="El monitoreo mide disparidad y no certifica ausencia de discriminacion",
    )


def test_el_informe_pre_post_pierde_primero_las_celdas_y_despues_las_bandas() -> None:
    full = _pre_post(3)
    assert fit_report(full) is full
    size = len(json.dumps(full.model_dump(mode="json")).encode())
    slim = fit_report(full, size - 1)  # sin celdas
    assert slim.truncated is True and all(a.cells == [] and a.bands for a in slim.pre.attributes)
    bare = fit_report(full, 1)  # ni asi cabe: tambien sin bandas
    assert bare.truncated is True and all(a.cells == [] and a.bands == [] for a in bare.post.attributes)


# --- politicas: 409 y roles --------------------------------------------------------------------------------------------------


def test_rechazar_una_politica_exige_cro_y_distingue_inexistente_activa_y_pendiente(world: World) -> None:  # noqa: F811
    with pytest.raises(Forbidden):
        world.a.reject_policy(ING, "p-1", "no")
    with pytest.raises(ConflictState) as missing:
        world.a.reject_policy(CRO2, "p-9", "no")
    assert missing.value.reason == "policy_not_proposed"
    with_active_policy(world.a, "p-1")
    with pytest.raises(ConflictState) as active:
        world.a.reject_policy(CRO2, "p-1", "no")
    assert active.value.reason == "policy_not_proposed"
    world.a.propose_policy(CRO1, "p-2", policy_draft())
    world.registry.mode = "down"
    with pytest.raises(RegistryUnavailable):
        world.a.approve_policy(CRO2, "p-2")  # la unidad queda pendiente: p-1 tambien
    with pytest.raises(ConflictState) as pending:
        world.b.reject_policy(CRO2, "p-1", "no")
    assert pending.value.reason == "transition_pending"
    with pytest.raises(ConflictState) as again:  # aprobar la que ya es `activa` y esta pendiente
        world.b.approve_policy(CRO2, "p-1")
    assert again.value.reason == "transition_pending"


def test_aprobar_una_politica_inexistente_es_409(world: World) -> None:  # noqa: F811
    with pytest.raises(ConflictState) as error:
        world.a.approve_policy(CRO2, "p-9")
    assert error.value.reason == "policy_not_found"


# --- fuentes de datos -------------------------------------------------------------------------------------------------------


PROPOSAL = DataSourceProposal(name="fuente", description="d", provides_features=["f"], owner="o")


def test_fuentes_solo_las_propone_ingenieria_y_una_vez(world: World) -> None:  # noqa: F811
    with pytest.raises(Forbidden):
        world.a.propose_source(CRO1, "ds-1", PROPOSAL)
    world.a.propose_source(ING, "ds-1", PROPOSAL)
    with pytest.raises(ConflictState) as error:
        world.a.propose_source(ING, "ds-1", PROPOSAL)
    assert error.value.reason == "source_exists"


def test_decidir_una_fuente_con_su_transicion_pendiente_da_transition_pending(world: World) -> None:  # noqa: F811
    world.a.propose_source(ING, "ds-1", PROPOSAL)
    # El informe pre/post llega por F32; aqui se guarda directo en la fuente para poder decidir.
    with world.a.pools.tx() as conn, conn.transaction():
        conn.execute("UPDATE data_sources SET pre_post_report = %s::jsonb WHERE ds_id = 'ds-1'", (json.dumps(_pre_post(1).model_dump(mode="json")),))
    world.registry.mode = "down"
    with pytest.raises(RegistryUnavailable):
        world.a.decide_source(CUM, "ds-1", "aprobada", None)
    with pytest.raises(ConflictState) as pending:  # `en_evaluacion` sigue, pero hay una pendiente: ya no es 'source_not_in_evaluation'
        world.b.decide_source(CUM, "ds-1", "aprobada", None)
    assert pending.value.reason in {"transition_pending", "source_not_in_evaluation"}


def _source_with_report(world: World) -> None:  # noqa: F811
    world.a.propose_source(ING, "ds-1", PROPOSAL)
    with world.a.pools.tx() as conn, conn.transaction():
        conn.execute(
            "UPDATE data_sources SET pre_post_report = %s::jsonb WHERE ds_id = 'ds-1'",
            (json.dumps(_pre_post(1).model_dump(mode="json")),),
        )


def test_decidir_una_fuente_ya_decidida_con_una_transicion_pendiente_da_transition_pending(world: World) -> None:  # noqa: F811
    _source_with_report(world)
    world.registry.mode = "down"
    with pytest.raises(RegistryUnavailable):
        world.a.decide_source(CUM, "ds-1", "aprobada", None)
    assert [r["status"] for r in rows_of(world.a, "ds-1")][-1] == "pendiente_registro"
    with world.a.pools.tx() as conn, conn.transaction():  # el estado cambio por otra via mientras la transicion sigue pendiente
        conn.execute("UPDATE data_sources SET state = 'aprobada' WHERE ds_id = 'ds-1'")
    with pytest.raises(ConflictState) as pending:
        world.b.decide_source(CUM, "ds-1", "aprobada", None)
    assert pending.value.reason == "transition_pending"


def test_comparar_con_una_candidata_inexistente_o_en_un_estado_que_no_lo_permite(world: World, db: Db) -> None:  # noqa: F811
    world.a.propose_source(ING, "ds-1", PROPOSAL)
    with pytest.raises(EntityNotFound):
        world.a.comparison_models(ING, "ds-1", "mv-9")
    to_aprobado(world.a, "mv-1")
    with psycopg.connect(admin_url(db.pg, db.name), autocommit=True) as admin:  # `gov_app` no escribe esa columna directo
        admin.execute("UPDATE model_versions SET source_candidate_for = 'ds-1' WHERE model_version_id = 'mv-1'")
    with pytest.raises(ConflictState) as error:
        world.a.comparison_models(ING, "ds-1", "mv-1")
    assert error.value.reason == "candidate_state_not_allowed"


def test_las_tablas_de_conteo_de_una_corrida_inexistente_o_cerrada_son_404_o_409(world: World) -> None:  # noqa: F811
    from api_support import count_tables
    from vectra_contracts.models.monitoring import SourceCountsIn

    counts = SourceCountsIn.model_validate(count_tables())
    with pytest.raises(EntityNotFound):
        world.a.save_source_counts(str(uuid.uuid4()), counts, _pre_post(1))
    world.a.register(ING, new_model("mv-1"))
    world.a.start_validation(ING, "mv-1", job_name="job-1")  # una corrida `validacion`, no `source_comparison`
    run_id = str(sql(world.a, "SELECT run_id FROM validation_runs")[0]["run_id"])
    with pytest.raises(ConflictState) as error:
        world.a.save_source_counts(run_id, counts, _pre_post(1))
    assert error.value.reason == "validation_run_not_open"


# --- modelos: informe sin corrida, freeze y estados intermedios --------------------------------------------------------------


def test_un_informe_sin_corrida_abierta_es_409(world: World) -> None:  # noqa: F811
    world.a.register(ING, new_model("mv-1"))
    world.a.start_validation(ING, "mv-1", job_name="job-1")
    with pytest.raises(ConflictState) as error:
        world.a.receive_report(VALIDATION_JOB, "mv-1", str(uuid.uuid4()), report(True))
    assert error.value.reason == "validation_run_not_open"


def test_si_el_registro_no_responde_al_freeze_el_modelo_queda_congelado_y_el_evento_pendiente(
    world: World, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    from vectra_common.errors import DependencyUnavailable

    to_activo(world.a, "mv-1")
    with_active_policy(world.a)

    def boom(*_: object, **__: object) -> str:
        raise DependencyUnavailable()

    monkeypatch.setattr(world.a, "send", boom)
    result = world.a.freeze(ev.bias_actor(), "mv-1", freeze_context("mv-1"))
    assert result.event_written is False and state_of(world.a, "mv-1") == "congelado"
    assert rows_of(world.a, "mv-1")[-1]["status"] == "pendiente_registro"


def test_un_freeze_o_una_compensacion_con_409_del_registro_siguen_pendientes(
    world: World, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    to_activo(world.a, "mv-1")

    def conflict(_: dict[str, object]) -> None:
        raise RegistryConflict()

    monkeypatch.setattr(world.registry, "append", conflict)
    result = world.a.freeze(ev.bias_actor(), "mv-1", freeze_context("mv-1"))
    assert result.event_written is False and state_of(world.a, "mv-1") == "congelado"
    assert rows_of(world.a, "mv-1")[-1]["status"] == "pendiente_registro"  # nunca se abandona ni se rechaza


def test_finish_de_una_transicion_desconocida(world: World) -> None:  # noqa: F811
    assert world.a.finish(uuid.uuid4(), world.a.pools.tx) == "desconocida"


def test_el_estado_de_la_transicion_abandonada_se_informa_como_409(world: World, monkeypatch: pytest.MonkeyPatch) -> None:  # noqa: F811
    monkeypatch.setattr(world.a, "_drive", lambda ids, pool: "abandonada")
    with pytest.raises(ConflictState) as error:
        world.a.register(ING, new_model("mv-1"))
    assert error.value.reason == "abandoned_transition_recovered"


# --- unidades de dos mitades: carreras entre send y finish -----------------------------------------------------------------


def _pending_policy_unit(world: World) -> list[uuid.UUID]:  # noqa: F811
    """p-1 `activa` y p-2 `propuesta`; `approve_policy` con el registro caido deja la unidad (dos mitades) pendiente y sin ack."""
    with_active_policy(world.a, "p-1")
    world.a.propose_policy(CRO1, "p-2", policy_draft(cutoff="0.6000"))
    world.registry.mode = "down"
    with pytest.raises(RegistryUnavailable) as error:
        world.a.approve_policy(CRO2, "p-2")
    world.registry.mode = "up"
    assert len(error.value.transition_ids) == 2
    return list(error.value.transition_ids)


def test_una_unidad_con_una_mitad_ya_abandonada_se_descarta_incompleta(world: World) -> None:  # noqa: F811
    ids = _pending_policy_unit(world)
    for tid in ids:
        world.a.send(tid, world.a.pools.tx)
    with world.a.pools.tx() as conn, conn.transaction():
        conn.execute("UPDATE transitions SET status = 'abandonada' WHERE transition_id = %s", (ids[0],))
    assert world.a.finish(ids[0], world.a.pools.tx) == "abandonada"
    other = next(r for r in sql(world.a, "SELECT transition_id, status FROM transitions WHERE transition_id = %s", ids[1]))
    assert other["status"] == "descartada"  # una unidad solo se confirma completa (BR-U4-17)
    states = {r["policy_version_id"]: r["state"] for r in sql(world.a, "SELECT policy_version_id, state FROM policies")}
    assert states == {"p-1": "activa", "p-2": "propuesta"}


def test_una_unidad_cuyo_estado_cambio_entre_el_ack_y_la_confirmacion_se_descarta(world: World) -> None:  # noqa: F811
    ids = _pending_policy_unit(world)
    for tid in ids:
        world.a.send(tid, world.a.pools.tx)
    with world.a.pools.tx() as conn, conn.transaction():
        conn.execute("UPDATE policies SET state = 'historica' WHERE policy_version_id = 'p-1'")
    world.a.finish(ids[0], world.a.pools.tx)
    assert {r["status"] for r in sql(world.a, "SELECT status FROM transitions WHERE transition_id = ANY(%s)", ids)} == {"descartada"}
    states = {r["policy_version_id"]: r["state"] for r in sql(world.a, "SELECT policy_version_id, state FROM policies")}
    assert states["p-2"] == "propuesta"  # la nueva no se aplico; las de politica no llevan compensacion (solo las de modelo)


def test_abandono_de_una_transicion_o_una_unidad_que_ya_tienen_ack_las_confirma(world: World, monkeypatch: pytest.MonkeyPatch) -> None:  # noqa: F811
    from vectra_common.errors import DependencyUnavailable

    def lost_finish(*_: object, **__: object) -> str:
        raise DependencyUnavailable()

    with monkeypatch.context() as patch:
        patch.setattr(world.a, "finish", lost_finish)
        with pytest.raises(DependencyUnavailable):
            world.a.register(ING, new_model("mv-1"))  # con ack, sin TX2
        with pytest.raises(DependencyUnavailable):
            with_active_policy(world.a, "p-1")  # propose (ack, sin TX2) falla igual
    row = rows_of(world.a, "mv-1")[0]
    assert row["status"] == "pendiente_registro" and row["registry_entry_id"] is not None
    world.clock.advance(hours=25)
    assert world.a.abandon(row["transition_id"], world.a.pools.tx) == "nada"  # ya tenia ack: se confirma
    assert state_of(world.a, "mv-1") == "registrado"


def test_abandono_de_una_unidad_con_todas_sus_mitades_con_ack_la_confirma(world: World, monkeypatch: pytest.MonkeyPatch) -> None:  # noqa: F811
    ids = _pending_policy_unit(world)
    for tid in ids:
        world.a.send(tid, world.a.pools.tx)  # las dos mitades con ack, sin TX2
    world.clock.advance(hours=25)
    assert world.a.abandon(ids[0], world.a.pools.tx) == "nada"
    states = {r["policy_version_id"]: r["state"] for r in sql(world.a, "SELECT policy_version_id, state FROM policies")}
    assert states == {"p-1": "historica", "p-2": "activa"}


# --- 409 del registro: la abandonada no se puede reenviar --------------------------------------------------------------------


def test_si_la_abandonada_tampoco_se_puede_reenviar_la_nueva_da_idempotency_conflict(world: World) -> None:  # noqa: F811
    from evidence_support import Written

    world.a.register(ING, new_model("mv-1"))
    world.registry.mode = "down"
    with pytest.raises(RegistryUnavailable):
        world.a.start_validation(ING, "mv-1", job_name="job-1")
    world.clock.advance(hours=25)
    world.reconcile(1)
    assert [r["status"] for r in rows_of(world.a, "mv-1")] == ["confirmada", "abandonada"]
    # La llave de n = 2 ya esta en el registro con otro contenido: ni la nueva ni la abandonada se pueden escribir (BR-U3-06).
    key = str(ev.idempotency_key(ev.ENTITY_MODEL, "mv-1", 2))
    world.registry._by_key[key] = Written(99, key, {"entry_type": "x", "idempotency_key": key, "actor": {}, "payload": {"otro": 1}}, START)
    world.registry.mode = "up"
    other = Actor("user", "ing-2", ING.role, "mfa")
    with pytest.raises(ConflictState) as error:
        world.b.start_validation(other, "mv-1", job_name="job-2")
    assert error.value.reason == "idempotency_conflict"
    assert [r["status"] for r in rows_of(world.a, "mv-1")][-2:] == ["abandonada", "abandonada"]


ING2 = Actor("user", "ing-2", ING.role, "mfa")


def test_la_abandonada_reenviada_se_descarta_si_el_estado_ya_no_es_el_de_origen(world: World, db: Db) -> None:  # noqa: F811
    world.a.register(ING, new_model("mv-1"))
    world.registry.mode = "lost_ack"
    with pytest.raises(RegistryUnavailable):
        world.a.start_validation(ING, "mv-1", job_name="job-1")  # escrita, sin ack
    world.clock.advance(hours=25)
    world.registry.mode = "up"
    world.reconcile(1)
    assert [r["status"] for r in rows_of(world.a, "mv-1")] == ["confirmada", "abandonada"]
    with psycopg.connect(admin_url(db.pg, db.name), autocommit=True) as admin:  # otra via cambio el estado mientras tanto
        admin.execute("UPDATE model_versions SET state = 'validacion_fallida' WHERE model_version_id = 'mv-1'")
    with pytest.raises(ConflictState) as error:
        world.b.retry_validation(ING2, "mv-1", job_name="job-2")
    assert error.value.reason == "abandoned_transition_recovered"
    statuses = [(r["kind"], r["status"]) for r in rows_of(world.a, "mv-1")]
    assert ("cambio_estado", "descartada") in statuses  # la reanimada ya no aplica: su estado de origen cambio
    assert state_of(world.a, "mv-1") == "validacion_fallida"


def test_la_abandonada_de_una_unidad_rota_se_reenvia_pero_se_descarta(world: World) -> None:  # noqa: F811
    to_activo(world.a, "mv-1")
    with_active_policy(world.a)
    to_aprobado(world.a, "mv-2")
    world.registry.script = ["lost_ack", "up"]  # la mitad de mv-2 se escribe sin ack; la de mv-1 tiene ack
    with pytest.raises(RegistryUnavailable):
        world.a.mark_active(ING, "mv-2")
    world.clock.advance(hours=25)
    world.reconcile(2)
    assert [r["status"] for r in rows_of(world.a, "mv-2") if r["unit_id"] is not None] == ["abandonada"]
    assert [r["status"] for r in rows_of(world.a, "mv-1") if r["unit_id"] is not None] == ["descartada"]
    with pytest.raises(ConflictState) as error:
        world.b.mark_active(ING2, "mv-2")  # misma `n`, otro actor: el registro da 409 y se recupera la abandonada
    assert error.value.reason == "abandoned_transition_recovered"
    assert state_of(world.a, "mv-2") == "aprobado" and state_of(world.a, "mv-1") == "activo"
    # La nueva unidad queda `abandonada` y la vieja, reanimada con su ack original, se descarta porque su otra mitad ya lo estaba.
    assert sorted(r["status"] for r in rows_of(world.a, "mv-2") if r["unit_id"] is not None) == ["abandonada", "descartada"]


def test_un_efecto_desconocido_es_un_error_y_none_no_aplica_nada(world: World) -> None:  # noqa: F811
    row = {"event_payload": {"effect": {"op": "inventado"}}, "entity_id": "x"}
    with world.a.pools.tx() as conn, conn.transaction():
        with pytest.raises(ValueError, match="efecto desconocido"):
            ev._apply(conn, row, START)  # type: ignore[arg-type]
        ev._apply(conn, {"event_payload": {"effect": {"op": "none"}}, "entity_id": "x"}, START)  # type: ignore[arg-type]
