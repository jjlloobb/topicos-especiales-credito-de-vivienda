"""Tablas derivadas de monitoreo e `integrity_checks`, con sus grants.

Revision ID: 0002
Revises: 0001

Paso 2 del plan de U3. domain-entities §1.2, §1.3 y §5.0; BR-U3-02, 13b, 17; NFR-U3-42.
Las tablas derivadas no llevan el trigger de solo-anexar: se reconstruyen desde la cadena (BR-U3-02, 17).
`integrity_checks` tampoco: es el estado de una operacion, no evidencia (domain-entities §5.0); nadie tiene `DELETE` ni `TRUNCATE`.
"""

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

# Catalogo de U0 §2.2: atributos de monitoreo y sus grupos (22 en total), bandas y resultados.
GROUPS = {
    "sexo": ("F", "M", "no_informado"),
    "rango_edad": ("18-25", "26-35", "36-45", "46-55", "56-65", "66+"),
    "region": ("andina", "caribe", "pacifica", "orinoquia", "amazonia", "insular"),
    "estrato": ("1", "2", "3", "4", "5", "6", "no_informado"),
}
BANDS = ("lt_20", "20_30", "gt_30")
OUTCOMES = ("favorable", "desfavorable", "revision_requerida")
FINAL_OUTCOMES = ("favorable", "desfavorable")
DECISIONS = ("sigue", "se_aparta", "resuelve_revision")
POPULATIONS = ("modelo", "humana")

DERIVED = (
    "monitoring_daily",
    "monitoring_entry_totals",
    "monitoring_case_index",
    "monitoring_invalid",
    "monitoring_watermark",
)


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


def upgrade() -> None:
    pairs = " OR ".join(f"(attribute = '{a}' AND {_in('"group"', g)})" for a, g in GROUPS.items())
    population = _in("population", POPULATIONS)
    op.execute(
        f"""
        CREATE TABLE monitoring_daily (
            population       text   NOT NULL CHECK ({population}),
            model_version_id text   NOT NULL,
            day              date   NOT NULL,
            attribute        text   NOT NULL,
            "group"          text   NOT NULL,
            band             text   NOT NULL CHECK ({_in("band", BANDS)}),
            result           text   NOT NULL CHECK ({_in("result", OUTCOMES)}),
            decision         text   NOT NULL CHECK ({_in("decision", (*DECISIONS, "-"))}),
            count            bigint NOT NULL CHECK (count >= 0),
            PRIMARY KEY (population, model_version_id, day, attribute, "group", band, result, decision),
            CHECK ({pairs}),
            -- `modelo`: `outcome` y decision '-'; `humana`: `final_outcome` y una decision.
            CHECK ((population = 'modelo' AND decision = '-') OR (population = 'humana' AND decision <> '-' AND {_in("result", FINAL_OUTCOMES)}))
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE monitoring_entry_totals (
            population       text   NOT NULL CHECK ({population}),
            model_version_id text   NOT NULL,
            day              date   NOT NULL,
            total            bigint NOT NULL,
            invalid          bigint NOT NULL,
            PRIMARY KEY (population, model_version_id, day),
            CHECK (total >= 0 AND invalid >= 0 AND invalid <= total)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE monitoring_case_index (
            case_id          uuid        PRIMARY KEY,
            counted_seq      bigint,
            evaluated_at     timestamptz NOT NULL,
            fixed_by_decision boolean    NOT NULL
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE monitoring_invalid (
            seq              bigint PRIMARY KEY,
            population       text   NOT NULL CHECK ({population}),
            model_version_id text   NOT NULL,
            day              date   NOT NULL,
            reason           text   NOT NULL
        )
        """
    )
    op.execute(
        """
        CREATE TABLE monitoring_watermark (
            id         smallint    PRIMARY KEY CHECK (id = 1),
            last_seq   bigint      NOT NULL CHECK (last_seq >= 0),
            updated_at timestamptz NOT NULL
        )
        """
    )
    # Una sola fila: el `FOR UPDATE` de cada lote del agregador la necesita y el `reset` no la borra (BR-U3-17).
    op.execute("INSERT INTO monitoring_watermark (id, last_seq, updated_at) VALUES (1, 0, now())")

    op.execute(
        """
        CREATE TABLE integrity_checks (
            check_id          uuid        PRIMARY KEY,
            mode              text        NOT NULL CHECK (mode IN ('full', 'range')),
            from_seq          bigint,
            to_seq            bigint,
            requested_by      text        NOT NULL,
            requested_at      timestamptz NOT NULL,
            started_at        timestamptz,
            finished_at       timestamptz,
            heartbeat_at      timestamptz,
            status            text        NOT NULL CHECK (status IN ('pendiente', 'en_curso', 'terminada', 'fallida')),
            progress_checked  bigint      NOT NULL DEFAULT 0,
            progress_total    bigint      NOT NULL DEFAULT 0,
            report            jsonb,
            reason            text        CHECK (reason IN ('interrumpida', 'error_de_ejecucion', 'plazo_vencido')),
            CONSTRAINT integrity_checks_progress CHECK (progress_checked <= progress_total),
            CONSTRAINT integrity_checks_report CHECK ((status = 'terminada') = (report IS NOT NULL)),
            CONSTRAINT integrity_checks_reason CHECK ((status = 'fallida') = (reason IS NOT NULL)),
            CONSTRAINT integrity_checks_range CHECK (
                (mode = 'range' AND from_seq IS NOT NULL AND to_seq IS NOT NULL AND from_seq <= to_seq)
                OR (mode = 'full' AND from_seq IS NULL AND to_seq IS NULL)
            )
        )
        """
    )
    # Una sola verificacion activa, de cualquier modo: indice unico parcial sobre una expresion constante.
    op.execute(
        "CREATE UNIQUE INDEX integrity_checks_single_active ON integrity_checks ((1)) "
        "WHERE status IN ('pendiente', 'en_curso')"
    )

    # Grants (domain-entities §1.2, §5.0). Nadie recibe `DELETE` ni `TRUNCATE` sobre `integrity_checks`.
    op.execute("GRANT SELECT, INSERT ON integrity_checks TO registry_app")
    op.execute("GRANT SELECT ON integrity_checks TO registry_verifier")
    op.execute("GRANT SELECT, INSERT ON integrity_checks TO registry_ondemand")
    op.execute(
        "GRANT UPDATE (status, started_at, finished_at, heartbeat_at, progress_checked, progress_total, report, reason) "
        "ON integrity_checks TO registry_ondemand"
    )
    # `registry_aggregator`: lee la cadena y escribe solo las derivadas, sin `TRUNCATE` (el `reset` lo hace `registry_migrator`).
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {', '.join(DERIVED)} TO registry_aggregator")
    # `registry_verifier`: las derivadas salvo `monitoring_case_index`, que es interna.
    op.execute(
        "GRANT SELECT ON monitoring_daily, monitoring_entry_totals, monitoring_invalid, monitoring_watermark "
        "TO registry_verifier"
    )


def downgrade() -> None:
    raise RuntimeError("no hay downgrade en registry-db (BR-U3-02)")
