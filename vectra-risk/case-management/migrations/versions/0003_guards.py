"""`case_transitions` con `guard_transition`, `guard_vencido` y `guard_ever_degraded`.

Revision ID: 0003
Revises: 0002

Paso 3 del plan de U8. BR-U8-12; INF-U8-01; P-U8-05; NFR-U8-41.

- `guard_transition` (`BEFORE INSERT OR UPDATE OF state`, `SECURITY DEFINER`, dueno `case_migrator`, `SET search_path`): en `INSERT`
  exige `en_evaluacion`, sin recomendacion y el rol `case_app`; en `UPDATE` con cambio de estado exige la fila
  (`OLD.state`, `NEW.state`, `session_user`) en `case_transitions`. Usa `session_user` porque dentro de una funcion `SECURITY DEFINER`
  `current_user` es el dueno; cada proceso se conecta con su rol, sin cambiar de rol en la sesion ni usar un pooler (P-U1-08).
- `guard_vencido` (`SECURITY INVOKER`, `current_user`): la tabla de cuatro filas de P-U8-05; lee los plazos de `retention_settings`.
- `guard_ever_degraded`: `ever_degraded` nunca vuelve de `true` a `false`, tampoco con el dueno.
- Ningun rol de la aplicacion tiene permisos sobre `case_transitions`: solo la lee `guard_transition`.

`CASE_TRANSITIONS` es una constante literal (`from_state`, `to_state`, `db_role`) que U08-T02 carga por ruta para compararla con
la tabla de `case_fsm` (sin el rol y sin la fila de creacion, que cubre la rama `INSERT` del trigger). Son las 16 filas de INF-U8-01
expandidas a pares; `en_sincronizacion` -> `en_sincronizacion` esta en la tabla pero no dispara el trigger (el estado no cambia).
"""

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

CASE_TRANSITIONS = (
    # case_worker: {en_evaluacion, en_sincronizacion} x {listo, en_sincronizacion, no_disponible, modelo_congelado}
    ("en_evaluacion", "listo", "case_worker"),
    ("en_evaluacion", "en_sincronizacion", "case_worker"),
    ("en_evaluacion", "no_disponible", "case_worker"),
    ("en_evaluacion", "modelo_congelado", "case_worker"),
    ("en_sincronizacion", "listo", "case_worker"),
    ("en_sincronizacion", "en_sincronizacion", "case_worker"),
    ("en_sincronizacion", "no_disponible", "case_worker"),
    ("en_sincronizacion", "modelo_congelado", "case_worker"),
    # case_app: barrido de BR-U8-10 y `retry` hacia `en_evaluacion`; decision confirmada hacia `decidido`
    ("modelo_congelado", "en_evaluacion", "case_app"),
    ("no_disponible", "en_evaluacion", "case_app"),
    ("listo", "decidido", "case_app"),
    # case_retention: retencion vencida sin decision (BR-U8-20)
    ("en_evaluacion", "vencido", "case_retention"),
    ("listo", "vencido", "case_retention"),
    ("en_sincronizacion", "vencido", "case_retention"),
    ("no_disponible", "vencido", "case_retention"),
    ("modelo_congelado", "vencido", "case_retention"),
)

TRANSITIONS_TABLE = """
CREATE TABLE case_transitions (
    from_state text NOT NULL,
    to_state text NOT NULL,
    db_role text NOT NULL,
    PRIMARY KEY (from_state, to_state, db_role)
);
"""

GUARD_TRANSITION = """
CREATE FUNCTION guard_transition() RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        IF NEW.state IS DISTINCT FROM 'en_evaluacion' OR NEW.recommendation IS NOT NULL
           OR NEW.recommendation_entry_id IS NOT NULL OR session_user::text <> 'case_app' THEN
            RAISE EXCEPTION 'guard_transition: un caso nuevo nace en en_evaluacion, sin recomendacion y desde case_app (estado %, rol %)',
                NEW.state, session_user;
        END IF;
        RETURN NEW;
    END IF;
    IF NEW.state IS DISTINCT FROM OLD.state AND NOT EXISTS (
        SELECT 1 FROM case_transitions t
        WHERE t.from_state = OLD.state AND t.to_state = NEW.state AND t.db_role = session_user::text
    ) THEN
        RAISE EXCEPTION 'guard_transition: % -> % no esta permitida al rol %', OLD.state, NEW.state, session_user;
    END IF;
    RETURN NEW;
END
$$;
ALTER FUNCTION guard_transition() OWNER TO case_migrator;
REVOKE ALL ON FUNCTION guard_transition() FROM PUBLIC;
CREATE TRIGGER guard_transition BEFORE INSERT OR UPDATE OF state ON cases
    FOR EACH ROW EXECUTE FUNCTION guard_transition();
"""

GUARD_VENCIDO = """
CREATE FUNCTION guard_vencido() RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path = pg_catalog, public AS $$
DECLARE
    undecided integer;
BEGIN
    IF NEW.state = 'vencido' THEN
        IF current_user::text <> 'case_retention' THEN
            RAISE EXCEPTION 'guard_vencido: solo case_retention escribe vencido (rol %)', current_user;
        END IF;
        IF OLD.state IN ('decidido', 'vencido') THEN
            RAISE EXCEPTION 'guard_vencido: un caso % no pasa a vencido', OLD.state;
        END IF;
        SELECT s.undecided_years INTO undecided FROM retention_settings s WHERE s.id = 1;
        IF undecided IS NULL OR OLD.created_at + make_interval(years => undecided) >= now() THEN
            RAISE EXCEPTION 'guard_vencido: la retencion del caso no ha vencido';
        END IF;
    ELSIF current_user::text = 'case_retention' AND NEW.state <> OLD.state THEN
        RAISE EXCEPTION 'guard_vencido: case_retention solo escribe vencido (no %)', NEW.state;
    END IF;
    RETURN NEW;
END
$$;
CREATE TRIGGER guard_vencido BEFORE UPDATE OF state ON cases
    FOR EACH ROW EXECUTE FUNCTION guard_vencido();
"""

GUARD_EVER_DEGRADED = """
CREATE FUNCTION guard_ever_degraded() RETURNS trigger LANGUAGE plpgsql SET search_path = pg_catalog, public AS $$
BEGIN
    IF OLD.ever_degraded AND NOT NEW.ever_degraded THEN
        RAISE EXCEPTION 'guard_ever_degraded: ever_degraded no vuelve a false';
    END IF;
    RETURN NEW;
END
$$;
CREATE TRIGGER guard_ever_degraded BEFORE UPDATE OF ever_degraded ON cases
    FOR EACH ROW EXECUTE FUNCTION guard_ever_degraded();
"""


def upgrade() -> None:
    op.execute(TRANSITIONS_TABLE)
    values = ", ".join(f"('{a}', '{b}', '{role}')" for a, b, role in CASE_TRANSITIONS)
    op.execute(f"INSERT INTO case_transitions (from_state, to_state, db_role) VALUES {values}")
    op.execute(GUARD_TRANSITION)
    op.execute(GUARD_VENCIDO)
    op.execute(GUARD_EVER_DEGRADED)


def downgrade() -> None:
    raise RuntimeError("las migraciones de case-db no tienen downgrade")
