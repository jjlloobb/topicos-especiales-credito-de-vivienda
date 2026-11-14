"""CA-7 (U12-T03, Paso 8, «Ademas, contra un Prometheus real»): las consultas de RT-5 contra un Prometheus **real** por digest.

Prometheus de Testcontainers sobre un bloque TSDB creado con `promtool tsdb create-blocks-from openmetrics` (de la misma imagen) a partir de un `Rt5Spec` con tiempos relativos a «ahora». Cada caso corre **dos veces**, con el
doble de Prometheus de `test_oracles_rt2_rt3_rt5.py` y con el real, y compara: mismo resultado y mismos codigos. Cada expresion del oraculo debe aceptarla la API (sin `bad_data`). Corre en `make check`, sin cluster.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fake_clock import FakeClock
from prometheus_tc import prometheus_with
from rt5_world import RUN_ID, JobKubectl, PromDouble, Rt5Spec, completed_job, every
from vectra_verification import guard
from vectra_verification.clients.k8s_read import K8sRead
from vectra_verification.clients.prom import ObsError, PromClient
from vectra_verification.scenarios import rt5

pytestmark = pytest.mark.integration

BASE = datetime.now(
    UTC
).replace(
    microsecond=0
)  # los datos son relativos a «ahora»; `fresh_base` lo recalcula al empezar cada prueba (la suite corre minutos despues de la coleccion)
T0 = BASE - timedelta(hours=6)
T1 = T0 + timedelta(seconds=20)
STARTED = T0 - timedelta(minutes=2)
WINDOW_END = T1 + timedelta(minutes=5)


@pytest.fixture(autouse=True)
def fresh_base() -> None:
    global BASE, T0, T1, STARTED, WINDOW_END
    BASE = datetime.now(UTC).replace(microsecond=0)
    T0 = BASE - timedelta(hours=6)
    T1 = T0 + timedelta(seconds=20)
    STARTED = T0 - timedelta(minutes=2)
    WINDOW_END = T1 + timedelta(minutes=5)


def spec(**over: object) -> Rt5Spec:
    built = Rt5Spec(
        started_at=STARTED,
        alert=every(T0, WINDOW_END),
        deny=[
            (t, 1.0) for t in every(T0 + timedelta(seconds=5), T1 + timedelta(minutes=14))
        ],  # nace en 1 y no crece
        counter=[(t, 0.0) for t in every(STARTED, BASE)],
    )
    for key, value in over.items():
        setattr(built, key, value)
    return built


def real_lowest(prom: PromClient) -> datetime:
    value = rt5._scalar(prom.query(rt5.RETENTION, datetime.now(UTC)))
    assert value is not None, (
        "Prometheus no se raspa a si mismo: falta prometheus_tsdb_lowest_timestamp_seconds"
    )
    return datetime.fromtimestamp(value, UTC)


def judged(
    base_url: str,
    data: Rt5Spec,
    *,
    t0: datetime | None = None,
    t1: datetime | None = None,
    started: datetime | None = None,
) -> tuple[rt5.Outcome, rt5.Outcome]:
    """El mismo caso con el doble y con Prometheus real. `lowest` del doble es el real (la fecha del primer dato depende de como `promtool` parte los bloques)."""
    t0, t1, started = (
        t0 or T0,
        t1 or T1,
        started or STARTED,
    )  # los de esta prueba (`fresh_base`), no los de la importacion
    with_real = PromClient(base_url)
    try:
        data.lowest = real_lowest(with_real)
        now = datetime.now(UTC)
        kubectl = JobKubectl(completed_job(t0, t1))
        real = rt5.run(K8sRead(kubectl), with_real, FakeClock(now), RUN_ID, started, environment=guard.KIND)
        double = rt5.run(
            K8sRead(JobKubectl(completed_job(t0, t1))),
            PromClient("http://prom", transport=PromDouble(data)),
            FakeClock(now),
            RUN_ID,
            started,
            environment=guard.KIND,
        )
    finally:
        with_real.close()
    return real, double


def same(real: rt5.Outcome, double: rt5.Outcome) -> None:
    assert (real.result, real.missing) == (double.result, double.missing), (real, double)


def test_rt5_promql_denial_series_born_at_1_and_alert_in_the_window_evaluated_6_hours_later_pass() -> None:
    data = spec()
    with prometheus_with(data) as url:
        real, double = judged(url, data)
        same(real, double)
        assert real.result == "pasa", real
        assert (
            real.readings["deny_max"] == 1.0
            and real.readings["counter_max"] == 0.0
            and real.readings["alert_points"] > 0
        )


def test_rt5_promql_every_expression_is_accepted_by_the_api_and_a_range_inside_promql_is_bad_data() -> None:
    data = spec()
    with prometheus_with(data) as url:
        prom = PromClient(url)
        for expression in (rt5.ALERT, rt5.DENY, rt5.COUNTER):
            assert prom.query_range(expression, T0, T1 + timedelta(minutes=15), 15.0).result_type == "matrix"
        for expression in (rt5.RETENTION, rt5.FAMILY_COUNT, rt5.FAMILY_LABELS):
            assert prom.query(expression, datetime.now(UTC)).result_type == "vector"
        with pytest.raises(
            ObsError, match="bad_data"
        ):  # un rango `[t0, ...]` dentro de PromQL: el error real
            prom.query_range(
                f"sum(inbound_http_authz_deny_total[{int((BASE - T0).total_seconds())}s])", T0, BASE, 15.0
            )
        with pytest.raises(ObsError, match="bad_data"):
            prom.query_range("increase(vectra_core_write_attempts_total[5m]) >", T0, BASE, 15.0)
        prom.close()


def test_rt5_promql_a_window_over_11000_points_is_rejected_unsplit_and_accepted_split() -> None:
    data = spec()
    with prometheus_with(data) as url:
        prom = PromClient(url)
        start = BASE - timedelta(hours=60)  # 14 400 puntos a 15 s
        with pytest.raises(ObsError, match="bad_data"):
            prom.query_range(rt5.COUNTER, start, BASE, 15.0)
        merged, saved = rt5.ranged(prom, rt5.COUNTER, start, BASE, 15.0)
        points = [value for values in merged.values() for _, value in values]
        assert points and max(points) == 0.0 and saved.start == start and saved.end == BASE
        prom.close()


def test_rt5_promql_the_alert_outside_the_window_fails_and_the_double_agrees() -> None:
    data = spec(alert=every(T1 + timedelta(hours=1), T1 + timedelta(hours=1, minutes=5)))
    with prometheus_with(data) as url:
        real, double = judged(url, data)
        same(real, double)
        assert real.result == "falla" and real.missing == ("rt5_alerta_core_write_attempt_ausente",)


def test_rt5_promql_the_mock_counter_at_0_passes_and_at_1_fails() -> None:
    zero = [(t, 0.0) for t in every(STARTED, T1 + timedelta(minutes=1))]
    one = [(t, 1.0) for t in every(T1 + timedelta(minutes=1, seconds=15), BASE)]
    data = spec(counter=zero + one)
    with prometheus_with(data) as url:
        real, double = judged(url, data)
        same(real, double)
        assert real.result == "falla" and real.missing == ("rt5_contador_del_mock_mayor_que_0",)


def test_rt5_promql_t0_before_the_first_datum_is_no_ejecutado() -> None:
    data = spec()
    with prometheus_with(data) as url:
        early = T0 - timedelta(days=2)
        real, double = judged(
            url, data, t0=early, t1=early + timedelta(seconds=20), started=early - timedelta(minutes=2)
        )
        same(real, double)
        assert real.result == "no ejecutado" and real.missing == ("rt5_retencion_no_cubre_t0",)


def test_rt5_promql_missing_series_the_family_absent_or_with_other_labels() -> None:
    data = spec(deny=[], alert=[])
    with prometheus_with(data) as url:
        real, double = judged(url, data)
        same(real, double)
        assert real.result == "falla" and real.missing[:2] == (
            "rt5_serie_denegaciones_ausente",
            "rt5_alerta_core_write_attempt_ausente",
        )
        assert "nadie raspa el proxy de Linkerd" in real.obtained
    other = spec(deny=[], other_family=[("vectra-app", "case-api")], other_until=BASE)
    with prometheus_with(other) as url:
        real, double = judged(url, other)
        same(real, double)
        assert (
            'namespace="vectra-app", route_name="case-api"' in real.obtained
            and "nadie raspa" not in real.obtained
        )


def test_rt5_promql_the_seam_with_a_remainder_smaller_than_the_step_is_not_asked_past_the_end() -> None:
    """F-03 (ronda 2): si lo que sobra tras un tramo es menor que `step`, Prometheus real responde `bad_data` a un `start > end`; `ranged` no lo pide y no pierde ni repite ningun punto."""
    data = spec(counter=[(t, 0.0) for t in every(BASE - timedelta(hours=48), BASE)])
    with prometheus_with(data) as url:
        prom = PromClient(url)
        end = datetime.now(UTC).replace(microsecond=0)
        start = end - timedelta(
            seconds=15.0 * (rt5.MAX_POINTS - 1) - 8.0
        )  # un tramo completo y 8 s... menos de 15 s de resto
        start = end - timedelta(seconds=15.0 * (rt5.MAX_POINTS - 1) + 7.0)
        merged, saved = rt5.ranged(prom, rt5.COUNTER, start, end, 15.0)
        stamps = [t for t, _ in next(iter(merged.values()))]
        assert (
            stamps == [start.timestamp() + 15.0 * n for n in range(len(stamps))]
            and len(stamps) == int((end - start).total_seconds() // 15) + 1
        )
        assert saved.end == end
        prom.close()
