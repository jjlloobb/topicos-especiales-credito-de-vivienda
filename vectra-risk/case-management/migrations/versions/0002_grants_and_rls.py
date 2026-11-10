"""Grants de `case_app`, `case_worker`, `case_retention` y `case_migrator`, y RLS de `evidence_outbox`.

Revision ID: 0002
Revises: 0001

Paso 3 del plan de U8. INF-U8-01 (rige sobre `logical-components.md` §1 donde difieren: `ever_degraded` en el `UPDATE` de
`case_worker`); NFR-U8-41. Los roles los crea U1 (`platform/data`, `case-db.roles`); `case_migrator` es el dueno de las tablas.

- `case_app`: `UPDATE` de `cases` solo en `(state, attempts, model_frozen_after_recommendation, updated_at)`; sin `DELETE`.
- `case_worker`: `UPDATE` de las columnas de evaluacion (sin `vencido`: lo impide `guard_vencido`); `SELECT`, `UPDATE`, `DELETE` en
  `evaluation_jobs`; solo `INSERT` en `evidence_outbox` (sin `SELECT`: no hay `RETURNING` ni `ON CONFLICT`).
- `case_retention`: `SELECT` por columna (en `DELETE ... WHERE` PostgreSQL exige `SELECT` de las columnas leidas).
- RLS en `evidence_outbox`: `worker_fail_closed_only` y `app_all`; `case_migrator` es dueno y la RLS no le aplica (sin `FORCE`).
"""

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

GRANTS = """
-- case_app (case-service)
GRANT SELECT, INSERT ON cases TO case_app;
GRANT UPDATE (state, attempts, model_frozen_after_recommendation, updated_at) ON cases TO case_app;
GRANT SELECT, INSERT, UPDATE ON case_identifiers TO case_app;
GRANT SELECT, INSERT ON evaluation_jobs TO case_app;
GRANT SELECT, INSERT ON intake_keys TO case_app;
GRANT SELECT, INSERT, UPDATE ON decisions TO case_app;
GRANT SELECT, INSERT, UPDATE ON explanation_views TO case_app;
GRANT SELECT, INSERT, UPDATE ON evidence_outbox TO case_app;
GRANT SELECT ON retention_runs TO case_app;
GRANT SELECT ON retention_settings TO case_app;

-- case_worker (case-worker)
GRANT SELECT ON cases TO case_worker;
GRANT UPDATE (state, attempts, last_cause, recommendation, recommendation_entry_id, escalation_count, ever_degraded, updated_at)
    ON cases TO case_worker;
GRANT SELECT ON case_identifiers TO case_worker;
GRANT SELECT, UPDATE, DELETE ON evaluation_jobs TO case_worker;
GRANT INSERT ON evidence_outbox TO case_worker;

-- case_retention (CronJob case-retention)
GRANT SELECT (case_id, state, created_at, application, anonymized_at) ON cases TO case_retention;
GRANT UPDATE (application, anonymized_at, state) ON cases TO case_retention;
GRANT SELECT (case_id) ON case_identifiers TO case_retention;
GRANT DELETE ON case_identifiers TO case_retention;
GRANT SELECT (case_id) ON evaluation_jobs TO case_retention;
GRANT DELETE ON evaluation_jobs TO case_retention;
GRANT SELECT (created_at) ON intake_keys TO case_retention;
GRANT DELETE ON intake_keys TO case_retention;
GRANT SELECT (case_id, decided_at, state) ON decisions TO case_retention;
GRANT INSERT ON retention_runs TO case_retention;
GRANT SELECT ON retention_settings TO case_retention;

-- Evidencia: RLS (INF-U8-01). El worker solo inserta `fail_closed`; `case_app` conserva todo.
ALTER TABLE evidence_outbox ENABLE ROW LEVEL SECURITY;
CREATE POLICY worker_fail_closed_only ON evidence_outbox FOR INSERT TO case_worker WITH CHECK (entry_type = 'fail_closed');
CREATE POLICY app_all ON evidence_outbox FOR ALL TO case_app USING (true) WITH CHECK (true);
"""


def upgrade() -> None:
    op.execute(GRANTS)


def downgrade() -> None:
    raise RuntimeError("las migraciones de case-db no tienen downgrade")
