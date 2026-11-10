"""Permisos por tabla y por columna de los cuatro roles (Paso 3; INF-U8-01; NFR-U8-41): cada caso con el rol real y lectura de vuelta."""

import pytest
from case_data import APP, RETENTION, WORKER, insert_case, insert_evidence, key_of, new_case, state_of
from case_pg import MIGRATOR, Db
from psycopg import errors
from psycopg.types.json import Jsonb

pytestmark = pytest.mark.integration


def test_case_worker_cannot_read_decisions(db: Db) -> None:
    with (
        db.as_role(WORKER) as conn,
        pytest.raises(errors.InsufficientPrivilege, match="permission denied for table decisions"),
    ):
        conn.execute("SELECT * FROM decisions")


def test_case_worker_cannot_delete_case_identifiers(db: Db) -> None:
    case_id = new_case(db)
    db.execute(
        "INSERT INTO case_identifiers (case_id, full_name, document_type, document_number, birth_date, municipality_code) "
        "VALUES (%s, 'Ana', 'CC', '123', '1990-01-01', '11001')",
        case_id,
    )
    with (
        db.as_role(WORKER) as conn,
        pytest.raises(errors.InsufficientPrivilege, match="permission denied for table case_identifiers"),
    ):
        conn.execute("DELETE FROM case_identifiers WHERE case_id = %s", (case_id,))
    assert db.query("SELECT count(*) FROM case_identifiers WHERE case_id = %s", case_id)[0][0] == 1


def test_case_worker_cannot_write_vencido(db: Db) -> None:
    case_id = new_case(db, created_at="now() - interval '3 years'")
    with db.as_role(WORKER) as conn, pytest.raises(errors.RaiseException, match="guard_"):
        conn.execute("UPDATE cases SET state = 'vencido' WHERE case_id = %s", (case_id,))
    assert state_of(db, case_id) == "en_evaluacion"


def test_case_app_cannot_delete_from_evaluation_jobs(db: Db) -> None:
    case_id = new_case(db)
    with db.as_role(APP) as conn:
        conn.execute("INSERT INTO evaluation_jobs (case_id) VALUES (%s)", (case_id,))
        with pytest.raises(errors.InsufficientPrivilege, match="permission denied for table evaluation_jobs"):
            conn.execute("DELETE FROM evaluation_jobs WHERE case_id = %s", (case_id,))
        with pytest.raises(errors.InsufficientPrivilege, match="permission denied for table evaluation_jobs"):
            conn.execute("UPDATE evaluation_jobs SET attempt = 1 WHERE case_id = %s", (case_id,))
    assert db.query("SELECT count(*), max(attempt) FROM evaluation_jobs WHERE case_id = %s", case_id) == [
        (1, 0)
    ]


@pytest.mark.parametrize(
    ("column", "value"),
    [
        ("recommendation", Jsonb({"outcome": "favorable"})),
        ("recommendation_entry_id", "entry-1"),
        ("last_cause", "scoring_unreachable"),
        ("escalation_count", 1),
    ],
)
def test_case_app_cannot_write_worker_columns(db: Db, column: str, value: object) -> None:
    case_id = new_case(db)
    with (
        db.as_role(APP) as conn,
        pytest.raises(errors.InsufficientPrivilege, match="permission denied for table cases"),
    ):
        conn.execute(f"UPDATE cases SET {column} = %s WHERE case_id = %s", (value, case_id))
    assert db.query(
        "SELECT count(*) FROM cases WHERE case_id = %s AND recommendation IS NULL AND recommendation_entry_id IS NULL "
        "AND last_cause IS NULL AND escalation_count = 0",
        case_id,
    ) == [(1,)]


def test_case_app_can_write_its_own_columns(db: Db) -> None:
    case_id = new_case(db, state="no_disponible")
    with db.as_role(APP) as conn:
        conn.execute(
            "UPDATE cases SET state = 'en_evaluacion', attempts = 0, model_frozen_after_recommendation = true, updated_at = now() "
            "WHERE case_id = %s",
            (case_id,),
        )
    assert db.query(
        "SELECT state, model_frozen_after_recommendation FROM cases WHERE case_id = %s", case_id
    ) == [("en_evaluacion", True)]


def test_insert_of_a_case_in_listo_raises_guard_transition(db: Db) -> None:
    with db.as_role(APP) as conn, pytest.raises(errors.RaiseException, match="guard_transition"):
        insert_case(conn, state="listo")
    assert db.query("SELECT count(*) FROM cases") == [(0,)]


@pytest.mark.parametrize("field", ["recommendation", "recommendation_entry_id"])
def test_insert_of_a_case_with_recommendation_raises_guard_transition(db: Db, field: str) -> None:
    kwargs: dict[str, object] = {field: {"outcome": "favorable"} if field == "recommendation" else "entry-1"}
    with db.as_role(APP) as conn, pytest.raises(errors.RaiseException, match="guard_transition"):
        insert_case(conn, **kwargs)  # type: ignore[arg-type]
    assert db.query("SELECT count(*) FROM cases") == [(0,)]


@pytest.mark.parametrize("role", [WORKER, RETENTION, MIGRATOR])
def test_only_case_app_inserts_cases(db: Db, role: str) -> None:
    """`INSERT` en `en_evaluacion` desde otro rol: sin permiso de tabla, o la excepcion de `guard_transition` (el dueno)."""
    expected = errors.RaiseException if role == MIGRATOR else errors.InsufficientPrivilege
    with db.as_role(role) as conn, pytest.raises(expected):
        insert_case(conn)
    assert db.query("SELECT count(*) FROM cases") == [(0,)]


def test_ever_degraded_the_worker_sets_it_to_true(db: Db) -> None:
    case_id = new_case(db)
    with db.as_role(WORKER) as conn:
        conn.execute(
            "UPDATE cases SET ever_degraded = true, state = 'en_sincronizacion', last_cause = 'scoring_unreachable' WHERE case_id = %s",
            (case_id,),
        )
    assert db.query("SELECT ever_degraded, state FROM cases WHERE case_id = %s", case_id) == [
        (True, "en_sincronizacion")
    ]


def test_ever_degraded_case_app_has_no_permission(db: Db) -> None:
    case_id = new_case(db)
    with (
        db.as_role(APP) as conn,
        pytest.raises(errors.InsufficientPrivilege, match="permission denied for table cases"),
    ):
        conn.execute("UPDATE cases SET ever_degraded = true WHERE case_id = %s", (case_id,))
    assert db.query("SELECT ever_degraded FROM cases WHERE case_id = %s", case_id) == [(False,)]


@pytest.mark.parametrize("role", [WORKER, MIGRATOR])
def test_ever_degraded_never_goes_back_to_false(db: Db, role: str) -> None:
    """Tampoco con el dueno: lo impide el trigger `guard_ever_degraded`."""
    case_id = new_case(db)
    db.execute("UPDATE cases SET ever_degraded = true WHERE case_id = %s", case_id)
    with db.as_role(role) as conn, pytest.raises(errors.RaiseException, match="guard_ever_degraded"):
        conn.execute("UPDATE cases SET ever_degraded = false WHERE case_id = %s", (case_id,))
    assert db.query("SELECT ever_degraded FROM cases WHERE case_id = %s", case_id) == [(True,)]


def test_case_worker_reads_cases_and_identifiers_but_not_intake_keys(db: Db) -> None:
    case_id = new_case(db)
    with db.as_role(WORKER) as conn:
        assert conn.execute("SELECT state FROM cases WHERE case_id = %s", (case_id,)).fetchall() == [
            ("en_evaluacion",)
        ]
        conn.execute("SELECT * FROM case_identifiers").fetchall()
        for table in ("intake_keys", "explanation_views", "retention_runs", "retention_settings"):
            with pytest.raises(errors.InsufficientPrivilege):
                conn.execute(f"SELECT 1 FROM {table}")


def test_case_retention_selects_by_column(db: Db) -> None:
    """`SELECT` por columna: lee lo que necesita para borrar y calcular plazos, no las columnas del solicitante."""
    new_case(db)
    with db.as_role(RETENTION) as conn:
        conn.execute("SELECT case_id, state, created_at, application, anonymized_at FROM cases").fetchall()
        conn.execute("SELECT case_id, decided_at, state FROM decisions").fetchall()
        with pytest.raises(errors.InsufficientPrivilege):
            conn.execute("SELECT recommendation FROM cases")
        with pytest.raises(errors.InsufficientPrivilege):
            conn.execute("SELECT justification FROM decisions")
        with pytest.raises(errors.InsufficientPrivilege):
            conn.execute("SELECT full_name FROM case_identifiers")


def test_case_app_inserts_evidence(db: Db) -> None:
    case_id = new_case(db)
    with db.as_role(APP) as conn:
        insert_evidence(conn, case_id, "explanation_view", key_of(case_id, "v"))
    assert db.query("SELECT count(*) FROM evidence_outbox") == [(1,)]
