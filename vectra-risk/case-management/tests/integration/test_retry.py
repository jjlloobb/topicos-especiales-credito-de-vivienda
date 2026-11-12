"""Paso 11: `retry` del CRO (BR-U8-11; US-112)."""

import json

import pytest
from case_pg import Db
from u8_support import auth, harness, scalar, seed_case
from vectra_common.metrics import REGISTRY

pytestmark = pytest.mark.integration


def retries() -> float:
    return REGISTRY.get_sample_value("vectra_case_retries_total") or 0.0


async def test_retry_from_no_disponible_goes_to_en_evaluacion_with_a_new_job_and_the_log(
    db: Db, capsys: pytest.CaptureFixture[str]
) -> None:
    case_id = seed_case(db, state="no_disponible", attempts=6, last_cause="scoring_unreachable")
    before = retries()
    async with harness(db) as h:
        r = await h.client.post(f"/v1/cases/{case_id}/retry", headers=auth("cro"))
    assert r.status_code == 200 and r.json() == {"case_id": str(case_id), "state": "en_evaluacion"}
    assert db.query("SELECT state, attempts FROM cases WHERE case_id = %s", case_id) == [("en_evaluacion", 0)]
    assert db.query("SELECT attempt FROM evaluation_jobs WHERE case_id = %s", case_id) == [(0,)]
    assert retries() == before + 1
    events = [json.loads(line) for line in capsys.readouterr().out.splitlines() if line.startswith("{")]
    log = next(e for e in events if e.get("event") == "case.retry_requested")
    assert (
        log["principal_subject"] == "cro-1"
        and log["principal_role"] == "cro"
        and log["case_id"] == str(case_id)
    )


@pytest.mark.parametrize("state", ["vencido", "listo", "en_evaluacion", "decidido", "modelo_congelado"])
async def test_retry_from_any_other_state_is_409_without_changes(db: Db, state: str) -> None:
    case_id = seed_case(db, state=state)
    before = retries()
    async with harness(db) as h:
        r = await h.client.post(f"/v1/cases/{case_id}/retry", headers=auth("cro"))
    assert r.status_code == 409 and r.json()["code"] == "conflict_state"
    assert scalar(db, "SELECT state FROM cases WHERE case_id = %s", case_id) == state
    assert scalar(db, "SELECT count(*) FROM evaluation_jobs") == 0 and retries() == before


async def test_retry_is_only_for_the_cro_and_needs_no_mfa(db: Db) -> None:
    case_id = seed_case(db, state="no_disponible")
    async with harness(db) as h:
        analyst = await h.client.post(f"/v1/cases/{case_id}/retry", headers=auth("analista"))
        cro = await h.client.post(
            f"/v1/cases/{case_id}/retry", headers=auth("cro")
        )  # el principal de la prueba tiene `acr = 1`, no `mfa`
    assert analyst.status_code == 403 and cro.status_code == 200


async def test_retry_that_clashes_with_a_live_job_is_409_without_changing_the_state(db: Db) -> None:
    """P-2 (a): el `INSERT` choca con el indice unico; la transaccion se revierte."""
    case_id = seed_case(db, state="no_disponible")
    db.execute("INSERT INTO evaluation_jobs (case_id, attempt) VALUES (%s, 6)", case_id)
    async with harness(db) as h:
        r = await h.client.post(f"/v1/cases/{case_id}/retry", headers=auth("cro"))
    assert r.status_code == 409
    assert scalar(db, "SELECT state FROM cases WHERE case_id = %s", case_id) == "no_disponible"


async def test_retry_on_an_unknown_case_is_404(db: Db) -> None:
    async with harness(db) as h:
        r = await h.client.post("/v1/cases/00000000-0000-4000-8000-000000000001/retry", headers=auth("cro"))
    assert r.status_code == 404


async def test_persistent_failure_since_is_the_time_of_the_state_change(db: Db) -> None:
    """P-4 (a): `since` sale de `cases.updated_at`, y cada `UPDATE` de U8 fija `updated_at`."""
    case_id = seed_case(db, state="no_disponible", attempts=6, last_cause="scoring_unreachable")
    async with harness(db) as h:
        r = await h.client.get("/v1/cases/failures", headers=auth("cro"))
    assert r.status_code == 200
    (item,) = r.json()
    updated = scalar(db, "SELECT updated_at FROM cases WHERE case_id = %s", case_id)
    assert item["case_id"] == str(case_id) and item["attempts"] == 6
    assert item["since"].replace("Z", "+00:00") == updated.isoformat()
