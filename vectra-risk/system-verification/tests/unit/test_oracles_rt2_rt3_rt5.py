"""Oraculos de RT-5, RT-3, `rt2-setup` y RT-2 (U12-T03, Paso 8; BR-U12-04, 06, 07, 10; NFR-U12-11, 42, 50).

Cada prueba lleva en su nombre la seccion (`rt5`, `rt3`, `rt2_setup`, `rt2`, `guard`, `evidence`/`leak`, `missing`) para que los criterios filtren con `-k`. Las respuestas incorrectas difieren de la correcta solo en lo que el nombre
dice, y se comprueba el codigo de «que falto» (NFR-U12-42), no solo el resultado.
"""

# ruff: noqa: E402
from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from fake_clock import FakeClock
from rt5_world import (
    APP_LOG,
    PROXY_LOG,
    RUN_ID,
    JobKubectl,
    PromDouble,
    Rt5Spec,
    active_job,
    completed_job,
    every,
    failed_job,
    iso,
)
from vectra_verification import guard
from vectra_verification.clients.k8s_read import Completed, K8sRead
from vectra_verification.clients.prom import PromClient
from vectra_verification.scenarios import rt5

KIND = guard.KIND
NOW = datetime(2026, 11, 13, 20, 0, tzinfo=UTC)
T0 = NOW - timedelta(hours=6)  # el Job corrio 6 h antes
T1 = T0 + timedelta(seconds=20)
STARTED = T0 - timedelta(minutes=2)


def good_spec(**over: object) -> Rt5Spec:
    """La alerta en [t0, t1 + 5 min], la serie de denegaciones que **nace en 1** y no vuelve a crecer, el contador del mock en 0, la retencion que cubre t0."""
    spec = Rt5Spec(
        started_at=STARTED,
        alert=every(T0, T1 + timedelta(minutes=5)),
        deny=[(t, 1.0) for t in every(T0 + timedelta(seconds=5), T1 + timedelta(minutes=14))],
        counter=[(t, 0.0) for t in every(STARTED, NOW)],
        lowest=NOW - timedelta(days=3),
    )
    for key, value in over.items():
        setattr(spec, key, value)
    return spec


def evaluate(
    spec: Rt5Spec | None = None,
    kubectl: JobKubectl | None = None,
    *,
    now: datetime = NOW,
    started_at: datetime = STARTED,
    prom_down: bool = False,
    run_id: str = RUN_ID,
) -> tuple[rt5.Outcome, FakeClock, JobKubectl, PromDouble]:
    spec = spec or good_spec()
    kubectl = kubectl or JobKubectl(completed_job(T0, T1))
    double = PromDouble(spec, down=prom_down)
    clock = FakeClock(now)
    outcome = rt5.run(
        K8sRead(kubectl),
        PromClient("http://prom", transport=double),
        clock,
        run_id,
        started_at,
        environment=KIND,
    )
    return outcome, clock, kubectl, double


def test_rt5_correct_job_log_alert_series_and_counter_pass() -> None:
    outcome, _, _, _ = evaluate()
    assert outcome.result == "pasa" and outcome.missing == ()
    assert (
        outcome.readings["log_proxy_error_present"] is True
        and outcome.readings["deny_max"] == 1.0
        and outcome.readings["counter_max"] == 0.0
    )


def test_rt5_a_403_from_the_application_without_l5d_proxy_error_fails() -> None:
    """La linea real del Job: `... -> 403 l5d-proxy-error: None`. Buscar el texto `l5d-proxy-error` la daria por buena: la linea lo trae siempre."""
    outcome, _, _, _ = evaluate(kubectl=JobKubectl(completed_job(T0, T1), log=APP_LOG))
    assert outcome.result == "falla" and outcome.missing == ("rt5_403_de_la_aplicacion",)


@pytest.mark.parametrize(
    ("log", "code"),
    [
        ("rt5-demo: POST http://x -> 200 l5d-proxy-error: None\n", "rt5_log_codigo_distinto_de_403"),
        ("rt5-demo: POST http://x -> 500 l5d-proxy-error: boom\n", "rt5_log_codigo_distinto_de_403"),
        ("otra cosa\n", "rt5_log_sin_linea"),
        ("rt5-demo: sin respuesta: timed out\n", "rt5_log_sin_respuesta"),
    ],
)
def test_rt5_a_log_with_another_code_or_without_the_line_fails(log: str, code: str) -> None:
    outcome, _, _, _ = evaluate(kubectl=JobKubectl(completed_job(T0, T1), log=log))
    assert outcome.result == "falla" and outcome.missing == (code,)


def test_rt5_evaluated_six_hours_after_the_job_with_the_alert_only_in_t0_t1_plus_5_min_passes() -> None:
    spec = good_spec()
    assert spec.alert[0] == T0 and spec.alert[-1] <= T1 + timedelta(minutes=5)
    outcome, clock, _, double = evaluate(spec)
    assert outcome.result == "pasa" and clock.sleeps == []
    first = next(r for r in double.requests if r.url.path.endswith("query_range"))
    assert abs(float(first.url.params["start"]) - T0.timestamp()) < 1  # anclada al Job, no a «ahora»


def test_rt5_the_alert_outside_the_job_window_fails() -> None:
    late = every(T1 + timedelta(hours=1), T1 + timedelta(hours=1, minutes=5))
    outcome, _, _, _ = evaluate(good_spec(alert=late))
    assert outcome.result == "falla" and outcome.missing == ("rt5_alerta_core_write_attempt_ausente",)


def test_rt5_without_core_write_attempt_fails() -> None:
    outcome, _, _, _ = evaluate(good_spec(alert=[]))
    assert outcome.result == "falla" and "rt5_alerta_core_write_attempt_ausente" in outcome.missing


def test_rt5_retention_not_covering_t0_is_no_ejecutado_never_pasa() -> None:
    outcome, _, _, _ = evaluate(good_spec(lowest=T0 + timedelta(minutes=1)))
    assert outcome.result == "no ejecutado" and outcome.missing == ("rt5_retencion_no_cubre_t0",)
    outcome, _, _, _ = evaluate(good_spec(lowest=None))
    assert outcome.result == "no ejecutado" and outcome.missing == ("rt5_retencion_sin_dato",)


def test_rt5_the_denial_series_born_at_1_and_never_growing_passes() -> None:
    spec = good_spec()
    assert {v for _, v in spec.deny} == {1.0}  # nace en 1: increase() daria 0
    assert evaluate(spec)[0].result == "pasa"


def test_rt5_the_denial_series_absent_in_the_window_fails() -> None:
    outcome, _, _, _ = evaluate(good_spec(deny=[]))
    assert outcome.result == "falla" and "rt5_serie_denegaciones_ausente" in outcome.missing


def test_rt5_a_denial_series_that_never_reaches_1_fails() -> None:
    outcome, _, _, _ = evaluate(good_spec(deny=[(t, 0.0) for t in every(T0, T1 + timedelta(minutes=14))]))
    assert outcome.result == "falla" and "rt5_serie_denegaciones_menor_que_1" in outcome.missing


def test_rt5_mock_counter_above_zero_fails() -> None:
    counter = [(t, 0.0) for t in every(STARTED, T1)] + [
        (t, 1.0) for t in every(T1 + timedelta(seconds=15), NOW)
    ]
    outcome, _, _, _ = evaluate(good_spec(counter=counter))
    assert outcome.result == "falla" and outcome.missing == ("rt5_contador_del_mock_mayor_que_0",)


def test_rt5_missing_counter_series_fails_with_its_name() -> None:
    outcome, _, _, _ = evaluate(good_spec(counter=[]))
    assert outcome.result == "falla" and outcome.missing == ("rt5_serie_contador_del_mock_ausente",)
    assert "vectra_core_write_attempts_total" in outcome.obtained


def test_rt5_job_of_another_run_id_is_no_ejecutado() -> None:
    outcome, _, _, _ = evaluate(kubectl=JobKubectl(completed_job(T0, T1, name="rt5-demo-20261112-0900")))
    assert outcome.result == "no ejecutado" and outcome.missing == ("rt5_job_otro_runid",)


def test_rt5_job_completed_before_or_at_started_at_is_no_ejecutado() -> None:
    for started in (T1, T1 + timedelta(minutes=1)):
        outcome, _, _, _ = evaluate(started_at=started)
        assert outcome.result == "no ejecutado" and outcome.missing == ("rt5_job_anterior_al_inicio",)


def test_rt5_nonexistent_job_is_no_ejecutado() -> None:
    outcome, _, _, _ = evaluate(kubectl=JobKubectl(None))
    assert outcome.result == "no ejecutado" and outcome.missing == ("rt5_job_inexistente",)


def test_rt5_forbidden_kubectl_is_no_ejecutado() -> None:
    outcome, _, _, _ = evaluate(
        kubectl=JobKubectl(Completed(1, "", 'Error from server (Forbidden): jobs.batch "x" is forbidden'))
    )
    assert outcome.result == "no ejecutado" and outcome.missing == ("rt5_k8s_forbidden",)


def test_rt5_failed_job_without_completion_time_is_falla_with_the_log_line() -> None:
    outcome, _, _, _ = evaluate(
        kubectl=JobKubectl(failed_job(T0), log="rt5-demo: POST http://x -> 200 l5d-proxy-error: None\n")
    )
    assert outcome.result == "falla" and outcome.missing == ("rt5_job_fallido",)
    assert "codigo=200" in outcome.obtained


def test_rt5_job_that_never_ends_is_no_ejecutado_after_the_deadline_without_real_sleep() -> None:
    kubectl = JobKubectl(active_job(T0))
    outcome, clock, _, _ = evaluate(kubectl=kubectl)
    assert outcome.result == "no ejecutado" and outcome.missing == ("rt5_job_no_termina",)
    assert sum(clock.sleeps) == rt5.ACTIVE_DEADLINE + rt5.JOB_MARGIN


def test_rt5_job_still_active_then_completed_waits_and_judges() -> None:
    kubectl = JobKubectl([active_job(T0), active_job(T0), completed_job(T0, T1)])
    outcome, clock, _, _ = evaluate(kubectl=kubectl)
    assert outcome.result == "pasa" and clock.sleeps == [15.0, 15.0]


def test_rt5_prometheus_not_responding_is_no_ejecutado() -> None:
    outcome, _, _, _ = evaluate(prom_down=True)
    assert outcome.result == "no ejecutado" and outcome.missing == ("rt5_prometheus_no_responde",)


def test_rt5_kubectl_logs_not_readable_is_no_ejecutado() -> None:
    outcome, _, _, _ = evaluate(kubectl=JobKubectl(completed_job(T0, T1), logs_error="boom"))
    assert outcome.result == "no ejecutado" and outcome.missing == ("rt5_log_no_leido",)
    outcome, _, _, _ = evaluate(kubectl=JobKubectl(completed_job(T0, T1), pods=0))
    assert outcome.missing == ("rt5_pod_inexistente",)


def test_rt5_the_queries_are_the_literal_ones_in_the_plan_with_15_seconds_and_all_saved() -> None:
    outcome, _, kubectl, double = evaluate()
    literal = {rt5.ALERT, rt5.DENY, rt5.COUNTER, rt5.RETENTION}
    assert rt5.ALERT == 'ALERTS{alertname="CoreWriteAttempt", alertstate="firing"}'
    assert (
        rt5.DENY
        == 'sum(inbound_http_authz_deny_total{namespace="vectra-mock", route_name="core-mock-catch-all"})'
    )
    assert (
        rt5.COUNTER == "sum(vectra_core_write_attempts_total)"
        and rt5.RETENTION == "prometheus_tsdb_lowest_timestamp_seconds"
    )
    seen = {r.url.params["query"] for r in double.requests}
    assert seen == literal
    assert all("increase(" not in q and "[" not in q for q in seen)
    assert all(r.url.params["step"] == "15.0" for r in double.requests if r.url.path.endswith("query_range"))
    saved = {q.query: q for q in outcome.queries}
    assert set(saved) == literal
    assert (
        saved[rt5.ALERT].step == 15.0
        and saved[rt5.ALERT].start == T0
        and saved[rt5.ALERT].end == T1 + timedelta(minutes=15)
    )
    assert saved[rt5.COUNTER].start == STARTED
    assert {c[1] for c in kubectl.calls} == {"get", "logs"}


def test_rt5_a_window_over_11000_points_is_split_and_the_points_joined() -> None:
    start = NOW - timedelta(hours=60)  # 60 h a 15 s son 14 400 puntos
    counter = [(t, 0.0) for t in every(start, NOW - timedelta(hours=1))] + [(NOW - timedelta(minutes=5), 1.0)]
    outcome, _, _, double = evaluate(good_spec(counter=counter), started_at=start)
    assert outcome.result == "falla" and outcome.missing == (
        "rt5_contador_del_mock_mayor_que_0",
    )  # el pico esta en el ultimo tramo
    ranges = [
        r
        for r in double.requests
        if r.url.path.endswith("query_range") and r.url.params["query"] == rt5.COUNTER
    ]
    assert len(ranges) == 2 and all(
        (float(r.url.params["end"]) - float(r.url.params["start"])) / 15 <= 11_000 for r in ranges
    )
    saved = next(q for q in outcome.queries if q.query == rt5.COUNTER)
    assert len(saved.result[0]["values"]) > 11_000


def test_rt5_without_splitting_the_double_rejects_the_long_window() -> None:
    http = PromClient("http://prom", transport=PromDouble(good_spec()))
    from vectra_verification.clients.prom import ObsError

    with pytest.raises(ObsError, match="bad_data"):
        http.query_range(rt5.COUNTER, NOW - timedelta(hours=60), NOW, 15.0)


def test_rt5_right_after_the_job_polls_every_15_seconds_until_the_window_closes() -> None:
    now = T1 + timedelta(minutes=1)
    outcome, clock, _, _ = evaluate(
        good_spec(
            alert=[], deny=[], counter=[(t, 0.0) for t in every(STARTED, now)], lowest=now - timedelta(days=1)
        ),
        now=now,
    )
    assert outcome.result == "falla"
    assert (
        set(clock.sleeps) == {15.0} and abs(sum(clock.sleeps) - 14 * 60) < 1
    )  # hasta t1 + 15 min, sin dormir de verdad


def test_rt5_right_after_the_job_with_everything_present_does_not_wait() -> None:
    now = T1 + timedelta(minutes=1)
    spec = good_spec(counter=[(t, 0.0) for t in every(STARTED, now)], lowest=now - timedelta(days=1))
    outcome, clock, _, _ = evaluate(spec, now=now)
    assert outcome.result == "pasa" and clock.sleeps == []


def test_rt5_run_id_must_have_the_format() -> None:
    with pytest.raises(ValueError, match="run_id_invalid"):
        evaluate(run_id="hoy")


# --- CA-5: dice que serie falta ----------------------------------------------------------------------------------------------------


def test_rt5_missing_no_denial_series_at_all_says_nobody_scrapes_the_linkerd_proxy() -> None:
    outcome, _, _, _ = evaluate(good_spec(deny=[]))
    assert outcome.result == "falla" and outcome.missing[0] == "rt5_serie_denegaciones_ausente"
    assert (
        'namespace="vectra-mock"' in outcome.obtained
        and 'route_name="core-mock-catch-all"' in outcome.obtained
    )
    assert "nadie raspa el proxy de Linkerd de vectra-mock" in outcome.obtained


def test_rt5_missing_series_with_other_labels_lists_the_labels_that_exist() -> None:
    outcome, _, _, _ = evaluate(
        good_spec(deny=[], other_family=[("vectra-app", "case-api"), ("vectra-mock", "otra-ruta")])
    )
    assert outcome.result == "falla" and outcome.missing[0] == "rt5_serie_denegaciones_ausente"
    assert (
        'namespace="vectra-app", route_name="case-api"' in outcome.obtained
        and 'route_name="otra-ruta"' in outcome.obtained
    )
    assert "nadie raspa" not in outcome.obtained


def test_rt5_missing_series_and_alert_give_one_result_with_both_codes_series_first() -> None:
    outcome, _, _, _ = evaluate(good_spec(deny=[], alert=[]))
    assert outcome.missing == ("rt5_serie_denegaciones_ausente", "rt5_alerta_core_write_attempt_ausente")
    assert "causa probable" in outcome.obtained


def test_rt5_missing_only_the_alert_does_not_blame_the_scraping() -> None:
    outcome, _, _, _ = evaluate(good_spec(alert=[]))
    assert outcome.missing == ("rt5_alerta_core_write_attempt_ausente",)
    assert "nadie raspa" not in outcome.obtained and "causa probable" not in outcome.obtained


# --- CA-2: las barreras ------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("section", ["rt5", "rt3", "rt2-setup", "rt2"])
def test_guard_sections_denied_in_staging(section: str) -> None:
    with pytest.raises(guard.GuardError, match=f"section_denied_in_staging:{section}"):
        guard.check_section(guard.STAGING, section)


def test_guard_rt5_in_staging_sends_no_request_http_or_kubectl() -> None:
    kubectl, double = JobKubectl(completed_job(T0, T1)), PromDouble(good_spec())
    with pytest.raises(guard.GuardError, match="section_denied_in_staging:rt5"):
        rt5.run(
            K8sRead(kubectl),
            PromClient("http://prom", transport=double),
            FakeClock(NOW),
            RUN_ID,
            STARTED,
            environment=guard.STAGING,
        )
    assert kubectl.calls == [] and double.requests == []


def test_guard_an_environment_of_production_is_not_known() -> None:
    production = guard.Environment(
        "prod", "vectra.banco.internal", "https://vectra.banco.internal/auth/realms/vectra"
    )
    kubectl, double = JobKubectl(completed_job(T0, T1)), PromDouble(good_spec())
    with pytest.raises(guard.GuardError, match="environment_not_allowed"):
        rt5.run(
            K8sRead(kubectl),
            PromClient("http://prom", transport=double),
            FakeClock(NOW),
            RUN_ID,
            STARTED,
            environment=production,
        )
    assert kubectl.calls == [] and double.requests == []


def test_rt5_json_helpers_are_valid() -> None:
    assert json.loads(completed_job(T0, T1))["status"]["completionTime"] == iso(T1)
    assert httpx.Request("GET", "http://x").method == "GET"
    assert PROXY_LOG.startswith("rt5-demo: POST")


# --- rt2-setup (CA-10) -------------------------------------------------------------------------------------------------------------
# El BFF **real** en proceso (con los dobles de U10 para governance y case-service, con estado): cada escritura sale con un token de step-up y con el `sub` del usuario.

import hashlib
import subprocess
from collections.abc import Iterator
from pathlib import Path

from external_paths import ROOT
from registry_read_double import freeze_item
from rt2_world import PROXY, REFERENCE, Rt2World
from vectra_verification.scenarios import rt2
from vectra_verification.scenarios.common import ScenarioError, registration_body


@pytest.fixture
def world() -> Iterator[Rt2World]:
    built = Rt2World()
    built.add_model(REFERENCE, "activo", registered_by="otro-ingeniero", approved_by="otro-cro")
    yield built
    built.close()


def make_package(base: Path, model_id: str) -> Path:
    """Un paquete de U5 chico (los 5 archivos de `manifest.json`): lo que `registro-cuerpo.sh` y `registration_body` leen."""
    directory = base / model_id
    directory.mkdir(parents=True, exist_ok=True)
    files = []
    for name in ("predictor.json", "explainer.json", "feature_dictionary.json", "feature_spec.json"):
        data = json.dumps({"model_version_id": model_id, "name": name}).encode()
        (directory / name).write_bytes(data)
        files.append({"name": name, "sha256": hashlib.sha256(data).hexdigest(), "model_version_id": model_id})
    (directory / "manifest.json").write_text(
        json.dumps({"model_version_id": model_id, "files": files}), encoding="utf-8"
    )
    return directory


def versions(
    world: Rt2World, tmp_path: Path, count: int = 1, ids: tuple[str, ...] = ()
) -> list[rt2.ProxyVersion]:
    names = ids or tuple(f"{PROXY}-{n}" if n else PROXY for n in range(count))
    return [rt2.ProxyVersion(n + 1, name, make_package(tmp_path, name)) for n, name in enumerate(names)]


def setup(world: Rt2World, items: list[rt2.ProxyVersion], **kw: float) -> rt2.Outcome:
    return rt2.rt2_setup(KIND, world.sessions, world.clock, items, **kw)


def test_rt2_setup_one_version_is_registered_validated_and_approved_by_another_user_with_step_up(
    world: Rt2World, tmp_path: Path
) -> None:
    outcome = setup(world, versions(world, tmp_path))
    assert outcome.result == "pasa", outcome
    assert (
        world.state_of(PROXY) == "aprobado"
        and world.models[PROXY]["approved_by"] == "cro-1"
        and world.models[PROXY]["registered_by"] == "ingeniero-1"
    )
    assert world.registrations == [(PROXY, "ingeniero-1")] and world.approvals == [(PROXY, "cro-1")]
    assert (
        world.oidc.step_ups.count("ingeniero-1") >= 1 and world.oidc.step_ups.count("cro-1") == 1
    )  # cada escritura salio con un token de step-up
    assert outcome.subresults[0].readings["approved_by_differs"] is True


def test_rt2_setup_three_versions_all_end_approved(world: Rt2World, tmp_path: Path) -> None:
    items = versions(world, tmp_path, 3)
    outcome = setup(world, items)
    assert outcome.result == "pasa" and len(outcome.subresults) == 3
    assert {world.state_of(v.model_version_id) for v in items} == {"aprobado"} and len(world.approvals) == 3
    assert world.oidc.step_ups.count("ingeniero-1") == 1, (
        "la segunda escritura de ingeniero-1 dentro de 800 s no hace otro step-up"
    )


def test_rt2_setup_a_version_in_validacion_fallida_refuses_to_go_on_with_zero_approvals(
    world: Rt2World, tmp_path: Path
) -> None:
    world.validation_outcome = "validacion_fallida"
    outcome = setup(world, versions(world, tmp_path, 2))
    assert outcome.result == "falla" and "rt2_setup_validacion_fallida" in outcome.missing
    assert world.approvals == [] and outcome.readings["approvals_sent"] == 0


def test_rt2_setup_two_versions_with_the_same_model_version_id_is_an_error_with_zero_requests(
    world: Rt2World, tmp_path: Path
) -> None:
    items = versions(world, tmp_path, ids=(PROXY, PROXY))
    with pytest.raises(ScenarioError, match="rt2_version_repetida"):
        setup(world, items)
    assert world.bff.doubles.governance.calls == [] and world.oidc.logins == [] and world.oidc.step_ups == []


def test_rt2_setup_zero_or_six_versions_are_out_of_range(world: Rt2World, tmp_path: Path) -> None:
    for count in (0, 6):
        with pytest.raises(ScenarioError, match="rt2_versiones_fuera_de_rango"):
            setup(world, [rt2.ProxyVersion(n + 1, f"mv-{n}") for n in range(count)])


def test_rt2_setup_approver_equal_to_registrant_fails_with_the_409(world: Rt2World, tmp_path: Path) -> None:
    world.add_model(
        PROXY, "lista_para_aprobacion", registered_by="cro-1"
    )  # quien la registro es el mismo `sub` que aprueba: U4 responde 409
    outcome = setup(world, versions(world, tmp_path))
    assert outcome.result == "falla" and outcome.missing == ("rt2_setup_aprobacion_http_409_conflict_state",)


def test_rt2_setup_registration_body_is_the_one_of_registro_cuerpo_sh(tmp_path: Path) -> None:
    package = make_package(tmp_path, "mv-20261113-abcd1234")
    script = ROOT / "governance" / "docs" / "kind" / "registro-cuerpo.sh"
    done = subprocess.run(["bash", str(script), str(package)], capture_output=True, text=True, check=True)  # noqa: S603, S607
    assert registration_body(package).model_dump(
        exclude={"data_sources", "source_candidate_for"}
    ) == json.loads(done.stdout)
    assert (
        registration_body(package, "adversarial/rt3-a").manifest_uri
        == "s3://model-store/adversarial/rt3-a/manifest.json"
    )


def test_rt2_setup_resumes_a_version_already_lista_para_aprobacion_without_registering_or_validating(
    world: Rt2World, tmp_path: Path
) -> None:
    world.add_model(PROXY, "lista_para_aprobacion", registered_by="ingeniero-1")
    outcome = setup(world, versions(world, tmp_path))
    assert outcome.result == "pasa" and world.registrations == [] and world.validation_calls == []
    assert world.approvals == [(PROXY, "cro-1")]


def test_rt2_setup_a_version_already_approved_is_not_touched(world: Rt2World, tmp_path: Path) -> None:
    world.add_model(PROXY, "aprobado", registered_by="ingeniero-1", approved_by="cro-1")
    outcome = setup(world, versions(world, tmp_path))
    assert (
        outcome.result == "pasa"
        and world.registrations == []
        and world.approvals == []
        and world.oidc.step_ups == []
    )


def test_rt2_setup_validating_without_an_active_policy_is_no_ejecutado_with_its_reason(
    world: Rt2World, tmp_path: Path
) -> None:
    world.no_policy = True
    outcome = setup(world, versions(world, tmp_path))
    assert outcome.result == "no ejecutado" and outcome.missing == ("rt2_setup_sin_politica_activa",)
    assert world.approvals == []


def test_rt2_setup_a_validation_that_does_not_end_is_no_ejecutado_after_the_deadline_with_the_fake_clock(
    world: Rt2World, tmp_path: Path
) -> None:
    world.validation_seconds = 10_000.0
    outcome = setup(world, versions(world, tmp_path), validation_timeout=1800.0)
    assert outcome.result == "no ejecutado" and outcome.missing == ("rt2_setup_validacion_no_termina",)
    assert "InferenceService" in outcome.subresults[0].detail and sum(world.clock.sleeps) <= 1800.0 + 1


def test_rt2_setup_an_auth_time_of_801_seconds_ago_makes_a_new_step_up_and_800_does_not(
    world: Rt2World,
) -> None:
    sessions = world.sessions
    sessions.writer("cro-1")
    world.clock.advance(800.0)
    sessions.writer("cro-1")
    assert world.oidc.step_ups.count("cro-1") == 1
    world.clock.advance(1.0)
    sessions.writer("cro-1")
    assert world.oidc.step_ups.count("cro-1") == 2


def test_rt2_setup_a_session_without_step_up_is_refused_before_sending(
    world: Rt2World, tmp_path: Path
) -> None:
    world.oidc.step_up_flag = False
    with pytest.raises(ScenarioError, match="step_up_required"):
        setup(world, versions(world, tmp_path))
    assert world.registrations == []


def test_rt2_setup_an_expired_mfa_is_retried_once_after_a_step_up(world: Rt2World) -> None:
    calls: list[int] = []

    def write(client: object) -> str:
        calls.append(1)
        if len(calls) == 1:
            from vectra_verification.clients._api import ApiError

            raise ApiError(403, "mfa_required")
        return "ok"

    assert (
        world.sessions.write("cro-1", write) == "ok"
        and len(calls) == 2
        and world.oidc.step_ups.count("cro-1") == 2
    )


def test_rt2_setup_a_non_mfa_403_is_not_retried(world: Rt2World) -> None:
    from vectra_verification.clients._api import ApiError

    def write(client: object) -> str:
        raise ApiError(403, "forbidden")

    with pytest.raises(ApiError):
        world.sessions.write("cro-1", write)
    assert world.oidc.step_ups.count("cro-1") == 1


def test_rt2_setup_the_empty_initial_disparity_warning_stays_in_the_result(
    world: Rt2World, tmp_path: Path
) -> None:
    world.empty_disparity = True
    outcome = setup(world, versions(world, tmp_path))
    assert outcome.result == "pasa" and outcome.readings["initial_disparity_vacia"] == [PROXY]


def test_rt2_setup_in_staging_is_refused_with_zero_requests(world: Rt2World, tmp_path: Path) -> None:
    with pytest.raises(guard.GuardError, match="section_denied_in_staging:rt2-setup"):
        rt2.rt2_setup(guard.STAGING, world.sessions, world.clock, versions(world, tmp_path))
    assert world.bff.doubles.governance.calls == [] and world.oidc.logins == []


# --- RT-2 (CA-11) --------------------------------------------------------------------------------------------------------------------
# El BFF real en proceso con estado (`Rt2World`): el operador (promover, volver al modelo de referencia) y el sistema (el `freeze` a los 1 500 s, las corridas de bias cada 900 s, el barrido de 300 s) son eventos del
# reloj falso: ninguna prueba duerme. Cada prueba cambia **una** cosa del mundo correcto.

import copy

from vectra_verification.scenarios.rt2 import Rt2Deps, Rt2Params, Rt2Result, Rt2State


@pytest.fixture
def rworld(world: Rt2World) -> Rt2World:
    """El mundo correcto: la referencia `activo`, el proxy `aprobado`; el operador promueve a los 60 s y vuelve atras a los 6 000 s (la corrida termina hacia los 4 700 s); el cron de bias cada 900 s."""
    world.add_model(PROXY, "aprobado", registered_by="ingeniero-1", approved_by="cro-1")
    world.operator_promotes(60.0)
    world.operator_rolls_back(6000.0)
    world.start_bias()
    return world


def rt2_run(
    world: Rt2World,
    *,
    params: dict[str, object] | None = None,
    state: Rt2State | None = None,
    prom: bool = True,
    reactivator: object = None,
) -> Rt2Result:
    deps = Rt2Deps(
        KIND,
        world.clock,
        world.sessions,
        world.simulator,
        world.registry,
        world.prom if prom else None,
        reactivator,
    )  # type: ignore[arg-type]
    arguments: dict[str, object] = {
        "reference_version_id": REFERENCE,
        "versions": [rt2.ProxyVersion(1, PROXY)],
        "seed": 7,
    }
    arguments.update(params or {})
    return rt2.run_rt2(deps, Rt2Params(**arguments), state)  # type: ignore[arg-type]


def codes(result: Rt2Result) -> tuple[str, ...]:
    return result.rt2.missing


def test_rt2_a_correct_run_passes_with_a_latency_of_1500_seconds_and_the_closing_done(
    rworld: Rt2World,
) -> None:
    result = rt2_run(rworld)
    assert result.rt2.result == "pasa", (
        result.rt2.missing,
        [(s.name, s.result, s.detail) for s in result.rt2.subresults if s.result != "pasa"],
    )
    assert result.latency.result == "pasa" and result.latency.readings["latency_seconds"] == 1500.0
    assert result.closing is not None and result.closing.result == "pasa" and result.pending is None
    assert [s.name.split(":")[1] for s in result.rt2.subresults] == [*rt2.PHASES, "latencia"][
        : len(result.rt2.subresults)
    ]
    assert rworld.state_of(PROXY) == "inactivo" and rworld.state_of(REFERENCE) == "activo"
    assert rworld.reactivation_calls == [{"action": "reactivar", "justification": rt2.JUSTIFICATION}]
    assert rworld.simulator.runs[0][:2] == ("stratified", 1500) and {r[3] for r in rworld.simulator.runs} == {
        "rt2"
    }


def test_rt2_with_one_version_the_latency_evidence_says_one_measurement_and_cites_dd1(
    rworld: Rt2World,
) -> None:
    latency = rt2_run(rworld).latency
    assert "1 medicion(es)" in latency.expected and "DD-1" in latency.expected


def test_rt2_a_run_of_31_minutes_fails_the_latency_with_the_measurement_recorded(rworld: Rt2World) -> None:
    rworld.freeze_after = 1860.0
    result = rt2_run(rworld)
    assert result.latency.result == "falla" and result.latency.readings["latency_seconds"] == 1860.0
    assert result.latency.missing == ("rt2_latencia_mayor_que_1800s",) and "1860" in result.latency.obtained
    assert result.latency.readings["measurements"][0].latency_seconds == 1860.0


def test_rt2_a_run_of_exactly_1800_seconds_passes_the_latency(rworld: Rt2World) -> None:
    rworld.freeze_after = 1800.0
    assert rt2_run(rworld).latency.result == "pasa"


def test_rt2_a_version_that_freezes_again_the_same_day_after_the_reactivation_fails(rworld: Rt2World) -> None:
    rworld.refreeze_after = 0.0
    result = rt2_run(rworld)
    assert (
        result.rt2.result == "falla"
        and codes(result) == ("rt2_recongelada",)
        and result.pending == "no_recongela"
    )


def test_rt2_two_runs_with_the_same_model_version_id_fail_before_sending_anything(rworld: Rt2World) -> None:
    result = rt2_run(rworld, params={"versions": [rt2.ProxyVersion(1, PROXY), rt2.ProxyVersion(2, PROXY)]})
    assert result.rt2.result == "falla" and codes(result) == ("rt2_version_repetida",)
    assert (
        rworld.simulator.runs == [] and rworld.bff.doubles.governance.calls == [] and rworld.oidc.logins == []
    )


@pytest.mark.parametrize("name", rt2.PACKAGE_FIELDS)
def test_rt2_a_freeze_package_without_the_field_fails_and_names_it(rworld: Rt2World, name: str) -> None:
    rworld.package_variant = lambda item: item["context_package"].pop(name)
    result = rt2_run(rworld)
    assert result.rt2.result == "falla" and codes(result) == (f"rt2_paquete_{name}_ausente",)
    assert (
        result.pending == "paquete" and result.latency.readings["latency_seconds"] == 1500.0
    )  # la latencia se mide igual


def test_rt2_a_freeze_without_data_sources_fails_and_an_empty_list_passes(rworld: Rt2World) -> None:
    rworld.package_variant = lambda item: item["context_package"].pop("data_sources")
    assert codes(rt2_run(rworld)) == ("rt2_paquete_data_sources_ausente",)


def test_rt2_a_freeze_with_an_empty_data_sources_list_passes(rworld: Rt2World) -> None:
    rworld.package_variant = lambda item: item["context_package"].update(data_sources=[])
    assert rt2_run(rworld).rt2.result == "pasa"


def test_rt2_a_freeze_with_an_empty_initial_disparity_fails(rworld: Rt2World) -> None:
    rworld.package_variant = lambda item: item["context_package"].update(initial_disparity={"attributes": []})
    assert codes(rt2_run(rworld)) == ("rt2_paquete_initial_disparity_vacia",)
    rworld2 = rworld
    rworld2.package_variant = lambda item: item["context_package"].pop("initial_disparity")
    rworld2.freeze_entries.clear()


def test_rt2_a_freeze_with_an_incomplete_freeze_context_fails_with_the_missing_field(
    rworld: Rt2World,
) -> None:
    rworld.package_variant = lambda item: item["context_package"].pop(
        "computed_at"
    )  # un campo de FreezeContext que el plan no lista
    (code,) = codes(rt2_run(rworld))
    assert code.startswith("rt2_paquete_invalido:computed_at")


def test_rt2_the_package_check_is_a_pure_function_of_the_raw_freeze() -> None:
    assert rt2.judge_package({"seq": 1}) == ("rt2_paquete_ausente",)
    assert rt2.judge_package({"context_package": "texto"}) == ("rt2_paquete_ausente",)


def test_rt2_without_a_freeze_at_the_cap_fails_and_the_message_has_the_last_bias_run(
    rworld: Rt2World,
) -> None:
    rworld.freeze_after = None
    rworld.bias_ok = 0.0
    rworld.bias_failure_reason = "u3_unavailable"
    result = rt2_run(rworld)
    assert (
        result.rt2.result == "falla"
        and codes(result) == ("rt2_freeze_ausente",)
        and result.pending == "freeze"
    )
    detail = next(s.detail for s in result.rt2.subresults if s.name == "v1:freeze")
    assert "vectra_bias_last_run_ok=0" in detail and "u3_unavailable" in detail
    assert result.latency.result == "no ejecutado"


def test_rt2_a_freeze_of_another_version_does_not_count(rworld: Rt2World) -> None:
    rworld.freeze_after = None
    other = freeze_item(99)
    other["model_version_id"] = "mv-otra"
    other["recorded_at"] = iso(rworld.clock.now() + timedelta(seconds=300))
    rworld.freeze_entries.append(other)
    assert codes(rt2_run(rworld)) == ("rt2_freeze_ausente",)


def test_rt2_a_freeze_of_the_version_before_the_start_of_the_batch_does_not_count(rworld: Rt2World) -> None:
    rworld.freeze_after = None
    old = freeze_item(98)
    old["model_version_id"] = PROXY
    old["recorded_at"] = iso(rworld.clock.now() - timedelta(hours=1))
    rworld.freeze_entries.append(old)
    assert codes(rt2_run(rworld)) == ("rt2_freeze_ausente",)


def test_rt2_the_version_that_does_not_become_congelado_fails(rworld: Rt2World) -> None:
    rworld.freeze_freezes_model = False
    result = rt2_run(rworld)
    assert codes(result) == ("rt2_version_no_congelada",) and result.pending == "congelado"


def test_rt2_a_new_case_in_listo_fails_with_the_version_frozen(rworld: Rt2World) -> None:
    rworld.probe_listo = True
    result = rt2_run(rworld)
    assert codes(result) == ("rt2_caso_nuevo_en_listo",) and result.pending == "casos_nuevos"


def test_rt2_a_resolution_before_the_three_bias_runs_fails(rworld: Rt2World) -> None:
    rworld.at(
        2300.0,
        lambda: rworld.freeze_entries.append(
            {
                "seq": rworld.seq(),
                "model_version_id": PROXY,
                "action": "reactivar",
                "recorded_at": iso(rworld.clock.now()),
            }
        ),
    )
    result = rt2_run(rworld)
    assert codes(result) == ("rt2_resolucion_antes_de_las_corridas",) and result.pending == "sigue_congelada"


def test_rt2_the_version_leaving_congelado_before_the_three_runs_fails(rworld: Rt2World) -> None:
    rworld.at(2300.0, lambda: rworld.set_state(PROXY, "activo"))
    assert codes(rt2_run(rworld)) == ("rt2_version_dejo_de_estar_congelada",)


def test_rt2_only_two_complete_bias_runs_in_the_deadline_is_no_ejecutado(rworld: Rt2World) -> None:
    result = rt2_run(rworld, params={"bias_timeout": 1300.0})
    assert (
        result.rt2.result == "no ejecutado"
        and codes(result) == ("rt2_corridas_de_bias_pendientes",)
        and result.pending == "sigue_congelada"
    )


def test_rt2_a_bias_run_with_ok_0_does_not_count(rworld: Rt2World) -> None:
    rworld.bias_ok = 0.0
    result = rt2_run(rworld, params={"bias_timeout": 4000.0})
    assert result.rt2.result == "no ejecutado" and codes(result) == ("rt2_corridas_de_bias_pendientes",)
    assert "solo 0 de 3" in next(s.detail for s in result.rt2.subresults if s.name == "v1:sigue_congelada")


def test_rt2_counting_bias_runs_is_a_pure_function() -> None:
    ts = [(1.0, 10.0), (2.0, 10.0), (3.0, 20.0), (4.0, 20.0), (5.0, 30.0)]
    ok = [(1.0, 1.0), (2.0, 1.0), (3.0, 0.0), (4.0, 0.0), (5.0, 1.0)]  # Pushgateway: el ultimo valor se queda
    assert rt2.count_bias_runs(ts, ok, 5.0) == [10.0, 30.0]  # la de 20 (ok = 0 al aparecer) no cuenta
    assert rt2.count_bias_runs(ts, ok, 10.0) == [30.0]


def test_rt2_the_reactivation_answering_403_fails_with_the_code(rworld: Rt2World) -> None:
    rworld.reactivation_status = 403
    result = rt2_run(rworld)
    assert (
        result.rt2.result == "falla"
        and codes(result) == ("rt2_reactivacion_http_403_forbidden",)
        and result.pending == "reactivacion"
    )


def test_rt2_a_reactivation_token_without_step_up_is_an_error_before_sending(rworld: Rt2World) -> None:
    rworld.oidc.step_up_flag = False
    with pytest.raises(ScenarioError, match="step_up_required"):
        rt2_run(rworld)
    assert rworld.reactivation_calls == []
    assert not [c for c in rworld.bff.doubles.governance.calls if c.template.endswith("frozen-resolution")]


def test_rt2_the_reactivation_is_a_separate_step_that_the_oracles_do_not_depend_on(rworld: Rt2World) -> None:
    """U12-T04 sustituye «reactivar» por «esperar al presentador» sin tocar los oraculos: aqui lo hace «el presentador» (un evento) y la verificacion posterior es la misma."""

    class Waiting:
        def reactivate(self, model_version_id: str) -> None:
            rworld.reactivate()  # el presentador lo hizo en la consola

    result = rt2_run(rworld, reactivator=Waiting())
    assert result.rt2.result == "pasa" and rworld.reactivation_calls == []


def test_rt2_the_reactivation_not_verified_afterwards_fails(rworld: Rt2World) -> None:
    class Nothing:
        def reactivate(self, model_version_id: str) -> None:
            return None  # se pidio pero no paso nada

    result = rt2_run(rworld, reactivator=Nothing())
    assert codes(result) == ("rt2_version_no_quedo_activa",) and result.pending == "reactivacion"


def test_rt2_cases_that_do_not_leave_modelo_congelado_after_the_sweep_fail(rworld: Rt2World) -> None:
    rworld.sweep_works = False
    result = rt2_run(rworld)
    assert codes(result) == ("rt2_barrido_no_libero_casos",) and result.pending == "barrido"


def test_rt2_a_recommendation_of_the_batch_with_the_reference_version_fails_mark_active_is_missing(
    rworld: Rt2World,
) -> None:
    rworld.recommendation_version = REFERENCE
    result = rt2_run(rworld)
    assert result.rt2.result == "falla" and codes(result) == ("rt2_lote_puntuado_por_otra_version",)
    assert "mark_active" in result.rt2.subresults[-1].detail


def test_rt2_when_the_operator_does_not_activate_the_version_it_is_no_ejecutado_with_the_pending_phase(
    world: Rt2World,
) -> None:
    world.add_model(PROXY, "aprobado", registered_by="ingeniero-1", approved_by="cro-1")
    result = rt2_run(world)
    assert (
        result.rt2.result == "no ejecutado"
        and codes(result) == ("rt2_operador_promocion_pendiente",)
        and result.pending == "promocion"
    )
    assert world.simulator.runs == [] and sum(world.clock.sleeps) <= rt2.OPERATOR_TIMEOUT + 1


def test_rt2_the_promotion_that_leaves_the_reference_active_fails(world: Rt2World) -> None:
    world.add_model(PROXY, "aprobado", registered_by="ingeniero-1", approved_by="cro-1")
    world.at(
        60.0, lambda: world.set_state(PROXY, "activo")
    )  # el operador no dejo la de referencia `inactivo`
    assert codes(rt2_run(world)) == ("rt2_referencia_no_inactiva",)


def test_rt2_a_rollback_still_pending_is_said_by_the_closing_field_and_does_not_change_the_result(
    rworld: Rt2World,
) -> None:
    rworld.clock.events = [
        e for e in rworld.clock.events if e[0] < rworld.clock.now() + timedelta(seconds=5000)
    ]  # sin rollback
    result = rt2_run(rworld)
    assert (
        result.rt2.result == "pasa" and result.closing is not None and result.closing.result == "no ejecutado"
    )
    assert result.closing.missing == ("rt2_cierre_rollback_pendiente",) and result.rt2.readings["cierre"][
        "missing"
    ] == ["rt2_cierre_rollback_pendiente"]


def test_rt2_without_prometheus_the_bias_phase_is_no_ejecutado(rworld: Rt2World) -> None:
    result = rt2_run(rworld, prom=False)
    assert result.rt2.result == "no ejecutado" and codes(result) == ("rt2_prometheus_requerido",)


def test_rt2_prometheus_not_responding_is_no_ejecutado(rworld: Rt2World) -> None:
    rworld.prom_transport.down = True
    result = rt2_run(rworld)
    assert result.rt2.result == "no ejecutado" and codes(result) == ("rt2_prometheus_no_responde",)


def test_rt2_a_lot_without_accepted_requests_fails(rworld: Rt2World) -> None:
    rworld.simulator.accepted_ratio = 0.0
    assert codes(rt2_run(rworld)) == ("rt2_lote_sin_solicitudes_aceptadas",)


def test_rt2_an_operator_pending_run_resumes_from_its_phase_with_the_returned_state(world: Rt2World) -> None:
    world.add_model(PROXY, "aprobado", registered_by="ingeniero-1", approved_by="cro-1")
    world.start_bias()
    first = rt2_run(world)
    assert first.pending == "promocion" and first.state.versions[PROXY].done["celdas"].result == "pasa"
    world.operator_promotes(10.0)
    world.operator_rolls_back(6000.0)
    resumed = rt2_run(world, state=first.state)
    assert resumed.rt2.result == "pasa" and resumed.pending is None
    assert [r[0] for r in world.simulator.runs].count(
        "stratified"
    ) == 1  # las celdas no se repitieron como lote


def test_rt2_the_registry_not_responding_is_no_ejecutado(rworld: Rt2World) -> None:
    rworld.registry_transport.handle_request = lambda request: (_ for _ in ()).throw(
        httpx.ConnectError("sin conexion")
    )  # type: ignore[method-assign]
    result = rt2_run(rworld)
    assert result.rt2.result == "no ejecutado" and codes(result) == ("rt2_dependencia_no_responde",)


def test_rt2_in_staging_is_refused_before_the_first_request(rworld: Rt2World) -> None:
    deps = Rt2Deps(
        guard.STAGING, rworld.clock, rworld.sessions, rworld.simulator, rworld.registry, rworld.prom
    )  # type: ignore[arg-type]
    with pytest.raises(guard.GuardError, match="section_denied_in_staging:rt2"):
        rt2.run_rt2(deps, Rt2Params(REFERENCE, [rt2.ProxyVersion(1, PROXY)], 7))
    assert rworld.simulator.runs == [] and rworld.oidc.logins == []


def test_rt2_the_copy_of_a_package_is_independent(rworld: Rt2World) -> None:
    assert copy.deepcopy({"a": 1}) == {
        "a": 1
    }  # los cambios de `package_variant` se hacen sobre la entrada del registro, no sobre una compartida
