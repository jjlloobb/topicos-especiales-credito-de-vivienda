"""Paso 10 (U04-T04), modelos: registrar con los paquetes reales de U5, validar (Job de K01), informe F32, aprobar, activar,
retirar, listas, `feature-spec`, `feature-dictionary` y `serving-config`. US-201, US-202, US-203, US-208, US-305.

BR-U4-03 (reactivar solo cumplimiento + MFA + step-up), BR-U4-05 (el Job), BR-U4-06 (registrar sin deserializar), BR-U4-07
(solo la sincronia bloquea), BR-U4-08 (`mark_active`), BR-U4-10 (cuatro ojos), BR-U4-18 y BR-U4-19 (diccionario y `feature_spec`).
La lectura de vuelta es con SQL y con la cadena del doble del registro; el codigo HTTP solo no basta.
"""

import json
from pathlib import Path

import pytest
from api_support import ApiWorld, registration_body
from evidence_support import report, to_activo, to_aprobado, with_active_policy
from vectra_governance.k8s_jobs import JobInfo
from vectra_reference.adversarial import ACCEPTED_BY_U4, REJECTED_BY_U4, rt3_package

pytestmark = pytest.mark.integration

PROMOTION = "governance:promotion"


def version_of(directory: Path) -> str:
    return str(json.loads((directory / "manifest.json").read_bytes())["model_version_id"])


async def register(world: ApiWorld, directory: Path, prefix: str = "pkg", sub: str = "ing-1", **over: object):  # type: ignore[no-untyped-def]
    body = registration_body(directory, world.store, prefix, **over)
    return await world.client.post("/v1/models", headers=world.user("ingeniero_riesgo", sub), json=body)


async def registered(world: ApiWorld, package_dir: Path) -> str:
    with_active_policy(world.svc)  # el lanzador pasa al Job la politica activa (BR-U7-04/05)
    response = await register(world, package_dir)
    assert response.status_code == 200, response.text
    return version_of(package_dir)


# --- Registro (BR-U4-06) ------------------------------------------------------------------------------------------------------


async def test_us_201_the_real_package_registers_and_leaves_its_evidence(world: ApiWorld, package_dir: Path) -> None:
    response = await register(world, package_dir)
    model_id = version_of(package_dir)
    assert response.status_code == 200, response.text  # el contrato de U0 responde 200 con la version
    assert response.json()["state"] == "registrado" and response.json()["model_version_id"] == model_id
    row = world.sql("SELECT * FROM model_versions WHERE model_version_id = %s", model_id)[0]
    assert (row["state"], row["registered_by"], row["inference_service"]) == ("registrado", "ing-1", f"isvc-{model_id[-8:]}")
    assert row["feature_dictionary"] == json.loads((package_dir / "feature_dictionary.json").read_bytes())
    assert world.sql("SELECT status FROM transitions WHERE entity_id = %s", model_id) == [{"status": "confirmada"}]
    assert world.chain(model_id) == ["registrado"]


@pytest.mark.parametrize("case_id", REJECTED_BY_U4)
async def test_br_u4_06_rt3_a_c_d_are_422_and_create_nothing(
    world: ApiWorld, package_dir: Path, tmp_path: Path, case_id: str
) -> None:
    rt3_package(case_id, package_dir, tmp_path / case_id)
    response = await register(world, tmp_path / case_id, case_id)
    assert response.status_code == 422, response.text
    assert response.json()["code"] == "validation_error"
    assert [world.count(t) for t in ("model_versions", "transitions")] == [0, 0]
    assert world.registry.chain == []


@pytest.mark.parametrize("case_id", ACCEPTED_BY_U4)
async def test_br_u4_06_rt3_b_is_accepted(world: ApiWorld, package_dir: Path, tmp_path: Path, case_id: str) -> None:
    rt3_package(case_id, package_dir, tmp_path / case_id)
    response = await register(world, tmp_path / case_id, case_id)
    assert response.status_code == 200, response.text
    assert world.state(version_of(tmp_path / case_id)) == "registrado"


async def test_us_201_altered_checksum_or_pickle_bytes_are_422_without_a_row(
    world: ApiWorld, package_dir: Path, tmp_path: Path
) -> None:
    assert (await register(world, package_dir, artifact_sha256="0" * 64)).status_code == 422
    target = tmp_path / "bad"
    rt3_package("RT3-b", package_dir, target)
    (target / "background.csv").write_bytes(b"\x80\x04pickle")  # bytes magicos de pickle en un archivo del manifiesto
    assert (await register(world, target, "bad")).status_code == 422
    assert world.count("model_versions") == 0 and world.registry.chain == []


async def test_registering_a_model_needs_the_engineer_with_mfa(world: ApiWorld, package_dir: Path) -> None:
    body = registration_body(package_dir, world.store, "pkg")
    for headers in (world.user("cro"), world.user("ingeniero_riesgo", mfa=False)):
        assert (await world.client.post("/v1/models", headers=headers, json=body)).status_code in (401, 403)
    assert world.count("model_versions") == 0


async def test_registering_twice_the_same_version_is_409(world: ApiWorld, package_dir: Path) -> None:
    await registered(world, package_dir)
    assert (await register(world, package_dir)).status_code == 409
    assert world.count("model_versions") == 1


# --- feature-dictionary y feature-spec (BR-U4-18, 19) -------------------------------------------------------------------------


async def test_br_u4_19_feature_spec_is_the_verified_file_byte_for_byte_and_only_for_its_identity(
    world: ApiWorld, package_dir: Path
) -> None:
    model_id = await registered(world, package_dir)
    path = f"/v1/models/{model_id}/feature-spec"
    mine = world.service("case-worker", "governance:read-feature-spec")
    other = world.service("explainability-service", "governance:read-dictionary")
    assert (await world.client.get(path, headers=other)).status_code == 403
    assert (await world.client.get(path, headers=world.user("cro"))).status_code == 403
    response = await world.client.get(path, headers=mine)
    assert response.status_code == 200
    assert response.content == (package_dir / "feature_spec.json").read_bytes()  # byte a byte
    assert (await world.client.get("/v1/models/mv-desconocido/feature-spec", headers=mine)).status_code == 404


async def test_br_u4_18_feature_dictionary_is_the_stored_copy_and_only_for_its_identity(
    world: ApiWorld, package_dir: Path
) -> None:
    model_id = await registered(world, package_dir)
    path = f"/v1/models/{model_id}/feature-dictionary"
    assert (await world.client.get(path, headers=world.service("case-worker", "governance:read-feature-spec"))).status_code == 403
    response = await world.client.get(path, headers=world.service("explainability-service", "governance:read-dictionary"))
    assert response.status_code == 200
    assert response.content == (package_dir / "feature_dictionary.json").read_bytes()


# --- Validacion (BR-U4-05, 07) -------------------------------------------------------------------------------------------------


async def test_br_u4_05_validation_creates_the_job_in_staging_with_ttl_deadline_and_no_retries(
    world: ApiWorld, package_dir: Path
) -> None:
    model_id = await registered(world, package_dir)
    response = await world.client.post(f"/v1/models/{model_id}/validations", headers=world.user("ingeniero_riesgo"))
    assert response.status_code == 200, response.text
    run = response.json()
    assert run["mode"] == "validacion" and run["state"] == "lanzado" and run["model_version_id"] == model_id
    # La lectura de vuelta: el manifiesto que recibio el doble de la API de Kubernetes, y su Job por `GET`.
    ((namespace, name), manifest) = next(iter(world.k8s.jobs.items()))
    assert (namespace, name) == ("vectra-staging", run["job_name"]) and manifest["metadata"]["namespace"] == "vectra-staging"
    assert manifest["kind"] == "Job" and manifest["apiVersion"] == "batch/v1"
    spec = manifest["spec"]
    assert (spec["ttlSecondsAfterFinished"], spec["activeDeadlineSeconds"], spec["backoffLimit"]) == (86400, 7200, 0)
    env = {e["name"]: e.get("value") for e in spec["template"]["spec"]["containers"][0]["env"]}
    assert env["VECTRA_JOB_MODE"] == "validacion" and env["VECTRA_RUN_ID"] == run["run_id"]
    assert env["VECTRA_MODEL_VERSION_ID"] == model_id and "VECTRA_SOURCE_ID" not in env
    # La politica activa de la base viaja al Job completa; el Job no lleva el corte como literal.
    active = world.sql("SELECT cutoff, low_confidence_threshold, channel_rules, normative FROM policies WHERE state = 'activa'")[0]
    sent = json.loads(env["VECTRA_POLICY"])
    assert sent["cutoff"] == format(active["cutoff"], ".4f")
    assert sent["low_confidence_threshold"] == format(active["low_confidence_threshold"], ".4f")
    assert sent["channel_rules"] == active["channel_rules"] and len(sent["normative"]) == len(active["normative"])
    assert "VECTRA_CUTOFF" not in env
    assert world.deps.jobs.get(name) == JobInfo()  # existe y no ha fallado
    world.k8s.status[name] = {"conditions": [{"type": "Failed", "status": "True", "reason": "DeadlineExceeded"}]}
    assert world.deps.jobs.get(name) == JobInfo(failed=True, deadline_exceeded=True)
    # Y en la base: la corrida con su plazo de 2 h, la version `en_validacion` y la evidencia.
    row = world.sql("SELECT * FROM validation_runs WHERE model_version_id = %s", model_id)[0]
    assert (row["mode"], row["state"], row["job_name"]) == ("validacion", "lanzado", name)
    assert (row["deadline_at"] - row["started_at"]).total_seconds() == 7200
    assert world.state(model_id) == "en_validacion" and world.chain(model_id) == ["registrado", "validacion_iniciada"]


async def test_without_an_active_policy_the_validation_is_refused_and_nothing_is_launched(
    world: ApiWorld, package_dir: Path
) -> None:
    response = await register(world, package_dir)
    model_id = version_of(package_dir)
    assert response.status_code == 200
    refused = await world.client.post(f"/v1/models/{model_id}/validations", headers=world.user("ingeniero_riesgo"))
    assert refused.status_code == 409 and refused.json()["code"] == "conflict_state"
    assert world.k8s.jobs == {} and world.count("validation_runs") == 0 and world.state(model_id) == "registrado"
    with_active_policy(world.svc)
    assert (await world.client.post(f"/v1/models/{model_id}/validations", headers=world.user("ingeniero_riesgo"))).status_code == 200


async def test_validation_needs_the_engineer_with_mfa_and_the_right_state(world: ApiWorld, package_dir: Path) -> None:
    model_id = await registered(world, package_dir)
    path = f"/v1/models/{model_id}/validations"
    assert (await world.client.post(path, headers=world.user("cro"))).status_code == 403
    assert (await world.client.post(path, headers=world.user("ingeniero_riesgo", mfa=False))).status_code in (401, 403)
    assert world.k8s.jobs == {}
    assert (await world.client.post(path, headers=world.user("ingeniero_riesgo"))).status_code == 200
    again = await world.client.post(path, headers=world.user("ingeniero_riesgo"))
    assert again.status_code == 409 and again.json()["code"] == "conflict_state"
    assert len(world.k8s.jobs) == 1
    assert (await world.client.post("/v1/models/mv-no/validations", headers=world.user("ingeniero_riesgo"))).status_code == 404


async def test_if_kubernetes_refuses_the_job_the_validation_fails_closed_with_503(world: ApiWorld, package_dir: Path) -> None:
    model_id = await registered(world, package_dir)
    world.k8s.fail_create = True
    response = await world.client.post(f"/v1/models/{model_id}/validations", headers=world.user("ingeniero_riesgo"))
    assert response.status_code == 503
    assert world.state(model_id) == "validacion_fallida"
    assert world.sql("SELECT state FROM validation_runs WHERE model_version_id = %s", model_id) == [{"state": "fallido"}]
    world.k8s.fail_create = False  # el ingeniero reintenta (`validacion_fallida -> en_validacion`)
    retry = await world.client.post(f"/v1/models/{model_id}/validations", headers=world.user("ingeniero_riesgo"))
    assert retry.status_code == 200 and world.state(model_id) == "en_validacion"


async def test_us_202_the_report_moves_the_version_and_only_the_sync_check_blocks(world: ApiWorld, package_dir: Path) -> None:
    model_id = await registered(world, package_dir)
    run = (await world.client.post(f"/v1/models/{model_id}/validations", headers=world.user("ingeniero_riesgo"))).json()
    path = f"/v1/models/{model_id}/validation-report"
    job = world.service("model-validation-job", "governance:validation-report")
    body = report(True).model_dump(mode="json")
    assert (await world.client.put(path, headers=world.service("someone", "governance:read-serving"), json=body)).status_code == 403
    response = await world.client.put(path, headers=job, json=body)
    assert response.status_code == 204, response.text
    assert world.state(model_id) == "lista_para_aprobacion"
    row = world.sql("SELECT state, report FROM validation_runs WHERE run_id = %s", run["run_id"])[0]
    assert row["state"] == "informe_recibido" and row["report"]["sync_check"]["passed"] is True
    assert world.chain(model_id)[-1] == "informe_validacion"
    assert (await world.client.put(path, headers=job, json=body)).status_code == 409  # ya no hay corrida `lanzado`
    detail = await world.client.get(f"/v1/models/{model_id}", headers=world.user("cro"))
    assert detail.json()["validation_report"]["sync_check"]["passed"] is True


async def test_us_202_a_failed_sync_check_leaves_validacion_fallida_but_the_auc_does_not_block(
    world: ApiWorld, package_dir: Path
) -> None:
    model_id = await registered(world, package_dir)
    await world.client.post(f"/v1/models/{model_id}/validations", headers=world.user("ingeniero_riesgo"))
    job = world.service("model-validation-job", "governance:validation-report")
    path = f"/v1/models/{model_id}/validation-report"
    assert (await world.client.put(path, headers=job, json=report(False).model_dump(mode="json"))).status_code == 204
    assert world.state(model_id) == "validacion_fallida" and world.chain(model_id)[-1] == "validacion_fallida"
    # AUC por debajo del objetivo, con la sincronia buena: no bloquea (BR-U4-07).
    await world.client.post(f"/v1/models/{model_id}/validations", headers=world.user("ingeniero_riesgo"))
    low = report(True).model_dump(mode="json") | {"auc_roc": "0.5000", "auc_meets_target": False}
    assert (await world.client.put(path, headers=job, json=low)).status_code == 204
    assert world.state(model_id) == "lista_para_aprobacion"


# --- Aprobacion, activacion, retiro (BR-U4-01, 08, 10) ---------------------------------------------------------------------------


def ready(world: ApiWorld, model_id: str) -> None:
    """Una version `lista_para_aprobacion` registrada por `ing-1`."""
    from evidence_support import ING, VALIDATION_JOB, new_model

    world.svc.register(ING, new_model(model_id))
    world.svc.start_validation(ING, model_id, job_name=f"job-{model_id}")
    run_id = str(world.sql("SELECT run_id FROM validation_runs WHERE model_version_id = %s", model_id)[0]["run_id"])
    world.svc.receive_report(VALIDATION_JOB, model_id, run_id, report(True))


async def test_us_203_the_cro_approves_and_the_engineer_cannot(world: ApiWorld) -> None:
    ready(world, "mv-2026-01-01-aaaaaaaa")
    path = "/v1/models/mv-2026-01-01-aaaaaaaa/approval"
    assert (await world.client.post(path, headers=world.user("ingeniero_riesgo"), json={"decision": "aprobado"})).status_code == 403
    assert world.state("mv-2026-01-01-aaaaaaaa") == "lista_para_aprobacion"
    response = await world.client.post(path, headers=world.user("cro", "cro-1"), json={"decision": "aprobado"})
    assert response.status_code == 204, response.text  # el contrato de U0: sin cuerpo
    row = world.sql("SELECT state, approved_by FROM model_versions")[0]
    assert (row["state"], row["approved_by"]) == ("aprobado", "cro-1")
    assert world.chain("mv-2026-01-01-aaaaaaaa")[-1] == "aprobado"


async def test_br_u4_10_the_cro_who_registered_cannot_approve_and_rejecting_needs_a_justification(world: ApiWorld) -> None:
    from evidence_support import ING, VALIDATION_JOB, new_model

    model_id = "mv-2026-01-01-bbbbbbbb"
    world.svc.register(ING.__class__("user", "cro-1", ING.role, "mfa"), new_model(model_id))  # registrada por la misma persona
    world.svc.start_validation(ING, model_id, job_name="j")
    run_id = str(world.sql("SELECT run_id FROM validation_runs")[0]["run_id"])
    world.svc.receive_report(VALIDATION_JOB, model_id, run_id, report(True))
    path = f"/v1/models/{model_id}/approval"
    assert (await world.client.post(path, headers=world.user("cro", "cro-1"), json={"decision": "aprobado"})).status_code == 409
    assert world.state(model_id) == "lista_para_aprobacion"
    assert (await world.client.post(path, headers=world.user("cro", "cro-2"), json={"decision": "rechazado"})).status_code == 422
    reject = await world.client.post(
        path, headers=world.user("cro", "cro-2"), json={"decision": "rechazado", "justification": "AUC insuficiente"}
    )
    assert reject.status_code == 204 and world.state(model_id) == "rechazado"
    assert world.sql("SELECT justification FROM transitions WHERE to_state = 'rechazado'") == [{"justification": "AUC insuficiente"}]


async def test_us_208_activation_swaps_the_versions_in_one_unit_and_recomputes_serving_config(world: ApiWorld) -> None:
    with_active_policy(world.svc)
    to_activo(world.svc, "mv-2026-01-01-aaaaaaaa")
    to_aprobado(world.svc, "mv-2026-02-01-bbbbbbbb")
    world.refresh()
    before = world.cache.current().etag
    path = "/v1/models/mv-2026-02-01-bbbbbbbb/activation"
    engineer = world.user("ingeniero_riesgo", scope=PROMOTION)
    assert (await world.client.post(path, headers=world.user("ingeniero_riesgo"), json={"evidence": "PR #1"})).status_code == 403
    assert (await world.client.post(path, headers=world.user("cro", scope=PROMOTION), json={"evidence": "PR #1"})).status_code == 403
    response = await world.client.post(path, headers=engineer, json={"evidence": "PR #1"})
    assert response.status_code == 204, response.text
    states = {r["model_version_id"]: r["state"] for r in world.sql("SELECT model_version_id, state FROM model_versions")}
    assert states == {"mv-2026-01-01-aaaaaaaa": "inactivo", "mv-2026-02-01-bbbbbbbb": "activo"}
    units = world.sql("SELECT unit_id FROM transitions WHERE to_state IN ('activo', 'inactivo') AND status = 'confirmada' AND from_state <> 'inactivo'")
    assert len({u["unit_id"] for u in units if u["unit_id"]}) == 1
    sc = world.sql("SELECT model_version_id, inference_service, etag FROM serving_config")[0]
    assert sc["model_version_id"] == "mv-2026-02-01-bbbbbbbb" and sc["etag"] != before
    activated = [w for w in world.registry.events("mv-2026-02-01-bbbbbbbb") if w.entry["payload"].get("event") == "activado"]
    assert activated[0].entry["payload"]["details"]["evidence"] == "PR #1"
    assert world.chain("mv-2026-01-01-aaaaaaaa")[-1] == "inactivado"


async def test_us_305_nobody_but_compliance_with_fresh_mfa_leaves_congelado(world: ApiWorld) -> None:
    """BR-U4-03: un CRO, un job o un webhook intentan reactivar -> denegado; cumplimiento con MFA y step-up, si."""
    from evidence_support import BIAS, freeze_context

    with_active_policy(world.svc)
    to_activo(world.svc, "mv-2026-01-01-aaaaaaaa")
    world.svc.freeze(BIAS, "mv-2026-01-01-aaaaaaaa", freeze_context("mv-2026-01-01-aaaaaaaa"))
    path = "/v1/models/mv-2026-01-01-aaaaaaaa/frozen-resolution"
    body = {"action": "reactivar", "justification": "causa raiz corregida"}
    attempts = {
        "cro": world.user("cro"),
        "ingeniero": world.user("ingeniero_riesgo"),
        "job de bias": world.service("bias-monitoring-job", "governance:freeze"),
        "job de validacion": world.service("model-validation-job", "governance:validation-report"),
        "webhook sin rol ni scope": world.service("webhook"),
        "cumplimiento sin MFA": world.user("cumplimiento", mfa=False),
        "cumplimiento con step-up vencido (16 min)": world.user("cumplimiento", age=16 * 60),
    }
    for who, headers in attempts.items():
        response = await world.client.post(path, headers=headers, json=body)
        assert response.status_code in (401, 403), (who, response.status_code)
        assert world.state("mv-2026-01-01-aaaaaaaa") == "congelado", who
    response = await world.client.post(path, headers=world.user("cumplimiento", age=14 * 60), json=body)
    assert response.status_code == 204, response.text
    assert world.state("mv-2026-01-01-aaaaaaaa") == "activo"
    assert world.chain("mv-2026-01-01-aaaaaaaa")[-2:] == ["freeze", "frozen_resolution"]
    # `descartar` sale a `retirado`; el justificante no puede faltar.
    assert (await world.client.post(path, headers=world.user("cumplimiento"), json={"action": "descartar"})).status_code == 422


async def test_br_u4_03_investigar_keeps_the_version_congelado_and_marks_it(world: ApiWorld) -> None:
    from evidence_support import BIAS, freeze_context

    with_active_policy(world.svc)
    to_activo(world.svc, "mv-2026-01-01-aaaaaaaa")
    world.svc.freeze(BIAS, "mv-2026-01-01-aaaaaaaa", freeze_context("mv-2026-01-01-aaaaaaaa"))
    response = await world.client.post(
        "/v1/models/mv-2026-01-01-aaaaaaaa/frozen-resolution",
        headers=world.user("cumplimiento"),
        json={"action": "investigar", "justification": "se abre una investigacion"},
    )
    assert response.status_code == 204
    row = world.sql("SELECT state, investigation FROM model_versions")[0]
    assert (row["state"], row["investigation"]) == ("congelado", True)


async def test_retirement_is_for_the_cro_and_only_from_a_state_that_allows_it(world: ApiWorld) -> None:
    ready(world, "mv-2026-01-01-aaaaaaaa")
    path = "/v1/models/mv-2026-01-01-aaaaaaaa/retirement"
    assert (await world.client.post(path, headers=world.user("cro"))).status_code == 409  # `lista_para_aprobacion` no se retira
    await world.client.post(
        "/v1/models/mv-2026-01-01-aaaaaaaa/approval",
        headers=world.user("cro"),
        json={"decision": "rechazado", "justification": "no cumple"},
    )
    assert (await world.client.post(path, headers=world.user("ingeniero_riesgo"))).status_code == 403
    response = await world.client.post(path, headers=world.user("cro"))
    assert response.status_code == 200 and response.json()["state"] == "retirado"
    assert world.state("mv-2026-01-01-aaaaaaaa") == "retirado" and world.chain("mv-2026-01-01-aaaaaaaa")[-1] == "retirado"
    assert (await world.client.post("/v1/models/mv-nope/retirement", headers=world.user("cro"))).status_code == 404


# --- Listas y serving-config ----------------------------------------------------------------------------------------------------


async def test_the_servable_version_is_one_and_follows_the_freeze(world: ApiWorld) -> None:
    from evidence_support import BIAS, freeze_context

    with_active_policy(world.svc)
    to_activo(world.svc, "mv-2026-01-01-aaaaaaaa")
    ready(world, "mv-2026-02-01-bbbbbbbb")
    path = "/v1/models?state=activo,congelado"
    for role in ("cro", "cumplimiento"):
        response = await world.client.get(path, headers=world.user(role))
        assert response.status_code == 200
        assert [(m["model_version_id"], m["state"]) for m in response.json()["items"]] == [("mv-2026-01-01-aaaaaaaa", "activo")]
    world.svc.freeze(BIAS, "mv-2026-01-01-aaaaaaaa", freeze_context("mv-2026-01-01-aaaaaaaa"))
    items = (await world.client.get(path, headers=world.user("cro"))).json()["items"]
    assert [(m["model_version_id"], m["state"]) for m in items] == [("mv-2026-01-01-aaaaaaaa", "congelado")]
    assert (await world.client.get(path, headers=world.user("analista"))).status_code == 403
    everything = (await world.client.get("/v1/models", headers=world.user("ingeniero_riesgo"))).json()
    assert everything["total"] == 2 and (await world.client.get("/v1/models?state=nope", headers=world.user("cro"))).status_code == 422


async def test_serving_config_answers_304_with_the_current_etag_and_changes_after_a_freeze(world: ApiWorld) -> None:
    from evidence_support import BIAS, freeze_context

    with_active_policy(world.svc)
    to_activo(world.svc, "mv-2026-01-01-aaaaaaaa")
    world.refresh()
    headers = world.service("scoring-service", "governance:read-serving")
    first = await world.client.get("/v1/serving-config", headers=headers)
    assert first.status_code == 200 and first.json()["state"] == "activo"
    etag = first.headers["etag"]
    assert etag.strip('"') == first.json()["etag"] == world.sql("SELECT etag FROM serving_config")[0]["etag"]
    assert (await world.client.get("/v1/serving-config", headers={**headers, "If-None-Match": etag})).status_code == 304
    assert (await world.client.get("/v1/serving-config", headers={**headers, "If-None-Match": '"otro"'})).status_code == 200
    assert (await world.client.get("/v1/serving-config", headers=world.user("cro"))).status_code == 403
    world.svc.freeze(BIAS, "mv-2026-01-01-aaaaaaaa", freeze_context("mv-2026-01-01-aaaaaaaa"))
    world.refresh()
    stale = await world.client.get("/v1/serving-config", headers={**headers, "If-None-Match": etag})
    assert stale.status_code == 200 and stale.json()["state"] == "congelado"


async def test_serving_config_is_503_while_the_copy_is_not_loaded(world: ApiWorld) -> None:
    response = await world.client.get("/v1/serving-config", headers=world.service("scoring-service", "governance:read-serving"))
    assert response.status_code == 503
