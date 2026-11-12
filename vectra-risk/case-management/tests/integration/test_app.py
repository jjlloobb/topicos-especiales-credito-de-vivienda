"""Paso 13: las 9 rutas de F04 y F10, bandeja, detalle, identificadores, logs y metricas (BR-U8-13, 13b; P-U8-06; US-107, US-108)."""

import json

import httpx
import pytest
from case_pg import Db
from prometheus_client.parser import text_string_to_metric_families
from u8_support import application, auth, harness, scalar, seed_case
from vectra_case import metrics
from vectra_case.app import build_app
from vectra_common.metrics import REGISTRY
from vectra_contracts.catalog import Outcome
from vectra_contracts.routes import REGISTRY as ROUTES

pytestmark = pytest.mark.integration


def logs(out: str) -> list[dict[str, object]]:
    return [json.loads(line) for line in out.splitlines() if line.startswith("{")]


def test_the_app_has_exactly_the_nine_routes_of_the_contract() -> None:
    app = build_app()
    paths = {(m, r.path) for r in app.routes for m in getattr(r, "methods", ())}  # type: ignore[attr-defined]
    assert paths == {(r.method, r.path) for r in ROUTES["case-service"]} and len(ROUTES["case-service"]) == 9


async def test_inbox_shows_every_state_and_only_listo_or_decidido_carry_a_score(db: Db) -> None:
    ids = {
        s: seed_case(db, state=s)
        for s in ("listo", "en_sincronizacion", "no_disponible", "modelo_congelado", "en_evaluacion")
    }
    async with harness(db) as h:
        r = await h.client.get("/v1/cases", headers=auth("analista"))
        details = {s: await h.client.get(f"/v1/cases/{i}", headers=auth("analista")) for s, i in ids.items()}
    assert r.status_code == 200 and r.json()["total"] == 5
    by_state = {i["state"]: i for i in r.json()["items"]}
    assert by_state["listo"]["score"] == "0.4200" and by_state["listo"]["outcome"] == "favorable"
    for state in ("en_sincronizacion", "no_disponible", "modelo_congelado", "en_evaluacion"):
        assert "score" not in by_state[state] and "outcome" not in by_state[state]
        assert "score" not in details[state].json() and "recommendation" not in details[state].json()
    assert (
        details["listo"].json()["score"] == "0.4200"
        and details["listo"].json()["recommendation"]["registry_entry_id"] == "7"
    )
    assert by_state["listo"]["applicant_display"] == "Ana María Gómez 4050"


async def test_failure_states_show_attempts_and_last_cause(db: Db) -> None:
    case_id = seed_case(db, state="en_sincronizacion", attempts=2, last_cause="scoring_unreachable")
    async with harness(db) as h:
        d = (await h.client.get(f"/v1/cases/{case_id}", headers=auth("cro"))).json()
    assert d["attempts"] == 2 and d["last_cause"] == "scoring_unreachable"


async def test_list_excludes_vencido_unless_the_state_filter_asks_for_it_and_paginates(db: Db) -> None:
    for _ in range(3):
        seed_case(db, state="listo")
    seed_case(db, state="vencido")
    async with harness(db) as h:
        default = await h.client.get("/v1/cases", headers=auth("analista"))
        vencido = await h.client.get("/v1/cases?state=vencido", headers=auth("analista"))
        page = await h.client.get("/v1/cases?page_size=2&page=2", headers=auth("cro"))
        several = await h.client.get("/v1/cases?state=listo,vencido", headers=auth("cro"))
    assert (
        default.json()["total"] == 3
        and vencido.json()["total"] == 1
        and vencido.json()["items"][0]["state"] == "vencido"
    )
    assert page.json()["total"] == 3 and len(page.json()["items"]) == 1 and page.json()["page"] == 2
    assert several.json()["total"] == 4


async def test_model_frozen_filter_returns_only_marked_or_only_unmarked(db: Db) -> None:
    marked = seed_case(db, state="listo", frozen_mark=True)
    plain = seed_case(db, state="listo")
    async with harness(db) as h:
        yes = await h.client.get("/v1/cases?model_frozen_after_recommendation=true", headers=auth("analista"))
        no = await h.client.get("/v1/cases?model_frozen_after_recommendation=false", headers=auth("analista"))
        both = await h.client.get("/v1/cases", headers=auth("analista"))
    assert [i["case_id"] for i in yes.json()["items"]] == [str(marked)]
    assert [i["case_id"] for i in no.json()["items"]] == [str(plain)]
    assert both.json()["total"] == 2


async def test_detail_for_the_analyst_has_no_sex_or_stratum_and_logs_case_viewed(
    db: Db, capsys: pytest.CaptureFixture[str]
) -> None:
    case_id = seed_case(db, state="listo")
    async with harness(db) as h:
        r = await h.client.get(f"/v1/cases/{case_id}", headers=auth("analista"))
    body = r.json()
    assert (
        r.status_code == 200
        and "sex" not in json.dumps(body)
        and "socioeconomic_stratum" not in json.dumps(body)
    )
    assert body["application"]["free_text"] if "free_text" in body["application"] else True
    assert body["identifiers"]["document_number"] == "1020304050" and body["anonymized"] is False
    viewed = [e for e in logs(capsys.readouterr().out) if e.get("event") == "case.viewed"]
    assert (
        viewed
        and viewed[0]["principal_subject"] == "analista-1"
        and viewed[0]["principal_role"] == "analista"
    )
    assert viewed[0]["case_id"] == str(case_id) and "full_name" not in viewed[0]


async def test_detail_of_a_decided_case_carries_the_decision(db: Db) -> None:
    case_id = seed_case(db, state="listo", outcome=Outcome.FAVORABLE)
    async with harness(db) as h:
        await h.client.post(
            f"/v1/cases/{case_id}/decision",
            json={
                "decision": "sigue",
                "final_outcome": "favorable",
                "used_factors": ["ninguno"],
                "justification": "",
            },
            headers=auth("analista"),
        )
        d = (await h.client.get(f"/v1/cases/{case_id}", headers=auth("analista"))).json()
    assert (
        d["state"] == "decidido"
        and d["decision"]["decided_by"] == "analista-1"
        and d["decision"]["decision"] == "sigue"
    )
    assert d["credit_status"] == "no_integrado"


async def test_get_case_identifiers_for_cumplimiento_returns_only_identifiers_and_anonymized(db: Db) -> None:
    plain = seed_case(db, state="listo")
    anonymized = seed_case(db, state="decidido", anonymized=True)
    async with harness(db) as h:
        ok = await h.client.get(f"/v1/cases/{plain}/identifiers", headers=auth("cumplimiento"))
        anon = await h.client.get(f"/v1/cases/{anonymized}/identifiers", headers=auth("cro"))
        denied = await h.client.get(f"/v1/cases/{plain}/identifiers", headers=auth("analista"))
    assert (
        ok.status_code == 200
        and set(ok.json()) == {"case_id", "identifiers", "anonymized"}
        and ok.json()["anonymized"] is False
    )
    assert anon.json() == {"case_id": str(anonymized), "anonymized": True}
    assert denied.status_code == 403


async def test_anonymized_detail_has_no_identifiers_and_an_empty_applicant_display(db: Db) -> None:
    case_id = seed_case(db, state="decidido", anonymized=True)
    async with harness(db) as h:
        d = (await h.client.get(f"/v1/cases/{case_id}", headers=auth("analista"))).json()
    assert d["anonymized"] is True and "identifiers" not in d and d["applicant_display"] == ""


async def test_a_route_without_scope_or_role_is_403_with_authz_denied_and_the_metric(
    db: Db, capsys: pytest.CaptureFixture[str]
) -> None:
    def denied() -> float:
        return (
            REGISTRY.get_sample_value(
                "vectra_authz_denied_total",
                {"code": "forbidden", "route_template": "/v1/intake/applications"},
            )
            or 0.0
        )

    before = denied()
    async with harness(db) as h:
        r = await h.client.post(
            "/v1/intake/applications", json=application(), headers=auth("noscope", **{"Idempotency-Key": "k"})
        )
        anon = await h.client.get("/v1/cases", headers={"Authorization": "Bearer nadie"})
    assert r.status_code == 403 and anon.status_code == 401
    assert denied() == before + 1
    events = logs(capsys.readouterr().out)
    assert any(e.get("event") == "authz.denied" and e.get("error_code") == "forbidden" for e in events)
    assert any(e.get("event") == "authz.denied" and e.get("error_code") == "unauthenticated" for e in events)
    assert scalar(db, "SELECT count(*) FROM cases") == 0


async def test_case_viewed_and_retry_requested_pass_the_strict_allowlist(
    db: Db, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """PBT-U0-07, modo strict: ningun campo se descarta y el actor esta presente."""
    monkeypatch.setenv("VECTRA_LOG_STRICT", "1")
    listo = seed_case(db, state="listo")
    failed = seed_case(db, state="no_disponible")
    async with harness(db) as h:
        assert (await h.client.get(f"/v1/cases/{listo}", headers=auth("analista"))).status_code == 200
        assert (await h.client.get(f"/v1/cases/{listo}/identifiers", headers=auth("cro"))).status_code == 200
        assert (await h.client.post(f"/v1/cases/{failed}/retry", headers=auth("cro"))).status_code == 200
    events = [
        e for e in logs(capsys.readouterr().out) if e.get("event") in ("case.viewed", "case.retry_requested")
    ]
    assert {e["event"] for e in events} == {"case.viewed", "case.retry_requested"}
    for e in events:
        assert e["principal_subject"] and e["principal_role"] and e["case_id"]


async def test_metrics_endpoint_shows_every_closed_set_series_at_zero_and_no_label_outside_the_allowlist(
    db: Db,
) -> None:
    async with harness(db) as h:
        transport = httpx.ASGITransport(app=h.app.state.ops_app)
        async with httpx.AsyncClient(transport=transport, base_url="http://ops") as ops:
            body = (await ops.get("/metrics")).text
    families = {f.name: f for f in text_string_to_metric_families(body)}
    attempts = families["vectra_case_attempts"].samples
    combos = {(s.labels["result"], s.labels["attempt"]) for s in attempts if s.name.endswith("_total")}
    assert combos == {(r, a) for r in metrics.ATTEMPT_RESULTS for a in metrics.ATTEMPTS} and len(combos) == 36
    assert {
        s.labels["entry_type"]
        for s in families["vectra_case_evidence_abandoned"].samples
        if s.name.endswith("_total")
    } == set(metrics.ENTRY_TYPES)
    for name in ("vectra_case_retries", "vectra_case_evidence_discarded"):
        assert any(s.name.endswith("_total") for s in families[name].samples)
    assert "vectra_cases_failclosed_persistent" in families and "vectra_case_jobs_overdue" in families
    for family in REGISTRY.collect():
        if family.name.startswith(("vectra_case", "vectra_cases")):
            for sample in family.samples:
                assert set(sample.labels) <= metrics.ALLOWED_LABELS | {"le"}, (family.name, sample.labels)
    for sample in families["vectra_case_attempts"].samples:
        if sample.name.endswith("_total") and sample.value:
            pytest.fail(f"un contador de U8 no arranca en 0: {sample}")
