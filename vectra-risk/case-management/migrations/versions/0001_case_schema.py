"""Tablas de `case-db` (domain-entities §1 a §3), sus indices parciales y la fila de `retention_settings`.

Revision ID: 0001

Paso 3 del plan de U8 (U08-T01). BR-U8-02, 12, 18, 20; P-U8-05.

- `evaluation_jobs`: el trabajo se borra al terminar (BR-U8-07), asi que toda fila esta viva y el indice unico sobre `case_id` es
  el de «un trabajo vivo por caso»; `CHECK (attempt BETWEEN 0 AND 6)`.
- `decisions`: indice unico parcial por `case_id` sobre `pendiente_registro` o `confirmada` (una `abandonada` no impide decidir).
- `evidence_outbox`: `UNIQUE (idempotency_key) WHERE state <> 'abandonada'` (domain-entities §3.1).
- `explanation_views`: clave (`case_id`, `user_id`) (BR-U8-19).
- `retention_settings`: una fila (`CHECK (id = 1)`); la primera revision la crea con los valores por omisión de P-U8-05 y el
  `env.py` la actualiza desde los values en cada migracion (P-1).

Sin `downgrade`, como en U3 y U4. Los grants (0002) y los guardas (0003) van aparte.
"""

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

STATES = "'en_evaluacion', 'listo', 'en_sincronizacion', 'no_disponible', 'modelo_congelado', 'decidido', 'vencido'"
EVIDENCE_STATES = "'pendiente_registro', 'confirmada', 'abandonada'"

TABLES = f"""
CREATE TABLE cases (
    case_id uuid PRIMARY KEY,
    state text NOT NULL CHECK (state IN ({STATES})),
    channel text NOT NULL,
    created_by jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    application jsonb NOT NULL,
    test_scenario_id text,
    escalation_count integer NOT NULL DEFAULT 0 CHECK (escalation_count >= 0),
    ever_degraded boolean NOT NULL DEFAULT false,
    attempts integer NOT NULL DEFAULT 0 CHECK (attempts BETWEEN 0 AND 6),
    last_cause text,
    recommendation jsonb,
    recommendation_entry_id text,
    model_frozen_after_recommendation boolean NOT NULL DEFAULT false,
    anonymized_at timestamptz
);

CREATE TABLE case_identifiers (
    case_id uuid PRIMARY KEY REFERENCES cases (case_id),
    full_name text NOT NULL,
    document_type text NOT NULL,
    document_number text NOT NULL,
    birth_date date NOT NULL,
    phone text,
    email text,
    address text,
    municipality_code text NOT NULL
);

CREATE TABLE intake_keys (
    scope text NOT NULL,
    idempotency_key text NOT NULL,
    body_sha256 text NOT NULL,
    case_id uuid NOT NULL REFERENCES cases (case_id),
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (scope, idempotency_key)
);

CREATE TABLE retention_runs (
    run_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    started_at timestamptz NOT NULL,
    finished_at timestamptz NOT NULL,
    status text NOT NULL CHECK (status IN ('exitosa', 'fallida')),
    anonymized_count integer NOT NULL DEFAULT 0,
    expired_count integer NOT NULL DEFAULT 0,
    overdue_remaining integer NOT NULL DEFAULT 0
);

CREATE TABLE retention_settings (
    id integer PRIMARY KEY CHECK (id = 1),
    decided_years integer NOT NULL CHECK (decided_years > 0),
    undecided_years integer NOT NULL CHECK (undecided_years > 0),
    intake_keys_days integer NOT NULL CHECK (intake_keys_days > 0),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
-- Valores por omision de P-U8-05; `env.py` los reemplaza con `retention.*` en cada migracion sin tocar `created_at`.
INSERT INTO retention_settings (id, decided_years, undecided_years, intake_keys_days) VALUES (1, 10, 2, 30);

CREATE TABLE evaluation_jobs (
    case_id uuid NOT NULL REFERENCES cases (case_id),
    attempt integer NOT NULL DEFAULT 0 CHECK (attempt BETWEEN 0 AND 6),
    run_at timestamptz NOT NULL DEFAULT now(),
    locked_until timestamptz
);
CREATE UNIQUE INDEX evaluation_jobs_one_live_job_per_case ON evaluation_jobs (case_id);
CREATE INDEX evaluation_jobs_run_at ON evaluation_jobs (run_at);

CREATE TABLE evidence_outbox (
    evidence_id uuid PRIMARY KEY,
    case_id uuid NOT NULL REFERENCES cases (case_id),
    entry_type text NOT NULL CHECK (entry_type IN ('human_decision', 'explanation_view', 'fail_closed')),
    idempotency_key uuid NOT NULL,
    payload jsonb NOT NULL,
    state text NOT NULL DEFAULT 'pendiente_registro'
        CHECK (state IN ({EVIDENCE_STATES}, 'descartada')),
    registry_entry_id text,
    attempts integer NOT NULL DEFAULT 0,
    next_attempt_at timestamptz NOT NULL DEFAULT now(),
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX evidence_outbox_live_key ON evidence_outbox (idempotency_key) WHERE state <> 'abandonada';
CREATE INDEX evidence_outbox_pending ON evidence_outbox (next_attempt_at) WHERE state = 'pendiente_registro';

CREATE TABLE decisions (
    decision_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id uuid NOT NULL REFERENCES cases (case_id),
    decision text NOT NULL,
    final_outcome text NOT NULL,
    used_factors jsonb NOT NULL,
    justification text NOT NULL,
    explanation_viewed_before boolean NOT NULL,
    decided_by jsonb NOT NULL,
    decided_at timestamptz NOT NULL DEFAULT now(),
    evidence_id uuid NOT NULL REFERENCES evidence_outbox (evidence_id),
    state text NOT NULL DEFAULT 'pendiente_registro' CHECK (state IN ({EVIDENCE_STATES}))
);
CREATE UNIQUE INDEX decisions_live_case ON decisions (case_id) WHERE state IN ('pendiente_registro', 'confirmada');

CREATE TABLE explanation_views (
    case_id uuid NOT NULL REFERENCES cases (case_id),
    user_id text NOT NULL,
    first_viewed_at timestamptz NOT NULL DEFAULT now(),
    evidence_id uuid NOT NULL REFERENCES evidence_outbox (evidence_id),
    PRIMARY KEY (case_id, user_id)
);
"""


def upgrade() -> None:
    op.execute(TABLES)


def downgrade() -> None:
    raise RuntimeError("las migraciones de case-db no tienen downgrade")
