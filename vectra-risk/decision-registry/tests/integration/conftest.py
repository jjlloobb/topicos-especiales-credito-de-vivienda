"""Los fixtures de PostgreSQL viven en `registry_pg.py` (los helpers se importan por nombre desde las pruebas)."""

from registry_pg import db, pg, roles, template_db  # noqa: F401
