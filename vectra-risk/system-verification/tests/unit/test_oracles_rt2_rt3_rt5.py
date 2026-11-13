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
    JOB,
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
    outcome = rt5.run(K8sRead(kubectl), PromClient("http://prom", transport=double), clock, run_id, started_at, environment=KIND)
    return outcome, clock, kubectl, double


def test_rt5_correct_job_log_alert_series_and_counter_pass() -> None:
    outcome, _, _, _ = evaluate()
    assert outcome.result == "pasa" and outcome.missing == ()
    assert outcome.readings["log_proxy_error_present"] is True and outcome.readings["deny_max"] == 1.0 and outcome.readings["counter_max"] == 0.0


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
    counter = [(t, 0.0) for t in every(STARTED, T1)] + [(t, 1.0) for t in every(T1 + timedelta(seconds=15), NOW)]
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
    outcome, _, _, _ = evaluate(kubectl=JobKubectl(Completed(1, "", 'Error from server (Forbidden): jobs.batch "x" is forbidden')))
    assert outcome.result == "no ejecutado" and outcome.missing == ("rt5_k8s_forbidden",)


def test_rt5_failed_job_without_completion_time_is_falla_with_the_log_line() -> None:
    outcome, _, _, _ = evaluate(kubectl=JobKubectl(failed_job(T0), log="rt5-demo: POST http://x -> 200 l5d-proxy-error: None\n"))
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
    assert rt5.DENY == 'sum(inbound_http_authz_deny_total{namespace="vectra-mock", route_name="core-mock-catch-all"})'
    assert rt5.COUNTER == "sum(vectra_core_write_attempts_total)" and rt5.RETENTION == "prometheus_tsdb_lowest_timestamp_seconds"
    seen = {r.url.params["query"] for r in double.requests}
    assert seen == literal
    assert all("increase(" not in q and "[" not in q for q in seen)
    assert all(r.url.params["step"] == "15.0" for r in double.requests if r.url.path.endswith("query_range"))
    saved = {q.query: q for q in outcome.queries}
    assert set(saved) == literal
    assert saved[rt5.ALERT].step == 15.0 and saved[rt5.ALERT].start == T0 and saved[rt5.ALERT].end == T1 + timedelta(minutes=15)
    assert saved[rt5.COUNTER].start == STARTED
    assert {c[1] for c in kubectl.calls} == {"get", "logs"}


def test_rt5_a_window_over_11000_points_is_split_and_the_points_joined() -> None:
    start = NOW - timedelta(hours=60)  # 60 h a 15 s son 14 400 puntos
    counter = [(t, 0.0) for t in every(start, NOW - timedelta(hours=1))] + [(NOW - timedelta(minutes=5), 1.0)]
    outcome, _, _, double = evaluate(good_spec(counter=counter), started_at=start)
    assert outcome.result == "falla" and outcome.missing == ("rt5_contador_del_mock_mayor_que_0",)  # el pico esta en el ultimo tramo
    ranges = [r for r in double.requests if r.url.path.endswith("query_range") and r.url.params["query"] == rt5.COUNTER]
    assert len(ranges) == 2 and all((float(r.url.params["end"]) - float(r.url.params["start"])) / 15 <= 11_000 for r in ranges)
    saved = next(q for q in outcome.queries if q.query == rt5.COUNTER)
    assert len(saved.result[0]["values"]) > 11_000


def test_rt5_without_splitting_the_double_rejects_the_long_window() -> None:
    http = PromClient("http://prom", transport=PromDouble(good_spec()))
    from vectra_verification.clients.prom import ObsError

    with pytest.raises(ObsError, match="bad_data"):
        http.query_range(rt5.COUNTER, NOW - timedelta(hours=60), NOW, 15.0)


def test_rt5_right_after_the_job_polls_every_15_seconds_until_the_window_closes() -> None:
    now = T1 + timedelta(minutes=1)
    outcome, clock, _, _ = evaluate(good_spec(alert=[], deny=[], counter=[(t, 0.0) for t in every(STARTED, now)], lowest=now - timedelta(days=1)), now=now)
    assert outcome.result == "falla"
    assert set(clock.sleeps) == {15.0} and abs(sum(clock.sleeps) - 14 * 60) < 1  # hasta t1 + 15 min, sin dormir de verdad


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
    assert 'namespace="vectra-mock"' in outcome.obtained and 'route_name="core-mock-catch-all"' in outcome.obtained
    assert "nadie raspa el proxy de Linkerd de vectra-mock" in outcome.obtained


def test_rt5_missing_series_with_other_labels_lists_the_labels_that_exist() -> None:
    outcome, _, _, _ = evaluate(good_spec(deny=[], other_family=[("vectra-app", "case-api"), ("vectra-mock", "otra-ruta")]))
    assert outcome.result == "falla" and outcome.missing[0] == "rt5_serie_denegaciones_ausente"
    assert 'namespace="vectra-app", route_name="case-api"' in outcome.obtained and 'route_name="otra-ruta"' in outcome.obtained
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
        rt5.run(K8sRead(kubectl), PromClient("http://prom", transport=double), FakeClock(NOW), RUN_ID, STARTED, environment=guard.STAGING)
    assert kubectl.calls == [] and double.requests == []


def test_guard_an_environment_of_production_is_not_known() -> None:
    production = guard.Environment("prod", "vectra.banco.internal", "https://vectra.banco.internal/auth/realms/vectra")
    kubectl, double = JobKubectl(completed_job(T0, T1)), PromDouble(good_spec())
    with pytest.raises(guard.GuardError, match="environment_not_allowed"):
        rt5.run(K8sRead(kubectl), PromClient("http://prom", transport=double), FakeClock(NOW), RUN_ID, STARTED, environment=production)
    assert kubectl.calls == [] and double.requests == []


def test_rt5_json_helpers_are_valid() -> None:
    assert json.loads(completed_job(T0, T1))["status"]["completionTime"] == iso(T1)
    assert httpx.Request("GET", "http://x").method == "GET"
    assert PROXY_LOG.startswith("rt5-demo: POST")
