"""`case_transitions` y `guard_transition` (Paso 3; BR-U8-12; INF-U8-01): una prueba por fila y por rol que no corresponde."""

import pytest
from case_data import APP, RETENTION, STATES, THREE_YEARS, WORKER, case_transitions, new_case, state_of
from case_pg import MIGRATOR, Db
from psycopg import errors

pytestmark = pytest.mark.integration

ROWS = case_transitions()
APP_ROLES = (APP, WORKER, RETENTION)


def test_there_are_sixteen_rows_and_the_table_matches_the_revision_constant(db: Db) -> None:
    assert len(ROWS) == 16
    assert len(set(ROWS)) == 16
    assert {role: sum(1 for r in ROWS if r[2] == role) for role in APP_ROLES} == {
        APP: 3,
        WORKER: 8,
        RETENTION: 5,
    }
    assert set(db.query("SELECT from_state, to_state, db_role FROM case_transitions")) == set(ROWS)


@pytest.mark.parametrize(
    ("from_state", "to_state", "role"), ROWS, ids=[f"{r[2]}:{r[0]}->{r[1]}" for r in ROWS]
)
def test_the_listed_role_makes_each_transition(db: Db, from_state: str, to_state: str, role: str) -> None:
    # 3 anos: tambien cubre `guard_vencido` en las cinco filas de `case_retention`.
    case_id = new_case(db, state=from_state, created_at=THREE_YEARS)
    with db.as_role(role) as conn:
        conn.execute("UPDATE cases SET state = %s WHERE case_id = %s", (to_state, case_id))
    assert state_of(db, case_id) == to_state


@pytest.mark.parametrize("role", [*APP_ROLES, MIGRATOR])
def test_any_other_role_or_missing_pair_raises(db: Db, role: str) -> None:
    allowed = {(a, b) for a, b, r in ROWS if r == role}
    cases = {state: new_case(db, state=state, created_at=THREE_YEARS) for state in STATES}
    attempts = 0
    with db.as_role(role) as conn:
        for from_state, case_id in cases.items():
            for to_state in STATES:
                if to_state == from_state or (from_state, to_state) in allowed:
                    continue
                attempts += 1
                with pytest.raises(errors.RaiseException, match="guard_"), conn.transaction():
                    conn.execute("UPDATE cases SET state = %s WHERE case_id = %s", (to_state, case_id))
    assert attempts >= 30
    for from_state, case_id in cases.items():
        assert state_of(db, case_id) == from_state


@pytest.mark.parametrize("role", APP_ROLES)
def test_no_application_role_reads_or_writes_case_transitions(db: Db, role: str) -> None:
    with db.as_role(role) as conn:
        with pytest.raises(
            errors.InsufficientPrivilege, match="permission denied for table case_transitions"
        ):
            conn.execute("SELECT * FROM case_transitions")
        with pytest.raises(
            errors.InsufficientPrivilege, match="permission denied for table case_transitions"
        ):
            conn.execute("INSERT INTO case_transitions VALUES ('listo', 'vencido', %s)", (role,))
        with pytest.raises(
            errors.InsufficientPrivilege, match="permission denied for table case_transitions"
        ):
            conn.execute("UPDATE case_transitions SET db_role = %s", (role,))
        with pytest.raises(
            errors.InsufficientPrivilege, match="permission denied for table case_transitions"
        ):
            conn.execute("DELETE FROM case_transitions")
    assert db.query("SELECT count(*) FROM case_transitions") == [(16,)]


@pytest.mark.parametrize("role", APP_ROLES)
@pytest.mark.parametrize("privilege", ["SELECT", "INSERT", "UPDATE", "DELETE"])
def test_has_table_privilege_is_false_for_the_application_roles(db: Db, role: str, privilege: str) -> None:
    assert db.query("SELECT has_table_privilege(%s, 'case_transitions', %s)", role, privilege) == [(False,)]


def test_guard_transition_is_security_definer_owned_by_the_migrator(db: Db) -> None:
    row = db.query(
        "SELECT p.prosecdef, r.rolname, p.proconfig FROM pg_proc p JOIN pg_roles r ON r.oid = p.proowner "
        "WHERE p.proname = 'guard_transition'"
    )
    assert row == [(True, MIGRATOR, ["search_path=pg_catalog, public"])]


def test_guard_vencido_is_security_invoker(db: Db) -> None:
    assert db.query("SELECT prosecdef FROM pg_proc WHERE proname = 'guard_vencido'") == [(False,)]


def test_guard_transition_compares_session_user_not_current_user(db: Db) -> None:
    """Dentro de `SECURITY DEFINER`, `current_user` es el dueno: la funcion debe usar `session_user`."""
    source = str(db.query("SELECT prosrc FROM pg_proc WHERE proname = 'guard_transition'")[0][0])
    assert "session_user" in source
    assert "current_user" not in source
