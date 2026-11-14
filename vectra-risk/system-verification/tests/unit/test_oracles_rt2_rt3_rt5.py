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
from vectra_verification.scenarios.outcome import SubOutcome, combine

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

import subprocess
from collections.abc import Iterator
from pathlib import Path

from external_paths import ROOT
from registry_read_double import freeze_item
from rt2_world import PROXY, REFERENCE, Rt2World, make_package
from vectra_verification.scenarios import rt2
from vectra_verification.scenarios.common import ScenarioError, registration_body


@pytest.fixture
def world() -> Iterator[Rt2World]:
    built = Rt2World()
    built.add_model(REFERENCE, "activo", registered_by="otro-ingeniero", approved_by="otro-cro")
    yield built
    built.close()


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
    # F-04: el sistema respondio y no detecto en 2 700 s: `RT2-LATENCY` es `falla`, no `no ejecutado`
    assert result.latency.result == "falla" and result.latency.missing == ("rt2_latencia_sin_freeze",)


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
    # referencia: la primera marca >= 5 (la de 10, la corrida que congelo); cuentan las correctas **estrictamente posteriores**: la de 20 (ok = 0) no cuenta
    assert rt2.count_bias_runs(ts, ok, 5.0) == [30.0]
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
    rworld.clock.events = [e for e in rworld.clock.events if e[2].__name__ != "back"]  # sin rollback
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


# --- RT-3 (CA-12) --------------------------------------------------------------------------------------------------------------------
# El registro por el BFF real (con el 422 de U4 en el doble de governance con la forma de `Problem`); los casos de sonda con el estado que da `case_state`; el `InferenceService` de staging con un `kubectl` guionizado.

from collections.abc import Callable
from typing import Any

from contract_world import problem
from rt2_world import ATTRIBUTES  # noqa: F401
from vectra_verification.scenarios import rt3
from vectra_verification.scenarios.rt3 import Rt3Deps, Rt3Package, Rt3Params

RT3B = "mv-rt3b"


def reject(case_id: str) -> Callable[[Any], tuple[int, Any]]:
    def respond(call: Any) -> tuple[int, Any]:
        body = problem(422, "validation_error")
        body["invalid_params"] = [{"name": "package", "reason_code": rt3.EXPECTED_REASON[case_id]}]
        return 422, body

    return respond


class IsvcKubectl:
    """`kubectl get inferenceservice/<n> -n vectra-staging`: `Ready` por nombre, o el error que diga `fail`."""

    def __init__(self, ready: dict[str, str] | None = None, fail: str | None = None) -> None:
        self.ready, self.fail, self.calls = ready or {}, fail, []  # type: ignore[var-annotated]

    def run(self, args: Any) -> Completed:
        self.calls.append(tuple(args))
        if self.fail:
            return Completed(1, "", self.fail)
        name = args[2].split("/")[1]
        status = self.ready.get(name, "False")
        return Completed(0, json.dumps({"status": {"conditions": [{"type": "Ready", "status": status}]}}), "")

    def start(self, args: Any) -> Any:  # pragma: no cover
        raise AssertionError("sin port-forward")


def f22_cases(
    cause: str | None = "timeout", state: str = "en_sincronizacion", attempts: int = 1
) -> Callable[[str, Any], tuple[str, str | None, int]]:
    return lambda case_id, record: (state, cause, attempts)


@pytest.fixture
def tworld(world: Rt2World, tmp_path: Path) -> Rt2World:
    """El mundo correcto de D1: U4 rechaza RT3-a, c y d; RT3-b comparte la version de la de referencia (409); F22 apagado deja los casos `en_sincronizacion` con `timeout`."""
    for case_id, token in (("RT3-a", "rt3-a"), ("RT3-c", "rt3-c"), ("RT3-d", "rt3-d")):
        world.register_overrides[token] = reject(case_id)
    world.register_overrides["rt3-b"] = lambda call: (409, problem(409, "conflict_state"))
    world.state_cases = f22_cases()
    return world


def rt3_params(tmp_path: Path, **over: Any) -> Rt3Params:
    packages = {
        c: Rt3Package(c, make_package(tmp_path, f"base-{c}"), t)
        for c, t in (("RT3-a", "rt3-a"), ("RT3-c", "rt3-c"), ("RT3-d", "rt3-d"), ("RT3-b", "rt3-b"))
    }
    arguments: dict[str, Any] = {
        "packages": packages,
        "seed": 5,
        "deployed": {"RT3-a": "isvc-a", "RT3-d": "isvc-d"},
    }
    arguments.update(over)
    return Rt3Params(**arguments)


def rt3_run(world: Rt2World, params: Rt3Params, k8s: IsvcKubectl | None = None) -> rt3.Outcome:
    from vectra_verification.clients.k8s_read import K8sRead

    deps = Rt3Deps(
        KIND,
        world.clock,
        world.sessions,
        world.simulator,
        world.registry,
        K8sRead(k8s or IsvcKubectl()),
        world.prom,
    )  # type: ignore[arg-type]
    return rt3.rt3(deps, params)


def sub(outcome: rt3.Outcome, name: str) -> Any:
    return next(s for s in outcome.subresults if s.name == name)


def test_rt3_a_c_and_d_rejected_with_the_models_unchanged_and_f22_with_timeout_and_no_recommendation_pass(
    tworld: Rt2World, tmp_path: Path
) -> None:
    outcome = rt3_run(tworld, rt3_params(tmp_path))
    assert outcome.result == "pasa", [
        (s.name, s.result, s.missing) for s in outcome.subresults if s.result != "pasa"
    ]
    assert [s.name for s in outcome.subresults] == [
        "RT3-a",
        "RT3-c",
        "RT3-d",
        "sin_cambio_en_modelos",
        "RT3-a-desplegado",
        "RT3-d-desplegado",
        "RT3-b",
        "F22",
    ]
    assert sub(outcome, "RT3-b").result == "no ejecutado" and sub(outcome, "RT3-b").missing == (
        "rt3b_version_ya_registrada",
    )
    assert sub(outcome, "RT3-a").readings["invalid_params"] == (("package", rt3.EXPECTED_REASON["RT3-a"]),)
    assert sub(outcome, "F22").readings["recommendations"] == 0


@pytest.mark.parametrize("case_id", ["RT3-a", "RT3-c", "RT3-d"])
def test_rt3_a_package_accepted_by_u4_fails(tworld: Rt2World, tmp_path: Path, case_id: str) -> None:
    token = case_id.lower()
    tworld.register_overrides.pop(token)  # el doble responde 200: «aceptado por U4»
    outcome = rt3_run(tworld, rt3_params(tmp_path))
    assert outcome.result == "falla" and f"rt3_{case_id}_aceptado_por_u4" in outcome.missing


@pytest.mark.parametrize(
    ("status", "body", "code"),
    [
        (422, problem(422, "unprocessable_explanation"), "rt3_RT3-a_estado_422_unprocessable_explanation"),
        (409, problem(409, "conflict_state"), "rt3_RT3-a_estado_409_conflict_state"),
        (403, problem(403, "forbidden"), "rt3_RT3-a_estado_403_forbidden"),
    ],
)
def test_rt3_a_422_with_another_code_or_a_409_or_a_403_fails_with_the_status_and_code(
    tworld: Rt2World, tmp_path: Path, status: int, body: dict[str, Any], code: str
) -> None:
    tworld.register_overrides["rt3-a"] = lambda call: (status, body)
    outcome = rt3_run(tworld, rt3_params(tmp_path))
    assert outcome.result == "falla" and outcome.missing == (code,)


def test_rt3_a_reason_code_different_from_the_table_fails(tworld: Rt2World, tmp_path: Path) -> None:
    def other(call: Any) -> tuple[int, Any]:
        body = problem(422, "validation_error")
        body["invalid_params"] = [{"name": "package", "reason_code": "manifest_sha256_mismatch"}]
        return 422, body

    tworld.register_overrides["rt3-a"] = other
    outcome = rt3_run(tworld, rt3_params(tmp_path))
    assert outcome.missing == ("rt3_RT3-a_reason_code_distinto",)


def test_rt3_a_422_without_invalid_params_of_the_package_fails(tworld: Rt2World, tmp_path: Path) -> None:
    tworld.register_overrides["rt3-a"] = lambda call: (422, problem(422, "validation_error"))
    assert rt3_run(tworld, rt3_params(tmp_path)).missing == ("rt3_RT3-a_sin_invalid_params_package",)


def test_rt3_a_new_version_in_the_model_list_after_the_registrations_fails(
    tworld: Rt2World, tmp_path: Path
) -> None:
    def leaks(call: Any) -> tuple[int, Any]:
        tworld.add_model("mv-colada", "registrado")
        return reject("RT3-c")(call)

    tworld.register_overrides["rt3-c"] = leaks
    outcome = rt3_run(tworld, rt3_params(tmp_path))
    assert (
        outcome.result == "falla"
        and outcome.missing == ("rt3_lista_de_modelos_cambio",)
        and "mv-colada" in sub(outcome, "sin_cambio_en_modelos").detail
    )


def test_rt3_the_active_version_changing_fails() -> None:
    result = rt3.judge_unchanged(
        {"mv-a": "activo", "mv-b": "inactivo"}, {"mv-a": "inactivo", "mv-b": "activo"}, "mv-a", "mv-b"
    )
    assert result.result == "falla" and result.missing == ("rt3_lista_de_modelos_cambio",)
    assert rt3.judge_unchanged({"a": "activo"}, {"a": "activo"}, "a", "a").result == "pasa"


def test_rt3_a_single_recommendation_in_the_window_fails_with_its_case_and_version(
    tworld: Rt2World, tmp_path: Path
) -> None:
    def stray() -> None:
        tworld.recommendations.append(
            {
                "entry_type": "recommendation",
                "seq": tworld.seq(),
                "recorded_at": iso(tworld.clock.now()),
                "case_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                "outcome": "favorable",
                "model_version_id": "mv-otra",
            }
        )

    tworld.on_probe = stray  # una `recommendation` de otra version dentro de la ventana de la sonda
    outcome = rt3_run(tworld, rt3_params(tmp_path))
    assert outcome.result == "falla" and outcome.missing == ("rt3_recommendation_con_f22_apagado",)
    assert (
        "3fa85f64-5717-4562-b3fc-2c963f66afa6" in sub(outcome, "F22").detail
        and "mv-otra" in sub(outcome, "F22").detail
    )


def test_rt3_without_failclosed_of_timeout_or_explainer_unavailable_fails_when_all_are_explainer_error(
    tworld: Rt2World, tmp_path: Path
) -> None:
    tworld.state_cases = f22_cases("explainer_error")
    outcome = rt3_run(tworld, rt3_params(tmp_path))
    assert (
        outcome.missing == ("rt3_f22_sin_causa_timeout_o_explainer_unavailable",)
        and "explainer_error" in sub(outcome, "F22").detail
    )


def test_rt3_all_the_probe_cases_in_listo_fail(tworld: Rt2World, tmp_path: Path) -> None:
    tworld.state_cases = f22_cases(None, "listo")
    assert rt3_run(tworld, rt3_params(tmp_path)).missing == ("rt3_f22_caso_en_listo",)


def test_rt3_cases_in_no_disponible_with_explainer_unavailable_pass(tworld: Rt2World, tmp_path: Path) -> None:
    tworld.state_cases = f22_cases("explainer_unavailable", "no_disponible", 6)
    assert rt3_run(tworld, rt3_params(tmp_path)).result == "pasa"


def test_rt3_a_case_in_en_evaluacion_without_attempts_after_the_deadline_fails(
    tworld: Rt2World, tmp_path: Path
) -> None:
    tworld.state_cases = f22_cases(None, "en_evaluacion", 0)
    outcome = rt3_run(tworld, rt3_params(tmp_path))
    assert "rt3_f22_caso_sin_intentos" in outcome.missing and sum(tworld.clock.sleeps) >= rt3.ATTEMPTS_TIMEOUT


def test_rt3_rejected_probes_fail_f22(tworld: Rt2World, tmp_path: Path) -> None:
    tworld.simulator.accepted_ratio = 0.0
    assert rt3_run(tworld, rt3_params(tmp_path)).missing == ("rt3_f22_sonda_rechazada",)


def test_rt3b_validacion_fallida_passes() -> None:
    result = rt3.judge_rt3b(rt3.RegistrationReading(200), "validacion_fallida", [], [], RT3B)
    assert result.result == "pasa" and result.mandatory is False


def test_rt3b_promoted_with_explainer_error_and_no_recommendation_passes_and_with_one_fails() -> None:
    cases = [
        rt3.CaseReading("c1", "en_sincronizacion", "explainer_error", 1),
        rt3.CaseReading("c2", "no_disponible", "feature_dictionary_incomplete", 6),
    ]
    assert rt3.judge_rt3b(rt3.RegistrationReading(200), "activo", cases, [], RT3B).result == "pasa"
    mine = [rt3.RecommendationReading("c1", RT3B)]
    result = rt3.judge_rt3b(rt3.RegistrationReading(200), "activo", cases, mine, RT3B)
    assert result.result == "falla" and result.missing == ("rt3b_recommendation_de_la_version_alterada",)
    wrong = [rt3.CaseReading("c1", "en_sincronizacion", "timeout", 1)]
    assert rt3.judge_rt3b(rt3.RegistrationReading(200), "activo", wrong, [], RT3B).missing == (
        "rt3b_sin_fail_closed_esperado",
    )


def test_rt3b_409_at_registration_is_no_ejecutado_and_does_not_lower_rt3() -> None:
    result = rt3.judge_rt3b(rt3.RegistrationReading(409, "conflict_state"), None, [], [], RT3B)
    assert result.result == "no ejecutado" and result.missing == ("rt3b_version_ya_registrada",)

    assert combine([result, SubOutcome("RT3-a", "pasa")])[0] == "pasa"


def test_rt3b_full_flow_registers_validates_and_a_validation_failure_passes(
    tworld: Rt2World, tmp_path: Path
) -> None:
    package = Rt3Package("RT3-b", make_package(tmp_path, RT3B), RT3B)
    tworld.register_overrides.pop("rt3-b")
    tworld.validation_outcome = "validacion_fallida"
    outcome = rt3_run(
        tworld, rt3_params(tmp_path, packages={**rt3_params(tmp_path).packages, "RT3-b": package})
    )
    assert sub(outcome, "RT3-b").result == "pasa" and tworld.registrations[-1] == (RT3B, "ingeniero-1")
    assert outcome.result == "pasa"


def test_rt3b_full_flow_promoted_by_the_operator_with_probes_in_failclosed_passes(
    tworld: Rt2World, tmp_path: Path
) -> None:
    from vectra_verification.clients.k8s_read import K8sRead

    package = Rt3Package("RT3-b", make_package(tmp_path, RT3B), RT3B)
    tworld.register_overrides.pop("rt3-b")
    tworld.state_cases = f22_cases("explainer_error")
    tworld.at(
        900.0, lambda: tworld.set_state(RT3B, "activo")
    )  # el operador la promueve, despues de que `cro-1` la apruebe
    deps = Rt3Deps(
        KIND,
        tworld.clock,
        tworld.sessions,
        tworld.simulator,
        tworld.registry,
        K8sRead(IsvcKubectl()),
        tworld.prom,
    )  # type: ignore[arg-type]
    result = rt3._rt3b(rt3.Rt3Run(deps, rt3_params(tmp_path)), package)
    assert result.result == "pasa", result
    assert tworld.approvals == [(RT3B, "cro-1")] and tworld.registrations[-1] == (RT3B, "ingeniero-1")
    assert result.readings["causes"] == ["explainer_error"]


def test_rt3_a_or_d_deployed_not_ready_passes_with_the_cause_not_read(
    tworld: Rt2World, tmp_path: Path
) -> None:
    outcome = rt3_run(tworld, rt3_params(tmp_path))
    for name in ("RT3-a-desplegado", "RT3-d-desplegado"):
        assert sub(outcome, name).result == "pasa" and sub(outcome, name).readings["causa_no_leida"] is True


def test_rt3_a_deployed_package_that_is_ready_fails(tworld: Rt2World, tmp_path: Path) -> None:
    outcome = rt3_run(tworld, rt3_params(tmp_path), IsvcKubectl({"isvc-a": "True"}))
    assert outcome.result == "falla" and outcome.missing == ("rt3_RT3-a-desplegado_listo",)


def test_rt3_forbidden_kubectl_for_the_deployed_ones_is_no_ejecutado_and_does_not_lower_rt3(
    tworld: Rt2World, tmp_path: Path
) -> None:
    outcome = rt3_run(
        tworld,
        rt3_params(tmp_path),
        IsvcKubectl(fail="Error from server (Forbidden): inferenceservices is forbidden"),
    )
    assert sub(outcome, "RT3-a-desplegado").result == "no ejecutado" and sub(
        outcome, "RT3-a-desplegado"
    ).missing == ("rt3_k8s_forbidden",)
    assert outcome.result == "pasa"  # P-2 (a): un no ejecutado opcional no baja RT-3


def test_rt3_wait_for_escalation_waits_over_19_minutes_without_real_sleep_and_only_informs(
    tworld: Rt2World, tmp_path: Path
) -> None:
    tworld.state_cases = lambda case_id, record: (
        ("no_disponible", "explainer_unavailable", 6)
        if (tworld.clock.now() - record.created).total_seconds() > 1170
        else ("en_sincronizacion", "timeout", 1)
    )
    tworld.gauge, tworld.alert_firing = 1.0, True
    outcome = rt3_run(tworld, rt3_params(tmp_path, wait_for_escalation=True))
    assert outcome.result == "pasa" and outcome.readings["escalated_to_no_disponible"] is True
    assert (
        outcome.readings["failclosed_persistent_max"] == 1.0
        and outcome.readings["failclosed_persistent_alert_firing"] is True
    )
    assert sum(tworld.clock.sleeps) > 1160.0


def test_rt3_the_registry_not_responding_is_no_ejecutado_and_the_bff_not_responding_too(
    tworld: Rt2World, tmp_path: Path
) -> None:
    tworld.registry_transport.handle_request = lambda request: (_ for _ in ()).throw(
        httpx.ConnectError("sin conexion")
    )  # type: ignore[method-assign]
    outcome = rt3_run(tworld, rt3_params(tmp_path))
    assert sub(outcome, "F22").result == "no ejecutado" and outcome.result == "no ejecutado"
    tworld.bff.doubles.governance.fail(503)
    assert rt3_run(tworld, rt3_params(tmp_path)).result == "no ejecutado"


def test_rt3_the_closing_after_reverting_f22_is_a_probe_case_that_reaches_listo(
    tworld: Rt2World, tmp_path: Path
) -> None:
    tworld.state_cases = None
    deps = Rt3Deps(KIND, tworld.clock, tworld.sessions, tworld.simulator, tworld.registry)
    assert rt3.rt3_closing(deps, rt3_params(tmp_path)).result == "pasa"
    tworld.state_cases = f22_cases()
    closing = rt3.rt3_closing(deps, rt3_params(tmp_path), timeout=120.0)
    assert closing.result == "no ejecutado" and closing.missing == ("rt3_cierre_f22_sigue_apagado",)


def test_rt3_missing_packages_are_refused_and_staging_is_refused_with_zero_requests(
    tworld: Rt2World, tmp_path: Path
) -> None:
    params = rt3_params(tmp_path)
    with pytest.raises(ScenarioError, match="rt3_paquetes_faltan"):
        rt3_run(tworld, Rt3Params({"RT3-a": params.packages["RT3-a"]}, 5))
    deps = Rt3Deps(guard.STAGING, tworld.clock, tworld.sessions, tworld.simulator, tworld.registry)
    with pytest.raises(guard.GuardError, match="section_denied_in_staging:rt3"):
        rt3.rt3(deps, params)
    assert tworld.oidc.logins == [] and tworld.simulator.runs == []


def test_guard_resolve_frozen_called_from_rt3_or_rt2_setup_is_refused_with_zero_requests(
    tworld: Rt2World,
) -> None:
    from vectra_contracts.models.governance import FrozenResolutionIn

    bff = tworld.sessions.writer("cumplimiento-1")
    before = len(tworld.bff.doubles.governance.calls)
    for section in ("rt3", "rt2-setup", "decisions"):
        with pytest.raises(guard.GuardError, match="reactivation_outside_rt2"):
            bff.resolve_frozen(PROXY, FrozenResolutionIn(action="reactivar", justification="x"), section)
    assert len(tworld.bff.doubles.governance.calls) == before


def test_guard_a_production_host_or_issuer_sends_zero_requests(tworld: Rt2World) -> None:
    from vectra_verification.clients.bff import BffClient

    with pytest.raises(guard.GuardError, match="environment_not_allowed"):
        BffClient(
            guard.Environment(
                "prod", "vectra.banco.internal", "https://vectra.banco.internal/auth/realms/vectra"
            ),
            tworld.oidc.login("analista-1"),
            TAG_FOR_TESTS,
        )
    assert tworld.bff.doubles.governance.calls == []


from rt2_world import TAG as TAG_FOR_TESTS  # noqa: E402


# --- CA-13: el filtro de evidencias sobre lo que devuelven los escenarios -------------------------------------------------------------

from vectra_contracts.models.application import ApplicationIn
from vectra_verification import evidence
from vectra_verification.credentials import Credentials
from vectra_verification.scenarios import outcome as outcome_module

SECRET_TOKEN = "hvs.CAESIJx-secreto-de-prueba-0001"
SECRETS = Credentials(KIND, "http://vault.vault.svc:8200", SECRET_TOKEN).secret_values()


def scenario_results(world: Rt2World, tworld: Rt2World | None, tmp_path: Path) -> dict[str, str]:
    """El resultado de cada escenario serializado, tal como lo escribira el Paso 13."""
    out: dict[str, str] = {}
    out["RT-5"] = outcome_module.to_text(evaluate()[0])
    result = rt2_run(world)
    out["RT-2"], out["RT2-LATENCY"] = (
        outcome_module.to_text(result.rt2),
        outcome_module.to_text(result.latency),
    )
    return out


def test_evidence_rt5_result_the_job_log_and_the_kubectl_json_pass_the_filter_unchanged() -> None:
    outcome, _, kubectl, _ = evaluate()
    text = outcome_module.to_text(outcome)
    assert evidence.prepare(text, SECRETS) == text
    log, document = PROXY_LOG, completed_job(T0, T1)
    for raw in (log, document, log + document):
        assert evidence.prepare(raw, SECRETS) == raw
    dev = Credentials(
        KIND, "http://vault.vault.svc:8200", "root"
    ).secret_values()  # el token de desarrollo de kind no bloquea (F-09)
    assert evidence.prepare(log + document + "/dev/root", dev) == log + document + "/dev/root"


def test_evidence_every_scenario_result_passes_the_filter_unchanged_and_has_no_applicant_field(
    rworld: Rt2World, tmp_path: Path
) -> None:
    results = scenario_results(rworld, None, tmp_path)
    setup_world = Rt2World()
    try:
        setup_world.add_model(REFERENCE, "activo")
        results["rt2-setup"] = outcome_module.to_text(setup(setup_world, versions(setup_world, tmp_path)))
        setup_world.state_cases = f22_cases()
        for case_id, token in (("RT3-a", "rt3-a"), ("RT3-c", "rt3-c"), ("RT3-d", "rt3-d")):
            setup_world.register_overrides[token] = reject(case_id)
        setup_world.register_overrides["rt3-b"] = lambda call: (409, problem(409, "conflict_state"))
        results["RT-3"] = outcome_module.to_text(rt3_run(setup_world, rt3_params(tmp_path)))
    finally:
        setup_world.close()
    assert set(results) == {"RT-5", "RT-2", "RT2-LATENCY", "rt2-setup", "RT-3"}
    fields = set(ApplicationIn.model_fields) - {
        "channel",
        "sex",
    }  # `channel` es el nombre de un canal, no un dato del solicitante
    for name, text in results.items():
        assert evidence.prepare(text, SECRETS) == text, name
        for field_name in fields:
            assert f'"{field_name}"' not in text, f"{name} trae el campo {field_name} de ApplicationIn"


def test_leak_the_messages_of_every_error_of_the_scenarios_carry_no_token(
    tworld: Rt2World, tmp_path: Path
) -> None:
    """Una corrida con fallos (401, 403, 409, 422, 500, tiempo agotado): ni el mensaje de `ApiError` ni el resultado traen un token, una contrasena ni un TOTP."""
    from vectra_verification.clients._api import ApiError, error_of

    bearer = SECRET_TOKEN + "-bearer"
    hostile = {
        "title": f"Authorization: Bearer {bearer}",
        "status": 500,
        "code": "internal_error",
        "correlation_id": "0" * 32,
        "type": "x",
    }
    for status, code in (
        (401, "unauthenticated"),
        (403, "forbidden"),
        (409, "conflict_state"),
        (422, "validation_error"),
        (500, "internal_error"),
    ):
        error = error_of(
            httpx.Response(status, json=problem(status, code), headers={"x-echo": f"Bearer {bearer}"})
        )
        assert bearer not in str(error) and "Bearer" not in str(error)
    assert bearer not in str(error_of(httpx.Response(500, json=hostile)))
    assert str(ApiError(0, "timeout")) == "http_0:timeout:-"
    for status, body in (
        (401, problem(401, "unauthenticated")),
        (403, problem(403, "forbidden")),
        (409, problem(409, "conflict_state")),
        (422, problem(422, "validation_error")),
        (500, problem(500, "internal_error")),
    ):
        tworld.register_overrides["rt3-a"] = lambda call, s=status, b=body: (s, b)  # type: ignore[misc]
        text = outcome_module.to_text(rt3_run(tworld, rt3_params(tmp_path)))
        assert evidence.prepare(text, SECRETS | {bearer}) == text
        assert "Bearer" not in text and "eyJ" not in text


def test_leak_the_filter_sees_a_jwt_in_a_scenario_result_and_a_loaded_secret() -> None:
    outcome, *_ = evaluate()
    text = outcome_module.to_text(outcome)
    with pytest.raises(evidence.EvidenceError, match="jwt"):
        evidence.prepare(text + " eyJhbGciOiJFUzI1NiJ9.eyJzdWIiOiJ4In0.c2ln", SECRETS)
    with pytest.raises(evidence.EvidenceError, match="secret"):
        evidence.prepare(text + " " + SECRET_TOKEN, SECRETS)


# --- ramas de error de los escenarios (cobertura de ramas de `scenarios/` >= 90 %) ------------------------------------------------


def test_rt2_setup_a_registration_rejected_with_422_fails_with_its_code(
    world: Rt2World, tmp_path: Path
) -> None:
    world.register_overrides[PROXY] = lambda call: (422, problem(422, "validation_error"))
    outcome = setup(world, versions(world, tmp_path))
    assert outcome.result == "falla" and outcome.missing == ("rt2_setup_registro_http_422_validation_error",)


def test_rt2_setup_a_version_that_does_not_exist_and_has_no_package_folder_fails(world: Rt2World) -> None:
    outcome = setup(world, [rt2.ProxyVersion(1, PROXY)])
    assert (
        outcome.result == "falla"
        and outcome.missing == ("rt2_setup_sin_paquete",)
        and world.registrations == []
    )


def test_rt2_setup_a_validation_call_refused_fails_and_a_bff_down_is_no_ejecutado(
    world: Rt2World, tmp_path: Path
) -> None:
    world.bff.doubles.governance.responders[("POST", "/v1/models/{id}/validations")] = lambda call: (
        403,
        problem(403, "forbidden"),
    )
    assert setup(world, versions(world, tmp_path)).missing == ("rt2_setup_validacion_http_403_forbidden",)
    world.bff.doubles.governance.fail(503)
    outcome = setup(world, versions(world, tmp_path, ids=("mv-otra-version",)))
    assert outcome.result == "no ejecutado" and outcome.missing == ("rt2_setup_dependencia_no_responde",)


def test_rt2_setup_an_approval_that_leaves_the_state_unchanged_or_the_same_user_fails(
    world: Rt2World, tmp_path: Path
) -> None:
    world.add_model(PROXY, "lista_para_aprobacion", registered_by="ingeniero-1")
    world.bff.doubles.governance.responders[("POST", "/v1/models/{id}/approval")] = lambda call: (204, None)
    outcome = setup(world, versions(world, tmp_path))
    assert outcome.missing == ("rt2_setup_no_quedo_aprobado",)
    world.bff.doubles.governance.responders[("POST", "/v1/models/{id}/approval")] = lambda call: (
        world.set_state(PROXY, "aprobado"),
        world.models[PROXY].update(approved_by="ingeniero-1"),
        (204, None),
    )[2]
    world.add_model(PROXY, "lista_para_aprobacion", registered_by="ingeniero-1")
    assert setup(world, versions(world, tmp_path)).missing == ("rt2_setup_aprobador_igual_al_registrante",)


def test_rt2_an_unknown_proxy_version_is_an_error_not_a_result(world: Rt2World) -> None:
    with pytest.raises(ScenarioError, match="rt2_modelo_desconocido"):
        rt2_run(world)


def test_rt2_without_a_freeze_the_message_says_when_there_is_no_prometheus_or_it_does_not_answer(
    rworld: Rt2World,
) -> None:
    rworld.freeze_after = None
    detail = next(s.detail for s in rt2_run(rworld, prom=False).rt2.subresults if s.name == "v1:freeze")
    assert "sin Prometheus" in detail
    fresh = Rt2World(freeze_after=None)
    try:
        fresh.add_model(REFERENCE, "activo")
        fresh.add_model(PROXY, "aprobado", registered_by="ingeniero-1", approved_by="cro-1")
        fresh.operator_promotes(60.0)
        original = fresh.prom_transport.handle_request

        def down_for_instant(request: httpx.Request) -> httpx.Response:
            if request.url.path.endswith("/query"):
                raise httpx.ConnectError("sin conexion")
            return original(request)

        fresh.prom_transport.handle_request = down_for_instant  # type: ignore[method-assign]
        detail = next(s.detail for s in rt2_run(fresh).rt2.subresults if s.name == "v1:freeze")
        assert "Prometheus no responde" in detail
    finally:
        fresh.close()


def test_rt2_a_package_with_a_value_that_is_not_json_fails_as_invalid() -> None:
    item = freeze_item(1)
    item["context_package"]["initial_disparity"] = {"attributes": [{"attribute": "sexo"}]}
    item["context_package"]["implicated"] = {1}  # un conjunto no se serializa a JSON
    assert rt2.judge_package(item) == ("rt2_paquete_invalido:json",)


def test_rt2_the_bias_phase_is_skipped_for_the_versions_after_the_first(rworld: Rt2World) -> None:
    deps = Rt2Deps(KIND, rworld.clock, rworld.sessions, rworld.simulator, rworld.registry, rworld.prom)
    run = rt2.Rt2Run(deps, Rt2Params(REFERENCE, [rt2.ProxyVersion(1, PROXY)], 7), Rt2State())
    skipped = rt2._sigue_congelada(run, rt2.ProxyVersion(2, "mv-2"), rt2.VersionState(), 1)
    assert skipped.result == "pasa" and skipped.readings == {"omitida": "solo en la primera version"}


def test_rt2_the_registry_not_answering_the_metrics_read_is_no_ejecutado_after_the_freeze_was_seen(
    rworld: Rt2World,
) -> None:
    original = rworld.registry_transport.handle_request

    def metrics_down(request: httpx.Request) -> httpx.Response:
        if request.url.params.get("projection") == "metrics":
            raise httpx.ConnectError("sin conexion")
        return original(request)

    rworld.registry_transport.handle_request = metrics_down  # type: ignore[method-assign]
    result = rt2_run(rworld)
    assert result.latency.result == "no ejecutado"
    assert any(s.missing == ("rt2_registro_no_responde",) for s in result.rt2.subresults)


def test_rt3_f22_with_a_state_outside_the_failclosed_or_cases_still_evaluating_fails() -> None:
    odd = rt3.judge_f22(
        [
            rt3.CaseReading("c1", "decidido", None, 1),
            rt3.CaseReading("c2", "en_sincronizacion", "timeout", 1),
        ],
        [],
    )
    assert "rt3_f22_estado_inesperado" in odd.missing
    waiting = rt3.judge_f22(
        [
            rt3.CaseReading("c1", "en_evaluacion", None, 2),
            rt3.CaseReading("c2", "en_sincronizacion", "timeout", 1),
        ],
        [],
    )
    assert waiting.missing == ("rt3_f22_caso_sin_estado_final",)
    assert rt3.judge_f22([], []).missing == ("rt3_f22_sin_casos_de_sonda",)


def test_rt3b_every_state_of_the_flow_has_its_own_code() -> None:
    ok = rt3.RegistrationReading(200)
    assert rt3.judge_rt3b(rt3.RegistrationReading(0, "timeout"), None, [], [], "mv").missing == (
        "rt3_dependencia_no_responde",
    )
    assert rt3.judge_rt3b(rt3.RegistrationReading(422, "validation_error"), None, [], [], "mv").missing == (
        "rt3b_registro_rechazado",
    )
    for state in (None, "registrado", "en_validacion"):
        assert rt3.judge_rt3b(ok, state, [], [], "mv").missing == ("rt3b_validacion_no_termina",)
    for state in ("lista_para_aprobacion", "aprobado"):
        assert rt3.judge_rt3b(ok, state, [], [], "mv").missing == ("rt3b_promocion_pendiente",)


def test_rt3_the_deployed_check_without_kubectl_not_found_or_failing_says_why(
    tworld: Rt2World, tmp_path: Path
) -> None:
    from vectra_verification.clients.k8s_read import K8sRead

    run = rt3.Rt3Run(
        Rt3Deps(KIND, tworld.clock, tworld.sessions, tworld.simulator, tworld.registry, None, None),
        rt3_params(tmp_path),
    )
    assert run.deployed_ready("isvc-a") == (None, "rt3_k8s_requerido")
    for message, code in (
        ('Error from server (NotFound): inferenceservices "x" not found', "rt3_inferenceservice_inexistente"),
        ("connection refused", "rt3_k8s_no_responde"),
    ):
        run.d.k8s = K8sRead(IsvcKubectl(fail=message))  # type: ignore[arg-type]
        assert run.deployed_ready("isvc-a") == (None, code)


def test_rt3_the_informative_reads_without_prometheus_or_with_it_failing_do_not_break(
    tworld: Rt2World, tmp_path: Path
) -> None:
    run = rt3.Rt3Run(
        Rt3Deps(KIND, tworld.clock, tworld.sessions, tworld.simulator, tworld.registry, None, None),
        rt3_params(tmp_path),
    )
    assert run.informative() == {"prometheus": "no disponible"}
    tworld.prom_transport.down = True
    run.d.prom = tworld.prom
    assert "prometheus" in run.informative()


def test_rt3_a_missing_deployed_name_or_a_missing_rt3b_package_is_no_ejecutado_and_does_not_lower_rt3(
    tworld: Rt2World, tmp_path: Path
) -> None:
    params = rt3_params(tmp_path, deployed={})
    without_b = Rt3Params({c: p for c, p in params.packages.items() if c != "RT3-b"}, 5)
    outcome = rt3_run(tworld, without_b)
    assert sub(outcome, "RT3-a-desplegado").missing == ("rt3_desplegado_sin_nombre",) and sub(
        outcome, "RT3-b"
    ).missing == ("rt3b_sin_paquete",)
    assert outcome.result == "pasa"


def test_rt3b_a_validation_refused_by_the_bff_is_a_failure_with_its_code(
    tworld: Rt2World, tmp_path: Path
) -> None:
    package = Rt3Package("RT3-b", make_package(tmp_path, RT3B), RT3B)
    tworld.register_overrides.pop("rt3-b")
    tworld.bff.doubles.governance.responders[("POST", "/v1/models/{id}/validations")] = lambda call: (
        403,
        problem(403, "forbidden"),
    )
    from vectra_verification.clients.k8s_read import K8sRead

    deps = Rt3Deps(
        KIND,
        tworld.clock,
        tworld.sessions,
        tworld.simulator,
        tworld.registry,
        K8sRead(IsvcKubectl()),
        tworld.prom,
    )  # type: ignore[arg-type]
    result = rt3._rt3b(rt3.Rt3Run(deps, rt3_params(tmp_path)), package)
    assert result.result == "falla" and result.missing == ("rt3b_http_403_forbidden",)


def test_rt3_the_closing_with_rejected_probes_or_the_bff_down_says_so(
    tworld: Rt2World, tmp_path: Path
) -> None:
    deps = Rt3Deps(KIND, tworld.clock, tworld.sessions, tworld.simulator, tworld.registry)
    tworld.simulator.accepted_ratio = 0.0
    assert rt3.rt3_closing(deps, rt3_params(tmp_path)).missing == ("rt3_cierre_sonda_rechazada",)
    tworld.simulator.accepted_ratio = 1.0
    tworld.bff.doubles.case.fail(503)
    closing = rt3.rt3_closing(deps, rt3_params(tmp_path))
    assert closing.result == "no ejecutado" and closing.missing == ("rt3_cierre_dependencia_no_responde",)


# --- ronda 2 (arbitraje): F-01 y F-02 -------------------------------------------------------------------------------------------


def test_rt3_f22_keeps_waiting_while_the_cases_are_en_evaluacion_even_with_attempts_at_1(
    tworld: Rt2World, tmp_path: Path
) -> None:
    tworld.state_cases = lambda case_id, record: (
        ("en_evaluacion", None, 1)
        if (tworld.clock.now() - record.created).total_seconds() < 7.0
        else ("en_sincronizacion", "timeout", 1)
    )
    outcome = rt3_run(tworld, rt3_params(tmp_path))
    assert outcome.result == "pasa", [
        (s.name, s.missing, s.detail) for s in outcome.subresults if s.result != "pasa"
    ]
    assert sub(outcome, "F22").readings["states"] == {"en_sincronizacion": 5}


def test_rt3_f22_cases_that_never_leave_en_evaluacion_fail_at_the_deadline_with_the_existing_code(
    tworld: Rt2World, tmp_path: Path
) -> None:
    tworld.state_cases = f22_cases(None, "en_evaluacion", 2)
    outcome = rt3_run(tworld, rt3_params(tmp_path))
    assert outcome.result == "falla" and outcome.missing == ("rt3_f22_caso_sin_estado_final",)
    assert sum(tworld.clock.sleeps) >= rt3.ATTEMPTS_TIMEOUT


def test_rt2_the_run_that_froze_is_not_one_more_bias_run_after_the_freeze(rworld: Rt2World) -> None:
    """F-02: con la corrida que congelo y solo 2 corridas mas, la fase no pasa (antes daba `pasa` unos 15 min antes de lo debido)."""
    result = rt2_run(rworld, params={"bias_timeout": 1900.0})
    assert result.rt2.result == "no ejecutado" and codes(result) == ("rt2_corridas_de_bias_pendientes",)
    assert "de 3 corridas" in next(s.detail for s in result.rt2.subresults if s.name == "v1:sigue_congelada")


def test_rt2_bias_counting_reference_is_the_first_mark_at_or_after_the_freeze() -> None:
    ts = [(1.0, 10.0), (2.0, 10.0), (3.0, 20.0), (4.0, 30.0), (5.0, 40.0)]
    ok = [(m, 1.0) for m, _ in ts]
    assert rt2.count_bias_runs(ts, ok, 15.0) == [30.0, 40.0]  # 20 es la que congelo: referencia, no cuenta
    assert rt2.count_bias_runs(ts, ok, 20.0) == [30.0, 40.0]
    assert rt2.count_bias_runs(ts, ok, 45.0) == []  # la corrida que congelo aun no termino: sin referencia
    assert rt2.count_bias_runs(ts, ok, 5.0) == [20.0, 30.0, 40.0]


# --- ronda 2: F-03, la costura de `ranged` -----------------------------------------------------------------------------------------


@pytest.mark.parametrize("extra", [0.0, 7.0, 14.0, 15.0, 22.0])
def test_rt5_ranged_never_asks_start_after_end_and_never_skips_or_repeats_a_point_at_the_seam(
    extra: float,
) -> None:
    start = NOW - timedelta(hours=60)
    end = start + timedelta(
        seconds=15.0 * (rt5.MAX_POINTS - 1) + extra
    )  # lo que sobra tras el primer tramo es menor que `step`
    spec = good_spec(counter=[(t, 0.0) for t in every(start, end)])
    double = PromDouble(spec)
    merged, saved = rt5.ranged(PromClient("http://prom", transport=double), rt5.COUNTER, start, end)
    asked = [(float(r.url.params["start"]), float(r.url.params["end"])) for r in double.requests]
    assert all(a <= b for a, b in asked), asked
    stamps = [t for t, _ in next(iter(merged.values()))]
    assert stamps == [
        start.timestamp() + 15.0 * n for n in range(int((end - start).total_seconds() // 15.0) + 1)
    ]  # sin huecos ni repetidos
    assert saved.end == end


# --- ronda 2: F-05 (infraestructura), F-07 (huecos de prueba) -----------------------------------------------------------------------

from vectra_verification.clients.k8s_read import K8sError
from vectra_verification.clients.oidc import OidcError


def forward_lost(request: httpx.Request) -> httpx.Response:
    raise K8sError("port_forward_lost:vectra-app/pod/decision-registry-0")


def test_rt2_a_lost_port_forward_is_no_ejecutado_with_its_code_and_keeps_the_resume_point(
    rworld: Rt2World,
) -> None:
    rworld.registry_transport.handle_request = forward_lost  # type: ignore[method-assign]
    result = rt2_run(rworld)
    assert (
        result.rt2.result == "no ejecutado"
        and codes(result) == ("rt2_port_forward_caido",)
        and result.pending == "freeze"
    )
    assert (
        result.state.versions[PROXY].done["lote"].result == "pasa"
        and result.state.versions[PROXY].batch is not None
    )
    assert result.latency.result == "no ejecutado"


def test_rt2_a_login_that_fails_is_no_ejecutado_with_its_code(rworld: Rt2World) -> None:
    def broken(user: str) -> Any:
        raise OidcError("login_timeout")

    rworld.oidc.login = broken  # type: ignore[method-assign]
    result = rt2_run(rworld)
    assert (
        result.rt2.result == "no ejecutado"
        and codes(result) == ("rt2_sesion_oidc_no_disponible",)
        and result.pending == "promocion"
    )
    assert "login_timeout" in result.rt2.subresults[-1].detail


def test_rt3_a_lost_port_forward_keeps_the_subresults_already_computed(
    tworld: Rt2World, tmp_path: Path
) -> None:
    tworld.registry_transport.handle_request = forward_lost  # type: ignore[method-assign]
    outcome = rt3_run(tworld, rt3_params(tmp_path))
    assert outcome.result == "no ejecutado" and outcome.missing[-1] == "rt3_port_forward_caido"
    assert [s.name for s in outcome.subresults][:4] == ["RT3-a", "RT3-c", "RT3-d", "sin_cambio_en_modelos"]
    assert outcome.readings["interrumpida_tras"][-1] == "RT3-b" and sub(outcome, "RT3-a").result == "pasa"


def test_rt3_a_login_that_fails_is_no_ejecutado(tworld: Rt2World, tmp_path: Path) -> None:
    def broken(user: str) -> Any:
        raise OidcError("login_rejected")

    tworld.oidc.login = broken  # type: ignore[method-assign]
    outcome = rt3_run(tworld, rt3_params(tmp_path))
    assert outcome.result == "no ejecutado" and outcome.missing == ("rt3_sesion_oidc_no_disponible",)


def test_rt5_a_lost_port_forward_or_a_kubectl_that_does_not_answer_is_no_ejecutado(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for message, code in (
        ("port_forward_lost:vectra-observability/pod/prometheus-0", "rt5_port_forward_caido"),
        ("get_failed:vectra-app/job:x", "rt5_kubectl_no_responde"),
    ):

        def failing(*args: Any, **kwargs: Any) -> Any:
            raise K8sError(message)

        monkeypatch.setattr(rt5, "read", failing)
        outcome, *_ = evaluate()
        assert outcome.result == "no ejecutado" and outcome.missing == (code,)


def test_rt5_a_run_id_with_no_stable_code_still_validates_before_reading() -> None:
    with pytest.raises(ValueError, match="run_id_invalid"):
        evaluate(run_id="x")


def test_rt3b_a_403_at_registration_is_a_failure_and_not_a_no_ejecutado() -> None:
    result = rt3.judge_rt3b(rt3.RegistrationReading(403, "forbidden"), None, [], [], RT3B)
    assert result.result == "falla" and result.missing == ("rt3b_registro_rechazado",)
    assert (
        combine([result, SubOutcome("RT3-a", "pasa")])[0] == "falla"
    )  # un `falla` opcional si baja RT-3 (P-2 (a))


def test_rt2_a_new_case_in_a_state_that_is_neither_listo_nor_modelo_congelado_fails(rworld: Rt2World) -> None:
    rworld.state_cases = lambda case_id, record: (
        ("no_disponible", "timeout", 6) if record.kind == "probe" else ("listo", None, 1)
    )
    result = rt2_run(rworld)
    assert codes(result) == ("rt2_caso_nuevo_no_quedo_modelo_congelado",) and result.pending == "casos_nuevos"
    assert "no_disponible" in next(s.detail for s in result.rt2.subresults if s.name == "v1:casos_nuevos")


def test_rt5_retention_is_compared_with_t0_and_not_with_t1() -> None:
    """La retencion cubre t1 pero no t0 (el Job duro 20 s): `no ejecutado`. Comparar con t1 lo dejaria pasar."""
    between = T0 + timedelta(seconds=10)
    outcome, *_ = evaluate(good_spec(lowest=between))
    assert outcome.result == "no ejecutado" and outcome.missing == ("rt5_retencion_no_cubre_t0",)
    assert evaluate(good_spec(lowest=T0))[0].result == "pasa"  # exactamente t0 cubre


# --- ronda 3: F-11, la marca de U9 va truncada al segundo -------------------------------------------------------------------------


def test_rt2_bias_counting_uses_the_truncated_second_of_the_freeze_as_the_reference() -> None:
    """F-11 (pura): el `recorded_at` es 20,4 y la marca de la corrida que congelo es 20 (truncada): es la referencia aunque sea menor que `after`."""
    ts = [(1.0, 10.0), (2.0, 20.0), (3.0, 30.0), (4.0, 40.0), (5.0, 50.0)]
    ok = [(m, 1.0) for m, _ in ts]
    assert rt2.count_bias_runs(ts, ok, 20.4) == [30.0, 40.0, 50.0]
    assert rt2.count_bias_runs(ts, ok, 20.0) == [30.0, 40.0, 50.0]
    assert rt2.count_bias_runs(ts, ok, 20.999) == [30.0, 40.0, 50.0]
    assert rt2.count_bias_runs(ts, ok, 21.0) == [40.0, 50.0]  # la marca 30 es la referencia si el freeze cae en el segundo 21


DELAYS = pytest.mark.parametrize("delay", [0.05, 0.9], ids=["mismo_segundo", "cruza_al_segundo_siguiente"])


@DELAYS
def test_rt2_f11_the_run_that_froze_plus_two_is_not_enough(rworld: Rt2World, delay: float) -> None:
    """F-11: con la marca entera de U9 (no posterior al `recorded_at`), la que congelo mas 2 no basta (freeze a 1 500 s, corridas cada 900 s, el `recorded_at` en .3 s: con 0,05 s la marca queda en el mismo segundo; con 0,9 s cruza)."""
    rworld.freeze_fraction, rworld.run_delay = 0.3, delay
    result = rt2_run(rworld, params={"bias_timeout": 1900.0})  # congelo + 2 corridas
    assert result.rt2.result == "no ejecutado" and codes(result) == ("rt2_corridas_de_bias_pendientes",)
    assert "solo 2 de 3" in next(s.detail for s in result.rt2.subresults if s.name == "v1:sigue_congelada")


@DELAYS
def test_rt2_f11_the_run_that_froze_plus_three_passes(rworld: Rt2World, delay: float) -> None:
    """F-11: la que congelo mas 3 da `pasa` (antes del arreglo el oraculo exigia 4 y daba `no ejecutado` en el tope de 3 600 s)."""
    rworld.freeze_fraction, rworld.run_delay = 0.3, delay
    result = rt2_run(rworld)
    assert result.rt2.result == "pasa", [(s.name, s.result, s.missing) for s in result.rt2.subresults]


def test_rt2_f12_a_403_in_the_freeze_phase_is_not_reported_as_no_freeze_at_the_cap(rworld: Rt2World) -> None:
    """F-12: solo `rt2_freeze_ausente` (sin freeze al tope de 2 700 s) da `rt2_latencia_sin_freeze` y su texto; un 403 en el primer sondeo no."""
    rworld.freezes_status = 403
    result = rt2_run(rworld)
    assert result.pending == "freeze" and codes(result) == ("rt2_http_403_forbidden",)
    assert result.rt2.result == "falla"
    assert result.latency.missing != ("rt2_latencia_sin_freeze",)
    assert "sin freeze al tope" not in result.latency.obtained
