"""Entorno de Alembic de `case-db`: SQL plano, sin modelos; una conexion psycopg 3 y una transaccion por revision.

P-1 (U08-T01): despues de las revisiones, y en la misma conexion de `case_migrator`, el entorno hace el upsert de
`retention_settings` con los plazos de los values de Helm (`retention.*`), que el Job de migracion (Paso 20) pasa en
`RETENTION_DECIDED_YEARS`, `RETENTION_UNDECIDED_YEARS` y `RETENTION_INTAKE_KEYS_DAYS`. Una revision que ya corrio no vuelve a
correr, asi que el upsert no puede vivir en una revision. Falta una variable o no es un entero positivo: la migracion falla.
La conexion usa la URL tal cual: sin cambiar de rol en la sesion ni de usuario (`guard_transition` depende de `session_user`, P-U1-08).
"""

import os

from alembic import context
from sqlalchemy import Connection, create_engine, text

config = context.config

RETENTION_VARIABLES = {
    "decided_years": "RETENTION_DECIDED_YEARS",
    "undecided_years": "RETENTION_UNDECIDED_YEARS",
    "intake_keys_days": "RETENTION_INTAKE_KEYS_DAYS",
}


def _url() -> str:
    url = config.get_main_option("sqlalchemy.url") or os.environ.get("CASE_DATABASE_URL")
    if not url:
        raise RuntimeError("falta sqlalchemy.url o CASE_DATABASE_URL")
    return url.replace("postgresql://", "postgresql+psycopg://", 1)


def retention_values() -> dict[str, int]:
    """Los tres plazos de `retention.*`; todos obligatorios y enteros positivos."""
    values: dict[str, int] = {}
    for column, variable in RETENTION_VARIABLES.items():
        raw = os.environ.get(variable, "")
        try:
            number = int(raw)
        except ValueError:
            number = 0
        if number <= 0 or str(number) != raw.strip():
            raise RuntimeError(
                f"{variable} debe ser un entero positivo (retention.{column}); recibido {raw!r}"
            )
        values[column] = number
    return values


def upsert_retention_settings(connection: Connection, values: dict[str, int]) -> None:
    """P-U8-05: actualiza los plazos y `updated_at`, nunca `created_at`."""
    connection.execute(
        text(
            "INSERT INTO retention_settings (id, decided_years, undecided_years, intake_keys_days) "
            "VALUES (1, :decided_years, :undecided_years, :intake_keys_days) "
            "ON CONFLICT (id) DO UPDATE SET decided_years = EXCLUDED.decided_years, "
            "undecided_years = EXCLUDED.undecided_years, intake_keys_days = EXCLUDED.intake_keys_days, updated_at = now()"
        ),
        values,
    )
    connection.commit()


def run_migrations_online() -> None:
    values = retention_values()  # antes de tocar la base: sin plazos validos no se migra
    engine = create_engine(_url())
    try:
        with engine.connect() as connection:
            context.configure(connection=connection, target_metadata=None, transaction_per_migration=True)
            with context.begin_transaction():
                context.run_migrations()
            connection.commit()
            upsert_retention_settings(connection, values)
    finally:
        engine.dispose()


if context.is_offline_mode():
    raise RuntimeError("las migraciones de case-db no tienen modo offline")
run_migrations_online()
