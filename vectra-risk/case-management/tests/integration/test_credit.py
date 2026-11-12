"""Paso 12: lectura del estado de credito (BR-U8-21; INF-U8-02; NFR-U8-25, 31). Solo `GET`, nunca falla `get_case`."""

import httpx
import pytest
from case_pg import Db
from u8_support import auth, harness, seed_case
from vectra_common import deps

pytestmark = pytest.mark.integration


def credit_status_of(body: dict[str, object]) -> object:
    return body.get("credit_status")


async def test_stopped_core_mock_get_case_answers_no_disponible_within_its_p99(db: Db) -> None:
    """E6 de P-U8-09."""
    case_id = seed_case(db, state="decidido")

    def down(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("mock detenido", request=request)

    async with harness(db, core_enabled=True, core_handler=down) as h:
        loop_time = __import__("time").perf_counter()
        r = await h.client.get(f"/v1/cases/{case_id}", headers=auth("analista"))
        elapsed = __import__("time").perf_counter() - loop_time
    assert r.status_code == 200 and r.json()["credit_status"] == "no_disponible"
    assert elapsed < 0.5 + 0.5  # timeout de 500 ms del core mas la lectura de la base


async def test_core_disabled_makes_zero_calls_registers_nothing_in_the_breaker_and_answers_no_integrado(
    db: Db,
) -> None:
    case_id = seed_case(db, state="decidido")
    async with harness(db, core_enabled=False) as h:
        r = await h.client.get(f"/v1/cases/{case_id}", headers=auth("analista"))
        assert h.services.credit._client is None  # noqa: SLF001 - no se creo el cliente
    assert r.json()["credit_status"] == "no_integrado"
    assert h.core_calls == []


async def test_core_disabled_leaves_the_circuit_gauge_untouched(db: Db) -> None:
    from vectra_common.metrics import REGISTRY

    case_id = seed_case(db, state="decidido")
    before = REGISTRY.get_sample_value("vectra_circuit_state", {"dependency": "core"})
    async with harness(db, core_enabled=False) as h:
        await h.client.get(f"/v1/cases/{case_id}", headers=auth("analista"))
    assert REGISTRY.get_sample_value("vectra_circuit_state", {"dependency": "core"}) == before


async def test_404_is_sin_credito_and_an_answer_is_passed_through(db: Db) -> None:
    case_id = seed_case(db, state="decidido")
    async with harness(db, core_enabled=True, core_handler=lambda r: httpx.Response(404, json={})) as h:
        r = await h.client.get(f"/v1/cases/{case_id}", headers=auth("analista"))
    assert r.json()["credit_status"] == "sin_credito"
    assert h.core_calls == [f"http://core/v1/credits/{case_id}"]
    async with harness(
        db,
        core_enabled=True,
        core_handler=lambda r: httpx.Response(200, json={"credit_id": "c1", "status": "aprobado"}),
    ) as h2:
        ok = await h2.client.get(f"/v1/cases/{case_id}", headers=auth("analista"))
    assert ok.json()["credit_status"] == "aprobado"


async def test_a_5xx_or_garbage_from_the_core_is_no_disponible_and_only_decided_cases_call_it(db: Db) -> None:
    decided = seed_case(db, state="decidido")
    listo = seed_case(db, state="listo")
    async with harness(db, core_enabled=True, core_handler=lambda r: httpx.Response(500)) as h:
        r500 = await h.client.get(f"/v1/cases/{decided}", headers=auth("analista"))
        await h.client.get(f"/v1/cases/{listo}", headers=auth("analista"))
    assert r500.json()["credit_status"] == "no_disponible" and len(h.core_calls) == 1
    async with harness(
        db, core_enabled=True, core_handler=lambda r: httpx.Response(200, text="no es json")
    ) as h2:
        garbage = await h2.client.get(f"/v1/cases/{decided}", headers=auth("analista"))
    assert garbage.json()["credit_status"] == "no_disponible"
    assert deps is not None


async def test_a_slow_core_past_500ms_is_no_disponible(db: Db) -> None:
    import asyncio

    case_id = seed_case(db, state="decidido")

    class Slow(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
            await asyncio.sleep(1.0)
            return httpx.Response(200, json={"credit_id": "c", "status": "aprobado"})

    from vectra_case.credit import CreditReader

    async with harness(db) as h:
        h.services.credit = CreditReader(True, "http://core", None, transport=Slow())
        r = await h.client.get(f"/v1/cases/{case_id}", headers=auth("analista"))
    assert r.json()["credit_status"] == "no_disponible"
