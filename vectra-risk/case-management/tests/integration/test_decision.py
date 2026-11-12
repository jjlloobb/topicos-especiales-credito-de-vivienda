"""Paso 10: decision, evidencia en dos fases y reconciliador (BR-U8-15..18; P-U8-02, 04, 09; US-108, US-502)."""

import asyncio
import uuid

import pytest
from case_pg import Db
from prometheus_client import REGISTRY as PROM
from u8_support import auth, decision_body, harness, insert_fail_closed, scalar, seed_case
from vectra_common.metrics import REGISTRY
from vectra_contracts.catalog import Outcome

pytestmark = pytest.mark.integration


def decide(case_id: uuid.UUID) -> str:
    return f"/v1/cases/{case_id}/decision"


def sample(name: str, **labels: str) -> float:
    return REGISTRY.get_sample_value(name, labels) or 0.0


async def test_sigue_writes_a_human_decision_with_the_actor_evidence_and_closes_the_case(db: Db) -> None:
    case_id = seed_case(db, state="listo")
    async with harness(db) as h:
        r = await h.client.post(decide(case_id), json=decision_body(), headers=auth("analista"))
    assert r.status_code == 200, r.text
    assert r.json()["registry_entry_id"] == "1" and r.json()["case_id"] == str(case_id)
    entries = h.registry.of_type("human_decision")
    assert len(entries) == 1
    entry = entries[0]["entry"]
    assert entry.actor.id == "analista-1" and entry.actor.acr == "1" and entry.actor.auth_time is not None
    assert entry.model_version_id == "mv-1" and entry.policy_version_id == "p1"
    assert entry.payload.recommendation_entry_id == "7" and entry.payload.explanation_viewed_before is False
    assert str(entry.idempotency_key) == str(uuid.uuid5(case_id, "human_decision"))
    assert db.query("SELECT state FROM cases WHERE case_id = %s", case_id) == [("decidido",)]
    assert db.query(
        "SELECT d.state, e.state FROM decisions d JOIN evidence_outbox e USING (evidence_id)"
    ) == [("confirmada", "confirmada")]


async def test_decision_on_a_no_disponible_case_is_409_without_entry(db: Db) -> None:
    case_id = seed_case(db, state="no_disponible")
    async with harness(db) as h:
        r = await h.client.post(decide(case_id), json=decision_body(), headers=auth("analista"))
    assert r.status_code == 409 and r.json()["code"] == "conflict_state"
    assert not h.registry.entries and scalar(db, "SELECT count(*) FROM evidence_outbox") == 0


async def test_decision_rejections_carry_only_the_code_without_reason(db: Db) -> None:
    case_id = seed_case(db, state="listo")
    async with harness(db) as h:
        foreign = await h.client.post(
            decide(case_id),
            json=decision_body(
                decision="se_aparta",
                final_outcome="desfavorable",
                used_factors=["nope"],
                justification="x" * 25,
            ),
            headers=auth("analista"),
        )
        incoherent = await h.client.post(
            decide(case_id), json=decision_body(final_outcome="desfavorable"), headers=auth("analista")
        )
        no_justification = await h.client.post(
            decide(case_id),
            json=decision_body(decision="se_aparta", final_outcome="desfavorable"),
            headers=auth("analista"),
        )
        cro = await h.client.post(decide(case_id), json=decision_body(), headers=auth("cro"))
    assert foreign.status_code == 422 and "reason" not in foreign.json()
    assert incoherent.status_code == 409 and "reason" not in incoherent.json()
    assert no_justification.status_code == 422
    assert cro.status_code == 403
    assert not h.registry.entries


async def test_second_decision_on_a_decided_or_pending_case_is_409(db: Db) -> None:
    case_id = seed_case(db, state="listo")
    async with harness(db) as h:
        h.registry.down = True
        first = await h.client.post(decide(case_id), json=decision_body(), headers=auth("analista"))
        second = await h.client.post(decide(case_id), json=decision_body(), headers=auth("analista2"))
    assert first.status_code == 503 and second.status_code == 409


async def test_registry_down_during_a_decision_is_503_pending_and_the_reconciler_confirms_it_later(
    db: Db,
) -> None:
    """E3 de P-U8-09."""
    case_id = seed_case(db, state="listo")
    async with harness(db) as h:
        h.registry.down = True
        r = await h.client.post(decide(case_id), json=decision_body(), headers=auth("analista"))
        assert r.status_code == 503
        assert db.query("SELECT state FROM decisions") == [("pendiente_registro",)]
        assert db.query("SELECT state FROM cases") == [("listo",)]
        h.registry.down = False
        h.clock.advance(minutes=10)  # pasa el backoff
        assert await h.reconciler.run_once() == 1
    assert db.query("SELECT state FROM cases") == [("decidido",)]
    assert db.query("SELECT state FROM decisions") == [("confirmada",)]
    assert len(h.registry.of_type("human_decision")) == 1


async def test_pending_for_24h_is_abandoned_and_the_case_accepts_another_decision(db: Db) -> None:
    case_id = seed_case(db, state="listo")
    before = sample("vectra_case_evidence_abandoned_total", entry_type="human_decision")
    async with harness(db) as h:
        h.registry.down = True
        await h.client.post(decide(case_id), json=decision_body(), headers=auth("analista"))
        h.clock.advance(hours=25)
        await h.reconciler.run_once()
        assert db.query(
            "SELECT d.state, e.state FROM decisions d JOIN evidence_outbox e USING (evidence_id)"
        ) == [("abandonada", "abandonada")]
        assert sample("vectra_case_evidence_abandoned_total", entry_type="human_decision") == before + 1
        h.registry.down = False
        again = await h.client.post(decide(case_id), json=decision_body(), headers=auth("analista"))
    assert again.status_code == 200
    assert db.query("SELECT state FROM cases") == [("decidido",)]


async def test_abandoned_decision_the_registry_did_write_then_a_new_decision_is_409_decision_already_recorded(
    db: Db,
) -> None:
    case_id = seed_case(db, state="listo")
    async with harness(db) as h:
        h.registry.lose_ack_next = 1  # el registro escribe y el ack se pierde
        first = await h.client.post(decide(case_id), json=decision_body(), headers=auth("analista"))
        assert first.status_code == 503 and len(h.registry.entries) == 1
        h.registry.down = True
        h.clock.advance(hours=25)
        await h.reconciler.run_once()  # abandona la pendiente
        h.registry.down = False
        second = await h.client.post(
            decide(case_id),
            json=decision_body(justification="otra justificacion distinta"),
            headers=auth("analista2"),
        )
    assert second.status_code == 409
    assert (
        second.json()["code"] == "conflict_state" and second.json()["reason"] == "decision_already_recorded"
    )
    rows = db.query(
        "SELECT d.decided_by->>'id', d.state, e.state FROM decisions d JOIN evidence_outbox e USING (evidence_id) ORDER BY d.decided_at"
    )
    assert rows == [("analista-1", "confirmada", "confirmada"), ("analista-2", "abandonada", "abandonada")]
    assert db.query("SELECT state FROM cases") == [("decidido",)]
    assert len(h.registry.of_type("human_decision")) == 1


async def test_vencido_case_rejects_decision_and_view_with_409(db: Db) -> None:
    case_id = seed_case(db, state="vencido")
    async with harness(db) as h:
        d = await h.client.post(decide(case_id), json=decision_body(), headers=auth("analista"))
        v = await h.client.post(f"/v1/cases/{case_id}/explanation-views", headers=auth("analista"))
    assert d.status_code == 409 and v.status_code == 409


async def test_explanation_viewed_before_counts_only_a_confirmed_view_by_the_same_user(db: Db) -> None:
    pending_case = seed_case(db, state="listo")
    confirmed_case = seed_case(db, state="listo")
    async with harness(db) as h:
        h.registry.down = True
        await h.client.post(
            f"/v1/cases/{pending_case}/explanation-views", headers=auth("analista")
        )  # queda pendiente
        h.registry.down = False
        await h.client.post(
            f"/v1/cases/{confirmed_case}/explanation-views", headers=auth("analista")
        )  # confirmada
        await h.client.post(f"/v1/cases/{confirmed_case}/explanation-views", headers=auth("analista2"))
        a = await h.client.post(decide(pending_case), json=decision_body(), headers=auth("analista"))
        b = await h.client.post(decide(confirmed_case), json=decision_body(), headers=auth("analista"))
        c = await h.client.post(
            decide(seed_case(db, state="listo")), json=decision_body(), headers=auth("analista")
        )
    assert a.status_code == b.status_code == c.status_code == 200
    flags = {
        str(e["entry"].case_id): e["entry"].payload.explanation_viewed_before
        for e in h.registry.of_type("human_decision")
    }
    assert (
        flags[str(pending_case)] is False and flags[str(confirmed_case)] is True and False in flags.values()
    )


async def test_never_more_than_4_reconciler_sends_in_flight_and_a_decision_does_not_wait(db: Db) -> None:
    """P-U8-02: registro doble de 2 s con 100 evidencias pendientes."""
    worker_case = seed_case(db, state="no_disponible")
    insert_fail_closed(db, worker_case, 100)
    decided = seed_case(db, state="listo")
    async with harness(db) as h:
        h.registry.delay = 2.0
        cycle = asyncio.create_task(h.reconciler.run_once())
        await asyncio.sleep(0.5)
        assert h.reconciler.max_in_flight == 4
        started = asyncio.get_event_loop().time()
        decision = asyncio.create_task(
            h.client.post(decide(decided), json=decision_body(), headers=auth("analista"))
        )
        await asyncio.sleep(0.3)
        assert (
            h.registry.arrivals[-1] - started < 0.5
        )  # la decision llego al registro sin esperar un turno del pool
        response = await decision
        assert response.status_code == 200 and asyncio.get_event_loop().time() - started < 3.5
        assert h.reconciler.max_in_flight == 4 and h.registry.max_in_flight <= 5
        cycle.cancel()
        await asyncio.gather(cycle, return_exceptions=True)


async def test_two_replicas_retry_each_pending_evidence_once_per_cycle(db: Db) -> None:
    case_id = seed_case(db, state="no_disponible")
    insert_fail_closed(db, case_id, 30)
    async with harness(db) as h, harness(db, registry=h.registry, clock=h.clock) as other:
        h.registry.fail_with = 400  # un 4xx no cuenta para el breaker: el ciclo envia las 30
        sent = await asyncio.gather(h.reconciler.run_once(), other.reconciler.run_once())
    assert sum(sent) == 30
    assert len(h.registry.requests) == 30
    assert len({r["idempotency_key"] for r in h.registry.requests}) == 30


async def test_reconciler_resends_with_the_same_key_payload_and_correlation_id_and_a_new_occurred_at(
    db: Db,
) -> None:
    case_id = seed_case(db, state="listo")
    async with harness(db) as h:
        h.registry.down = True
        await h.client.post(decide(case_id), json=decision_body(), headers=auth("analista"))
        h.registry.down = False
        h.clock.advance(minutes=6)
        await h.reconciler.run_once()
    first, second = h.registry.requests
    assert (
        first["idempotency_key"] == second["idempotency_key"]
        and first["correlation_id"] == second["correlation_id"]
    )
    assert first["payload"] == second["payload"] and first["actor"] == second["actor"]
    assert first["occurred_at"] != second["occurred_at"]


async def test_fail_closed_inserted_by_the_worker_is_sent_by_the_reconciler(db: Db) -> None:
    case_id = seed_case(db, state="no_disponible")
    insert_fail_closed(db, case_id, 1)
    async with harness(db) as h:
        assert await h.reconciler.run_once() == 1
    assert len(h.registry.of_type("fail_closed")) == 1
    assert db.query("SELECT state FROM evidence_outbox") == [("confirmada",)]


def test_metrics_exist_with_zero_series() -> None:
    assert PROM is not None
    for entry_type in ("human_decision", "explanation_view", "fail_closed"):
        assert (
            REGISTRY.get_sample_value("vectra_case_evidence_abandoned_total", {"entry_type": entry_type})
            is not None
        )
        assert (
            REGISTRY.get_sample_value(
                "vectra_case_evidence_pending_oldest_seconds", {"entry_type": entry_type}
            )
            is not None
        )
    assert REGISTRY.get_sample_value("vectra_case_evidence_discarded_total") is not None


async def test_decided_case_outcome_param_is_used(db: Db) -> None:
    case_id = seed_case(db, state="listo", outcome=Outcome.DESFAVORABLE)
    async with harness(db) as h:
        ok = await h.client.post(
            decide(case_id), json=decision_body(final_outcome="desfavorable"), headers=auth("analista")
        )
    assert ok.status_code == 200
