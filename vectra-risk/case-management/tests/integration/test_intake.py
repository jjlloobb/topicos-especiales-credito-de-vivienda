"""Paso 9: ingesta y alta manual (BR-U8-01..04; US-101, US-102, US-109) contra PostgreSQL real con el rol `case_app`."""

import json
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from case_pg import Db, url
from psycopg import connect
from u8_support import APPLICATION, application, auth, harness, scalar
from vectra_case.retention import purge_intake_keys

pytestmark = pytest.mark.integration
INTAKE = "/v1/intake/applications"
MANUAL = "/v1/cases"


def headers(who: str, key: str | None = None, **extra: str) -> dict[str, str]:
    h = auth(who, **extra)
    if key is not None:
        h["Idempotency-Key"] = key
    return h


async def test_valid_simulator_application_creates_an_en_evaluacion_case_with_its_job(db: Db) -> None:
    async with harness(db) as h:
        r = await h.client.post(INTAKE, json=application(), headers=headers("simulator", "k1"))
    assert r.status_code == 200, r.text
    case_id = r.json()["case_id"]
    assert r.json()["state"] == "en_evaluacion"
    assert db.query("SELECT state, channel FROM cases WHERE case_id = %s", case_id) == [
        ("en_evaluacion", "web")
    ]
    assert scalar(db, "SELECT count(*) FROM evaluation_jobs WHERE case_id = %s AND attempt = 0", case_id) == 1
    assert scalar(db, "SELECT count(*) FROM case_identifiers WHERE case_id = %s", case_id) == 1
    # los identificadores no viajan a `cases.application`
    stored = scalar(db, "SELECT application FROM cases WHERE case_id = %s", case_id)
    assert "document_number" not in stored and stored["sex"] == "F"


async def test_invalid_application_is_4xx_without_a_case(db: Db) -> None:
    async with harness(db) as h:
        r = await h.client.post(
            INTAKE, json=application(document_number="abc"), headers=headers("simulator", "k1")
        )
    assert 400 <= r.status_code < 500
    assert "abc" not in r.text
    assert scalar(db, "SELECT count(*) FROM cases") == 0


async def test_adversarial_case_keeps_its_test_scenario_id(db: Db) -> None:
    async with harness(db, allow_test_scenarios=True) as h:
        r = await h.client.post(
            INTAKE,
            json=application(),
            headers=headers("simulator", "k1", **{"X-Test-Scenario": "free-text-injection"}),
        )
    assert r.status_code == 200
    assert (
        scalar(db, "SELECT test_scenario_id FROM cases WHERE case_id = %s", r.json()["case_id"])
        == "free-text-injection"
    )


@pytest.mark.parametrize("who", ["simulator", "channel"])
async def test_test_scenario_with_allow_false_is_422(db: Db, who: str) -> None:
    async with harness(db, allow_test_scenarios=False) as h:
        r = await h.client.post(
            INTAKE, json=application(), headers=headers(who, "k1", **{"X-Test-Scenario": "x"})
        )
    assert r.status_code == 422
    assert scalar(db, "SELECT count(*) FROM cases") == 0


async def test_test_scenario_from_a_client_other_than_the_simulator_is_422_even_if_allowed(db: Db) -> None:
    async with harness(db, allow_test_scenarios=True) as h:
        r = await h.client.post(
            INTAKE, json=application(), headers=headers("channel", "k1", **{"X-Test-Scenario": "x"})
        )
    assert r.status_code == 422


async def test_missing_idempotency_key_is_422(db: Db) -> None:
    async with harness(db) as h:
        r = await h.client.post(INTAKE, json=application(), headers=headers("simulator"))
    assert r.status_code == 422 and scalar(db, "SELECT count(*) FROM cases") == 0


async def test_manual_case_by_an_analyst_has_channel_manual_and_the_user(db: Db) -> None:
    async with harness(db) as h:
        r = await h.client.post(MANUAL, json=application(), headers=headers("analista", "m1"))
    assert r.status_code == 200, r.text
    row = db.query(
        "SELECT channel, created_by, application->>'channel' FROM cases WHERE case_id = %s",
        r.json()["case_id"],
    )[0]
    assert row[0] == "manual" and row[2] == "manual"
    assert row[1] == {"kind": "user", "id": "analista-1"}


async def test_manual_case_by_cumplimiento_is_403_with_authz_denied(
    db: Db, capsys: pytest.CaptureFixture[str]
) -> None:
    async with harness(db) as h:
        r = await h.client.post(MANUAL, json=application(), headers=headers("cumplimiento", "m1"))
    assert r.status_code == 403
    assert scalar(db, "SELECT count(*) FROM cases") == 0
    events = [json.loads(line) for line in capsys.readouterr().out.splitlines() if line.startswith("{")]
    assert any(
        e.get("event") == "authz.denied" and e.get("principal_subject") == "cumplimiento-1" for e in events
    )


@pytest.mark.parametrize(
    "text", ["'; DROP TABLE cases; --", "<script>alert(1)</script>", "línea 1\nlínea 2\t¿ñ? 😀"]
)
async def test_free_text_is_stored_byte_for_byte_and_unescaped(db: Db, text: str) -> None:
    async with harness(db) as h:
        r = await h.client.post(INTAKE, json=application(free_text=text), headers=headers("simulator", "k1"))
    assert r.status_code == 200, r.text
    stored = scalar(db, "SELECT application->>'free_text' FROM cases WHERE case_id = %s", r.json()["case_id"])
    assert stored.encode() == text.encode()
    assert scalar(db, "SELECT count(*) FROM cases") == 1  # la tabla sigue ahi


async def test_manual_case_repeated_with_the_same_key_is_the_same_case(db: Db) -> None:
    async with harness(db) as h:
        a = await h.client.post(MANUAL, json=application(), headers=headers("analista", "m1"))
        b = await h.client.post(MANUAL, json=application(), headers=headers("analista", "m1"))
        c = await h.client.post(
            MANUAL, json=application(requested_amount=1_000_000), headers=headers("analista", "m1")
        )
        d = await h.client.post(MANUAL, json=application(), headers=headers("analista2", "m1"))
    assert a.status_code == b.status_code == 200 and a.json()["case_id"] == b.json()["case_id"]
    assert c.status_code == 409 and c.json()["code"] == "conflict_state"
    assert d.status_code == 200 and d.json()["case_id"] != a.json()["case_id"]  # otro alcance: no choca
    assert scalar(db, "SELECT count(*) FROM cases") == 2


async def test_same_key_other_body_is_409_without_a_second_case(db: Db) -> None:
    async with harness(db) as h:
        a = await h.client.post(INTAKE, json=application(), headers=headers("channel", "k"))
        b = await h.client.post(INTAKE, json=application(term_months=120), headers=headers("channel", "k"))
        c = await h.client.post(INTAKE, json=application(term_months=120), headers=headers("channel2", "k"))
    assert a.status_code == 200 and b.status_code == 409 and c.status_code == 200
    assert scalar(db, "SELECT count(*) FROM cases") == 2


async def test_purged_key_is_free_again(db: Db) -> None:
    async with harness(db) as h:
        a = await h.client.post(INTAKE, json=application(), headers=headers("channel", "k"))
        db.execute("UPDATE intake_keys SET created_at = %s", datetime.now(UTC) - timedelta(days=31))
        with connect(url(db.pg, db.name, "case_retention", "case_retention"), autocommit=True) as conn:
            assert purge_intake_keys(conn) == 1
        b = await h.client.post(INTAKE, json=application(term_months=120), headers=headers("channel", "k"))
    assert b.status_code == 200 and b.json()["case_id"] != a.json()["case_id"]


def test_application_constant_is_valid() -> None:
    assert uuid.UUID(int=0) and APPLICATION["channel"] == "web"
