"""Las propiedades de `append` corren contra el cluster de Testcontainers (primaria + standby) de `tests/integration`."""

import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "integration"))

from cluster_dbs import drop_db, make_db  # noqa: E402
from registry_cluster import Cluster, ClusterDb, cluster, cluster_template  # noqa: E402, F401


@pytest.fixture(scope="module")
def shared_db(request: pytest.FixtureRequest) -> Iterator[ClusterDb]:
    """Una base para todos los ejemplos de un modulo (las propiedades de tiempo solo necesitan una cabeza que avance)."""
    live: Cluster = request.getfixturevalue("cluster")
    cdb = make_db(live, request.getfixturevalue("cluster_template"))
    yield cdb
    drop_db(cdb)
