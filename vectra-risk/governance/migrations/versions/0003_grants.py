"""Grants de `gov_app`, `gov_archiver` y `gov_migrator`; sin `DELETE` en las tablas de historia.

Revision ID: 0003
Revises: 0002

Paso 2 del plan de U4. NFR-U4-30; INF-U4-03; P-U4-06. Los roles los crea U1 (`platform/data`, `governance-db.roles`).
`gov_migrator` es el dueno de las tablas y por eso tiene `DELETE` implicito: la migracion se lo revoca (NFR-U4-30).
Permisos por columna: lo que una columna no lista no se puede cambiar con ese rol; `gov_archiver` no toca `state`.
"""

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

HISTORY = ("model_versions", "policies", "data_sources", "transitions", "validation_runs", "serving_config")


def upgrade() -> None:
    op.execute(
        "GRANT SELECT, INSERT ON model_versions, policies, data_sources, transitions, validation_runs TO gov_app"
    )
    op.execute("GRANT SELECT, UPDATE ON serving_config TO gov_app")
    op.execute("GRANT UPDATE (state, approved_by, investigation, updated_at) ON model_versions TO gov_app")
    op.execute(
        "GRANT UPDATE (state, approved_by, activated_at, superseded_at, rejection_justification) ON policies TO gov_app"
    )
    op.execute(
        "GRANT UPDATE (state, pre_post_report, decided_by, decision_justification, decided_at, updated_at) "
        "ON data_sources TO gov_app"
    )
    op.execute("GRANT UPDATE (status, registry_entry_id, confirmed_at) ON transitions TO gov_app")
    op.execute("GRANT UPDATE (state, report, finished_at) ON validation_runs TO gov_app")
    # INF-U4-03: el archivador lee versiones y transiciones y solo escribe la copia WORM.
    op.execute("GRANT SELECT ON model_versions, transitions TO gov_archiver")
    op.execute("GRANT UPDATE (archived_uri, archived_at) ON model_versions TO gov_archiver")
    # NFR-U4-30: ni siquiera el dueno borra historia.
    op.execute(f"REVOKE DELETE, TRUNCATE ON {', '.join(HISTORY)} FROM gov_migrator")
    op.execute(f"REVOKE ALL ON {', '.join(HISTORY)} FROM PUBLIC")


def downgrade() -> None:
    raise RuntimeError("las migraciones de governance-db no tienen downgrade")
