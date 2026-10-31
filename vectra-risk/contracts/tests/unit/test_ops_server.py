"""NFR-U0-48."""

import httpx

from vectra_common import process
from vectra_common.metrics import AUTHZ_DENIED
from vectra_common.ops_server import create_ops_app


def client(readiness=None):
    process.reset_for_tests()
    app = create_ops_app(readiness)
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://ops")


async def test_routes_and_nothing_else():
    AUTHZ_DENIED.labels(code="forbidden", route_template="/x").inc(0)
    async with client() as c:
        assert (await c.get("/healthz")).status_code == 200
        assert (await c.get("/readyz")).status_code == 200
        metrics = await c.get("/metrics")
        assert metrics.status_code == 200 and "vectra_authz_denied_total" in metrics.text
        assert (await c.get("/v1/cases")).status_code == 404


async def test_readiness_predicate():
    async with client(lambda: False) as c:
        assert (await c.get("/readyz")).status_code == 503
        assert (await c.get("/healthz")).status_code == 200

    def boom():
        raise RuntimeError("x")

    async with client(boom) as c:
        assert (await c.get("/readyz")).status_code == 503
        assert (await c.get("/healthz")).status_code == 200


async def test_process_marked_as_service():
    async with client():
        assert process.current() == "service"
