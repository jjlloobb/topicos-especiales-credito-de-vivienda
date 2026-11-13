"""CA-11 (contra `case-service` real), CA-12 (ritmo, claves, informe, semillas) y CA-13 (barrera horaria con reloj con zona) del simulador (U12 Paso 6; BR-U12-01, 02; NFR-U12-10, 50; PBT-10)."""

import dataclasses
import json
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from contract_world import KEY_PATTERN, LightGateway
from fake_clock import START, FakeClock, NaiveClock

from vectra_verification import guard, sampler
from vectra_verification.clients._api import SCENARIO_PATTERN, TRACEPARENT_PATTERN, RunTag
from vectra_verification.clients.gateway import GatewayClient
from vectra_verification.clock import Clock
from vectra_verification.guard import STAGING, GuardError
from vectra_verification.simulator import MAX_RATE, MAX_RESENDS, Simulator, SimulatorError, read_delivery

PREFIX = "3fa9c2d1"
IDENTIFIERS = ("full_name", "document_number", "phone", "email", "address", "broker_id")


def _simulator(
    environment: guard.Environment,
    delivery: Path,
    clock: FakeClock | None = None,
    light: LightGateway | None = None,
):  # type: ignore[no-untyped-def]
    clock = clock or FakeClock()
    light = light or LightGateway(clock)
    population = read_delivery(delivery, clock.now())
    gateway = GatewayClient(
        environment, lambda: "tok-channel-simulator", RunTag("normal", PREFIX), transport=light
    )
    return Simulator(environment, gateway, clock, population, PREFIX), light, clock, population


def _max_in_one_second(times: list[float]) -> int:
    return max(sum(1 for u in times if t <= u < t + 1.0 - 1e-6) for t in times)


@pytest.mark.parametrize(("rate", "volume"), [(30.0, 300), (10.0, 100)])
def test_the_simulator_never_exceeds_the_rate_in_any_sliding_one_second_window(
    u5_delivery: Path, dynamic_environment: guard.Environment, rate: float, volume: int
) -> None:
    simulator, light, clock, _ = _simulator(dynamic_environment, u5_delivery)
    result = simulator.run("normal", volume, 11, rate=rate)
    assert result.report.sent == volume == len(light.requests) and _max_in_one_second(light.sent_at) <= rate
    assert clock.sleeps  # el ritmo se cumple con el reloj inyectado: no duerme de verdad


def test_a_rate_over_30_is_an_error_and_zero_requests(
    u5_delivery: Path, dynamic_environment: guard.Environment
) -> None:
    simulator, light, _, _ = _simulator(dynamic_environment, u5_delivery)
    assert MAX_RATE == 30.0
    for rate in (31.0, 0.0, -1.0):
        with pytest.raises(SimulatorError, match="rate_out_of_range"):
            simulator.run("normal", 10, 1, rate=rate)
    assert light.requests == []


def test_idempotency_keys_are_distinct_within_a_run_and_between_two_runs_with_the_same_seed(
    u5_delivery: Path, dynamic_environment: guard.Environment
) -> None:
    simulator, light, _, _ = _simulator(dynamic_environment, u5_delivery)
    first = simulator.run("normal", 40, 5)
    second = simulator.run("normal", 40, 5)
    keys = [r.headers["Idempotency-Key"] for r in light.requests]
    assert len(keys) == 80 == len(set(keys)) and all(KEY_PATTERN.fullmatch(k) for k in keys)
    assert first.sent_positions == second.sent_positions  # mismas filas, claves nuevas


def test_the_run_report_has_no_identifiers_and_the_positions_travel_apart(
    u5_delivery: Path, dynamic_environment: guard.Environment
) -> None:
    simulator, _, _, population = _simulator(dynamic_environment, u5_delivery)
    result = simulator.run("normal", 30, 9)
    report = result.report
    names = {f.name for f in dataclasses.fields(report)}
    assert {
        "scenario",
        "sent",
        "accepted",
        "rejected_by_code",
        "case_ids",
        "started_at",
        "finished_at",
    } <= names
    assert {"generator_version", "seed", "sampling_seed", "rate", "run_prefix"} <= names and not any(
        "position" in n or "rows" in n.replace("test_rows", "") for n in names
    )
    text = json.dumps(dataclasses.asdict(report), default=str)
    for position in result.sent_positions:
        application = population.applications[position].model_dump()
        for field in IDENTIFIERS:
            assert application[field] is None or str(application[field]) not in text
    assert json.dumps(list(result.sent_positions)) not in text and len(result.sent_positions) == 30
    assert (report.generator_version, report.seed, report.sampling_seed, report.rate, report.run_prefix) == (
        "1.0.0",
        20261101,
        9,
        10.0,
        PREFIX,
    )


def test_same_seed_same_rows_in_the_same_order_and_another_seed_other_rows(
    u5_delivery: Path, dynamic_environment: guard.Environment
) -> None:
    simulator, _, _, _ = _simulator(dynamic_environment, u5_delivery)
    a, b, c = (simulator.run("normal", 30, seed).sent_positions for seed in (3, 3, 4))
    assert a == b and a != c


def test_normal_uses_the_sampler_normal_and_stratified_sends_every_row_it_returns(
    u5_delivery: Path, dynamic_environment: guard.Environment
) -> None:
    simulator, light, _, population = _simulator(dynamic_environment, u5_delivery)
    normal = simulator.run("normal", 25, 6)
    assert (
        normal.sent_positions == tuple(int(i) for i in sampler.normal(population.rows, 25, 6))
        and normal.report.short_cells == ()
    )
    before = len(light.requests)
    stratified = simulator.run("stratified", 50, 6, rate=30.0)
    sample = sampler.stratified(population.rows, 50, 6)
    assert (
        stratified.sent_positions == tuple(int(i) for i in sample.ids)
        and len(stratified.sent_positions) >= 50
    )  # el volumen es un piso
    assert (
        stratified.report.sent == len(light.requests) - before == len(sample.ids)
        and stratified.report.short_cells == sample.short
    )


def test_rejected_by_code_groups_and_the_totals_add_up(
    u5_delivery: Path, dynamic_environment: guard.Environment
) -> None:
    simulator, light, _, _ = _simulator(dynamic_environment, u5_delivery)
    light.intake_script.extend([(422, {}), (422, {})])
    report = simulator.run("normal", 10, 2).report
    assert report.rejected_by_code == {"validation_error": 2} and report.accepted == 8 == len(report.case_ids)
    assert report.accepted + sum(report.rejected_by_code.values()) == report.sent == 10


def test_429_and_503_resend_the_same_request_with_the_same_key_and_body_and_count_it(
    u5_delivery: Path, dynamic_environment: guard.Environment
) -> None:
    simulator, light, _, _ = _simulator(dynamic_environment, u5_delivery)
    light.intake_script.extend([(429, {"Retry-After": "1"}), (503, {}), (503, {"Retry-After": "2"})])
    report = simulator.run("normal", 3, 2).report
    first_three = light.requests[:4]
    assert report.resends == 3 and report.accepted == 3 and report.sent == 3
    assert (
        len({r.headers["Idempotency-Key"] for r in first_three}) == 1
        and len({r.content for r in first_three}) == 1
    )
    # sin respuesta tras los reenvios maximos: se cuenta como rechazada y no se cambia el contenido
    light.intake_script.extend([(503, {})] * (MAX_RESENDS + 1))
    stuck = simulator.run("normal", 1, 9).report
    assert stuck.resends == MAX_RESENDS and stuck.rejected_by_code == {"dependency_unavailable": 1}


def test_every_request_carries_the_scenario_header_and_the_prefix_in_the_traceparent(
    u5_delivery: Path, dynamic_environment: guard.Environment
) -> None:
    simulator, light, _, _ = _simulator(dynamic_environment, u5_delivery)
    simulator.run("normal", 12, 1)
    for request in light.requests:
        assert (
            SCENARIO_PATTERN.fullmatch(request.headers["X-Test-Scenario"])
            and request.headers["X-Test-Scenario"] == f"normal.{PREFIX}"
        )
        assert TRACEPARENT_PATTERN.fullmatch(request.headers["traceparent"]) and request.headers[
            "traceparent"
        ].split("-")[1].startswith(PREFIX)


def test_the_request_body_is_the_application_without_default_or_the_synthetic_id(
    u5_delivery: Path, dynamic_environment: guard.Environment
) -> None:
    simulator, light, _, _ = _simulator(dynamic_environment, u5_delivery)
    simulator.run("normal", 5, 1)
    assert all(
        "default" not in json.loads(b) and "synthetic_id" not in json.loads(b) for b in light.intake_bodies
    )
    assert Counter(light.sent_by_path) == {"POST /api/intake/v1/intake/applications": 5}


# ---- CA-13: la barrera horaria recibe un reloj con zona -------------------------------------------------------------------------------------------


def test_clock_at_22_30_utc_decisions_is_refused_before_the_first_request_and_at_10_00_it_starts(
    u5_delivery: Path, dynamic_environment: guard.Environment
) -> None:
    late = FakeClock(datetime(2026, 11, 13, 22, 30, tzinfo=UTC))
    simulator, light, _, _ = _simulator(dynamic_environment, u5_delivery, late)
    with pytest.raises(GuardError, match="decisions_would_end_after_23_utc"):
        simulator.run("normal", 2000, 1, section="decisions")
    assert light.requests == []
    morning = FakeClock(datetime(2026, 11, 13, 10, 0, tzinfo=UTC))
    simulator, light, _, _ = _simulator(dynamic_environment, u5_delivery, morning)
    assert simulator.run("normal", 20, 1, section="decisions").report.sent == 20


def test_clock_the_real_clock_returns_utc_with_a_timezone() -> None:
    now = Clock().now()
    assert now.utcoffset() == timedelta(0) and abs((datetime.now(UTC) - now).total_seconds()) < 5


def test_clock_a_naive_clock_is_refused_by_the_guard_with_clock_without_timezone(
    u5_delivery: Path, dynamic_environment: guard.Environment
) -> None:
    """Rojo de CA-13: un reloj que devuelve `datetime.utcnow()` (sin zona)."""
    simulator, light, _, _ = _simulator(dynamic_environment, u5_delivery, NaiveClock(START))
    with pytest.raises(GuardError, match="clock_without_timezone"):
        simulator.run("normal", 10, 1, section="decisions")
    assert light.requests == []


def test_guard_in_staging_101_cases_are_refused_and_100_are_not(u5_delivery: Path) -> None:
    clock = FakeClock()
    light = LightGateway(clock)
    population = read_delivery(u5_delivery, clock.now())
    gateway = GatewayClient(STAGING, lambda: "t", RunTag("normal", PREFIX), transport=light)
    simulator = Simulator(STAGING, gateway, clock, population, PREFIX)
    with pytest.raises(GuardError, match="decisions_volume_over_100_in_staging"):
        simulator.run("normal", 101, 1, section="decisions")
    assert light.requests == [] and simulator.run("normal", 100, 1, section="decisions").report.sent == 100


# ---- CA-11: el simulador contra `case-service` real (U8) sobre PostgreSQL de Testcontainers ---------------------------------------------------------


def _real_simulator(environment: guard.Environment, delivery: Path, transport, token: str):  # type: ignore[no-untyped-def]
    clock = FakeClock()
    population = read_delivery(delivery, clock.now())
    gateway = GatewayClient(environment, lambda: token, RunTag("normal", PREFIX), transport=transport)
    return Simulator(environment, gateway, clock, population, PREFIX)


def test_real_case_service_accepts_20_normal_requests_and_stores_their_scenario(
    u5_delivery: Path, dynamic_environment: guard.Environment, db
) -> None:  # type: ignore[no-untyped-def]
    from real_case import real_case_service

    with real_case_service(db) as (transport, _):
        simulator = _real_simulator(dynamic_environment, u5_delivery, transport, "simulator")
        report = simulator.run("normal", 20, 4).report
    assert (
        report.sent == report.accepted == 20
        and len(set(report.case_ids)) == 20
        and report.rejected_by_code == {}
    )
    rows = db.query("SELECT case_id::text, test_scenario_id FROM cases")
    assert (
        len(rows) == 20
        and {r[1] for r in rows} == {f"normal.{PREFIX}"}
        and {r[0] for r in rows} == set(report.case_ids)
    )
    assert len(simulator.keys_used) == 20 and all(
        KEY_PATTERN.fullmatch(k) for k in simulator.keys_used
    )  # las claves que U8 aceptaria


def test_real_case_service_rejects_another_client_with_422_counted_in_rejected_by_code(
    u5_delivery: Path, dynamic_environment: guard.Environment, db
) -> None:  # type: ignore[no-untyped-def]
    from real_case import real_case_service

    with real_case_service(db) as (transport, _):
        report = (
            _real_simulator(dynamic_environment, u5_delivery, transport, "channel")
            .run("normal", 20, 4)
            .report
        )
    assert (
        report.accepted == 0 and report.sent == 20 and report.rejected_by_code == {"validation_error": 20}
    )  # no es una excepcion
    assert db.query("SELECT count(*) FROM cases") == [(0,)]


def test_real_case_service_rejects_the_raw_parquet_columns_which_is_why_default_is_never_sent(
    u5_delivery: Path, dynamic_environment: guard.Environment, db
) -> None:  # type: ignore[no-untyped-def]
    """Rojo de CA-11: sin quitar `default` (y `synthetic_id`), `ApplicationIn` es estricto y U8 rechaza las 20. Un doble escrito a mano no lo habria visto."""
    import httpx
    import pyarrow.parquet as pq
    from real_case import real_case_service

    records = pq.read_table(u5_delivery / "datasets" / "test.parquet").to_pylist()[:20]
    statuses = []
    with (
        real_case_service(db) as (transport, _),
        httpx.Client(transport=transport, base_url="https://x.test") as http,
    ):
        for i, record in enumerate(records):
            response = http.post(
                "/api/intake/v1/intake/applications",
                json=record,
                headers={"Authorization": "Bearer simulator", "Idempotency-Key": f"raw-{i}"},
            )
            statuses.append(response.status_code)
    assert statuses == [422] * 20 and db.query("SELECT count(*) FROM cases") == [(0,)]
