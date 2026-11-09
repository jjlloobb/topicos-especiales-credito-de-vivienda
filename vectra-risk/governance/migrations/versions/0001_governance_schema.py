"""Tablas de `governance-db`, indices parciales, triggers de P-U4-06 y NOTIFY de `serving_config`.

Revision ID: 0001
Revises:

Paso 2 del plan de U4. domain-entities §1-§5; BR-U4-02, 03, 17; P-U4-01, 06.
`validation_runs` se crea aqui sin `mode`; la revision 0002 lo agrega (la migracion de datos existentes, segunda revision del FD de U9).
Los roles los crea U1 (CloudNativePG, `platform/data`); los grants van en la revision 0003.
La llave de idempotencia de `transitions` (UUIDv5(`entity_type:entity_id`, n), BR-U4-17) la calcula el servicio al crear la fila;
aqui es `NOT NULL` y sin `UNIQUE`: tras un abandono, la transicion nueva con el mismo `n` reutiliza la llave (BR-U4-17).
"""

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

MODEL_STATES = (
    "registrado",
    "en_validacion",
    "validacion_fallida",
    "lista_para_aprobacion",
    "aprobado",
    "rechazado",
    "activo",
    "inactivo",
    "congelado",
    "retirado",
)
POLICY_STATES = ("propuesta", "activa", "rechazada", "historica")
SOURCE_STATES = ("propuesta", "en_evaluacion", "aprobada", "rechazada")
ARTIFACT_FORMATS = ("onnx", "xgboost_json", "xgboost_ubj", "lightgbm_txt")
RUN_STATES = ("lanzado", "informe_recibido", "fallido", "timeout")
ENTITY_TYPES = ("model_version", "policy", "data_source")
TRANSITION_KINDS = ("cambio_estado", "compensacion")
TRANSITION_STATUSES = ("pendiente_registro", "confirmada", "abandonada", "descartada")


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


GUARD_UNFREEZE = """
CREATE FUNCTION guard_unfreeze() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    resolution text := current_setting('vectra.frozen_resolution', true);
BEGIN
    IF OLD.state = 'congelado'
       AND (NEW.state IN ('activo', 'retirado') OR NEW.investigation IS DISTINCT FROM OLD.investigation) THEN
        IF resolution IS NULL OR resolution = '' OR NOT EXISTS (
            SELECT 1 FROM transitions t
            WHERE t.transition_id::text = resolution
              AND t.status = 'confirmada'
              AND t.entity_type = 'model_version'
              AND t.entity_id = OLD.model_version_id
              AND t.kind = 'cambio_estado'
              AND t.from_state = 'congelado'
              AND t.to_state = NEW.state
              AND t.actor ->> 'role' = 'cumplimiento'
        ) THEN
            RAISE EXCEPTION 'guard_unfreeze: la version % esta congelada y no hay una frozen_resolution confirmada de cumplimiento',
                OLD.model_version_id USING ERRCODE = 'insufficient_privilege';
        END IF;
    END IF;
    RETURN NEW;
END $$
"""

# El `freeze` cambia el estado sin esperar el ack (BR-U4-15): su transicion puede estar `pendiente_registro` o `confirmada`.
GUARD_FREEZE = """
CREATE FUNCTION guard_freeze() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    freeze_id text := current_setting('vectra.freeze', true);
BEGIN
    IF NEW.state = 'congelado' AND OLD.state IS DISTINCT FROM 'congelado' THEN
        IF freeze_id IS NULL OR freeze_id = '' OR NOT EXISTS (
            SELECT 1 FROM transitions t
            WHERE t.transition_id::text = freeze_id
              AND t.status IN ('pendiente_registro', 'confirmada')
              AND t.entity_type = 'model_version'
              AND t.entity_id = OLD.model_version_id
              AND t.kind = 'cambio_estado'
              AND t.to_state = 'congelado'
              AND t.actor ->> 'sub' = 'bias-monitoring-job'
        ) THEN
            RAISE EXCEPTION 'guard_freeze: la version % solo pasa a congelado con una transicion freeze de bias-monitoring-job',
                OLD.model_version_id USING ERRCODE = 'insufficient_privilege';
        END IF;
    END IF;
    RETURN NEW;
END $$
"""

NOTIFY_FUNCTION = """
CREATE FUNCTION notify_serving_config() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    -- P-U4-01: PostgreSQL entrega la notificacion al confirmar la transaccion, no antes.
    PERFORM pg_notify('serving_config', COALESCE(NEW.etag, ''));
    RETURN NULL;
END $$
"""


def upgrade() -> None:
    op.execute(
        f"""
        CREATE TABLE data_sources (
            ds_id text PRIMARY KEY,
            name text NOT NULL,
            description text NOT NULL DEFAULT '',
            provides_features text[] NOT NULL DEFAULT '{{}}',
            owner text NOT NULL,
            proposed_by text NOT NULL,
            state text NOT NULL DEFAULT 'propuesta' CHECK ({_in("state", SOURCE_STATES)}),
            pre_post_report jsonb,
            decided_by text,
            decision_justification text,
            decided_at timestamptz,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE model_versions (
            model_version_id text PRIMARY KEY,
            state text NOT NULL DEFAULT 'registrado' CHECK ({_in("state", MODEL_STATES)}),
            artifact_uri text NOT NULL,
            artifact_format text NOT NULL CHECK ({_in("artifact_format", ARTIFACT_FORMATS)}),
            artifact_sha256 text NOT NULL CHECK (artifact_sha256 ~ '^[0-9a-f]{{64}}$'),
            explainer_uri text NOT NULL,
            explainer_sha256 text NOT NULL CHECK (explainer_sha256 ~ '^[0-9a-f]{{64}}$'),
            inference_service text NOT NULL,
            manifest_uri text NOT NULL,
            manifest_sha256 text NOT NULL CHECK (manifest_sha256 ~ '^[0-9a-f]{{64}}$'),
            feature_dictionary_version text NOT NULL,
            feature_dictionary jsonb NOT NULL,
            feature_spec jsonb NOT NULL,
            data_sources text[] NOT NULL DEFAULT '{{}}',
            source_candidate_for text REFERENCES data_sources (ds_id),
            registered_by text NOT NULL,
            approved_by text,
            investigation boolean NOT NULL DEFAULT false,
            archived_uri text,
            archived_at timestamptz,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    # Una sola version `activo` o `congelado` a la vez (BR-U4-02).
    op.execute(
        "CREATE UNIQUE INDEX model_versions_one_live ON model_versions ((true)) WHERE state IN ('activo', 'congelado')"
    )
    op.execute(
        f"""
        CREATE TABLE policies (
            policy_version_id text PRIMARY KEY,
            cutoff numeric NOT NULL,
            low_confidence_threshold numeric NOT NULL,
            channel_rules jsonb NOT NULL,
            normative jsonb NOT NULL,
            state text NOT NULL DEFAULT 'propuesta' CHECK ({_in("state", POLICY_STATES)}),
            proposed_by text NOT NULL,
            approved_by text,
            activated_at timestamptz,
            superseded_at timestamptz,
            rejection_justification text,
            created_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    # Como maximo una politica `activa` (domain-entities §3.1).
    op.execute("CREATE UNIQUE INDEX policies_one_active ON policies ((true)) WHERE state = 'activa'")
    op.execute(
        f"""
        CREATE TABLE transitions (
            transition_id uuid PRIMARY KEY,
            entity_type text NOT NULL CHECK ({_in("entity_type", ENTITY_TYPES)}),
            entity_id text NOT NULL,
            transition_number integer NOT NULL CHECK (transition_number >= 1),
            idempotency_key uuid NOT NULL,
            from_state text NOT NULL,
            to_state text NOT NULL,
            actor jsonb NOT NULL,
            justification text,
            kind text NOT NULL DEFAULT 'cambio_estado' CHECK ({_in("kind", TRANSITION_KINDS)}),
            status text NOT NULL DEFAULT 'pendiente_registro' CHECK ({_in("status", TRANSITION_STATUSES)}),
            unit_id uuid,
            event_payload jsonb NOT NULL,
            correlation_id text NOT NULL,
            registry_entry_id text,
            created_at timestamptz NOT NULL DEFAULT now(),
            confirmed_at timestamptz,
            -- Una compensacion no cambia estado y solo existe en versiones de modelo (BR-U4-17).
            CONSTRAINT transitions_compensation CHECK (
                kind <> 'compensacion' OR (from_state = to_state AND entity_type = 'model_version')
            ),
            CONSTRAINT transitions_confirmed CHECK (status <> 'confirmada' OR confirmed_at IS NOT NULL)
        )
        """
    )
    # `abandonada` libera el `n`; `descartada` y las pendientes lo conservan (precisado el 2026-10-06, revision del FD de U8).
    op.execute(
        "CREATE UNIQUE INDEX transitions_entity_n ON transitions (entity_type, entity_id, transition_number) "
        "WHERE status <> 'abandonada'"
    )
    op.execute(
        "CREATE INDEX transitions_pending ON transitions (created_at) WHERE status = 'pendiente_registro'"
    )
    op.execute("CREATE INDEX transitions_idempotency_key ON transitions (idempotency_key)")
    # domain-entities §2.2: el `ValidationReport` va como columna JSON de la corrida que lo recibe.
    op.execute(
        f"""
        CREATE TABLE validation_runs (
            run_id uuid PRIMARY KEY,
            model_version_id text NOT NULL REFERENCES model_versions (model_version_id),
            job_name text NOT NULL,
            state text NOT NULL DEFAULT 'lanzado' CHECK ({_in("state", RUN_STATES)}),
            report jsonb,
            started_at timestamptz NOT NULL DEFAULT now(),
            deadline_at timestamptz NOT NULL,
            finished_at timestamptz
        )
        """
    )
    # Una sola fila (domain-entities §5): nula hasta la primera transicion confirmada.
    op.execute(
        """
        CREATE TABLE serving_config (
            id smallint PRIMARY KEY DEFAULT 1 CHECK (id = 1),
            model_version_id text REFERENCES model_versions (model_version_id),
            state text,
            policy_version_id text REFERENCES policies (policy_version_id),
            feature_dictionary_version text,
            inference_service text,
            normative_current jsonb,
            effective_from timestamptz,
            etag text
        )
        """
    )
    op.execute("INSERT INTO serving_config (id) VALUES (1)")
    op.execute(GUARD_UNFREEZE)
    op.execute(GUARD_FREEZE)
    op.execute(NOTIFY_FUNCTION)
    op.execute(
        "CREATE TRIGGER guard_unfreeze BEFORE UPDATE ON model_versions FOR EACH ROW EXECUTE FUNCTION guard_unfreeze()"
    )
    op.execute(
        "CREATE TRIGGER guard_freeze BEFORE UPDATE ON model_versions FOR EACH ROW EXECUTE FUNCTION guard_freeze()"
    )
    op.execute(
        "CREATE TRIGGER notify_serving_config AFTER INSERT OR UPDATE ON serving_config "
        "FOR EACH ROW EXECUTE FUNCTION notify_serving_config()"
    )


def downgrade() -> None:
    raise RuntimeError(
        "las migraciones de governance-db no tienen downgrade: las tablas de historia no se borran"
    )
