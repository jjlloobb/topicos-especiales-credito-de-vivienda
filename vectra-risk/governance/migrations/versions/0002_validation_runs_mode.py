"""`validation_runs.mode`, `source_id` y `baseline_version_id` (segunda revision del FD de U9, 2026-10-08).

Revision ID: 0002
Revises: 0001

Paso 2 del plan de U4. domain-entities §2.1. Las filas existentes quedan con `mode = 'validacion'`.
"""

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE validation_runs "
        "ADD COLUMN mode text NOT NULL DEFAULT 'validacion' CHECK (mode IN ('validacion', 'source_comparison')), "
        "ADD COLUMN source_id text REFERENCES data_sources (ds_id), "
        "ADD COLUMN baseline_version_id text REFERENCES model_versions (model_version_id)"
    )
    # En `source_comparison`, fuente y version base son obligatorias; en `validacion`, nulas.
    op.execute(
        """
        ALTER TABLE validation_runs ADD CONSTRAINT validation_runs_mode_source CHECK (
            (mode = 'source_comparison' AND source_id IS NOT NULL AND baseline_version_id IS NOT NULL)
            OR (mode = 'validacion' AND source_id IS NULL AND baseline_version_id IS NULL)
        )
        """
    )


def downgrade() -> None:
    raise RuntimeError("las migraciones de governance-db no tienen downgrade")
