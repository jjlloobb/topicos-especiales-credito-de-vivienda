"""Los fixtures de PostgreSQL viven en `registry_pg.py` (una primaria) y `registry_cluster.py` (primaria + standby sincrono).

`env` arma el servicio completo sobre una base del cluster: los cuatro pools de P-U3-04 (primaria y standby reales), un reloj fijo
y un cliente HTTP contra la app de `create_app`, con tokens firmados con las llaves de prueba de U0.
"""

import json
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

import httpx
import pytest
from entries import entry_dict
from registry_cluster import ClusterDb, cdb, cluster, cluster_template  # noqa: F401
from registry_pg import db, pg, roles, template_db  # noqa: F401
from service_harness import APPEND_CASE, APPEND_GOVERNANCE, APPEND_SCORING, Clock, client_for, service_token
from vectra_registry.api import ServiceConfig
from vectra_registry.pools import Pools

APPEND_SCOPE = {
    "recommendation": APPEND_SCORING,
    "fail_closed": APPEND_SCORING,
    "human_decision": APPEND_CASE,
    "explanation_view": APPEND_CASE,
    "model_event": APPEND_GOVERNANCE,
    "policy_event": APPEND_GOVERNANCE,
    "data_source_event": APPEND_GOVERNANCE,
    "freeze": APPEND_GOVERNANCE,
    "frozen_resolution": APPEND_GOVERNANCE,
}


@dataclass
class Env:
    cdb: ClusterDb
    pools: Pools
    clock: Clock
    config: ServiceConfig
    client: httpx.AsyncClient

    async def post(self, data: dict[str, Any], scope: str | None = None) -> httpx.Response:
        scope = scope or APPEND_SCOPE[data["entry_type"]]
        return await self.client.post("/v1/entries", content=json.dumps(data), headers={**service_token(scope), "content-type": "application/json"})

    async def append(self, entry_type: str, **kwargs: Any) -> dict[str, Any]:
        """Un append que debe aceptarse: devuelve el ack."""
        data = entry_dict(entry_type, now=self.clock.now, **kwargs)
        response = await self.post(data)
        assert response.status_code == 200, response.text
        return {**response.json(), "idempotency_key": data["idempotency_key"]}

    def rows(self, where: str = "", *params: object) -> list[tuple[object, ...]]:
        return self.cdb.db.query(f"SELECT seq, entry_type FROM registry_entries {where} ORDER BY seq", *params)


@pytest.fixture
async def env(cdb: ClusterDb) -> AsyncIterator[Env]:  # noqa: F811
    pools = Pools.build(cdb.dsns())
    clock = Clock()
    config = ServiceConfig(clock=clock)
    client = client_for(pools, config)
    yield Env(cdb, pools, clock, config, client)
    await client.aclose()
    await pools.close()
