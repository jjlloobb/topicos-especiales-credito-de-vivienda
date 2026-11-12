"""Paso 10: consulta de la explicacion (BR-U8-19; US-501) y su evidencia (`descartada` por BR-U0-37)."""

import pytest
from case_pg import Db
from u8_support import auth, harness, scalar, seed_case
from vectra_common.metrics import REGISTRY

pytestmark = pytest.mark.integration


def view(case_id: object) -> str:
    return f"/v1/cases/{case_id}/explanation-views"


def discarded() -> float:
    return REGISTRY.get_sample_value("vectra_case_evidence_discarded_total") or 0.0


async def test_first_view_writes_one_entry_and_the_second_is_204_without_a_new_one(db: Db) -> None:
    case_id = seed_case(db, state="listo")
    async with harness(db) as h:
        first = await h.client.post(view(case_id), headers=auth("analista"))
        second = await h.client.post(view(case_id), headers=auth("analista"))
        other_user = await h.client.post(view(case_id), headers=auth("analista2"))
    assert first.status_code == second.status_code == other_user.status_code == 204
    entries = h.registry.of_type("explanation_view")
    assert len(entries) == 2  # una por (caso, usuario)
    e = entries[0]["entry"]
    assert e.payload.recommendation_entry_id == "7" and e.actor.id == "analista-1"
    assert db.query("SELECT state FROM evidence_outbox ORDER BY created_at") == [
        ("confirmada",),
        ("confirmada",),
    ]


async def test_only_the_analyst_can_view_and_the_case_must_be_listo_or_decidido(db: Db) -> None:
    listo = seed_case(db, state="listo")
    en_eval = seed_case(db, state="en_evaluacion")
    async with harness(db) as h:
        cro = await h.client.post(view(listo), headers=auth("cro"))
        early = await h.client.post(view(en_eval), headers=auth("analista"))
        missing = await h.client.post(view("00000000-0000-4000-8000-000000000001"), headers=auth("analista"))
    assert cro.status_code == 403 and early.status_code == 409 and missing.status_code == 404
    assert not h.registry.entries


async def test_decided_anonymized_case_accepts_the_view(db: Db) -> None:
    case_id = seed_case(db, state="decidido", anonymized=True)
    async with harness(db) as h:
        r = await h.client.post(view(case_id), headers=auth("analista"))
    assert r.status_code == 204 and len(h.registry.of_type("explanation_view")) == 1


async def test_pending_view_is_204_and_sent_later_by_the_reconciler(db: Db) -> None:
    case_id = seed_case(db, state="listo")
    async with harness(db) as h:
        h.registry.down = True
        r = await h.client.post(view(case_id), headers=auth("analista"))
        assert r.status_code == 204 and not h.registry.entries
        h.registry.down = False
        h.clock.advance(minutes=6)
        await h.reconciler.run_once()
    assert len(h.registry.of_type("explanation_view")) == 1


async def test_an_abandoned_view_is_recovered_with_the_original_payload_and_key(db: Db) -> None:
    case_id = seed_case(db, state="listo")
    async with harness(db) as h:
        h.registry.down = True
        await h.client.post(view(case_id), headers=auth("analista"))
        h.clock.advance(hours=25)
        await h.reconciler.run_once()
        assert db.query("SELECT state FROM evidence_outbox") == [("abandonada",)]
        still_down = await h.client.post(view(case_id), headers=auth("analista"))
        assert still_down.status_code == 204
        assert db.query("SELECT state FROM evidence_outbox") == [("pendiente_registro",)]  # sigue pendiente
        h.registry.down = False
        h.clock.advance(minutes=6)
        await h.reconciler.run_once()
    assert db.query("SELECT state FROM evidence_outbox") == [("confirmada",)]
    sent = h.registry.requests
    assert (
        len({r["idempotency_key"] for r in sent}) == 1 and len({r["payload"]["viewed_at"] for r in sent}) == 1
    )
    assert len(h.registry.of_type("explanation_view")) == 1


async def test_a_view_the_registry_rejects_with_422_is_discarded_and_never_resent(db: Db) -> None:
    """BR-U0-37: `viewed_at` de mas de 7 dias. La consulta se conserva; la evidencia es terminal."""
    case_id = seed_case(db, state="listo")
    before = discarded()
    async with harness(db) as h:
        h.registry.down = True
        await h.client.post(view(case_id), headers=auth("analista"))
        h.clock.advance(days=8)
        await h.reconciler.run_once()  # abandona (24 h)
        h.registry.down = False
        reopened = await h.client.post(view(case_id), headers=auth("analista"))  # reenvia el original: 422
        assert reopened.status_code == 204
        assert db.query("SELECT state FROM evidence_outbox") == [("descartada",)]
        assert discarded() == before + 1
        calls = len(h.registry.requests)
        again = await h.client.post(view(case_id), headers=auth("analista"))
        await h.reconciler.run_once()
        assert (
            again.status_code == 204 and len(h.registry.requests) == calls
        )  # sin reenvio aunque se abra de nuevo
    assert scalar(db, "SELECT count(*) FROM explanation_views") == 1  # la consulta si ocurrio
    assert not h.registry.entries
