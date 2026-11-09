"""Las propiedades de `append` corren contra el cluster de Testcontainers (primaria + standby) de `tests/integration`."""

import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

# `tests/property/` es un paquete (`__init__.py`) para que su `test_aggregator.py` no choque con el de `tests/integration/` al correr los dos
# juntos; por eso sus hermanos (`cluster_dbs`) y los de `integration/` se agregan al path a mano.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "integration"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from cluster_dbs import drop_db, make_db  # noqa: E402
from registry_cluster import Cluster, ClusterDb, cluster, cluster_template  # noqa: E402, F401


@pytest.fixture(scope="module")
def shared_db(request: pytest.FixtureRequest) -> Iterator[ClusterDb]:
    """Una base para todos los ejemplos de un modulo (las propiedades de tiempo solo necesitan una cabeza que avance)."""
    live: Cluster = request.getfixturevalue("cluster")
    cdb = make_db(live, request.getfixturevalue("cluster_template"))
    yield cdb
    drop_db(cdb)
