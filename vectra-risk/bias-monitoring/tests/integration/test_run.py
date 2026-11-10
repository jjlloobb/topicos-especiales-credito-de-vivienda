"""Paso 8: la corrida completa contra los dobles (BR-U9-08..14, 20; P-U9-01, 07; NFR-U9-01, 04, 20, 21; US-302, US-303, US-308)."""

from __future__ import annotations

import asyncio
import io
import json
import resource
import time
import tracemalloc
from datetime import UTC, datetime, timedelta

import pytest
from builders import full_catalog
from scenario import NOW, clear, make_deps, seed
from support import load_u5_counts
from vectra_bias import config
from vectra_bias.run import EXIT_FAILED, EXIT_OK, EXIT_PUSH, log_outcome, run_once
from vectra_contracts.catalog import LOG_RECORD_FIELDS
from world import World, freeze_record

TODAY = NOW.date()


def go(world: World, now: datetime = NOW, **kwargs):
    deps = make_deps(world, lambda: now, **kwargs)
    return asyncio.run(run_once(deps))


def gauge(world: World, group: str, name: str, **labels: str) -> str | None:
    return world.pushgateway.value(group, name, **labels)


def u5_world(variant: str) -> World:
    world = World()
    for version in ("v1",):
        world.registry.add_day(version, "modelo", TODAY, load_u5_counts(variant))
    return world


# --- RT-2 y las reglas (US-302, US-303) ----------------------------------------------------------------------------------


def test_rt2_the_proxy_variant_freezes_with_region_as_the_trigger_attribute():
    world = u5_world("proxy")
    outcome = go(world)
    assert outcome.report.complete and outcome.exit_code == EXIT_OK
    assert world.governance.frozen == {"v1"}
    package = world.governance.packages[0]
    assert package.trigger_attribute == "region"
    assert [i["attribute"] for i in package.implicated] == [
        "region"
    ]  # los que cumplen R4 (el limite de estrato es 0,0277)
    assert package.after.trigger_attribute == "region"
    assert package.before == "sin_datos"
    assert gauge(world, "success", "vectra_bias_last_success_timestamp") is not None


def test_rt2_the_base_model_does_not_freeze():
    world = u5_world("base")
    outcome = go(world)
    assert outcome.report.complete
    assert world.governance.calls == []
    assert gauge(world, "run", "vectra_bias_rule_met", model_version_id="v1", population="modelo") == "0"


# BR-U9-14: la poblacion humana nunca congela, pero la regla se evalua igual para `vectra_bias_rule_met{population="humana"}`.
def test_high_human_and_low_model_sets_rule_met_for_humana_and_never_calls_freeze():
    world = World()
    seed(world, "v1", TODAY, model="low", human="high")
    outcome = go(world)
    assert outcome.report.complete
    assert gauge(world, "run", "vectra_bias_rule_met", model_version_id="v1", population="humana") == "1"
    assert gauge(world, "run", "vectra_bias_rule_met", model_version_id="v1", population="modelo") == "0"
    assert world.governance.calls == []


def test_a_high_human_population_does_not_freeze_even_when_the_model_is_also_high_in_another_version():
    world = World()
    seed(world, "v1", TODAY, model="low", human="high")
    seed(world, "v2", TODAY, model="high", human="low")
    go(world)
    assert world.governance.frozen == {"v2"}


def test_after_the_freeze_a_1_pp_measurement_makes_no_call():
    world = World()
    seed(world, "v1", TODAY, model="high")
    go(world)
    assert world.governance.frozen == {"v1"}
    calls = len(world.governance.calls)
    clear(world, "v1")
    seed(world, "v1", TODAY, model="low")
    again = go(world, NOW + timedelta(minutes=15))
    assert again.report.complete
    assert len(world.governance.calls) == calls


def test_the_departure_rate_is_part_of_the_human_result():
    world = World()
    seed(world, "v1", TODAY, model="low", human="low")
    outcome = go(world)
    human = outcome.report.versions[0].human.result
    assert human.population == "humana"
    assert human.departure_rates, "con 600 decisiones por celda y dia hay tasa de apartamiento"
    assert all(0 <= float(d.rate) <= 1 for d in human.departure_rates)


# --- invalidas y agregador ------------------------------------------------------------------------------------------------


def _invalid_world(invalid_per_day: int) -> World:
    world = World()
    seed(world, "v1", TODAY, days=1, model="high", n=100, invalid_per_day=invalid_per_day)
    return world


def test_invalid_entries_at_0_5_percent_complete_the_run():
    world = _invalid_world(0)
    total = world.registry.entries[("v1", "modelo", TODAY)][0]
    world = _invalid_world(round(total * 0.005))
    outcome = go(world)
    assert outcome.report.complete
    assert int(gauge(world, "run", "vectra_bias_invalid_entries")) > 0
    assert world.governance.frozen == {"v1"}


def test_invalid_entries_at_1_5_percent_fail_the_run_without_freezing():
    world = _invalid_world(0)
    total = world.registry.entries[("v1", "modelo", TODAY)][0]
    world = _invalid_world(round(total * 0.015))
    outcome = go(world)
    assert not outcome.report.complete and outcome.report.failure_reason == "invalidas"
    assert outcome.exit_code == EXIT_FAILED
    assert world.governance.calls == []
    assert gauge(world, "run", "vectra_bias_last_run_failure", reason="invalidas") == "1"
    assert "success" not in world.pushgateway.names()


def test_the_ratio_exactly_at_1_percent_does_not_fail():
    world = World()
    seed(world, "v1", TODAY, days=1, model="low", n=100)
    base = world.registry.entries[("v1", "modelo", TODAY)][0]
    clear(world, "v1")
    # invalidas i y total t = base + i (las invalidas suman al total): i / t = 1 % <=> i = base / 99
    seed(world, "v1", TODAY, days=1, model="low", n=100, invalid_per_day=base // 99)
    total, invalid = world.registry.entries[("v1", "modelo", TODAY)]
    assert invalid * 100 == total or invalid * 100 < total * 1.0001
    assert go(world).report.complete


def test_an_unattributable_decision_counts_once_on_both_sides_even_with_two_range_requests():
    world = World()
    for v in ("v1", "v2", "v3", "v4"):
        seed(world, v, TODAY, days=10, model="low", human="low", n=100)
    world.registry.unattributable[TODAY] = 1
    outcome = go(world)
    posts = [c for c in world.registry.calls if c.method == "POST"]
    assert [len(c.body.ranges) for c in posts] == [1, 12, 4]  # descubrimiento + 12 + 4
    assert [c.body.unattributable_range is not None for c in posts] == [True, False, False]  # solo la primera
    assert outcome.report.complete
    assert gauge(world, "run", "vectra_bias_invalid_entries") == "1"
    window = [TODAY - timedelta(days=d) for d in range(10)]
    entries = [
        world.registry.entries[(v, p, day)][0]
        for v in ("v1", "v2", "v3", "v4")
        for p in ("modelo", "humana")
        for day in window
    ]
    assert gauge(world, "run", "vectra_bias_total_entries") == str(sum(entries) + 1)


# BR-U9-10: todo o nada: un agregador atrasado hace fallar la corrida, sin congelar con datos parciales.
def test_an_aggregator_lagging_45_minutes_fails_the_run():
    world = World()
    seed(world, "v1", TODAY, model="high")
    world.registry.lag_seconds = 45 * 60
    outcome = go(world)
    assert outcome.report.failure_reason == "agregador_atrasado"
    assert world.governance.calls == [] and "success" not in world.pushgateway.names()
    world.registry.lag_seconds = 30 * 60
    assert go(world, NOW + timedelta(minutes=15)).report.complete  # 30 min exactos no es atraso


# --- escenarios P-U9-07 ---------------------------------------------------------------------------------------------------


# BR-U9-10: todo o nada: si falla la lectura del registro la corrida falla y no congela.
def test_e1_registry_down_fails_the_run_with_lectura_and_the_model_keeps_serving():
    world = World()
    seed(world, "v1", TODAY, model="high")
    world.registry.status = 503
    outcome = go(world)
    assert outcome.report.failure_reason == "lectura" and outcome.exit_code == EXIT_FAILED
    assert world.governance.calls == []
    assert gauge(world, "run", "vectra_bias_last_run_failure", reason="lectura") == "1"


def test_e1_a_registry_too_slow_is_a_reading_failure():
    world = World()
    seed(world, "v1", TODAY, model="high")
    world.registry.delay = 60.0
    assert go(world).report.failure_reason == "lectura"


def test_e3_governance_down_tries_4_times_per_version_and_the_others_are_still_tried():
    world = World()
    seed(world, "v1", TODAY, model="high")
    seed(world, "v2", TODAY, model="high")
    world.governance.script["v1"] = ["5xx"] * 10
    outcome = go(world)
    assert outcome.report.failure_reason == "freeze" and not outcome.report.complete
    assert len(world.governance.freeze_calls("v1")) == 4
    assert len(world.governance.freeze_calls("v2")) == 1
    assert world.governance.frozen == {"v2"}
    assert world.pushgateway.names() >= {"run", "freeze-v1"} and "freeze-v2" not in world.pushgateway.names()
    assert "success" not in world.pushgateway.names()
    world.governance.script.clear()
    second = go(world, NOW + timedelta(minutes=15))
    assert (
        second.report.complete and "freeze-v1" not in world.pushgateway.names()
    )  # la corrida siguiente vuelve a intentar


def test_e4_pushgateway_down_exits_non_zero_but_the_freeze_stays_applied():
    world = World()
    seed(world, "v1", TODAY, model="high")
    world.pushgateway.down = True
    outcome = go(world)
    assert outcome.exit_code == EXIT_PUSH != 0
    assert outcome.report.complete and world.governance.frozen == {"v1"}
    assert outcome.published is not None and outcome.published.errors


class Killed(BaseException):
    """El pod muere a mitad de corrida: no es una `Exception`, nada de `run` lo atrapa."""


def test_e5_the_pod_dies_midway_without_partial_freezes_and_the_next_run_evaluates_the_rest():
    world = World()
    seed(world, "v1", TODAY, model="high")
    seed(world, "v2", TODAY, model="high")

    def die_after_the_first_freeze(version: str) -> None:
        raise Killed

    world.governance.on_freeze = die_after_the_first_freeze
    with pytest.raises(Killed):
        go(world)
    assert world.governance.frozen == {"v1"}  # el freeze ya aplicado se mantiene; v2 aun no
    assert "success" not in world.pushgateway.names()
    world.governance.on_freeze = None
    again = go(world, NOW + timedelta(minutes=15))
    assert again.report.complete and world.governance.frozen == {"v1", "v2"}
    assert [c.status for c in world.governance.freeze_calls("v1")] == [204, 409]


def test_e5_dying_during_the_reading_never_freezes():
    world = World()
    seed(world, "v1", TODAY, model="high")
    original = world.registry.handle
    state = {"posts": 0}

    async def die_on_the_second_query(request):
        if request.method == "POST":
            state["posts"] += 1
            if state["posts"] == 2:
                raise Killed
        return await original(request)

    world.registry.transport = lambda: __import__("httpx").MockTransport(die_on_the_second_query)
    with pytest.raises(Killed):
        go(world)
    assert world.governance.calls == []


def test_e7_keycloak_down_fails_before_any_call_with_token_and_no_last_success():
    world = World()
    seed(world, "v1", TODAY, model="high")
    world.keycloak.down = True
    outcome = go(world)
    assert outcome.report.failure_reason == "token"
    assert world.registry.calls == [] and world.governance.calls == []
    assert len(world.keycloak.requests) == config.TOKEN_ATTEMPTS == 2
    assert gauge(world, "run", "vectra_bias_last_run_failure", reason="token") == "1"
    assert "success" not in world.pushgateway.names()


# --- reactivacion ---------------------------------------------------------------------------------------------------------


def test_after_a_reactivation_on_day_d_the_runs_of_d_and_d_plus_1_do_not_freeze_and_new_data_does():
    world = World()
    d = TODAY
    seed(world, "v1", d, days=30, model="high")
    world.registry.freezes = [
        freeze_record("v1", NOW - timedelta(days=1), [("reactivar", NOW.replace(hour=23, minute=50))])
    ]
    on_d = go(world, NOW.replace(hour=23, minute=55))
    assert on_d.report.complete and world.governance.calls == []
    next_day = d + timedelta(days=1)
    on_d1 = go(world, datetime(next_day.year, next_day.month, next_day.day, 0, 15, tzinfo=UTC))
    assert on_d1.report.complete and world.governance.calls == []  # ventana desde D + 1: sin muestra
    assert gauge(world, "run", "vectra_bias_rule_met", model_version_id="v1", population="modelo") == "0"
    seed(world, "v1", next_day, days=1, model="high")  # datos nuevos con 12 pp o mas
    on_d1_later = go(world, datetime(next_day.year, next_day.month, next_day.day, 6, 0, tzinfo=UTC))
    assert on_d1_later.report.complete and world.governance.frozen == {"v1"}
    assert world.governance.packages[0].window_start == next_day


# --- logs ----------------------------------------------------------------------------------------------------------------


def test_run_logs_use_only_catalog_fields_and_invalid_entries_only_a_seq(monkeypatch):
    from vectra_common.logging import configure

    monkeypatch.setenv("VECTRA_LOG_STRICT", "1")
    stream = io.StringIO()
    configure("bias-monitoring-job", stream)
    world = World()
    seed(world, "v1", TODAY, days=1, model="high", n=100, invalid_per_day=1)
    world.registry.invalid_seqs = [41, 42]
    world.governance.script["v1"] = ["5xx"] * 10
    outcome = go(world)
    log_outcome(outcome, 12)
    lines = [json.loads(line) for line in stream.getvalue().splitlines()]
    assert lines
    assert all(set(line) <= LOG_RECORD_FIELDS for line in lines)
    invalid = [line for line in lines if "seq" in line]
    assert [line["seq"] for line in invalid] == [41, 42]
    assert all(set(line) <= {"seq", "timestamp", "level", "service", "event"} for line in invalid)
    assert any(line.get("status") == "fallida" and line.get("error_code") == "freeze" for line in lines)


# --- duracion y memoria (NFR-U9-01, 04) -----------------------------------------------------------------------------------


def test_a_run_with_3_versions_and_dense_cells_takes_under_2_minutes_and_reports_its_peak_memory():
    world = World()
    for v, gap in (("v1", 0.2), ("v2", 0.0), ("v3", 0.2)):
        for d in range(37):
            day = TODAY - timedelta(days=d)
            world.registry.add_day(v, "modelo", day, full_catalog(rate_gap=gap, n=60))
            world.registry.add_day(v, "humana", day, full_catalog(rate_gap=0.0, n=40), decisions=True)
    tracemalloc.start()
    began = time.monotonic()
    outcome = go(world)
    elapsed = time.monotonic() - began
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    rss_mib = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
    print(
        f"run_duration_s={elapsed:.2f} tracemalloc_peak_mib={peak / 2**20:.1f} process_maxrss_mib={rss_mib:.0f}"
    )
    assert outcome.report.complete
    assert elapsed < 120
    assert world.governance.frozen == {"v1", "v3"}
    assert peak / 2**20 < 0.7 * 256  # NFR-U9-04: 70 % de 256 MiB


def test_python_dash_m_vectra_bias_run_starts_and_a_missing_configuration_is_a_failed_run():
    import subprocess
    import sys

    result = subprocess.run(  # noqa: S603 - el interprete de las pruebas, sin entrada externa
        [sys.executable, "-m", "vectra_bias.run"],
        capture_output=True,
        text=True,
        env={"PATH": "/usr/bin"},
        check=False,
    )
    assert result.returncode == EXIT_FAILED
    line = json.loads(result.stdout.strip().splitlines()[-1])
    assert line["error_code"] == "configuracion" and set(line) <= LOG_RECORD_FIELDS
