"""Migraciones de `governance-db` (Paso 2 del plan de U4): una prueba por viñeta de la aceptacion, con SQL real contra el contenedor."""

import uuid

import psycopg
import pytest
from governance_pg import MIGRATOR, Db
from psycopg import errors
from psycopg.types.json import Jsonb

pytestmark = pytest.mark.integration

SHA = "a" * 64
ROLES = ("gov_app", "gov_archiver", MIGRATOR)
HISTORY = ("model_versions", "policies", "data_sources", "transitions")


def key(entity_type: str, entity_id: str, n: int) -> uuid.UUID:
    """BR-U4-17: UUIDv5(`entity_type:entity_id`, n). La calcula el servicio; aqui, el mismo calculo."""
    return uuid.uuid5(uuid.NAMESPACE_URL, f"{entity_type}:{entity_id}:{n}")


def add_model(conn: psycopg.Connection[tuple[object, ...]], model_id: str, state: str = "registrado") -> None:
    conn.execute(
        "INSERT INTO model_versions (model_version_id, state, artifact_uri, artifact_format, artifact_sha256, explainer_uri, "
        "explainer_sha256, inference_service, manifest_uri, manifest_sha256, feature_dictionary_version, feature_dictionary, "
        "feature_spec, registered_by) VALUES (%s, %s, 'u', 'onnx', %s, 'e', %s, %s, 'm', %s, '1', %s, %s, 'ing')",
        (model_id, state, SHA, SHA, "isvc-" + model_id[-8:], SHA, Jsonb({}), Jsonb({})),
    )


def add_policy(
    conn: psycopg.Connection[tuple[object, ...]], policy_id: str, state: str = "propuesta"
) -> None:
    conn.execute(
        "INSERT INTO policies (policy_version_id, cutoff, low_confidence_threshold, channel_rules, normative, state, proposed_by) "
        "VALUES (%s, 0.5, 0.6, %s, %s, %s, 'cro')",
        (policy_id, Jsonb({}), Jsonb([]), state),
    )


def add_source(conn: psycopg.Connection[tuple[object, ...]], ds_id: str) -> None:
    conn.execute(
        "INSERT INTO data_sources (ds_id, name, owner, proposed_by) VALUES (%s, 'n', 'o', 'ing')", (ds_id,)
    )


def add_transition(
    conn: psycopg.Connection[tuple[object, ...]],
    entity_type: str,
    entity_id: str,
    n: int,
    status: str = "pendiente_registro",
    *,
    from_state: str = "congelado",
    to_state: str = "activo",
    actor: dict[str, str] | None = None,
    kind: str = "cambio_estado",
    transition_id: uuid.UUID | None = None,
    idempotency_key: uuid.UUID | None = None,
) -> uuid.UUID:
    tid = transition_id or uuid.uuid4()
    conn.execute(
        "INSERT INTO transitions (transition_id, entity_type, entity_id, transition_number, idempotency_key, from_state, to_state, "
        "actor, kind, status, event_payload, correlation_id, confirmed_at) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'c', CASE WHEN %s = 'confirmada' THEN now() END)",
        (
            tid,
            entity_type,
            entity_id,
            n,
            idempotency_key or key(entity_type, entity_id, n),
            from_state,
            to_state,
            Jsonb(actor or {"kind": "user", "sub": "u1", "role": "cumplimiento"}),
            kind,
            status,
            Jsonb({}),
            status,
        ),
    )
    return tid


def unfreeze(db: Db, model_id: str, resolution: uuid.UUID | str | None, new_state: str = "activo") -> None:
    """UPDATE como `gov_app` en una transaccion que fija `vectra.frozen_resolution` (lo que hara el handler de Bloque D)."""
    with db.as_role("gov_app") as conn, conn.transaction():
        if resolution is not None:
            conn.execute("SELECT set_config('vectra.frozen_resolution', %s, true)", (str(resolution),))
        conn.execute(
            "UPDATE model_versions SET state = %s WHERE model_version_id = %s", (new_state, model_id)
        )


def state_of(db: Db, model_id: str) -> str:
    return str(db.query("SELECT state FROM model_versions WHERE model_version_id = %s", model_id)[0][0])


# --- transitions: indice parcial de `n` -------------------------------------------------------------------------------------


def test_descartada_reserva_el_n(db: Db) -> None:
    with db.as_role("gov_app") as conn:
        add_model(conn, "mv-1")
        add_transition(conn, "model_version", "mv-1", 5, "descartada")
        with pytest.raises(errors.UniqueViolation):
            add_transition(conn, "model_version", "mv-1", 5)


def test_abandonada_libera_el_n(db: Db) -> None:
    with db.as_role("gov_app") as conn:
        add_model(conn, "mv-1")
        first = add_transition(conn, "model_version", "mv-1", 5, "abandonada")
        second = add_transition(
            conn, "model_version", "mv-1", 5
        )  # misma llave: BR-U4-17 reenvia la abandonada
    assert first != second
    rows = db.query(
        "SELECT status FROM transitions WHERE entity_id = 'mv-1' AND transition_number = 5 ORDER BY status"
    )
    assert rows == [("abandonada",), ("pendiente_registro",)]


def test_el_indice_parcial_de_transitions_esta_en_pg_indexes(db: Db) -> None:
    definition = str(
        db.query("SELECT indexdef FROM pg_indexes WHERE indexname = 'transitions_entity_n'")[0][0]
    )
    assert "UNIQUE" in definition and "(entity_type, entity_id, transition_number)" in definition
    assert "WHERE (status <> 'abandonada'::text)" in definition


def test_llaves_distintas_entre_politica_y_fuente_con_el_mismo_entity_id_y_n(db: Db) -> None:
    with db.as_role("gov_app") as conn:
        add_policy(conn, "x-1")
        add_source(conn, "x-1")
        add_transition(conn, "policy", "x-1", 3, from_state="propuesta", to_state="activa")
        add_transition(conn, "data_source", "x-1", 3, from_state="propuesta", to_state="en_evaluacion")
    rows = db.query(
        "SELECT entity_type, idempotency_key FROM transitions WHERE entity_id = 'x-1' AND transition_number = 3"
    )
    assert len(rows) == 2
    assert len({r[1] for r in rows}) == 2
    assert {r[1] for r in rows} == {key("policy", "x-1", 3), key("data_source", "x-1", 3)}


def test_dos_pendientes_de_la_misma_politica_con_el_mismo_n_violan_el_indice(db: Db) -> None:
    with db.as_role("gov_app") as conn:
        add_policy(conn, "p-1")
        add_transition(conn, "policy", "p-1", 1, from_state="propuesta", to_state="activa")
        with pytest.raises(errors.UniqueViolation):
            add_transition(conn, "policy", "p-1", 1, from_state="propuesta", to_state="rechazada")


def test_la_compensacion_no_cambia_estado_ni_existe_fuera_de_modelos(db: Db) -> None:
    with db.as_role("gov_app") as conn:
        add_model(conn, "mv-1")
        add_transition(
            conn, "model_version", "mv-1", 1, kind="compensacion", from_state="activo", to_state="activo"
        )
        with pytest.raises(errors.CheckViolation):
            add_transition(
                conn,
                "model_version",
                "mv-1",
                2,
                kind="compensacion",
                from_state="activo",
                to_state="inactivo",
            )
        add_policy(conn, "p-1")
        with pytest.raises(errors.CheckViolation):
            add_transition(
                conn, "policy", "p-1", 1, kind="compensacion", from_state="activa", to_state="activa"
            )


# --- una sola version viva y una sola politica activa -----------------------------------------------------------------------


def test_dos_versiones_activo_violan_el_indice(db: Db) -> None:
    with db.as_role("gov_app") as conn:
        add_model(conn, "mv-1", "activo")
        with pytest.raises(errors.UniqueViolation):
            add_model(conn, "mv-2", "activo")


def test_activo_y_congelado_tampoco_conviven(db: Db) -> None:
    with db.as_role("gov_app") as conn:
        add_model(conn, "mv-1", "congelado")
        with pytest.raises(errors.UniqueViolation):
            add_model(conn, "mv-2", "activo")
        add_model(conn, "mv-3", "inactivo")


def test_dos_politicas_activa_violan_el_indice(db: Db) -> None:
    with db.as_role("gov_app") as conn:
        add_policy(conn, "p-1", "activa")
        with pytest.raises(errors.UniqueViolation):
            add_policy(conn, "p-2", "activa")
        add_policy(conn, "p-3", "historica")


# --- guard_unfreeze / guard_freeze (P-U4-06) --------------------------------------------------------------------------------


def frozen_with_transition(db: Db, model_id: str = "mv-1", **kwargs: object) -> uuid.UUID:
    with db.as_role("gov_app") as conn:
        add_model(conn, model_id, "congelado")
        return add_transition(conn, "model_version", model_id, 1, "confirmada", **kwargs)  # type: ignore[arg-type]


def test_update_directo_congelado_a_activo_falla(db: Db) -> None:
    frozen_with_transition(db)
    with pytest.raises(errors.InsufficientPrivilege, match="guard_unfreeze"):
        unfreeze(db, "mv-1", None)
    assert state_of(db, "mv-1") == "congelado"


def test_variable_fijada_sin_transicion_de_cumplimiento_falla(db: Db) -> None:
    frozen_with_transition(db)
    with pytest.raises(errors.InsufficientPrivilege, match="guard_unfreeze"):
        unfreeze(db, "mv-1", uuid.uuid4())
    assert state_of(db, "mv-1") == "congelado"


def test_resolucion_de_otra_version_falla(db: Db) -> None:
    frozen_with_transition(db, "mv-1")
    with db.as_role("gov_app") as conn:
        # mv-2 es `inactivo` (el indice solo admite una viva) pero tiene una resolucion confirmada de cumplimiento.
        add_model(conn, "mv-2", "inactivo")
        other = add_transition(conn, "model_version", "mv-2", 1, "confirmada")
    with pytest.raises(errors.InsufficientPrivilege, match="guard_unfreeze"):
        unfreeze(db, "mv-1", other)
    assert state_of(db, "mv-1") == "congelado"


@pytest.mark.parametrize(
    ("entity_type", "from_state", "to_state"),
    [("policy", "propuesta", "activa"), ("data_source", "propuesta", "en_evaluacion")],
)
def test_fila_de_politica_o_fuente_con_el_mismo_entity_id_falla(
    db: Db, entity_type: str, from_state: str, to_state: str
) -> None:
    frozen_with_transition(db)
    with db.as_role("gov_app") as conn:
        # La fila lleva el mismo `entity_id` textual y los estados que pide el trigger; solo cambia `entity_type`.
        fake = add_transition(
            conn, entity_type, "mv-1", 1, "confirmada", from_state="congelado", to_state="activo"
        )
    with pytest.raises(errors.InsufficientPrivilege, match="guard_unfreeze"):
        unfreeze(db, "mv-1", fake)
    assert state_of(db, "mv-1") == "congelado"


@pytest.mark.parametrize(
    ("status", "kwargs", "new_state"),
    [
        ("pendiente_registro", {}, "activo"),
        ("confirmada", {"actor": {"kind": "user", "sub": "u", "role": "cro"}}, "activo"),
        ("confirmada", {"kind": "compensacion", "to_state": "congelado"}, "activo"),
        ("confirmada", {"from_state": "activo"}, "activo"),
        ("confirmada", {}, "retirado"),  # la transicion dice `activo` y el UPDATE pide `retirado`
    ],
)
def test_resolucion_con_una_condicion_incumplida_falla(
    db: Db, status: str, kwargs: dict[str, object], new_state: str
) -> None:
    with db.as_role("gov_app") as conn:
        add_model(conn, "mv-1", "congelado")
        tid = add_transition(conn, "model_version", "mv-1", 1, status, **kwargs)  # type: ignore[arg-type]
    with pytest.raises(errors.InsufficientPrivilege, match="guard_unfreeze"):
        unfreeze(db, "mv-1", tid, new_state)
    assert state_of(db, "mv-1") == "congelado"


def test_camino_legitimo_de_guard_unfreeze_pasa(db: Db) -> None:
    tid = frozen_with_transition(db)
    unfreeze(db, "mv-1", tid)
    assert state_of(db, "mv-1") == "activo"


def test_camino_legitimo_a_retirado_pasa(db: Db) -> None:
    tid = frozen_with_transition(db, to_state="retirado")
    unfreeze(db, "mv-1", tid, "retirado")
    assert state_of(db, "mv-1") == "retirado"


def test_investigar_cambia_investigation_solo_con_la_resolucion(db: Db) -> None:
    tid = frozen_with_transition(db, to_state="congelado")
    with pytest.raises(errors.InsufficientPrivilege, match="guard_unfreeze"), db.as_role("gov_app") as conn:
        conn.execute("UPDATE model_versions SET investigation = true WHERE model_version_id = 'mv-1'")
    with db.as_role("gov_app") as conn, conn.transaction():
        conn.execute("SELECT set_config('vectra.frozen_resolution', %s, true)", (str(tid),))
        conn.execute("UPDATE model_versions SET investigation = true WHERE model_version_id = 'mv-1'")
    assert db.query("SELECT investigation, state FROM model_versions") == [(True, "congelado")]


def test_guard_unfreeze_no_estorba_las_otras_transiciones(db: Db) -> None:
    with db.as_role("gov_app") as conn:
        add_model(conn, "mv-1", "registrado")
        conn.execute("UPDATE model_versions SET state = 'en_validacion' WHERE model_version_id = 'mv-1'")
    assert state_of(db, "mv-1") == "en_validacion"


def freeze(db: Db, model_id: str, transition: uuid.UUID | None) -> None:
    with db.as_role("gov_app") as conn, conn.transaction():
        if transition is not None:
            conn.execute("SELECT set_config('vectra.freeze', %s, true)", (str(transition),))
        conn.execute("UPDATE model_versions SET state = 'congelado' WHERE model_version_id = %s", (model_id,))


def test_guard_freeze_rechaza_sin_la_transicion_de_bias_monitoring(db: Db) -> None:
    with db.as_role("gov_app") as conn:
        add_model(conn, "mv-1", "activo")
        wrong = add_transition(
            conn,
            "model_version",
            "mv-1",
            1,
            from_state="activo",
            to_state="congelado",
            actor={"kind": "user", "sub": "u1", "role": "cumplimiento"},
        )
    with pytest.raises(errors.InsufficientPrivilege, match="guard_freeze"):
        freeze(db, "mv-1", None)
    with pytest.raises(errors.InsufficientPrivilege, match="guard_freeze"):
        freeze(db, "mv-1", uuid.uuid4())
    with pytest.raises(errors.InsufficientPrivilege, match="guard_freeze"):
        freeze(db, "mv-1", wrong)
    assert state_of(db, "mv-1") == "activo"


def test_guard_freeze_exige_la_version_de_la_transicion(db: Db) -> None:
    with db.as_role("gov_app") as conn:
        add_model(conn, "mv-1", "activo")
        add_model(conn, "mv-2", "inactivo")
        other = add_transition(
            conn,
            "model_version",
            "mv-2",
            1,
            from_state="activo",
            to_state="congelado",
            actor={"kind": "service", "sub": "bias-monitoring-job", "role": "service"},
        )
    with pytest.raises(errors.InsufficientPrivilege, match="guard_freeze"):
        freeze(db, "mv-1", other)


def test_camino_legitimo_de_guard_freeze_pasa(db: Db) -> None:
    with db.as_role("gov_app") as conn:
        add_model(conn, "mv-1", "activo")
        tid = add_transition(
            conn,
            "model_version",
            "mv-1",
            1,
            from_state="activo",
            to_state="congelado",
            actor={"kind": "service", "sub": "bias-monitoring-job", "role": "service"},
        )
    freeze(db, "mv-1", tid)
    assert state_of(db, "mv-1") == "congelado"


# --- validation_runs.mode ---------------------------------------------------------------------------------------------------


def test_la_migracion_deja_mode_validacion_en_las_filas_existentes(empty_db: Db) -> None:
    empty_db.migrate("0001")
    assert not empty_db.query(
        "SELECT 1 FROM information_schema.columns WHERE table_name = 'validation_runs' AND column_name = 'mode'"
    )
    with empty_db.connect() as conn:
        add_model(conn, "mv-1")
        for _ in range(2):
            conn.execute(
                "INSERT INTO validation_runs (run_id, model_version_id, job_name, deadline_at) "
                "VALUES (%s, 'mv-1', 'job', now() + interval '2 hours')",
                (uuid.uuid4(),),
            )
    empty_db.migrate("head")
    assert (
        empty_db.query("SELECT mode, source_id, baseline_version_id FROM validation_runs")
        == [("validacion", None, None)] * 2
    )


def insert_run(
    conn: psycopg.Connection[tuple[object, ...]], mode: str, source: str | None, baseline: str | None
) -> None:
    conn.execute(
        "INSERT INTO validation_runs (run_id, model_version_id, job_name, deadline_at, mode, source_id, baseline_version_id) "
        "VALUES (%s, 'mv-2', 'job', now() + interval '2 hours', %s, %s, %s)",
        (uuid.uuid4(), mode, source, baseline),
    )


def test_source_comparison_exige_fuente_y_version_base(db: Db) -> None:
    with db.as_role("gov_app") as conn:
        add_source(conn, "ds-1")
        add_model(conn, "mv-1", "activo")
        add_model(conn, "mv-2")
        with pytest.raises(errors.CheckViolation, match="validation_runs_mode_source"):
            insert_run(conn, "source_comparison", None, "mv-1")
        with pytest.raises(errors.CheckViolation, match="validation_runs_mode_source"):
            insert_run(conn, "source_comparison", "ds-1", None)
        with pytest.raises(errors.CheckViolation, match="validation_runs_mode_source"):
            insert_run(conn, "validacion", "ds-1", None)
        insert_run(conn, "source_comparison", "ds-1", "mv-1")
        insert_run(conn, "validacion", None, None)
    assert db.query("SELECT mode FROM validation_runs ORDER BY mode") == [
        ("source_comparison",),
        ("validacion",),
    ]


def test_mode_desconocido_viola_el_check(db: Db) -> None:
    with db.as_role("gov_app") as conn:
        add_model(conn, "mv-2")
        with pytest.raises(errors.CheckViolation):
            insert_run(conn, "otro", None, None)


# --- grants ------------------------------------------------------------------------------------------------------------------


def test_gov_archiver_no_puede_cambiar_state(db: Db) -> None:
    with db.as_role("gov_app") as conn:
        add_model(conn, "mv-1", "activo")
    with db.as_role("gov_archiver") as conn:
        with pytest.raises(errors.InsufficientPrivilege):
            conn.execute("UPDATE model_versions SET state = 'inactivo' WHERE model_version_id = 'mv-1'")
        conn.execute(
            "UPDATE model_versions SET archived_uri = 's3://x', archived_at = now() WHERE model_version_id = 'mv-1'"
        )
    assert state_of(db, "mv-1") == "activo"
    assert db.query("SELECT archived_uri FROM model_versions") == [("s3://x",)]
    columns = db.query(
        "SELECT column_name FROM information_schema.column_privileges WHERE grantee = 'gov_archiver' "
        "AND table_name = 'model_versions' AND privilege_type = 'UPDATE' ORDER BY 1"
    )
    assert columns == [("archived_at",), ("archived_uri",)]


def test_gov_archiver_lee_versiones_y_transiciones_y_nada_mas(db: Db) -> None:
    with db.as_role("gov_archiver") as conn:
        conn.execute("SELECT count(*) FROM model_versions")
        conn.execute("SELECT count(*) FROM transitions")
        for table in ("policies", "data_sources", "serving_config"):
            with pytest.raises(errors.InsufficientPrivilege):
                conn.execute(f"SELECT count(*) FROM {table}")
        with pytest.raises(errors.InsufficientPrivilege):
            conn.execute("UPDATE transitions SET status = 'confirmada'")


@pytest.mark.parametrize("role", ROLES)
def test_ningun_rol_tiene_delete_sobre_las_tablas_de_historia(db: Db, role: str) -> None:
    for table in (*HISTORY, "validation_runs", "serving_config"):
        rows = db.query(
            "SELECT has_table_privilege(%s, %s, 'DELETE'), has_table_privilege(%s, %s, 'TRUNCATE')",
            role,
            table,
            role,
            table,
        )
        assert rows == [(False, False)], f"{role} puede borrar {table}"


def test_gov_migrator_es_el_dueno_y_aun_asi_no_borra(db: Db) -> None:
    owners = {r[0] for r in db.query("SELECT tableowner FROM pg_tables WHERE schemaname = 'public'")}
    assert owners == {MIGRATOR}
    with db.as_role(MIGRATOR) as conn, pytest.raises(errors.InsufficientPrivilege):
        conn.execute("DELETE FROM transitions")


def test_gov_app_no_cambia_el_contenido_de_una_transicion(db: Db) -> None:
    with db.as_role("gov_app") as conn:
        add_model(conn, "mv-1")
        add_transition(conn, "model_version", "mv-1", 1)
        conn.execute("UPDATE transitions SET status = 'confirmada', confirmed_at = now()")
        with pytest.raises(errors.InsufficientPrivilege):
            conn.execute("UPDATE transitions SET event_payload = '{}'::jsonb")
        with pytest.raises(errors.InsufficientPrivilege):
            conn.execute("UPDATE model_versions SET archived_uri = 'x'")


def test_la_migracion_no_siembra_politicas_ni_versiones(db: Db) -> None:
    for table in ("policies", "model_versions", "data_sources", "transitions", "validation_runs"):
        assert db.query(f"SELECT count(*) FROM {table}") == [(0,)]
    assert db.query("SELECT id, model_version_id, policy_version_id, etag FROM serving_config") == [
        (1, None, None, None)
    ]


# --- NOTIFY serving_config ----------------------------------------------------------------------------------------------------


def test_notify_llega_con_el_etag_solo_al_confirmar(db: Db) -> None:
    etag = "sha256:" + "cd" * 32
    with db.connect() as listener, db.connect() as writer:
        listener.execute("LISTEN serving_config")
        with writer.transaction():
            writer.execute("UPDATE serving_config SET etag = %s WHERE id = 1", (etag,))
            assert list(listener.notifies(timeout=0.5)) == []  # antes de confirmar no llega nada
        received = []
        for notice in listener.notifies(timeout=5):
            received.append(notice)
            break
    assert [(n.channel, n.payload) for n in received] == [("serving_config", etag)]


def test_notify_no_llega_si_la_transaccion_se_revierte(db: Db) -> None:
    with db.connect() as listener, db.connect() as writer:
        listener.execute("LISTEN serving_config")
        with pytest.raises(RuntimeError, match="rollback"), writer.transaction():
            writer.execute("UPDATE serving_config SET etag = 'x' WHERE id = 1")
            raise RuntimeError("rollback")
        assert list(listener.notifies(timeout=1, stop_after=1)) == []


# --- estructura (lectura de vuelta) ------------------------------------------------------------------------------------------


def test_estructura_declarada(db: Db) -> None:
    tables = {r[0] for r in db.query("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")}
    assert tables >= {
        "model_versions",
        "transitions",
        "validation_runs",
        "policies",
        "data_sources",
        "serving_config",
        "alembic_version",
    }
    triggers = {r[0] for r in db.query("SELECT tgname FROM pg_trigger WHERE NOT tgisinternal")}
    assert triggers == {"guard_unfreeze", "guard_freeze", "notify_serving_config"}
    partial = {
        r[0]
        for r in db.query(
            "SELECT indexname FROM pg_indexes WHERE schemaname = 'public' AND indexdef LIKE '%UNIQUE%WHERE%'"
        )
    }
    assert partial == {"model_versions_one_live", "policies_one_active", "transitions_entity_n"}
    cols = {
        r[0]
        for r in db.query(
            "SELECT column_name FROM information_schema.columns WHERE table_name = 'model_versions'"
        )
    }
    assert {"archived_uri", "archived_at", "source_candidate_for", "investigation"} <= cols
    assert "pre_post_report" in {
        r[0]
        for r in db.query(
            "SELECT column_name FROM information_schema.columns WHERE table_name = 'data_sources'"
        )
    }
