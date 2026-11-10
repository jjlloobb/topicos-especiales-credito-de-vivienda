"""Paso 7: `publish` contra el doble del Pushgateway (BR-U9-20, F106; P-U9-05, P-U9-02; NFR-U9-22)."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

from builders import batch_client, population_report, uniform, with_gap
from vectra_bias import config
from vectra_bias.freeze_client import CONFLICT, FAILED, FROZEN, FreezeOutcome
from vectra_bias.publish import RunReport, VersionReport, publish
from world import PUSHGATEWAY_URL, World

T0 = datetime(2026, 11, 9, 12, 0, tzinfo=UTC)
HIGH = with_gap("region", 0.2, 2000)  # cumple la regla
LOW = uniform(0.5, 2000)  # no la cumple


def run(coro):
    return asyncio.run(coro)


def client(world: World):
    return batch_client("pushgateway", PUSHGATEWAY_URL, world.pushgateway.transport())


def version(v: str, counts=LOW, freeze: FreezeOutcome | None = None) -> VersionReport:
    return VersionReport(
        v, population_report(counts, "modelo", v), population_report(uniform(0.5, 100), "humana", v), freeze
    )


def report(
    *versions: VersionReport,
    minute: int = 0,
    complete: bool = True,
    reason: str | None = None,
    calculated: bool = True,
) -> RunReport:
    finished = T0 + timedelta(minutes=minute)
    return RunReport(finished, finished, complete, reason, calculated, tuple(versions), 0, 100)


def ok(attempts: int = 1, outcome: str = FROZEN) -> FreezeOutcome:
    return FreezeOutcome(outcome, attempts)


def failed() -> FreezeOutcome:
    return FreezeOutcome(FAILED, 4, "status_503")


# --- grupos run y success ------------------------------------------------------------------------------------------------


def test_a_complete_run_pushes_run_and_success_with_put():
    world = World()
    result = run(publish(client(world), report(version("v1"))))
    assert result.ok
    assert world.pushgateway.names() == {"run", "success"}
    assert [(c.method, c.path) for c in world.pushgateway.calls if c.method == "PUT"] == [
        ("PUT", "/metrics/job/bias-monitoring/group/run"),
        ("PUT", "/metrics/job/bias-monitoring/group/success"),
    ]
    assert world.pushgateway.value("run", "vectra_bias_last_run_ok") == "1"
    assert world.pushgateway.value("success", "vectra_bias_last_success_timestamp") == str(
        int(T0.timestamp())
    )
    assert all(
        c.timeout == config.PUSH_TIMEOUT_S
        for c in world.pushgateway.calls
        if "group/run" in c.path or "group/success" in c.path
    )


def test_a_failed_run_pushes_run_only_and_does_not_delete_last_success():
    world = World()
    run(publish(client(world), report(version("v1"), minute=0)))
    before = world.pushgateway.value("success", "vectra_bias_last_success_timestamp")
    result = run(
        publish(client(world), report(minute=15, complete=False, reason="lectura", calculated=False))
    )
    assert result.ok
    assert world.pushgateway.value("success", "vectra_bias_last_success_timestamp") == before
    assert world.pushgateway.value("run", "vectra_bias_last_run_ok") == "0"
    assert world.pushgateway.value("run", "vectra_bias_last_run_failure", reason="lectura") == "1"
    assert not [c for c in world.pushgateway.calls[-3:] if c.method == "DELETE"]


def test_a_version_that_stops_being_evaluated_disappears_from_the_run_group():
    world = World()
    run(publish(client(world), report(version("v1"), version("v2"))))
    assert {
        lab["model_version_id"]
        for n, lab, _ in world.pushgateway.group("bias-monitoring", "run")
        if n == "vectra_bias_rule_met"
    } == {"v1", "v2"}
    run(publish(client(world), report(version("v2"), minute=15)))
    assert {
        lab["model_version_id"]
        for n, lab, _ in world.pushgateway.group("bias-monitoring", "run")
        if n == "vectra_bias_rule_met"
    } == {"v2"}


def test_aggregate_lower_publishes_the_r4_limit_of_every_attribute_and_rule_met_both_populations():
    world = World()
    run(publish(client(world), report(version("v1", HIGH))))
    lower = {
        lab["attribute"]: v
        for n, lab, v in world.pushgateway.group("bias-monitoring", "run")
        if n == "vectra_bias_aggregate_lower" and lab["population"] == "modelo"
    }
    assert set(lower) == {"sexo", "rango_edad", "region", "estrato"}
    assert float(lower["region"]) > 0.05 > max(float(v) for a, v in lower.items() if a != "region")
    assert (
        world.pushgateway.value("run", "vectra_bias_rule_met", model_version_id="v1", population="modelo")
        == "1"
    )
    assert (
        world.pushgateway.value("run", "vectra_bias_rule_met", model_version_id="v1", population="humana")
        == "0"
    )


def test_all_the_series_are_gauges_with_a_type_line_each():
    world = World()
    run(publish(client(world), report(version("v1", HIGH))))
    body = next(c.body for c in world.pushgateway.calls if c.path.endswith("/group/run"))
    typed = {line.split()[2] for line in body.splitlines() if line.startswith("# TYPE")}
    assert all(line.endswith("gauge") for line in body.splitlines() if line.startswith("# TYPE"))
    names = {
        line.split("{")[0].split(" ")[0] for line in body.splitlines() if line and not line.startswith("#")
    }
    assert names == typed
    assert {"vectra_bias_disparity", "vectra_bias_aggregate_lower", "vectra_bias_rule_met", "vectra_bias_cell_size",
            "vectra_bias_invalid_entries", "vectra_bias_total_entries", "vectra_bias_last_run_timestamp", "vectra_bias_last_run_ok"} <= names  # fmt: skip


# --- grupos freeze-<v> ---------------------------------------------------------------------------------------------------


def test_a_failed_freeze_puts_the_group_and_a_successful_one_deletes_it():
    world = World()
    run(publish(client(world), report(version("v1", HIGH, failed()), complete=False, reason="freeze")))
    assert "freeze-v1" in world.pushgateway.names()
    assert world.pushgateway.value("freeze-v1", "vectra_bias_freeze_failed", model_version_id="v1") == "1"
    run(publish(client(world), report(version("v1", HIGH, ok()), minute=15)))
    assert "freeze-v1" not in world.pushgateway.names()


def test_a_409_deletes_the_group_too():
    world = World()
    run(publish(client(world), report(version("v1", HIGH, failed()), complete=False, reason="freeze")))
    run(publish(client(world), report(version("v1", HIGH, ok(outcome=CONFLICT)), minute=15)))
    assert "freeze-v1" not in world.pushgateway.names()


def test_the_group_persists_after_a_run_that_fails_before_the_calculation():
    world = World()
    run(publish(client(world), report(version("v1", HIGH, failed()), complete=False, reason="freeze")))
    calls_before = len(world.pushgateway.calls)
    run(
        publish(
            client(world), report(minute=15, complete=False, reason="agregador_atrasado", calculated=False)
        )
    )
    assert "freeze-v1" in world.pushgateway.names()
    new = world.pushgateway.calls[calls_before:]
    assert {(c.method) for c in new} == {"PUT"} and all(
        "group/run" in c.path for c in new
    )  # no lista, no borra, no crea


def test_the_group_goes_away_in_a_complete_run_where_the_version_no_longer_meets_the_rule():
    world = World()
    run(publish(client(world), report(version("v1", HIGH, failed()), complete=False, reason="freeze")))
    run(publish(client(world), report(version("v1", LOW), minute=15)))
    assert "freeze-v1" not in world.pushgateway.names()


def test_the_group_goes_away_in_a_complete_run_where_the_version_is_no_longer_evaluated():
    world = World()
    run(
        publish(
            client(world),
            report(version("v1", HIGH, failed()), version("v2"), complete=False, reason="freeze"),
        )
    )
    run(publish(client(world), report(version("v2"), minute=15)))
    assert "freeze-v1" not in world.pushgateway.names()


def test_the_group_stays_in_a_failed_run_where_another_version_failed_and_this_one_no_longer_meets_the_rule():
    world = World()
    run(publish(client(world), report(version("v1", HIGH, failed()), complete=False, reason="freeze")))
    run(
        publish(
            client(world),
            report(
                version("v1", LOW), version("v2", HIGH, failed()), minute=15, complete=False, reason="freeze"
            ),
        )
    )
    assert {"freeze-v1", "freeze-v2"} <= world.pushgateway.names()


def test_20_stale_groups_are_deleted_16_per_run_and_then_the_last_4():
    world = World()
    for i in range(20):
        world.pushgateway.put_group("bias-monitoring", f"freeze-old{i:02d}", "vectra_bias_freeze_failed")
    world.pushgateway.put_group("otro-job", "freeze-ajeno")
    world.pushgateway.put_group("bias-monitoring", "otro-grupo")
    first = run(publish(client(world), report(version("v1"))))
    assert len(first.deleted_stale) == config.MAX_STALE_GROUP_DELETES == 16
    stale = [n for n in world.pushgateway.names() if n.startswith("freeze-old")]
    assert len(stale) == 4
    second = run(publish(client(world), report(version("v1"), minute=15)))
    assert len(second.deleted_stale) == 4
    assert not [n for n in world.pushgateway.names() if n.startswith("freeze-old")]
    # Ningun DELETE toca un grupo de otro job ni un grupo que no sea freeze-<v>.
    assert ("job", "otro-job") in {k[0] for k in world.pushgateway.groups}
    assert "otro-grupo" in world.pushgateway.names()
    deletes = [c.path for c in world.pushgateway.calls if c.method == "DELETE"]
    assert deletes and all(p.startswith("/metrics/job/bias-monitoring/group/freeze-") for p in deletes)


def test_every_group_operation_is_cut_at_5_seconds():
    world = World()
    world.pushgateway.put_group("bias-monitoring", "freeze-old")
    run(publish(client(world), report(version("v1", HIGH, failed()), complete=False, reason="freeze")))
    timeouts = {(c.method, c.path.rsplit("/", 1)[-1]): c.timeout for c in world.pushgateway.calls}
    assert timeouts[("PUT", "freeze-v1")] == config.GROUP_CALL_TIMEOUT_S == 5
    run(publish(client(world), report(version("v1", HIGH, ok()), minute=15)))
    assert {c.timeout for c in world.pushgateway.calls if c.method in ("DELETE", "GET")} == {5}
    world.pushgateway.delay = 60.0
    result = run(
        publish(
            client(world), report(version("v1", HIGH, failed()), complete=False, reason="freeze", minute=30)
        )
    )
    assert not result.ok
    assert world.clock.slept and set(world.clock.slept) == {5}


def test_a_pushgateway_down_returns_the_errors_without_raising():
    world = World()
    world.pushgateway.down = True
    result = run(
        publish(client(world), report(version("v1", HIGH, failed()), complete=False, reason="freeze"))
    )
    assert not result.ok
    assert any(e.startswith("PUT:run") for e in result.errors)
    assert not world.pushgateway.groups


def test_a_failed_listing_does_not_stop_the_other_operations():
    world = World()
    world.pushgateway.failing_paths = {"/api/v1/metrics"}
    run(publish(client(world), report(version("v1", HIGH, ok()))))
    result = run(publish(client(world), report(version("v1"), minute=15)))
    assert not result.ok and any(e.startswith("GET:groups") for e in result.errors)
    assert world.pushgateway.value("success", "vectra_bias_last_success_timestamp") == str(
        int((T0 + timedelta(minutes=15)).timestamp())
    )
