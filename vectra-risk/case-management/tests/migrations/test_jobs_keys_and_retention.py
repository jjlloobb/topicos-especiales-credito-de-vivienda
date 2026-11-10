"""Cola, llaves de ingesta, `guard_vencido` y `retention_settings` (Paso 3; BR-U8-02, 07, 20; P-U8-05; P-1)."""

import uuid

import pytest
from case_data import APP, RETENTION, WORKER, new_case, state_of
from case_pg import RETENTION_DEFAULTS, RETENTION_VARIABLES, Db
from psycopg import errors

pytestmark = pytest.mark.integration

ONE_YEAR = "now() - interval '1 year'"
OVER_TWO_YEARS = "now() - interval '2 years 1 day'"


def test_attempt_seven_violates_the_check(db: Db) -> None:
    case_id = new_case(db)
    with db.as_role(APP) as conn, pytest.raises(errors.CheckViolation, match="evaluation_jobs"):
        conn.execute("INSERT INTO evaluation_jobs (case_id, attempt) VALUES (%s, 7)", (case_id,))
    assert db.query("SELECT count(*) FROM evaluation_jobs") == [(0,)]


def test_attempt_zero_to_six_is_accepted_and_the_worker_cannot_write_seven(db: Db) -> None:
    case_id = new_case(db)
    with db.as_role(APP) as conn:
        conn.execute("INSERT INTO evaluation_jobs (case_id, attempt) VALUES (%s, 0)", (case_id,))
    with db.as_role(WORKER) as conn:
        conn.execute(
            "UPDATE evaluation_jobs SET attempt = 6, locked_until = now() WHERE case_id = %s", (case_id,)
        )
        with pytest.raises(errors.CheckViolation):
            conn.execute("UPDATE evaluation_jobs SET attempt = 7 WHERE case_id = %s", (case_id,))
    assert db.query("SELECT attempt FROM evaluation_jobs WHERE case_id = %s", case_id) == [(6,)]


def test_one_live_job_per_case(db: Db) -> None:
    case_id = new_case(db)
    with db.as_role(APP) as conn:
        conn.execute("INSERT INTO evaluation_jobs (case_id) VALUES (%s)", (case_id,))
        with pytest.raises(errors.UniqueViolation, match="evaluation_jobs_one_live_job_per_case"):
            conn.execute("INSERT INTO evaluation_jobs (case_id) VALUES (%s)", (case_id,))
    with db.as_role(WORKER) as conn:
        conn.execute("DELETE FROM evaluation_jobs WHERE case_id = %s", (case_id,))
    with db.as_role(APP) as conn:
        conn.execute("INSERT INTO evaluation_jobs (case_id) VALUES (%s)", (case_id,))
    assert db.query("SELECT count(*) FROM evaluation_jobs WHERE case_id = %s", case_id) == [(1,)]


def test_intake_key_is_unique_per_scope_and_key(db: Db) -> None:
    case_id = new_case(db)
    other = new_case(db)
    with db.as_role(APP) as conn:
        conn.execute(
            "INSERT INTO intake_keys (scope, idempotency_key, body_sha256, case_id) VALUES ('canal', 'k1', 'h', %s)",
            (case_id,),
        )
        conn.execute(
            "INSERT INTO intake_keys (scope, idempotency_key, body_sha256, case_id) VALUES ('otro', 'k1', 'h', %s)",
            (other,),
        )
        with pytest.raises(errors.UniqueViolation):
            conn.execute(
                "INSERT INTO intake_keys (scope, idempotency_key, body_sha256, case_id) VALUES ('canal', 'k1', 'h2', %s)",
                (other,),
            )
    assert db.query("SELECT count(*) FROM intake_keys") == [(2,)]


def test_case_app_writes_vencido_raises(db: Db) -> None:
    case_id = new_case(db, created_at=OVER_TWO_YEARS)
    with db.as_role(APP) as conn, pytest.raises(errors.RaiseException, match="guard_"):
        conn.execute("UPDATE cases SET state = 'vencido' WHERE case_id = %s", (case_id,))
    assert state_of(db, case_id) == "en_evaluacion"


def test_case_retention_vencido_on_a_one_year_case_raises(db: Db) -> None:
    case_id = new_case(db, created_at=ONE_YEAR)
    with (
        db.as_role(RETENTION) as conn,
        pytest.raises(errors.RaiseException, match="guard_vencido: la retencion del caso no ha vencido"),
    ):
        conn.execute("UPDATE cases SET state = 'vencido' WHERE case_id = %s", (case_id,))
    assert state_of(db, case_id) == "en_evaluacion"


def test_case_retention_vencido_on_a_two_years_and_one_day_case_succeeds(db: Db) -> None:
    case_id = new_case(db, created_at=OVER_TWO_YEARS)
    with db.as_role(RETENTION) as conn:
        conn.execute("UPDATE cases SET state = 'vencido' WHERE case_id = %s", (case_id,))
    assert state_of(db, case_id) == "vencido"


def test_case_retention_writes_listo_raises(db: Db) -> None:
    case_id = new_case(db, created_at=OVER_TWO_YEARS)
    with db.as_role(RETENTION) as conn, pytest.raises(errors.RaiseException, match="guard_transition"):
        conn.execute("UPDATE cases SET state = 'listo' WHERE case_id = %s", (case_id,))
    assert state_of(db, case_id) == "en_evaluacion"


def test_guard_vencido_rejects_a_decided_case(db: Db) -> None:
    case_id = new_case(db, state="decidido", created_at=OVER_TWO_YEARS)
    with db.as_role(RETENTION) as conn, pytest.raises(errors.RaiseException, match="guard_"):
        conn.execute("UPDATE cases SET state = 'vencido' WHERE case_id = %s", (case_id,))
    assert state_of(db, case_id) == "decidido"


def test_case_retention_anonymizes_a_decided_case_without_changing_its_state(db: Db) -> None:
    """`application` y `anonymized_at` no son `state`: ni `guard_transition` ni `guard_vencido` se disparan."""
    case_id = new_case(db, state="decidido", created_at=OVER_TWO_YEARS)
    with db.as_role(RETENTION) as conn:
        conn.execute(
            "UPDATE cases SET application = application - 'free_text', anonymized_at = now() WHERE case_id = %s",
            (case_id,),
        )
    assert db.query(
        "SELECT state, application ? 'free_text', anonymized_at IS NOT NULL FROM cases WHERE case_id = %s",
        case_id,
    ) == [("decidido", False, True)]


@pytest.mark.parametrize("role", [RETENTION, APP])
def test_case_retention_and_case_app_cannot_write_retention_settings(db: Db, role: str) -> None:
    with db.as_role(role) as conn:
        assert conn.execute("SELECT undecided_years FROM retention_settings").fetchall() == [(2,)]
        for statement in (
            "UPDATE retention_settings SET undecided_years = 99",
            "INSERT INTO retention_settings (id, decided_years, undecided_years, intake_keys_days) VALUES (2, 1, 1, 1)",
            "DELETE FROM retention_settings",
        ):
            with pytest.raises(
                errors.InsufficientPrivilege, match="permission denied for table retention_settings"
            ):
                conn.execute(statement)
    assert db.query("SELECT decided_years, undecided_years, intake_keys_days FROM retention_settings") == [
        (10, 2, 30)
    ]


def test_retention_settings_is_a_single_row(db: Db) -> None:
    with db.admin() as conn, pytest.raises(errors.CheckViolation):
        conn.execute(
            "INSERT INTO retention_settings (id, decided_years, undecided_years, intake_keys_days) VALUES (2, 1, 1, 1)"
        )


def test_changing_the_retention_and_migrating_again_applies_the_new_value_and_keeps_created_at(
    empty_db: Db,
) -> None:
    empty_db.migrate(undecided_years=3)
    created_before, updated_before = empty_db.query("SELECT created_at, updated_at FROM retention_settings")[
        0
    ]
    assert empty_db.query(
        "SELECT decided_years, undecided_years, intake_keys_days FROM retention_settings"
    ) == [(10, 3, 30)]
    case_id = new_case(empty_db, created_at=OVER_TWO_YEARS)
    with empty_db.as_role(RETENTION) as conn, pytest.raises(errors.RaiseException, match="no ha vencido"):
        conn.execute("UPDATE cases SET state = 'vencido' WHERE case_id = %s", (case_id,))
    assert state_of(empty_db, case_id) == "en_evaluacion"

    empty_db.migrate(decided_years=7, undecided_years=2, intake_keys_days=15)
    created_after, updated_after = empty_db.query("SELECT created_at, updated_at FROM retention_settings")[0]
    assert empty_db.query(
        "SELECT decided_years, undecided_years, intake_keys_days FROM retention_settings"
    ) == [(7, 2, 15)]
    assert created_after == created_before
    assert updated_after > updated_before  # type: ignore[operator]
    with empty_db.as_role(RETENTION) as conn:
        conn.execute("UPDATE cases SET state = 'vencido' WHERE case_id = %s", (case_id,))
    assert state_of(empty_db, case_id) == "vencido"
    assert empty_db.query("SELECT count(*) FROM retention_settings") == [(1,)]


@pytest.mark.parametrize("variable", sorted(RETENTION_VARIABLES))
@pytest.mark.parametrize("value", [None, "", "0", "-1", "abc", "2.5"])
def test_the_migration_fails_without_a_positive_integer_for_each_retention_value(
    empty_db: Db, variable: str, value: str | None
) -> None:
    assert set(RETENTION_DEFAULTS) == set(RETENTION_VARIABLES)
    with pytest.raises(RuntimeError, match=RETENTION_VARIABLES[variable]):
        empty_db.migrate(**{variable: value})
    # Falla antes de tocar la base: no quedo ninguna tabla.
    assert empty_db.query("SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public'") == [
        (0,)
    ]


def test_owner_can_read_its_tables_and_row_security_does_not_apply_to_it(db: Db) -> None:
    case_id = new_case(db)
    with db.as_role(APP) as conn:
        conn.execute(
            "INSERT INTO evidence_outbox (evidence_id, case_id, entry_type, idempotency_key, payload) "
            "VALUES (%s, %s, 'human_decision', %s, '{}')",
            (uuid.uuid4(), case_id, uuid.uuid4()),
        )
    with db.as_role("case_migrator") as conn:
        assert conn.execute("SELECT count(*) FROM evidence_outbox").fetchall() == [(1,)]
