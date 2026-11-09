"""P-U4-04 (Paso 9): 5 conexiones por replica, contadas en `pg_stat_activity` por `application_name`."""

from collections.abc import Iterator

import pytest
from evidence_support import FakeRegistry, SimClock, make_service, wait_for
from governance_pg import Db
from vectra_governance.convergence import ServingConfigCache
from vectra_governance.pools import POOL_SIZES

pytestmark = pytest.mark.integration


@pytest.fixture
def two_replicas(db: Db) -> Iterator[tuple[ServingConfigCache, ServingConfigCache]]:
    clock = SimClock()
    registry = FakeRegistry(clock)
    caches = []
    for replica in ("a", "b"):
        svc = make_service(db, registry, clock, replica)  # abre tx (2), read (1) y background (1)
        caches.append(ServingConfigCache(svc.pools, clock=clock))
    for cache in caches:
        cache.start()  # y la conexion `listen`
    yield caches[0], caches[1]
    for cache in caches:
        cache.stop()
        cache.pools.close()


def connections(db: Db) -> dict[str, int]:
    rows = db.query(
        "SELECT application_name, count(*) FROM pg_stat_activity WHERE application_name LIKE 'governance:%%' "
        "GROUP BY application_name"
    )
    return {str(name): int(count) for name, count in rows}  # type: ignore[call-overload]


def test_cada_replica_tiene_5_conexiones(db: Db, two_replicas: tuple[ServingConfigCache, ServingConfigCache]) -> None:
    assert wait_for(lambda: all(c.listening for c in two_replicas), 5) is not None
    found = connections(db)
    for replica in ("a", "b"):
        mine = {name: n for name, n in found.items() if name.startswith(f"governance:{replica}:")}
        assert mine == {
            f"governance:{replica}:tx": 2,
            f"governance:{replica}:read": 1,
            f"governance:{replica}:background": 1,
            f"governance:{replica}:listen": 1,
        }
        assert sum(mine.values()) == 5
    assert sum(found.values()) == 10


def test_los_tamanos_son_los_de_p_u4_04() -> None:
    assert {name: size for name, (size, _wait) in POOL_SIZES.items()} == {"tx": 2, "read": 1, "background": 1, "listen": 1}
