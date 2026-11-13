"""Paso 18 (U08-T04): las ramas de `evidence`, `sweeps` e `intake` que las pruebas de U08-T03 no recorrian (cobertura del 100 %, NFR-U8-50).

No cambian el comportamiento de `case-service`: cada prueba afirma sobre la base o sobre la respuesta, no sobre la cobertura.
"""

import asyncio
import uuid
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
from case_pg import Db
from u8_support import application, auth, decision_body, harness, scalar, seed_case
from vectra_case import evidence, metrics
from vectra_case.evidence import AppendResult, RegistryClient
from vectra_common import process
from vectra_contracts.models.explanation import RegistryAck
from worker_support import bulk_cases, case_row

pytestmark = pytest.mark.integration
ACK = RegistryAck(registry_entry_id="9", seq=9, recorded_at=datetime(2026, 11, 12, tzinfo=UTC))


def registry_client(handler: Any) -> RegistryClient:
    process.ensure_service()
    return RegistryClient("http://registry", None, transport=httpx.MockTransport(handler))


async def test_registry_client_maps_a_5xx_an_unknown_status_a_bad_ack_and_a_connection_error_to_unavailable() -> (
    None
):
    answers: list[Any] = [
        httpx.Response(500, json={}),
        httpx.Response(403, json={}),
        httpx.Response(200, json={"junk": 1}),
        httpx.ConnectError("el registro no responde"),
    ]

    def handler(_: httpx.Request) -> httpx.Response:
        answer = answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer  # type: ignore[no-any-return]

    client = registry_client(handler)
    try:
        results = [await client.append({"entry_type": "fail_closed"}) for _ in range(4)]
    finally:
        await client.aclose()
    assert results == [AppendResult("unavailable")] * 4


def test_the_default_clock_is_utc() -> None:
    assert evidence._utc_now().tzinfo is UTC


async def view_row(h: Any, case_id: uuid.UUID) -> dict[str, Any]:
    async with h.database.tx() as conn:
        cur = await conn.execute("SELECT * FROM evidence_outbox WHERE case_id = %s", (case_id,))
        return dict(await cur.fetchone())


async def test_confirming_or_discarding_a_row_that_is_no_longer_pending_changes_nothing(db: Db) -> None:
    case_id = seed_case(db, state="listo")
    async with harness(db) as h:
        assert (
            await h.client.post(f"/v1/cases/{case_id}/explanation-views", headers=auth("analista"))
        ).status_code == 204
        row = await view_row(h, case_id)
        assert row["state"] == "confirmada"  # el envio inmediato la confirmo
        before = metrics.EVIDENCE_DISCARDED._value.get()  # type: ignore[attr-defined]
        assert await h.evidence._confirm(row, ACK) is False
        await h.evidence._discard(row)
    assert metrics.EVIDENCE_DISCARDED._value.get() == before  # type: ignore[attr-defined]
    assert scalar(db, "SELECT state FROM evidence_outbox WHERE case_id = %s", case_id) == "confirmada"


async def test_a_decision_on_a_case_that_does_not_exist_is_404(db: Db) -> None:
    async with harness(db) as h:
        r = await h.client.post(
            f"/v1/cases/{uuid.uuid4()}/decision", json=decision_body(), headers=auth("analista")
        )
    assert r.status_code == 404


async def test_a_live_outbox_row_with_the_same_key_but_no_live_decision_is_409(db: Db) -> None:
    case_id = seed_case(db, state="listo")
    db.execute(
        "INSERT INTO evidence_outbox (evidence_id, case_id, entry_type, idempotency_key, payload, state) "
        "VALUES (%s, %s, 'human_decision', %s, '{}'::jsonb, 'confirmada')",
        uuid.uuid4(),
        case_id,
        uuid.uuid5(case_id, "human_decision"),
    )
    async with harness(db) as h:
        r = await h.client.post(
            f"/v1/cases/{case_id}/decision", json=decision_body(), headers=auth("analista")
        )
    assert r.status_code == 409 and case_row(db, case_id)["state"] == "listo"
    assert scalar(db, "SELECT count(*) FROM decisions WHERE case_id = %s", case_id) == 0


async def test_a_registry_conflict_without_an_abandoned_decision_leaves_the_decision_pending(db: Db) -> None:
    case_id = seed_case(db, state="listo")
    async with harness(db) as h:
        h.registry.fail_with = 409  # el registro dice que la llave existe con otro contenido
        r = await h.client.post(
            f"/v1/cases/{case_id}/decision", json=decision_body(), headers=auth("analista")
        )
        assert r.status_code == 503
    assert scalar(db, "SELECT state FROM decisions WHERE case_id = %s", case_id) == "pendiente_registro"
    assert (
        scalar(db, "SELECT attempts FROM evidence_outbox WHERE case_id = %s", case_id) == 1
    )  # `_fail` tomo nota


async def abandoned_then_new_decision(db: Db, answers: list[AppendResult]) -> int:
    """Una decision abandonada (el registro estuvo caido 25 h) y una nueva cuyo envio recibe `answers` en orden."""
    case_id = seed_case(db, state="listo")
    async with harness(db) as h:
        h.registry.down = True
        assert (
            await h.client.post(
                f"/v1/cases/{case_id}/decision", json=decision_body(), headers=auth("analista")
            )
        ).status_code == 503
        h.clock.advance(hours=25)
        await h.reconciler.run_once()  # abandona la pendiente
        h.registry.down = False
        queue = iter(answers)

        async def fake(_: dict[str, Any]) -> AppendResult:
            return next(queue)

        h.evidence.registry.append = fake  # type: ignore[method-assign]
        r = await h.client.post(
            f"/v1/cases/{case_id}/decision", json=decision_body(), headers=auth("analista2")
        )
    assert case_row(db, case_id)["state"] == "listo"  # ningun intercambio: el caso sigue `listo`
    return r.status_code


async def test_an_abandoned_decision_that_the_registry_also_answers_with_a_conflict_is_skipped(
    db: Db,
) -> None:
    status = await abandoned_then_new_decision(db, [AppendResult("conflict"), AppendResult("conflict")])
    assert status == 503


async def test_an_abandoned_decision_whose_resend_does_not_get_an_ack_stops_the_resolution(db: Db) -> None:
    status = await abandoned_then_new_decision(db, [AppendResult("conflict"), AppendResult("unavailable")])
    assert status == 503


async def test_the_reconciler_loop_runs_cycles_until_stopped_and_a_stopped_cycle_does_nothing(db: Db) -> None:
    case_id = seed_case(db, state="listo")
    async with harness(db) as h:
        h.registry.down = True
        await h.client.post(f"/v1/cases/{case_id}/explanation-views", headers=auth("analista"))
        h.registry.down = False
        h.clock.advance(minutes=10)
        task = asyncio.create_task(h.reconciler.run_forever())
        await asyncio.sleep(1.4)  # un ciclo y la espera de RECONCILER_INTERVAL
        h.reconciler.stop()
        await asyncio.wait_for(task, 5)
        assert await h.reconciler.run_once() == 0
    assert scalar(db, "SELECT state FROM evidence_outbox WHERE case_id = %s", case_id) == "confirmada"


async def test_sweeper_loop_stop_and_a_second_batch_of_frozen_cases(db: Db) -> None:
    ids = bulk_cases(
        db, 101, state="modelo_congelado", jobs=False
    )  # BATCH_SIZE + 1: el barrido da dos vueltas
    async with harness(db) as h:
        assert await h.sweeper.run_once() == "done"
        assert {case_row(db, i)["state"] for i in ids} == {"en_evaluacion"}
        assert scalar(db, "SELECT count(*) FROM evaluation_jobs") == 101
        task = asyncio.create_task(h.sweeper.run_forever(interval=0.05))
        await asyncio.sleep(0.3)
        h.sweeper.stop()
        await asyncio.wait_for(task, 5)
        assert await h.sweeper.run_once() == "skipped"  # detenido: no toca nada


async def test_a_scenario_header_that_is_not_a_valid_identifier_is_422_even_for_the_simulator(db: Db) -> None:
    async with harness(db, allow_test_scenarios=True) as h:
        r = await h.client.post(
            "/v1/intake/applications",
            json=application(),
            headers=auth("simulator", **{"Idempotency-Key": "k-bad", "X-Test-Scenario": "no valido!"}),
        )
    assert r.status_code == 422
    assert scalar(db, "SELECT count(*) FROM cases") == 0
