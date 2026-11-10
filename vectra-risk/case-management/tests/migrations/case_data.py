"""Datos de prueba de `case-db`: los casos nacen como `case_app` (`guard_transition` en `INSERT`), el resto lo prepara el superusuario."""

import importlib.util
import uuid
from pathlib import Path

from case_pg import CASE, Conn, Db
from psycopg.types.json import Jsonb

STATES = (
    "en_evaluacion",
    "listo",
    "en_sincronizacion",
    "no_disponible",
    "modelo_congelado",
    "decidido",
    "vencido",
)
APP, WORKER, RETENTION = "case_app", "case_worker", "case_retention"
THREE_YEARS = "now() - interval '3 years'"


def case_transitions() -> tuple[tuple[str, str, str], ...]:
    """`CASE_TRANSITIONS` de la revision 0003, cargada por ruta (como lo hace U08-T02 para `case_fsm`)."""
    path = CASE / "migrations" / "versions" / "0003_guards.py"
    spec = importlib.util.spec_from_file_location("case_revision_0003", Path(path))
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.CASE_TRANSITIONS  # type: ignore[no-any-return]


def insert_case(
    conn: Conn,
    *,
    state: str = "en_evaluacion",
    created_at: str = "now()",
    recommendation: object = None,
    recommendation_entry_id: str | None = None,
) -> uuid.UUID:
    """`INSERT` de un caso con la conexion dada (la de `case_app` en las pruebas); `created_at` es una expresion SQL."""
    case_id = uuid.uuid4()
    conn.execute(
        "INSERT INTO cases (case_id, state, channel, created_by, application, created_at, recommendation, recommendation_entry_id) "
        f"VALUES (%s, %s, 'manual', %s, %s, {created_at}, %s, %s)",
        (
            case_id,
            state,
            Jsonb({"kind": "user", "id": "analista-1"}),
            Jsonb({"department_code": "11", "free_text": "nota"}),
            Jsonb(recommendation) if recommendation is not None else None,
            recommendation_entry_id,
        ),
    )
    return case_id


def new_case(db: Db, *, state: str = "en_evaluacion", created_at: str = "now()") -> uuid.UUID:
    """Un caso creado como `case_app` y, si hace falta otro estado, llevado ahi por el superusuario sin triggers."""
    with db.as_role(APP) as conn:
        case_id = insert_case(conn, created_at=created_at)
    if state != "en_evaluacion":
        db.execute("UPDATE cases SET state = %s WHERE case_id = %s", state, case_id)
    return case_id


def state_of(db: Db, case_id: uuid.UUID) -> str:
    return str(db.query("SELECT state FROM cases WHERE case_id = %s", case_id)[0][0])


def key_of(case_id: uuid.UUID, name: str) -> uuid.UUID:
    return uuid.uuid5(case_id, name)


def insert_evidence(
    conn: Conn,
    case_id: uuid.UUID,
    entry_type: str,
    idempotency_key: uuid.UUID,
    state: str = "pendiente_registro",
) -> uuid.UUID:
    evidence_id = uuid.uuid4()
    conn.execute(
        "INSERT INTO evidence_outbox (evidence_id, case_id, entry_type, idempotency_key, payload, state) "
        "VALUES (%s, %s, %s, %s, %s, %s)",
        (evidence_id, case_id, entry_type, idempotency_key, Jsonb({"entry": entry_type}), state),
    )
    return evidence_id


def insert_decision(
    conn: Conn, case_id: uuid.UUID, evidence_id: uuid.UUID, state: str = "pendiente_registro"
) -> uuid.UUID:
    decision_id = uuid.uuid4()
    conn.execute(
        "INSERT INTO decisions (decision_id, case_id, decision, final_outcome, used_factors, justification, "
        "explanation_viewed_before, decided_by, evidence_id, state) "
        "VALUES (%s, %s, 'sigue', 'favorable', %s, %s, true, %s, %s, %s)",
        (
            decision_id,
            case_id,
            Jsonb(["ninguno"]),
            "x" * 20,
            Jsonb({"kind": "user", "id": "analista-1"}),
            evidence_id,
            state,
        ),
    )
    return decision_id
