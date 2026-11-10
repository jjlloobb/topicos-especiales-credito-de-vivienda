"""Paso 7: `registry_client` y `freeze_client` contra los dobles de U3, U4 y Keycloak (P-U9-02, NFR-U9-03, 22; BR-U9-09, 12)."""

from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime, timedelta

import pytest
from builders import batch_client, ensure_batch, uniform
from vectra_bias import config
from vectra_bias.context import build_context_package, measure
from vectra_bias.freeze_client import CONFLICT, FAILED, FROZEN, freeze
from vectra_bias.freeze_rule import attribute_limits, decide
from vectra_bias.registry_client import RegistryError, plan_queries, query_daily, read_freezes
from vectra_bias.window import version_ranges
from vectra_contracts.models.monitoring import (
    AffectedVolume,
    DayRange,
    MonitoringQuery,
    MonitoringRangeRequest,
)
from world import GOVERNANCE_URL, REGISTRY_URL, World, freeze_record

TODAY = date(2026, 11, 9)
NOW = datetime(2026, 11, 9, 12, tzinfo=UTC)


def run(coro):
    return asyncio.run(coro)


def registry_client(world: World):
    token = world.keycloak.provider("decision-registry", ("registry:read:monitoring",))
    return batch_client("registry", REGISTRY_URL, world.registry.transport(), token)


def governance_client(world: World):
    token = world.keycloak.provider("governance", ("governance:freeze",))
    return batch_client("governance", GOVERNANCE_URL, world.governance.transport(), token)


def context_for(version: str):
    counts = uniform(0.5, 100)
    after = measure(counts, 30, "modelo", version, TODAY - timedelta(days=29), TODAY)
    return build_context_package(
        model_version_id=version,
        computed_at=NOW,
        threshold_pp=config_threshold(),
        n_min=30,
        window_days=30,
        schedule="2,17,32,47 * * * *",
        stale_after_s=3600,
        window_start=TODAY - timedelta(days=29),
        before=None,
        after=after,
        last_7_days=None,
        decision=decide("modelo", config_threshold(), attribute_limits(counts, 30)),
        affected_volume=AffectedVolume(total=1, favorable=1),
    )


def config_threshold():
    from decimal import Decimal

    return Decimal(5)


def ranges_for(version: str) -> list[MonitoringRangeRequest]:
    r = version_ranges(TODAY, 30, TODAY - timedelta(days=60), None)
    spans = {
        "antes": ("modelo", r.before),
        "despues": ("modelo", r.after),
        "7d": ("modelo", r.last_7_days),
        "humana": ("humana", r.human_after),
    }
    return [
        MonitoringRangeRequest(
            range_id=f"{version}:{k}",
            model_version_id=version,
            population=p,
            from_day=s.from_day,
            to_day=s.to_day,
        )
        for k, (p, s) in spans.items()
    ]


# --- timeouts de cada llamada --------------------------------------------------------------------------------------------


def test_every_call_is_cut_at_its_timeout_with_slow_doubles():
    world = World()
    registry = registry_client(world)
    governance = governance_client(world)
    query = MonitoringQuery(ranges=ranges_for("v1"), include_versions=True)

    world.registry.delay = 60.0
    with pytest.raises(RegistryError):
        run(read_freezes(registry))
    with pytest.raises(RegistryError):
        run(query_daily(registry, query))
    assert world.clock.slept == [config.FREEZES_TIMEOUT_S, config.QUERY_TIMEOUT_S]
    assert (
        [c.timeout for c in world.registry.calls]
        == [config.FREEZES_TIMEOUT_S, config.QUERY_TIMEOUT_S]
        == [3, 5]
    )

    world.clock.slept.clear()
    world.governance.delay = 60.0
    outcome = run(freeze(governance, "v1", context_for("v1"), world.clock.sleep))
    assert outcome.outcome == FAILED
    assert [c.timeout for c in world.governance.calls] == [config.FREEZE_TIMEOUT_S] * 4
    assert config.FREEZE_TIMEOUT_S == 3


def test_a_slow_double_that_answers_within_the_timeout_is_not_cut():
    world = World()
    world.registry.delay = 2.9
    assert run(read_freezes(registry_client(world))) == []


def test_registry_errors_are_a_single_reading_failure():
    world = World()
    client = registry_client(world)
    for status in (500, 503, 404):
        world.registry.status = status
        with pytest.raises(RegistryError):
            run(read_freezes(client))
    world.registry.status = None
    world.keycloak.down = True
    token_less = batch_client("registry-no-token", REGISTRY_URL, world.registry.transport())
    with pytest.raises(RegistryError):
        run(read_freezes(token_less))


# --- registry_client -----------------------------------------------------------------------------------------------------


def test_the_freezes_come_back_as_u0_records():
    world = World()
    world.registry.freezes = [
        freeze_record("v1", NOW - timedelta(days=3), [("reactivar", NOW - timedelta(days=1))])
    ]
    records = run(read_freezes(registry_client(world)))
    assert [r.model_version_id for r in records] == ["v1"]
    assert records[0].resolutions[0].action == "reactivar"


def test_four_versions_make_two_requests_of_12_and_4_and_the_unattributable_is_taken_once():
    world = World()
    for i in range(4):
        world.registry.unattributable[TODAY - timedelta(days=i)] = 1
    ranges = [r for v in ("v1", "v2", "v3", "v4") for r in ranges_for(v)]
    window = DayRange(from_day=TODAY - timedelta(days=29), to_day=TODAY)
    queries = plan_queries(ranges, window)
    assert [len(q.ranges) for q in queries] == [12, 4]
    assert [q.unattributable_range for q in queries] == [window, None]
    assert {r.range_id for q in queries for r in q.ranges} == {r.range_id for r in ranges}  # ninguna se omite
    client = registry_client(world)
    windows = [run(query_daily(client, q)) for q in queries]
    assert [w.unattributable_invalid for w in windows] == [4, 0]
    assert sum(w.unattributable_invalid for w in windows) == 4  # una sola vez
    assert [len(c.body.ranges) for c in world.registry.calls] == [12, 4]


def test_a_single_version_group_of_up_to_three_versions_is_one_request():
    ranges = [r for v in ("v1", "v2", "v3") for r in ranges_for(v)]
    assert [len(q.ranges) for q in plan_queries(ranges, None)] == [12]
    assert plan_queries([], None) == []


def test_the_registry_double_sums_the_days_of_a_range_and_reports_the_versions():
    world = World()
    for d in range(3):
        world.registry.add_day(
            "v1", "modelo", TODAY - timedelta(days=d), uniform(0.5, 40), invalid=1 if d == 0 else 0
        )
    query = MonitoringQuery(
        ranges=[
            MonitoringRangeRequest(
                range_id="a",
                model_version_id="v1",
                population="modelo",
                from_day=TODAY - timedelta(days=5),
                to_day=TODAY,
            )
        ],
        include_versions=True,
    )
    window = run(query_daily(registry_client(world), query))
    assert [(v.model_version_id, v.first_day, v.last_day) for v in window.versions] == [
        ("v1", TODAY - timedelta(days=2), TODAY)
    ]
    assert sum(c.count for c in window.counts if c.attribute == "sexo") == 3 * 2 * 3 * 40
    assert [(t.total_entries, t.invalid_entries) for t in window.totals] == [(3 * 720 + 1, 1)]


# --- freeze_client -------------------------------------------------------------------------------------------------------


def test_freeze_succeeds_at_the_first_attempt_with_the_job_token():
    world = World()
    outcome = run(freeze(governance_client(world), "v1", context_for("v1"), world.clock.sleep))
    assert (outcome.outcome, outcome.attempts) == (FROZEN, 1)
    assert world.governance.frozen == {"v1"}
    assert world.keycloak.requests[0]["scope"] == "governance:freeze"


def test_freeze_with_a_persistent_503_makes_4_attempts_waiting_1_2_and_4_seconds():
    world = World()
    world.governance.script["v1"] = ["5xx"] * 10
    outcome = run(freeze(governance_client(world), "v1", context_for("v1"), world.clock.sleep))
    assert (outcome.outcome, outcome.attempts) == (FAILED, 4)
    assert len(world.governance.freeze_calls("v1")) == 4
    assert world.clock.slept == [1, 2, 4]
    assert outcome.reason == "status_503"


def test_freeze_recovers_when_a_retry_succeeds():
    world = World()
    world.governance.script["v1"] = ["5xx", "5xx"]
    outcome = run(freeze(governance_client(world), "v1", context_for("v1"), world.clock.sleep))
    assert (outcome.outcome, outcome.attempts) == (FROZEN, 3)
    assert world.clock.slept == [1, 2]


def test_freeze_retries_a_timeout():
    world = World()
    world.governance.script["v1"] = ["timeout", "ok"]
    outcome = run(freeze(governance_client(world), "v1", context_for("v1"), world.clock.sleep))
    assert (outcome.outcome, outcome.attempts) == (FROZEN, 2)


def test_freeze_with_a_409_is_one_attempt_and_a_success():
    world = World()
    world.governance.script["v1"] = ["409"]
    outcome = run(freeze(governance_client(world), "v1", context_for("v1"), world.clock.sleep))
    assert (outcome.outcome, outcome.attempts, outcome.ok) == (CONFLICT, 1, True)
    assert len(world.governance.freeze_calls()) == 1
    assert world.clock.slept == []


def test_freeze_of_an_already_frozen_version_is_a_409_without_retry():
    world = World()
    client = governance_client(world)
    run(freeze(client, "v1", context_for("v1"), world.clock.sleep))
    again = run(freeze(client, "v1", context_for("v1"), world.clock.sleep))
    assert (again.outcome, again.attempts) == (CONFLICT, 1)


@pytest.mark.parametrize("script", ["403", "400"])
def test_freeze_with_another_4xx_is_one_attempt_and_failed(script):
    world = World()
    world.governance.script["v1"] = [script]
    outcome = run(freeze(governance_client(world), "v1", context_for("v1"), world.clock.sleep))
    assert (outcome.outcome, outcome.attempts, outcome.ok) == (FAILED, 1, False)
    assert world.clock.slept == []


def test_freeze_without_the_scope_gets_a_403():
    world = World()
    token = world.keycloak.provider("governance", ("registry:read:monitoring",))
    client = batch_client("governance", GOVERNANCE_URL, world.governance.transport(), token)
    outcome = run(freeze(client, "v1", context_for("v1"), world.clock.sleep))
    assert (outcome.outcome, outcome.attempts) == (FAILED, 1)


def test_ensure_batch_is_idempotent():
    ensure_batch()
    ensure_batch()
