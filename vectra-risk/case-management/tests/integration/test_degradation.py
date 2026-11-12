"""Paso 13: degradacion por dependencia, una fila de P-U8-03 por prueba (NFR-U8-21..25; RESILIENCY-06)."""

import httpx
import psycopg
import pytest
from case_pg import Db, url
from psycopg import sql
from u8_support import application, auth, decision_body, harness, scalar, seed_case
from vectra_case.app import Settings

pytestmark = pytest.mark.integration


def settings(db: Db, dsn: str | None = None) -> Settings:
    return Settings(
        db_dsn=dsn or url(db.pg, db.name, "case_app", "case_app"),
        governance_url="http://127.0.0.1:9",
        registry_url="http://127.0.0.1:9",
        core_enabled=True,
        core_url="http://127.0.0.1:9",
        allow_test_scenarios=False,
    )


async def readyz(app: object) -> int:
    transport = httpx.ASGITransport(app=app.state.ops_app)  # type: ignore[attr-defined]
    async with httpx.AsyncClient(transport=transport, base_url="http://ops") as ops:
        return (await ops.get("/readyz")).status_code


def read_only(db: Db) -> None:
    with psycopg.connect(url(db.pg, "postgres", "postgres", "postgres"), autocommit=True) as conn:
        conn.execute(
            sql.SQL("ALTER DATABASE {} SET default_transaction_read_only = on").format(
                sql.Identifier(db.name)
            )
        )


async def test_case_db_read_only_writes_are_503_without_effect_reads_continue_and_it_stays_ready(
    db: Db,
) -> None:
    listo = seed_case(db, state="listo")
    read_only(db)
    async with harness(db, settings=settings(db)) as h:
        intake = await h.client.post(
            "/v1/intake/applications",
            json=application(),
            headers=auth("simulator", **{"Idempotency-Key": "k"}),
        )
        manual = await h.client.post(
            "/v1/cases", json=application(), headers=auth("analista", **{"Idempotency-Key": "k"})
        )
        decision = await h.client.post(
            f"/v1/cases/{listo}/decision", json=decision_body(), headers=auth("analista")
        )
        view = await h.client.post(f"/v1/cases/{listo}/explanation-views", headers=auth("analista"))
        read = await h.client.get(f"/v1/cases/{listo}", headers=auth("analista"))
        listing = await h.client.get("/v1/cases", headers=auth("analista"))
        ready = await readyz(h.app)
    assert intake.status_code == manual.status_code == decision.status_code == view.status_code == 503
    assert intake.json()["code"] == "dependency_unavailable"
    assert read.status_code == 200 and listing.status_code == 200 and ready == 200
    assert (
        scalar(db, "SELECT count(*) FROM cases") == 1
        and scalar(db, "SELECT count(*) FROM evidence_outbox") == 0
    )
    assert (
        scalar(db, "SELECT count(*) FROM decisions") == 0
        and scalar(db, "SELECT count(*) FROM explanation_views") == 0
    )
    assert not h.registry.entries


async def test_case_db_unreachable_is_not_ready_and_writes_are_503(db: Db) -> None:
    dead = "postgresql://case_app:case_app@127.0.0.1:9/none"
    async with harness(db, settings=settings(db, dead)) as h:
        assert await readyz(h.app) == 503
    assert h.core_calls == []


async def test_governance_scoring_registry_or_core_down_keep_the_service_ready_and_serving(db: Db) -> None:
    decided = seed_case(db, state="decidido")

    def boom(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("caido", request=request)

    async with harness(db, settings=settings(db), core_enabled=True, core_handler=boom) as h:
        h.registry.down = True
        h.governance_handler.down = True
        ready = await readyz(h.app)
        intake = await h.client.post(
            "/v1/intake/applications",
            json=application(),
            headers=auth("simulator", **{"Idempotency-Key": "k"}),
        )
        detail = await h.client.get(f"/v1/cases/{decided}", headers=auth("analista"))
        view = await h.client.post(
            f"/v1/cases/{seed_case(db, state='listo')}/explanation-views", headers=auth("analista")
        )
        sweep = await h.sweeper.run_once()
    assert (
        ready == 200 and intake.status_code == 200 and detail.status_code == 200 and view.status_code == 204
    )
    assert detail.json()["credit_status"] == "no_disponible" and sweep == "skipped"


async def test_registry_down_decision_is_503_and_pending(db: Db) -> None:
    listo = seed_case(db, state="listo")
    async with harness(db, settings=settings(db)) as h:
        h.registry.down = True
        decision = await h.client.post(
            f"/v1/cases/{listo}/decision", json=decision_body(), headers=auth("analista")
        )
        ready = await readyz(h.app)
    assert decision.status_code == 503 and ready == 200
    assert db.query("SELECT state FROM decisions") == [("pendiente_registro",)]
