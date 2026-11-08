"""Migraciones de `registry-db` contra PostgreSQL real (Paso 2 del plan de U3; US-401).

Un caso (o una familia parametrizada) por viñeta de la aceptación del plan. Cada lectura es SQL real contra el contenedor:
`pg_class`, `information_schema` o las tablas, nunca el código de salida de Alembic.
"""

import hashlib
import json
import uuid
from datetime import UTC, datetime

import psycopg
import pytest
from psycopg import errors, sql

from registry_pg import FINGERPRINT, Db, migrate, u1_roles

pytestmark = pytest.mark.integration

PARTITION_SIZE = 10_800_000
EXPECTED_ROLES = {
    "registry_app",
    "registry_verifier",
    "registry_ondemand",
    "registry_health",
    "registry_migrator",
    "registry_aggregator",
}


def denied(db: Db, role: str, statement: str, *params: object) -> None:
    with db.as_role(role) as conn, pytest.raises(errors.InsufficientPrivilege):
        conn.execute(statement, params or None)  # type: ignore[arg-type]


# --- Los roles de U1 -------------------------------------------------------------------------------------------------------


def test_u1_declara_los_seis_roles_que_usa_el_paso_2() -> None:
    """Si U1 no tiene uno de los roles, el Paso 2 no puede darles grants: la prueba se detiene aquí."""
    assert EXPECTED_ROLES <= set(u1_roles())


def test_registry_health_solo_tiene_pg_monitor(db: Db) -> None:
    members = db.query(
        "SELECT pg_has_role('registry_health', 'pg_monitor', 'member'), "
        "has_table_privilege('registry_health', 'registry_entries', 'SELECT')"
    )
    assert members == [(True, False)]
    denied(db, "registry_health", "SELECT * FROM registry_entries")


# --- Viñeta 1: registry_app ------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE registry_entries SET actor_id = 'x' WHERE seq = 0",
        "DELETE FROM registry_entries WHERE seq = 0",
        "TRUNCATE registry_entries",
    ],
    ids=["update", "delete", "truncate"],
)
def test_registry_app_no_puede_update_delete_ni_truncate(db: Db, statement: str) -> None:
    denied(db, "registry_app", statement)


def test_registry_app_inserta_y_lee(db: Db) -> None:
    seq = db.insert_entry("registry_app")
    with db.as_role("registry_app") as conn:
        assert conn.execute("SELECT count(*) FROM registry_entries WHERE seq = %s", (seq,)).fetchone() == (1,)
        assert conn.execute("SELECT seq FROM registry_head").fetchone() == (seq,)


# --- Viñeta 2: el trigger contra el superusuario ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("statement", "operation"),
    [
        ("UPDATE registry_entries SET actor_id = 'x' WHERE seq = 0", "UPDATE"),
        ("DELETE FROM registry_entries WHERE seq = 0", "DELETE"),
        ("TRUNCATE registry_entries", "TRUNCATE"),
        ("UPDATE registry_entries_default SET actor_id = 'x'", "UPDATE"),
        ("TRUNCATE registry_entries_default", "TRUNCATE"),
    ],
    ids=["update", "delete", "truncate", "update-en-la-particion", "truncate-en-la-particion"],
)
def test_el_trigger_detiene_al_superusuario(db: Db, statement: str, operation: str) -> None:
    db.insert_entry(
        seq=10**12
    )  # una fila en DEFAULT, para que el UPDATE de la particion tenga algo que tocar
    with db.connect() as conn:
        assert conn.execute("SELECT rolsuper FROM pg_roles WHERE rolname = current_user").fetchone() == (
            True,
        )
        with pytest.raises(errors.RaiseException, match=f"solo de anexar.*{operation}"):
            conn.execute(statement)
    assert db.query("SELECT count(*) FROM registry_entries") == [(2,)]


def test_el_trigger_cubre_cada_particion(db: Db) -> None:
    rows = db.query(
        "SELECT c.relname, t.tgname FROM pg_trigger t JOIN pg_class c ON c.oid = t.tgrelid "
        "WHERE NOT t.tgisinternal AND t.tgname LIKE '%%no_truncate' AND c.relname LIKE 'registry_entries%%' ORDER BY 1"
    )
    assert len(rows) == 5  # la madre, tres anos y DEFAULT


# --- Viñeta 3: génesis -----------------------------------------------------------------------------------------------------


def test_existe_una_sola_genesis_con_seq_cero(db: Db) -> None:
    assert db.query("SELECT seq FROM registry_entries WHERE entry_type = 'genesis'") == [(0,)]
    assert db.query("SELECT count(*) FROM registry_entries") == [(1,)]


def test_la_genesis_lleva_su_contenido_y_su_hash(db: Db) -> None:
    [(canonical, prev_hash, entry_hash, actor_kind)] = db.query(
        "SELECT canonical, prev_hash, hash, actor_kind FROM registry_entries WHERE seq = 0"
    )
    assert isinstance(canonical, bytes) and isinstance(prev_hash, bytes) and isinstance(entry_hash, bytes)
    assert prev_hash == bytes(32)
    assert entry_hash == hashlib.sha256(prev_hash + canonical).digest()
    body = json.loads(canonical)
    assert body["seq"] == 0 and body["entry_type"] == "genesis" and actor_kind == "system"
    assert body["payload"]["checkpoint_key_fingerprint"] == FINGERPRINT
    assert (
        body["payload"]["schema_version"] and body["payload"]["contract_version"] == body["contract_version"]
    )
    # JCS: claves ordenadas y sin espacios.
    assert canonical == json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def test_no_se_admite_una_segunda_genesis_ni_otro_tipo_en_seq_cero(db: Db) -> None:
    with db.as_role("registry_app") as conn:
        for entry_type, seq in (("genesis", 1), ("model_event", 0)):
            with pytest.raises((errors.CheckViolation, errors.UniqueViolation)):
                conn.execute(
                    "INSERT INTO registry_entries (seq, idempotency_key, entry_type, actor_kind, actor_id, occurred_at, "
                    "recorded_at, correlation_id, contract_version, canonical, prev_hash, hash) "
                    "VALUES (%s, %s, %s, 'system', 'system', now(), now(), 'c', '0.1.0', %s, %s, %s)",
                    (seq, uuid.uuid4(), entry_type, b"{}", bytes(32), bytes(32)),
                )


def test_la_migracion_sin_huella_de_llave_falla_y_no_deja_nada(pg, roles) -> None:  # type: ignore[no-untyped-def]
    with psycopg.connect(
        f"postgresql://postgres:postgres@{pg.get_container_host_ip()}:{pg.get_exposed_port(5432)}/postgres",
        autocommit=True,
    ) as conn:
        conn.execute(sql.SQL("CREATE DATABASE sin_huella OWNER registry_migrator"))
    with pytest.raises(RuntimeError, match="REGISTRY_CHECKPOINT_KEY_FINGERPRINT"):
        migrate(pg, "sin_huella", fingerprint=None)
    with psycopg.connect(
        f"postgresql://postgres:postgres@{pg.get_container_host_ip()}:{pg.get_exposed_port(5432)}/sin_huella",
        autocommit=True,
    ) as conn:
        assert conn.execute("SELECT to_regclass('registry_entries')").fetchone() == (None,)


def test_aplicar_dos_veces_no_agrega_otra_genesis(pg, db: Db) -> None:  # type: ignore[no-untyped-def]
    migrate(pg, db.name)
    assert db.query("SELECT count(*) FROM registry_entries WHERE entry_type = 'genesis'") == [(1,)]


# --- Viñeta 4: particiones y DEFAULT ---------------------------------------------------------------------------------------


def test_la_tabla_esta_particionada_por_rango_de_seq_con_tres_anos_y_default(db: Db) -> None:
    year = datetime.now(UTC).year
    rows = db.query(
        "SELECT c.relname, pg_get_expr(c.relpartbound, c.oid) FROM pg_inherits i JOIN pg_class c ON c.oid = i.inhrelid "
        "WHERE i.inhparent = 'registry_entries'::regclass ORDER BY 1"
    )
    assert dict(rows) == {
        f"registry_entries_{year}": f"FOR VALUES FROM ('0') TO ('{PARTITION_SIZE}')",
        f"registry_entries_{year + 1}": f"FOR VALUES FROM ('{PARTITION_SIZE}') TO ('{2 * PARTITION_SIZE}')",
        f"registry_entries_{year + 2}": f"FOR VALUES FROM ('{2 * PARTITION_SIZE}') TO ('{3 * PARTITION_SIZE}')",
        "registry_entries_default": "DEFAULT",
    }
    assert db.query(
        "SELECT partstrat FROM pg_partitioned_table WHERE partrelid = 'registry_entries'::regclass"
    ) == [("r",)]


def test_una_fila_fuera_de_rango_cae_en_default(db: Db) -> None:
    year = datetime.now(UTC).year
    for seq, expected in (
        (1, f"registry_entries_{year}"),
        (PARTITION_SIZE - 1, f"registry_entries_{year}"),
        (PARTITION_SIZE, f"registry_entries_{year + 1}"),
        (3 * PARTITION_SIZE - 1, f"registry_entries_{year + 2}"),
        (3 * PARTITION_SIZE, "registry_entries_default"),
        (10**12, "registry_entries_default"),
    ):
        db.insert_entry(seq=seq)
        assert db.query("SELECT tableoid::regclass::text FROM registry_entries WHERE seq = %s", seq) == [
            (expected,)
        ]


# --- Índices y columnas de domain-entities §1 ------------------------------------------------------------------------------


def test_columnas_e_indices_de_registry_entries(db: Db) -> None:
    columns = dict(
        db.query(
            "SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'registry_entries'"
        )
    )
    assert (
        columns["seq"] == "bigint" and columns["idempotency_key"] == "uuid"
    )  # UUIDv5 del checkpoint (P-U3-03)
    assert (
        columns["canonical"] == "bytea"
        and columns["case_id"] == "uuid"
        and columns["recorded_at"] == "timestamp with time zone"
    )
    indexed = {
        row[0]
        for row in db.query(
            "SELECT a.attname FROM pg_index i JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY (i.indkey) "
            "WHERE i.indrelid = 'registry_entries_default'::regclass"
        )
    }
    assert {"seq", "case_id", "idempotency_key", "entry_type", "recorded_at"} <= indexed


def test_idempotency_key_es_unica_en_todas_las_particiones(db: Db) -> None:
    key = uuid.uuid5(uuid.NAMESPACE_URL, "checkpoint:2026-11-08T10:00:00Z")  # forma del UUIDv5 del checkpoint
    db.insert_entry(key=key)
    with pytest.raises(errors.UniqueViolation):
        db.insert_entry(seq=10**12, key=key)  # otra particion


def test_restricciones_de_longitud_de_hash_y_tamano(db: Db) -> None:
    with db.as_role("registry_app") as conn, pytest.raises(errors.CheckViolation):
        conn.execute(
            "INSERT INTO registry_entries (seq, idempotency_key, entry_type, actor_kind, actor_id, occurred_at, recorded_at, "
            "correlation_id, contract_version, canonical, prev_hash, hash) "
            "VALUES (1, %s, 'model_event', 'service', 's', now(), now(), 'c', '0.1.0', %s, %s, %s)",
            (uuid.uuid4(), b"{}", bytes(31), bytes(32)),
        )


# --- Viñeta 5: registry_aggregator y las derivadas -------------------------------------------------------------------------

DAILY_ROW = (
    'INSERT INTO monitoring_daily (population, model_version_id, day, attribute, "group", band, result, decision, count) '
    "VALUES ('modelo', 'm1', '2026-11-08', 'sexo', 'F', 'lt_20', 'favorable', '-', 1)"
)


@pytest.mark.parametrize(
    "statement",
    [
        "INSERT INTO registry_entries (seq, idempotency_key, entry_type, actor_kind, actor_id, occurred_at, recorded_at, "
        "correlation_id, contract_version, canonical, prev_hash, hash) VALUES (1, gen_random_uuid(), 'model_event', 's', 's', "
        "now(), now(), 'c', '0.1.0', '\\x7b7d', '\\x00', '\\x00')",
        "UPDATE registry_entries SET actor_id = 'x'",
        "DELETE FROM registry_entries",
    ],
    ids=["insert", "update", "delete"],
)
def test_registry_aggregator_no_escribe_en_registry_entries(db: Db, statement: str) -> None:
    denied(db, "registry_aggregator", statement)


def test_registry_aggregator_lee_registry_entries(db: Db) -> None:
    with db.as_role("registry_aggregator") as conn:
        assert conn.execute("SELECT count(*) FROM registry_entries").fetchone() == (1,)


def test_registry_aggregator_escribe_en_las_derivadas_pero_sin_truncate(db: Db) -> None:
    with db.as_role("registry_aggregator") as conn:
        conn.execute(DAILY_ROW)
        conn.execute("UPDATE monitoring_daily SET count = 2")
        conn.execute("DELETE FROM monitoring_daily")
        conn.execute(DAILY_ROW)
        conn.execute("UPDATE monitoring_watermark SET last_seq = 5, updated_at = now()")
        with pytest.raises(errors.InsufficientPrivilege):
            conn.execute("TRUNCATE monitoring_daily")
    assert db.query("SELECT count(*) FROM monitoring_daily") == [(1,)]


def test_registry_app_no_escribe_en_monitoring_daily(db: Db) -> None:
    denied(db, "registry_app", DAILY_ROW)


def test_las_derivadas_no_tienen_el_trigger_de_solo_anexar(db: Db) -> None:
    with db.as_role("registry_aggregator") as conn:
        conn.execute(DAILY_ROW)
    with db.connect() as conn:
        conn.execute("UPDATE monitoring_daily SET count = 3")
        conn.execute("TRUNCATE monitoring_daily")  # el dueño las vacía en una reconstrucción (BR-U3-17)


def test_registry_verifier_lee_las_derivadas_salvo_monitoring_case_index(db: Db) -> None:
    with db.as_role("registry_verifier") as conn:
        for table in (
            "monitoring_daily",
            "monitoring_entry_totals",
            "monitoring_invalid",
            "monitoring_watermark",
        ):
            conn.execute(sql.SQL("SELECT * FROM {}").format(sql.Identifier(table)))
    denied(db, "registry_verifier", "SELECT * FROM monitoring_case_index")
    denied(db, "registry_verifier", "UPDATE monitoring_watermark SET last_seq = 9")


def test_las_cinco_tablas_derivadas_y_sus_llaves(db: Db) -> None:
    keys = dict(
        db.query(
            "SELECT tc.table_name, string_agg(kcu.column_name, ',' ORDER BY kcu.ordinal_position) "
            "FROM information_schema.table_constraints tc JOIN information_schema.key_column_usage kcu "
            "ON kcu.constraint_name = tc.constraint_name AND kcu.table_name = tc.table_name "
            "WHERE tc.constraint_type = 'PRIMARY KEY' AND tc.table_name LIKE 'monitoring_%%' GROUP BY 1"
        )
    )
    assert keys == {
        "monitoring_daily": "population,model_version_id,day,attribute,group,band,result,decision",
        "monitoring_entry_totals": "population,model_version_id,day",
        "monitoring_case_index": "case_id",
        "monitoring_invalid": "seq",
        "monitoring_watermark": "id",
    }
    columns = {
        row[0]
        for row in db.query(
            "SELECT column_name FROM information_schema.columns WHERE table_name = 'monitoring_case_index'"
        )
    }
    assert columns == {"case_id", "counted_seq", "evaluated_at", "fixed_by_decision"}
    assert db.query("SELECT id, last_seq FROM monitoring_watermark") == [(1, 0)]


@pytest.mark.parametrize(
    "statement",
    [
        "INSERT INTO monitoring_daily VALUES ('modelo', 'm', '2026-11-08', 'sexo', 'F', 'lt_20', 'favorable', '-', -1)",
        "INSERT INTO monitoring_daily VALUES ('modelo', 'm', '2026-11-08', 'sexo', 'andina', 'lt_20', 'favorable', '-', 1)",
        "INSERT INTO monitoring_daily VALUES ('modelo', 'm', '2026-11-08', 'edad', 'F', 'lt_20', 'favorable', '-', 1)",
        "INSERT INTO monitoring_daily VALUES ('modelo', 'm', '2026-11-08', 'sexo', 'F', 'zz', 'favorable', '-', 1)",
        "INSERT INTO monitoring_daily VALUES ('modelo', 'm', '2026-11-08', 'sexo', 'F', 'lt_20', 'otro', '-', 1)",
        "INSERT INTO monitoring_daily VALUES ('modelo', 'm', '2026-11-08', 'sexo', 'F', 'lt_20', 'favorable', 'sigue', 1)",
        "INSERT INTO monitoring_daily VALUES ('humana', 'm', '2026-11-08', 'sexo', 'F', 'lt_20', 'revision_requerida', 'sigue', 1)",
        "INSERT INTO monitoring_entry_totals VALUES ('modelo', 'm', '2026-11-08', 1, 2)",
        "INSERT INTO monitoring_entry_totals VALUES ('modelo', 'm', '2026-11-08', -1, 0)",
        "INSERT INTO monitoring_watermark VALUES (2, 0, now())",
    ],
    ids=[
        "count-negativo",
        "grupo-de-otro-atributo",
        "atributo-desconocido",
        "banda",
        "resultado",
        "decision-en-modelo",
        "humana-con-revision",
        "invalid-mayor-que-total",
        "total-negativo",
        "watermark-id-2",
    ],
)
def test_los_check_de_las_derivadas(db: Db, statement: str) -> None:
    with db.as_role("registry_aggregator") as conn, pytest.raises(errors.CheckViolation):
        conn.execute(statement)


# --- Viñeta 6: integrity_checks ---------------------------------------------------------------------------------------------

CHECK_INSERT = (
    "INSERT INTO integrity_checks (check_id, mode, requested_by, requested_at, status{extra_cols}) "
    "VALUES (gen_random_uuid(), 'full', 'cro-1', now(), %s{extra_vals})"
)


def insert_check(db: Db, role: str, status: str, **extra: str) -> None:
    columns = "".join(f", {c}" for c in extra)
    values = "".join(f", {v}" for v in extra.values())
    with db.as_role(role) as conn:
        conn.execute(CHECK_INSERT.format(extra_cols=columns, extra_vals=values), (status,))


def test_integrity_checks_tiene_las_columnas_de_domain_entities(db: Db) -> None:
    columns = {
        row[0]
        for row in db.query(
            "SELECT column_name FROM information_schema.columns WHERE table_name = 'integrity_checks'"
        )
    }
    assert columns == {
        "check_id", "mode", "from_seq", "to_seq", "requested_by", "requested_at", "started_at", "finished_at",
        "heartbeat_at", "status", "progress_checked", "progress_total", "report", "reason",
    }  # fmt: skip


def test_dos_filas_pendiente_son_unique_violation(db: Db) -> None:
    insert_check(db, "registry_app", "pendiente")
    with pytest.raises(errors.UniqueViolation):
        insert_check(db, "registry_app", "pendiente")


def test_una_activa_de_cualquier_modo_bloquea_a_otra(db: Db) -> None:
    insert_check(db, "registry_app", "en_curso", started_at="now()", heartbeat_at="now()")
    with pytest.raises(errors.UniqueViolation):
        insert_check(db, "registry_app", "pendiente")


def test_terminada_y_fallida_no_bloquean_a_una_nueva(db: Db) -> None:
    insert_check(db, "registry_app", "terminada", report="'{}'::jsonb", finished_at="now()")
    insert_check(db, "registry_app", "fallida", reason="'interrumpida'")
    insert_check(db, "registry_app", "pendiente")
    assert db.query("SELECT count(*) FROM integrity_checks") == [(3,)]


@pytest.mark.parametrize(
    ("status", "extra"),
    [
        ("terminada", {}),
        ("fallida", {}),
        ("pendiente", {"report": "'{}'::jsonb"}),
        ("pendiente", {"reason": "'interrumpida'"}),
        ("terminada", {"report": "'{}'::jsonb", "reason": "'plazo_vencido'"}),
        ("fallida", {"reason": "'otra'"}),
        ("pendiente", {"progress_checked": "5", "progress_total": "3"}),
        ("pendiente", {"mode": "'x'"}),
    ],
    ids=[
        "terminada-sin-report",
        "fallida-sin-reason",
        "report-en-pendiente",
        "reason-en-pendiente",
        "reason-en-terminada",
        "reason-desconocida",
        "progreso-mayor-que-total",
        "modo-desconocido",
    ],
)
def test_los_check_de_integrity_checks(db: Db, status: str, extra: dict[str, str]) -> None:
    mode_override = extra.pop("mode", None)
    if mode_override is not None:
        with db.as_role("registry_app") as conn, pytest.raises(errors.CheckViolation):
            conn.execute(
                "INSERT INTO integrity_checks (check_id, mode, requested_by, requested_at, status) "
                "VALUES (gen_random_uuid(), 'x', 'cro-1', now(), 'pendiente')"
            )
        return
    with pytest.raises(errors.CheckViolation):
        insert_check(db, "registry_app", status, **extra)


def test_range_exige_sus_extremos(db: Db) -> None:
    with db.as_role("registry_app") as conn:
        with pytest.raises(errors.CheckViolation):
            conn.execute(
                "INSERT INTO integrity_checks (check_id, mode, requested_by, requested_at, status) "
                "VALUES (gen_random_uuid(), 'range', 'cro-1', now(), 'pendiente')"
            )
        conn.execute(
            "INSERT INTO integrity_checks (check_id, mode, from_seq, to_seq, requested_by, requested_at, status) "
            "VALUES (gen_random_uuid(), 'range', 1, 9, 'cro-1', now(), 'pendiente')"
        )


def test_registry_app_hace_update_de_integrity_checks_denegado(db: Db) -> None:
    insert_check(db, "registry_app", "pendiente")
    denied(db, "registry_app", "UPDATE integrity_checks SET status = 'en_curso'")


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE integrity_checks SET status = 'en_curso'",
        "INSERT INTO integrity_checks (check_id, mode, requested_by, requested_at, status) "
        "VALUES (gen_random_uuid(), 'full', 'x', now(), 'pendiente')",
    ],
    ids=["update", "insert"],
)
def test_registry_verifier_no_escribe_en_integrity_checks(db: Db, statement: str) -> None:
    insert_check(db, "registry_app", "pendiente")
    denied(db, "registry_verifier", statement)
    with db.as_role("registry_verifier") as conn:
        assert conn.execute("SELECT count(*) FROM integrity_checks").fetchone() == (1,)


def test_registry_ondemand_actualiza_status_pero_no_requested_by(db: Db) -> None:
    insert_check(db, "registry_app", "pendiente")
    with db.as_role("registry_ondemand") as conn:
        conn.execute(
            "UPDATE integrity_checks SET status = 'en_curso', started_at = now(), heartbeat_at = now()"
        )
        conn.execute("UPDATE integrity_checks SET progress_total = 10, progress_checked = 4")
        conn.execute(
            "UPDATE integrity_checks SET status = 'terminada', finished_at = now(), report = '{}'::jsonb"
        )
    assert db.query("SELECT status FROM integrity_checks") == [("terminada",)]
    denied(db, "registry_ondemand", "UPDATE integrity_checks SET requested_by = 'otro'")
    denied(db, "registry_ondemand", "UPDATE integrity_checks SET requested_at = now()")
    denied(db, "registry_ondemand", "UPDATE integrity_checks SET mode = 'range'")


def test_registry_ondemand_inserta_la_full_mensual(db: Db) -> None:
    insert_check(db, "registry_ondemand", "pendiente")
    assert db.query("SELECT requested_by FROM integrity_checks") == [("cro-1",)]


@pytest.mark.parametrize(
    "statement",
    [
        "INSERT INTO registry_entries (seq, idempotency_key, entry_type, actor_kind, actor_id, occurred_at, recorded_at, "
        "correlation_id, contract_version, canonical, prev_hash, hash) VALUES (1, gen_random_uuid(), 'model_event', 's', 's', "
        "now(), now(), 'c', '0.1.0', '\\x7b7d', '\\x00', '\\x00')",
        "UPDATE registry_entries SET actor_id = 'x'",
        "DELETE FROM registry_entries",
    ],
    ids=["insert", "update", "delete"],
)
def test_registry_ondemand_no_escribe_en_registry_entries(db: Db, statement: str) -> None:
    denied(db, "registry_ondemand", statement)
    with db.as_role("registry_ondemand") as conn:
        assert conn.execute("SELECT count(*) FROM registry_entries").fetchone() == (1,)


@pytest.mark.parametrize(
    "role",
    ["registry_app", "registry_verifier", "registry_ondemand", "registry_aggregator", "registry_health"],
)
def test_nadie_hace_delete_ni_truncate_de_integrity_checks(db: Db, role: str) -> None:
    insert_check(db, "registry_app", "pendiente")
    denied(db, role, "DELETE FROM integrity_checks")
    denied(db, role, "TRUNCATE integrity_checks")
    assert db.query("SELECT count(*) FROM integrity_checks") == [(1,)]
