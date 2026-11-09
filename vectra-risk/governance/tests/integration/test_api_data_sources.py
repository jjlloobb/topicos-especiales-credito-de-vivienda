"""Paso 10 (U04-T04), fuentes de datos (US-306 por Q-6): alta y lista, version candidata con `source_candidate_for`,
`start_source_comparison` (BR-U4-13 punto 2), `PUT /v1/validation-runs/{run_id}/source-counts` (F32), `compare_source` (F25) y la
decision de cumplimiento con el `PrePostReport` (<= 48 KiB).

BR-U4-13 (ciclo de la fuente), BR-U4-10 (cuatro ojos de la fuente), BR-U4-01 (la candidata no se aprueba ni se activa con la
fuente `en_evaluacion`). Sigue diferido el modo `source_comparison` del `model-validation-job` y la rama del barrido (Paso 13).
"""

import json
from pathlib import Path

import pytest
from api_support import ApiWorld, count_tables, registration_body
from evidence_support import ING, new_model, report, to_activo, with_active_policy

pytestmark = pytest.mark.integration

DS = "ds-1"
CANDIDATE = "mv-2026-03-01-cccccccc"
ACTIVE = "mv-2026-01-01-aaaaaaaa"
JOB = ("model-validation-job", "governance:validation-report")
PROPOSAL = {"name": "Buro alterno", "description": "Datos de pagos de servicios", "provides_features": ["f1"], "owner": "datos"}


def candidate(world: ApiWorld, model_id: str = CANDIDATE, source: str = DS) -> None:
    """Una version candidata de `source` (registrada por la capa de servicio; la via HTTP la cubre otra prueba)."""
    new = new_model(model_id)
    reg = new.registration.model_copy(update={"data_sources": [source], "source_candidate_for": source})
    world.svc.register(ING, new.__class__(**{**new.__dict__, "registration": reg}))


def comparison_runs(world: ApiWorld) -> list[dict[str, object]]:
    return world.sql("SELECT state FROM validation_runs WHERE mode = 'source_comparison' ORDER BY started_at")


def with_isvcs(world: ApiWorld, *models: str) -> None:
    for model in models:
        world.k8s.inference_services.add(world.sql("SELECT inference_service FROM model_versions WHERE model_version_id = %s", model)[0]["inference_service"])


def comparison_ready(world: ApiWorld) -> None:
    """Fuente `en_evaluacion`, version `activo` y candidata, con los dos `InferenceService` de staging."""
    world.put_source(DS)
    with_active_policy(world.svc)
    to_activo(world.svc, ACTIVE)
    candidate(world)
    with_isvcs(world, ACTIVE, CANDIDATE)


async def compare(world: ApiWorld, source: str = DS, candidate_id: str = CANDIDATE, role: str = "ingeniero_riesgo"):  # type: ignore[no-untyped-def]
    return await world.client.post(
        f"/v1/data-sources/{source}/comparisons", headers=world.user(role), json={"candidate_version_id": candidate_id}
    )


# --- Alta y lista -------------------------------------------------------------------------------------------------------------


async def test_us_306_the_engineer_proposes_a_source_which_goes_to_en_evaluacion(world: ApiWorld) -> None:
    response = await world.client.post("/v1/data-sources", headers=world.user("ingeniero_riesgo", "ing-1"), json=PROPOSAL)
    assert response.status_code == 200, response.text
    source = response.json()
    assert source["state"] == "en_evaluacion" and source["proposed_by"] == "ing-1"
    row = world.sql("SELECT * FROM data_sources")[0]
    assert (row["ds_id"], row["state"], row["proposed_by"], row["name"]) == (source["ds_id"], "en_evaluacion", "ing-1", "Buro alterno")
    assert [e["event"] for e in world.source_events(source["ds_id"])] == ["evaluacion_iniciada"]
    assert world.sql("SELECT status, to_state FROM transitions") == [{"status": "confirmada", "to_state": "en_evaluacion"}]
    for role in ("cro", "cumplimiento", "analista"):
        assert (await world.client.post("/v1/data-sources", headers=world.user(role), json=PROPOSAL)).status_code == 403
    assert (await world.client.post("/v1/data-sources", headers=world.user("ingeniero_riesgo", mfa=False), json=PROPOSAL)).status_code in (401, 403)
    assert world.count("data_sources") == 1


async def test_the_list_of_sources_is_for_engineer_cro_and_compliance(world: ApiWorld) -> None:
    world.put_source(DS)
    world.put_source("ds-2", state="aprobada")
    for role in ("ingeniero_riesgo", "cro", "cumplimiento"):
        response = await world.client.get("/v1/data-sources", headers=world.user(role))
        assert response.status_code == 200 and {s["ds_id"]: s["state"] for s in response.json()} == {DS: "en_evaluacion", "ds-2": "aprobada"}
    assert (await world.client.get("/v1/data-sources", headers=world.user("analista"))).status_code == 403


# --- Version candidata (BR-U4-13 punto 1) ------------------------------------------------------------------------------------------


async def test_a_candidate_with_its_source_en_evaluacion_registers_and_cannot_be_approved_or_activated(
    world: ApiWorld, package_dir: Path
) -> None:
    world.put_source(DS)
    with_active_policy(world.svc)
    body = registration_body(package_dir, world.store, "pkg", data_sources=[DS], source_candidate_for=DS)
    response = await world.client.post("/v1/models", headers=world.user("ingeniero_riesgo"), json=body)
    assert response.status_code == 200, response.text
    model_id = response.json()["model_version_id"]
    row = world.sql("SELECT state, source_candidate_for, data_sources FROM model_versions")[0]
    assert (row["state"], row["source_candidate_for"], row["data_sources"]) == ("registrado", DS, [DS])
    # La candidata llega a `lista_para_aprobacion`; el CRO no la aprueba mientras la fuente siga `en_evaluacion`.
    await world.client.post(f"/v1/models/{model_id}/validations", headers=world.user("ingeniero_riesgo"))
    await world.client.put(f"/v1/models/{model_id}/validation-report", headers=world.service(*JOB), json=report(True).model_dump(mode="json"))
    assert world.state(model_id) == "lista_para_aprobacion"
    approval = await world.client.post(f"/v1/models/{model_id}/approval", headers=world.user("cro"), json={"decision": "aprobado"})
    assert approval.status_code == 409 and world.state(model_id) == "lista_para_aprobacion"
    # Ni activarla, aunque llegara a `aprobado` por otra via: la fuente decide.
    with world.db.connect() as conn:
        conn.execute("UPDATE model_versions SET state = 'aprobado'")
    activation = await world.client.post(
        f"/v1/models/{model_id}/activation", headers=world.user("ingeniero_riesgo", scope="governance:promotion"), json={"evidence": "PR"}
    )
    assert activation.status_code == 409 and world.state(model_id) == "aprobado"


async def test_a_common_version_that_declares_a_source_not_approved_is_422_but_an_approved_one_is_fine(
    world: ApiWorld, package_dir: Path
) -> None:
    world.put_source(DS)
    headers = world.user("ingeniero_riesgo")
    transitions = world.count("transitions")
    for over in (
        {"data_sources": [DS]},  # fuente `en_evaluacion` sin ser candidata
        {"data_sources": ["ds-desconocida"]},
        {"data_sources": [], "source_candidate_for": "ds-desconocida"},
    ):
        body = registration_body(package_dir, world.store, "pkg", **over)
        assert (await world.client.post("/v1/models", headers=headers, json=body)).status_code == 422, over
        assert world.count("model_versions") == 0 and world.count("transitions") == transitions  # sin version ni transicion
    world.put_source("ds-ok", state="aprobada")
    body = registration_body(package_dir, world.store, "pkg", data_sources=["ds-ok"])
    assert (await world.client.post("/v1/models", headers=headers, json=body)).status_code == 200
    assert world.sql("SELECT data_sources, source_candidate_for FROM model_versions") == [{"data_sources": ["ds-ok"], "source_candidate_for": None}]


# --- start_source_comparison (BR-U4-13 punto 2) --------------------------------------------------------------------------------------


async def test_start_source_comparison_creates_the_job_in_staging_in_source_comparison_mode(world: ApiWorld) -> None:
    comparison_ready(world)
    transitions = world.count("transitions")
    response = await compare(world)
    assert response.status_code == 200, response.text
    run = response.json()
    assert (run["mode"], run["state"], run["source_id"], run["baseline_version_id"], run["model_version_id"]) == (
        "source_comparison", "lanzado", DS, ACTIVE, CANDIDATE,
    )
    ((namespace, name), manifest) = next(iter(world.k8s.jobs.items()))
    assert (namespace, name) == ("vectra-staging", run["job_name"])
    spec = manifest["spec"]
    assert (spec["ttlSecondsAfterFinished"], spec["activeDeadlineSeconds"], spec["backoffLimit"]) == (86400, 7200, 0)
    env = {e["name"]: e.get("value") for e in spec["template"]["spec"]["containers"][0]["env"]}
    assert env["VECTRA_JOB_MODE"] == "source_comparison" and env["VECTRA_SOURCE_ID"] == DS
    assert (env["VECTRA_MODEL_VERSION_ID"], env["VECTRA_BASELINE_VERSION_ID"]) == (CANDIDATE, ACTIVE)
    row = world.sql("SELECT * FROM validation_runs WHERE run_id = %s", run["run_id"])[0]
    assert (row["mode"], row["state"], row["source_id"], row["baseline_version_id"]) == ("source_comparison", "lanzado", DS, ACTIVE)
    assert (row["deadline_at"] - row["started_at"]).total_seconds() == 7200
    # La comparacion no cambia el estado de ninguna version ni escribe evidencia.
    assert (world.state(CANDIDATE), world.state(ACTIVE)) == ("registrado", "activo")
    assert world.count("transitions") == transitions


async def test_start_source_comparison_without_an_active_version_is_409_no_active_version(world: ApiWorld) -> None:
    world.put_source(DS)
    candidate(world)
    with_isvcs(world, CANDIDATE)
    response = await compare(world)
    assert response.status_code == 409 and response.json()["reason"] == "no_active_version"
    assert world.k8s.jobs == {} and comparison_runs(world) == []


async def test_start_source_comparison_against_a_frozen_version_is_409_active_version_frozen(world: ApiWorld) -> None:
    from evidence_support import BIAS, freeze_context

    comparison_ready(world)
    world.svc.freeze(BIAS, ACTIVE, freeze_context(ACTIVE))
    response = await compare(world)
    assert response.status_code == 409 and response.json()["reason"] == "active_version_frozen"
    assert world.k8s.jobs == {}


async def test_start_source_comparison_needs_both_staging_inference_services(world: ApiWorld) -> None:
    comparison_ready(world)
    for missing in (ACTIVE, CANDIDATE):
        world.k8s.inference_services.clear()
        with_isvcs(world, *({ACTIVE, CANDIDATE} - {missing}))
        response = await compare(world)
        assert response.status_code == 409, missing
    assert world.k8s.jobs == {} and comparison_runs(world) == []


async def test_start_source_comparison_is_409_with_another_one_launched_or_the_wrong_candidate_or_source(world: ApiWorld) -> None:
    comparison_ready(world)
    other = "mv-2026-04-01-dddddddd"
    world.put_source("ds-9")
    candidate(world, other, "ds-9")
    with_isvcs(world, other)
    assert (await compare(world)).status_code == 200
    assert (await compare(world)).status_code == 409  # otra comparacion `lanzado` de la misma fuente
    assert (await compare(world, DS, other)).status_code == 409  # la candidata es de otra fuente
    assert (await compare(world, "ds-9", ACTIVE)).status_code == 409  # `activo` no es candidata
    assert (await compare(world, "ds-nope")).status_code == 404
    world.put_source("ds-10", state="aprobada")
    assert (await compare(world, "ds-10")).status_code == 409  # la fuente no esta `en_evaluacion`
    assert len(world.k8s.jobs) == 1 and len(comparison_runs(world)) == 1


async def test_start_source_comparison_is_for_the_engineer_with_mfa_only(world: ApiWorld) -> None:
    comparison_ready(world)
    for role in ("cro", "cumplimiento", "analista"):
        assert (await compare(world, role=role)).status_code == 403
    response = await world.client.post(
        f"/v1/data-sources/{DS}/comparisons", headers=world.user("ingeniero_riesgo", mfa=False), json={"candidate_version_id": CANDIDATE}
    )
    assert response.status_code in (401, 403)
    assert world.k8s.jobs == {}


async def test_if_kubernetes_refuses_the_comparison_job_the_run_is_closed_and_the_comparison_can_be_retried(world: ApiWorld) -> None:
    comparison_ready(world)
    world.k8s.fail_create = True
    assert (await compare(world)).status_code == 503
    assert comparison_runs(world) == [{"state": "fallido"}]
    world.k8s.fail_create = False
    assert (await compare(world)).status_code == 200  # la corrida fallida no cuenta como `lanzado`


# --- source-counts (F32) y compare_source (F25) ----------------------------------------------------------------------------------


async def launched_run(world: ApiWorld) -> str:
    comparison_ready(world)
    return str((await compare(world)).json()["run_id"])


async def test_source_counts_stores_the_counts_and_the_pre_post_report_once(world: ApiWorld) -> None:
    run_id = await launched_run(world)
    path = f"/v1/validation-runs/{run_id}/source-counts"
    assert (await world.client.put(path, headers=world.service("someone", "governance:read-serving"), json=count_tables())).status_code == 403
    response = await world.client.put(path, headers=world.service(*JOB), json=count_tables())
    assert response.status_code == 204, response.text
    run = world.sql("SELECT state, report, finished_at FROM validation_runs WHERE mode = 'source_comparison'")[0]
    assert run["state"] == "informe_recibido" and run["finished_at"] is not None
    assert run["report"] == json.loads(json.dumps(count_tables()))  # solo tablas de conteo, nunca filas
    stored = world.sql("SELECT pre_post_report FROM data_sources")[0]["pre_post_report"]
    assert stored["source_id"] == DS and stored["disclaimer"]
    assert [r.source_id for r in world.bias.requests] == [DS]  # F25 recibio las tablas
    assert world.bias.requests[0].model_dump(mode="json")["pre"] == count_tables()["pre"]
    assert (await world.client.put(path, headers=world.service(*JOB), json=count_tables())).status_code == 409  # solo una vez
    assert len(world.bias.requests) == 1  # y no volvio a llamar a bias
    assert world.state(CANDIDATE) == "registrado"


async def test_source_counts_on_a_validation_run_or_an_unknown_one_or_bad_tables_is_refused(world: ApiWorld) -> None:
    world.svc.register(ING, new_model("mv-2026-05-01-eeeeeeee"))
    world.svc.start_validation(ING, "mv-2026-05-01-eeeeeeee", job_name="j")
    validation_run = str(world.sql("SELECT run_id FROM validation_runs WHERE state = 'lanzado'")[0]["run_id"])
    job = world.service(*JOB)
    response = await world.client.put(f"/v1/validation-runs/{validation_run}/source-counts", headers=job, json=count_tables())
    assert response.status_code == 409
    assert (await world.client.put("/v1/validation-runs/00000000-0000-0000-0000-000000000000/source-counts", headers=job, json=count_tables())).status_code == 404
    assert (await world.client.put("/v1/validation-runs/no-es-uuid/source-counts", headers=job, json=count_tables())).status_code == 404
    assert world.bias.requests == []
    run_id = await launched_run(world)
    three = {**count_tables(), "pre": count_tables()["pre"][:3]}
    assert (await world.client.put(f"/v1/validation-runs/{run_id}/source-counts", headers=job, json=three)).status_code == 422
    assert world.sql("SELECT state FROM validation_runs WHERE run_id = %s", run_id) == [{"state": "lanzado"}]
    assert (await world.client.put(f"/v1/validation-runs/{run_id}/source-counts", headers=world.service("x", "governance:read-serving"), json=count_tables())).status_code == 403


async def test_if_bias_is_down_the_counts_are_not_consumed(world: ApiWorld) -> None:
    run_id = await launched_run(world)
    path = f"/v1/validation-runs/{run_id}/source-counts"
    world.bias.fail = True
    assert (await world.client.put(path, headers=world.service(*JOB), json=count_tables())).status_code == 503
    assert world.sql("SELECT state FROM validation_runs WHERE run_id = %s", run_id) == [{"state": "lanzado"}]
    assert world.sql("SELECT pre_post_report FROM data_sources") == [{"pre_post_report": None}]
    world.bias.fail = False
    assert (await world.client.put(path, headers=world.service(*JOB), json=count_tables())).status_code == 204


# --- decision de cumplimiento ----------------------------------------------------------------------------------------------------


def decision(decision: str = "aprobada", **over: object) -> dict[str, object]:
    return {"decision": decision, "justification": "revisado", **over}


async def decide(world: ApiWorld, body: dict[str, object] | None = None, role: str = "cumplimiento", sub: str = "cum-1", source: str = DS):  # type: ignore[no-untyped-def]
    return await world.client.post(f"/v1/data-sources/{source}/decision", headers=world.user(role, sub), json=body or decision())


async def test_deciding_without_a_pre_post_report_is_409(world: ApiWorld) -> None:
    world.put_source(DS)
    response = await decide(world)
    assert response.status_code == 409
    assert world.sql("SELECT state, decided_by FROM data_sources") == [{"state": "en_evaluacion", "decided_by": None}]
    assert world.source_events(DS) == []


async def test_compliance_approves_with_the_report_and_the_event_carries_it(world: ApiWorld) -> None:
    world.put_source(DS, groups=1)
    response = await decide(world)
    assert response.status_code == 204, response.text
    row = world.sql("SELECT state, decided_by, decision_justification, decided_at FROM data_sources")[0]
    assert (row["state"], row["decided_by"], row["decision_justification"]) == ("aprobada", "cum-1", "revisado") and row["decided_at"]
    (event,) = world.source_events(DS)
    assert event["event"] == "aprobada" and event["pre_post_report"]["source_id"] == DS and event["pre_post_report"]["truncated"] is False
    assert (await decide(world)).status_code == 409  # ya esta decidida


async def test_compliance_rejects_with_the_report_and_the_event_says_rechazada(world: ApiWorld) -> None:
    world.put_source(DS, groups=1)
    assert (await decide(world, decision("rechazada"))).status_code == 204
    assert world.sql("SELECT state FROM data_sources") == [{"state": "rechazada"}]
    assert [e["event"] for e in world.source_events(DS)] == ["rechazada"] and world.source_events(DS)[0]["pre_post_report"]


async def test_a_report_over_48_kib_reaches_the_event_without_cells_and_with_truncated_true(world: ApiWorld) -> None:
    world.put_source(DS, groups=60)
    stored = world.sql("SELECT pre_post_report FROM data_sources")[0]["pre_post_report"]
    assert len(json.dumps(stored)) > 48 * 1024  # el caso: el informe guardado pesa mas de 48 KiB
    assert (await decide(world)).status_code == 204
    (event,) = world.source_events(DS)
    report_sent = event["pre_post_report"]
    assert len(json.dumps(report_sent)) <= 48 * 1024
    assert report_sent["truncated"] is True
    assert all(a["cells"] == [] for side in ("pre", "post") for a in report_sent[side]["attributes"])
    assert all(a["aggregate"] == "0.0100" for a in report_sent["pre"]["attributes"])  # las agregadas se conservan
    assert world.sql("SELECT pre_post_report FROM data_sources")[0]["pre_post_report"] == stored  # la fuente guarda el completo


async def test_br_u4_10_the_proposer_cannot_decide_and_only_compliance_with_mfa_does(world: ApiWorld) -> None:
    world.put_source(DS, groups=1, proposed_by="cum-1")
    assert (await decide(world, sub="cum-1")).status_code == 409  # cuatro ojos
    for role in ("ingeniero_riesgo", "cro", "analista"):
        assert (await decide(world, role=role)).status_code == 403
    mfa_less = await world.client.post(f"/v1/data-sources/{DS}/decision", headers=world.user("cumplimiento", mfa=False), json=decision())
    assert mfa_less.status_code in (401, 403)
    assert (await decide(world, source="ds-nope")).status_code == 404
    assert world.sql("SELECT state FROM data_sources") == [{"state": "en_evaluacion"}]
    assert (await decide(world, sub="cum-2")).status_code == 204


async def test_us_306_end_to_end_the_source_is_approved_and_then_the_candidate_can_be_approved(world: ApiWorld) -> None:
    """Propuesta -> candidata -> comparacion -> conteos -> informe -> decision -> la candidata se aprueba (BR-U4-13)."""
    proposed = await world.client.post("/v1/data-sources", headers=world.user("ingeniero_riesgo", "ing-1"), json=PROPOSAL)
    ds = proposed.json()["ds_id"]
    with_active_policy(world.svc)
    to_activo(world.svc, ACTIVE)
    candidate(world, CANDIDATE, ds)
    with_isvcs(world, ACTIVE, CANDIDATE)
    run = (await compare(world, ds)).json()
    await world.client.put(f"/v1/validation-runs/{run['run_id']}/source-counts", headers=world.service(*JOB), json=count_tables())
    # La candidata pasa su validacion; mientras la fuente no este aprobada, no se aprueba.
    world.svc.start_validation(ING, CANDIDATE, job_name="j-val")
    val_run = str(world.sql("SELECT run_id FROM validation_runs WHERE mode = 'validacion' AND state = 'lanzado'")[0]["run_id"])
    from evidence_support import VALIDATION_JOB

    world.svc.receive_report(VALIDATION_JOB, CANDIDATE, val_run, report(True))
    approval = f"/v1/models/{CANDIDATE}/approval"
    assert (await world.client.post(approval, headers=world.user("cro"), json={"decision": "aprobado"})).status_code == 409
    assert (await decide(world, source=ds)).status_code == 204
    assert world.sql("SELECT state FROM data_sources WHERE ds_id = %s", ds) == [{"state": "aprobada"}]
    assert (await world.client.post(approval, headers=world.user("cro"), json={"decision": "aprobado"})).status_code == 204
    assert world.state(CANDIDATE) == "aprobado"
    assert [e["event"] for e in world.source_events(ds)] == ["evaluacion_iniciada", "aprobada"]
