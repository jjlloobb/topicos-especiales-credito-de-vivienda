"""RLS de `evidence_outbox`, indices parciales y orden del conflicto tras un abandono (Paso 3; INF-U8-01; BR-U8-09, 18)."""

import uuid

import pytest
from case_data import APP, WORKER, insert_decision, insert_evidence, key_of, new_case, state_of
from case_pg import Db
from psycopg import errors
from psycopg.types.json import Jsonb

pytestmark = pytest.mark.integration


def test_case_worker_inserts_fail_closed(db: Db) -> None:
    case_id = new_case(db)
    with db.as_role(WORKER) as conn:
        evidence_id = insert_evidence(conn, case_id, "fail_closed", key_of(case_id, "fail_closed:0"))
    assert db.query("SELECT entry_type, state FROM evidence_outbox WHERE evidence_id = %s", evidence_id) == [
        ("fail_closed", "pendiente_registro")
    ]


@pytest.mark.parametrize("entry_type", ["human_decision", "explanation_view"])
def test_case_worker_cannot_insert_other_entry_types(db: Db, entry_type: str) -> None:
    case_id = new_case(db)
    with db.as_role(WORKER) as conn, pytest.raises(errors.InsufficientPrivilege, match="row-level security"):
        insert_evidence(conn, case_id, entry_type, key_of(case_id, entry_type))
    assert db.query("SELECT count(*) FROM evidence_outbox") == [(0,)]


def test_case_app_inserts_the_three_entry_types(db: Db) -> None:
    case_id = new_case(db)
    with db.as_role(APP) as conn:
        for entry_type in ("human_decision", "explanation_view", "fail_closed"):
            insert_evidence(conn, case_id, entry_type, key_of(case_id, entry_type))
    assert db.query("SELECT entry_type FROM evidence_outbox ORDER BY entry_type") == [
        ("explanation_view",),
        ("fail_closed",),
        ("human_decision",),
    ]


def test_case_worker_repeats_fail_closed_inside_a_savepoint_and_the_transaction_commits(db: Db) -> None:
    """BR-U8-09: sin `RETURNING` ni `ON CONFLICT`; el `unique_violation` se trata como exito y la transaccion confirma."""
    case_id = new_case(db)
    key = key_of(case_id, "fail_closed:0")
    with db.as_role(WORKER) as conn:
        insert_evidence(conn, case_id, "fail_closed", key)  # el escalamiento anterior, ya confirmado
        with conn.transaction():
            with pytest.raises(errors.UniqueViolation), conn.transaction():  # el SAVEPOINT
                insert_evidence(conn, case_id, "fail_closed", key)
            # De vuelta en el SAVEPOINT, el resto del escalamiento sigue y confirma.
            conn.execute(
                "UPDATE cases SET state = 'no_disponible', last_cause = 'scoring_unreachable', escalation_count = 1, "
                "ever_degraded = true WHERE case_id = %s",
                (case_id,),
            )
    assert db.query("SELECT count(*) FROM evidence_outbox WHERE idempotency_key = %s", key) == [(1,)]
    assert db.query(
        "SELECT state, last_cause, escalation_count, ever_degraded FROM cases WHERE case_id = %s", case_id
    ) == [("no_disponible", "scoring_unreachable", 1, True)]


def test_case_worker_insert_returning_is_denied(db: Db) -> None:
    """Documenta por que el codigo no usa `RETURNING`: `case_worker` no tiene `SELECT` sobre la tabla."""
    case_id = new_case(db)
    with (
        db.as_role(WORKER) as conn,
        pytest.raises(errors.InsufficientPrivilege, match="permission denied for table evidence_outbox"),
    ):
        conn.execute(
            "INSERT INTO evidence_outbox (evidence_id, case_id, entry_type, idempotency_key, payload) "
            "VALUES (%s, %s, 'fail_closed', %s, %s) RETURNING evidence_id",
            (uuid.uuid4(), case_id, key_of(case_id, "fail_closed:0"), Jsonb({})),
        )
    assert db.query("SELECT count(*) FROM evidence_outbox") == [(0,)]


def test_case_worker_on_conflict_do_update_is_denied(db: Db) -> None:
    """Documenta por que el codigo no usa `ON CONFLICT DO UPDATE`: sin `SELECT` ni `UPDATE` sobre la tabla."""
    case_id = new_case(db)
    key = key_of(case_id, "fail_closed:0")
    with db.as_role(WORKER) as conn:
        insert_evidence(conn, case_id, "fail_closed", key)
        with pytest.raises(errors.InsufficientPrivilege, match="permission denied for table evidence_outbox"):
            conn.execute(
                "INSERT INTO evidence_outbox (evidence_id, case_id, entry_type, idempotency_key, payload) "
                "VALUES (%s, %s, 'fail_closed', %s, %s) ON CONFLICT (idempotency_key) WHERE state <> 'abandonada' "
                "DO UPDATE SET attempts = 99",
                (uuid.uuid4(), case_id, key, Jsonb({})),
            )
    assert db.query("SELECT attempts FROM evidence_outbox WHERE idempotency_key = %s", key) == [(0,)]


def test_new_decision_after_an_abandoned_one_reuses_the_key_without_conflict(db: Db) -> None:
    case_id = new_case(db, state="listo")
    key = key_of(case_id, "human_decision")
    with db.as_role(APP) as conn:
        old_evidence = insert_evidence(conn, case_id, "human_decision", key, state="abandonada")
        insert_decision(conn, case_id, old_evidence, state="abandonada")
        new_evidence = insert_evidence(conn, case_id, "human_decision", key)
        new_decision = insert_decision(conn, case_id, new_evidence)
    assert db.query("SELECT state FROM evidence_outbox WHERE idempotency_key = %s ORDER BY state", key) == [
        ("abandonada",),
        ("pendiente_registro",),
    ]
    assert db.query("SELECT state FROM decisions WHERE decision_id = %s", new_decision) == [
        ("pendiente_registro",)
    ]


def test_a_second_live_row_with_the_same_key_raises_unique_violation(db: Db) -> None:
    case_id = new_case(db, state="listo")
    key = key_of(case_id, "human_decision")
    with db.as_role(APP) as conn:
        insert_evidence(conn, case_id, "human_decision", key, state="abandonada")
        insert_evidence(conn, case_id, "human_decision", key)
        with pytest.raises(errors.UniqueViolation, match="evidence_outbox_live_key"):
            insert_evidence(conn, case_id, "human_decision", key)
        with pytest.raises(errors.UniqueViolation, match="evidence_outbox_live_key"):
            insert_evidence(conn, case_id, "human_decision", key, state="confirmada")
    assert db.query("SELECT count(*) FROM evidence_outbox WHERE idempotency_key = %s", key) == [(2,)]


def test_a_second_live_decision_for_a_case_raises_unique_violation(db: Db) -> None:
    case_id = new_case(db, state="listo")
    with db.as_role(APP) as conn:
        insert_decision(
            conn, case_id, insert_evidence(conn, case_id, "human_decision", uuid.uuid4()), state="abandonada"
        )
        insert_decision(conn, case_id, insert_evidence(conn, case_id, "human_decision", uuid.uuid4()))
        with pytest.raises(errors.UniqueViolation, match="decisions_live_case"):
            insert_decision(
                conn,
                case_id,
                insert_evidence(conn, case_id, "human_decision", uuid.uuid4()),
                state="confirmada",
            )
    assert db.query("SELECT count(*) FROM decisions WHERE case_id = %s", case_id) == [(2,)]


def _abandoned_then_new(db: Db) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID, uuid.UUID, uuid.UUID]:
    """El abandono de BR-U8-18: la anterior `abandonada` (que si estaba en el registro) y la nueva `pendiente_registro`, con la misma llave."""
    case_id = new_case(db, state="listo")
    key = key_of(case_id, "human_decision")
    with db.as_role(APP) as conn:
        old_evidence = insert_evidence(conn, case_id, "human_decision", key, state="abandonada")
        old_decision = insert_decision(conn, case_id, old_evidence, state="abandonada")
        new_evidence = insert_evidence(conn, case_id, "human_decision", key)
        new_decision = insert_decision(conn, case_id, new_evidence)
    return case_id, old_decision, old_evidence, new_decision, new_evidence


def test_conflict_order_new_to_abandoned_before_old_to_confirmed_succeeds(db: Db) -> None:
    case_id, old_decision, old_evidence, new_decision, new_evidence = _abandoned_then_new(db)
    with db.as_role(APP) as conn, conn.transaction():
        conn.execute("UPDATE decisions SET state = 'abandonada' WHERE decision_id = %s", (new_decision,))
        conn.execute(
            "UPDATE evidence_outbox SET state = 'abandonada' WHERE evidence_id = %s", (new_evidence,)
        )
        conn.execute("UPDATE decisions SET state = 'confirmada' WHERE decision_id = %s", (old_decision,))
        conn.execute(
            "UPDATE evidence_outbox SET state = 'confirmada' WHERE evidence_id = %s", (old_evidence,)
        )
        conn.execute("UPDATE cases SET state = 'decidido' WHERE case_id = %s", (case_id,))
    assert db.query("SELECT decision_id = %s, state FROM decisions ORDER BY state", old_decision) == [
        (False, "abandonada"),
        (True, "confirmada"),
    ]
    assert db.query("SELECT evidence_id = %s, state FROM evidence_outbox ORDER BY state", old_evidence) == [
        (False, "abandonada"),
        (True, "confirmada"),
    ]
    assert state_of(db, case_id) == "decidido"


def test_conflict_order_old_to_confirmed_before_new_to_abandoned_raises_unique_violation(db: Db) -> None:
    case_id, old_decision, old_evidence, new_decision, new_evidence = _abandoned_then_new(db)
    with db.as_role(APP) as conn, pytest.raises(errors.UniqueViolation):
        with conn.transaction():
            conn.execute("UPDATE decisions SET state = 'confirmada' WHERE decision_id = %s", (old_decision,))
            conn.execute("UPDATE decisions SET state = 'abandonada' WHERE decision_id = %s", (new_decision,))
    with db.as_role(APP) as conn, pytest.raises(errors.UniqueViolation):
        with conn.transaction():
            conn.execute(
                "UPDATE evidence_outbox SET state = 'confirmada' WHERE evidence_id = %s", (old_evidence,)
            )
            conn.execute(
                "UPDATE evidence_outbox SET state = 'abandonada' WHERE evidence_id = %s", (new_evidence,)
            )
    assert db.query("SELECT state FROM decisions ORDER BY decision_id = %s", old_decision) == [
        ("pendiente_registro",),
        ("abandonada",),
    ]
    assert state_of(db, case_id) == "listo"


def test_explanation_views_have_a_unique_case_and_user(db: Db) -> None:
    case_id = new_case(db, state="listo")
    with db.as_role(APP) as conn:
        evidence = insert_evidence(conn, case_id, "explanation_view", uuid.uuid4())
        conn.execute(
            "INSERT INTO explanation_views (case_id, user_id, evidence_id) VALUES (%s, 'u1', %s)",
            (case_id, evidence),
        )
        conn.execute(
            "INSERT INTO explanation_views (case_id, user_id, evidence_id) VALUES (%s, 'u2', %s)",
            (case_id, evidence),
        )
        with pytest.raises(errors.UniqueViolation):
            conn.execute(
                "INSERT INTO explanation_views (case_id, user_id, evidence_id) VALUES (%s, 'u1', %s)",
                (case_id, evidence),
            )
    assert db.query("SELECT user_id FROM explanation_views WHERE case_id = %s ORDER BY user_id", case_id) == [
        ("u1",),
        ("u2",),
    ]


def test_case_worker_cannot_touch_explanation_views_or_decisions(db: Db) -> None:
    case_id = new_case(db)
    with db.as_role(WORKER) as conn:
        with pytest.raises(
            errors.InsufficientPrivilege, match="permission denied for table explanation_views"
        ):
            conn.execute(
                "INSERT INTO explanation_views (case_id, user_id, evidence_id) VALUES (%s, 'u', %s)",
                (case_id, uuid.uuid4()),
            )
        with pytest.raises(errors.InsufficientPrivilege, match="permission denied for table decisions"):
            insert_decision(conn, case_id, uuid.uuid4())
