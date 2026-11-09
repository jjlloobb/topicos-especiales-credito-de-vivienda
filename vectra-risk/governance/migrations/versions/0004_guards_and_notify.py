"""`guard_unfreeze` cierra toda salida de `congelado`, `investigation` solo `false -> true` y `NOTIFY` solo si cambia el `etag`.

Revision ID: 0004
Revises: 0003

Paso 8 y 9 del plan de U4 (U04-T03). `plans/governance-bloque-d-precisiones.md` Q-1, Q-2 y Q-4; P-U4-06; P-U4-01.

- Q-1: toda actualizacion con `OLD.state = 'congelado'` y `NEW.state` distinto se rechaza, salvo a `activo` o `retirado`
  con la `frozen_resolution` confirmada de cumplimiento cuyo `to_state` sea el estado nuevo. `congelado -> inactivo`
  (y despues `inactivo -> activo`) ya no reactiva sin resolucion.
- Q-2: `investigation` solo pasa de `false` a `true`, en una version `congelado` que sigue `congelado`, con la resolucion
  `investigar` (la fila confirmada `congelado -> congelado`). Cualquier otro cambio se rechaza en cualquier estado.
- Q-4: el trigger de `serving_config` se dispara solo si cambia el `etag` y la funcion nunca notifica con payload vacio.
  El trigger pasa a `AFTER UPDATE`: `serving_config` es una sola fila sembrada en `0001`, no recibe `INSERT` (y `OLD`
  no existe en un trigger de `INSERT`).

Sin `downgrade`, como `0001`-`0003`.
"""

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

GUARD_UNFREEZE = """
CREATE OR REPLACE FUNCTION guard_unfreeze() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    resolution text := current_setting('vectra.frozen_resolution', true);
    leaves boolean := NEW.state IS DISTINCT FROM OLD.state;
    marks boolean := NEW.investigation IS DISTINCT FROM OLD.investigation;
BEGIN
    -- Q-2: `investigation` solo cambia de false a true, en `congelado` que sigue `congelado`.
    IF marks AND NOT (OLD.state = 'congelado' AND NOT leaves AND NOT OLD.investigation AND NEW.investigation) THEN
        RAISE EXCEPTION 'guard_unfreeze: investigation solo pasa de false a true en la version % congelada y con la resolucion investigar',
            OLD.model_version_id USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF OLD.state = 'congelado' AND (leaves OR marks) THEN
        -- Q-1: la unica salida es a `activo` o `retirado`.
        IF leaves AND NEW.state NOT IN ('activo', 'retirado') THEN
            RAISE EXCEPTION 'guard_unfreeze: la version % congelada solo sale a activo o retirado, no a %',
                OLD.model_version_id, NEW.state USING ERRCODE = 'insufficient_privilege';
        END IF;
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

NOTIFY_FUNCTION = """
CREATE OR REPLACE FUNCTION notify_serving_config() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    -- P-U4-01: PostgreSQL entrega la notificacion al confirmar la transaccion, no antes.
    -- Q-4: nunca con payload vacio; un `etag` nulo lo cubre el sondeo de 1 s.
    IF NEW.etag IS NOT NULL AND NEW.etag <> '' THEN
        PERFORM pg_notify('serving_config', NEW.etag);
    END IF;
    RETURN NULL;
END $$
"""


def upgrade() -> None:
    op.execute(GUARD_UNFREEZE)
    op.execute(NOTIFY_FUNCTION)
    op.execute("DROP TRIGGER notify_serving_config ON serving_config")
    op.execute(
        "CREATE TRIGGER notify_serving_config AFTER UPDATE ON serving_config "
        "FOR EACH ROW WHEN (NEW.etag IS DISTINCT FROM OLD.etag) EXECUTE FUNCTION notify_serving_config()"
    )


def downgrade() -> None:
    raise RuntimeError("las migraciones de governance-db no tienen downgrade")
