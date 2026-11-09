"""Los fixtures de PostgreSQL viven en `governance_pg.py` (una primaria, roles de U1); los de la API, aqui."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from api_support import ApiWorld
from governance_pg import Db, db, empty_db, pg, roles, template_db  # noqa: F401
from vectra_reference.generate import load_config, with_overrides
from vectra_reference.release import run_release


@pytest.fixture(scope="session")
def package_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """El paquete real de U5 (una entrega chica, 6 000 filas): bytes que governance verifica sin deserializar."""
    return run_release(
        tmp_path_factory.mktemp("release"), with_overrides(load_config(), n_rows=6000), enforce_min_auc=False
    ).package_dir


@pytest.fixture
def world(db: Db) -> Iterator[ApiWorld]:  # noqa: F811
    api = ApiWorld(db)
    try:
        yield api
    finally:
        api.close()
