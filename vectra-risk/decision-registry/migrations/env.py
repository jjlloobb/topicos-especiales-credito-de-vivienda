"""Entorno de Alembic de `registry-db`: SQL plano, sin modelos; una conexion psycopg 3 y una transaccion por revision."""

import os

from alembic import context
from sqlalchemy import create_engine

config = context.config


def _url() -> str:
    url = config.get_main_option("sqlalchemy.url") or os.environ.get("REGISTRY_DATABASE_URL")
    if not url:
        raise RuntimeError("falta sqlalchemy.url o REGISTRY_DATABASE_URL")
    return url.replace("postgresql://", "postgresql+psycopg://", 1)


def run_migrations_online() -> None:
    engine = create_engine(_url())
    try:
        with engine.connect() as connection:
            context.configure(connection=connection, target_metadata=None, transaction_per_migration=True)
            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()


if context.is_offline_mode():
    raise RuntimeError(
        "las migraciones de registry-db no tienen modo offline: la genesis se calcula al aplicarlas"
    )
run_migrations_online()
