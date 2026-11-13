"""CA-13 y CA-17: la seccion `decisions` con el volumen de demostracion de 2 000 (U12 Paso 6; BR-U12-06; NFR-U12-32), con dobles en proceso (los validados contra el contrato) y reloj falso."""

import socket
import time
from datetime import UTC, datetime
from pathlib import Path

import pytest
from contract_world import LightGateway, case_detail_json
from fake_clock import FakeClock

from vectra_verification import guard
from vectra_verification.clients._api import RunTag
from vectra_verification.clients.gateway import GatewayClient
from vectra_verification.driver import (
    ANALYSTS,
    CASE_SIZE_CASES,
    DEMO_MIX,
    DEMO_VOLUME,
    Driver,
    default_volume,
    run_decisions,
)
from vectra_verification.guard import KIND, STAGING, GuardError
from vectra_verification.simulator import Simulator, read_delivery

PREFIX = "3fa9c2d1"


class Session:
    def __init__(self, user: str) -> None:
        self.user, self.step_up = user, False

    def bearer(self) -> str:
        return f"tok-{self.user}"

    def refresh(self) -> None:  # pragma: no cover - el doble no responde 401
        raise AssertionError("no se esperaba un 401")


def _world(environment: guard.Environment, delivery: Path, clock: FakeClock | None = None):  # type: ignore[no-untyped-def]
    clock = clock or FakeClock()
    light = LightGateway(clock)
    population = read_delivery(delivery, clock.now())
    simulator = Simulator(
        environment,
        GatewayClient(
            environment, lambda: "tok-channel-simulator", RunTag("normal", PREFIX), transport=light
        ),
        clock,
        population,
        PREFIX,
    )
    driver = Driver(
        environment,
        {u: Session(u) for u in ANALYSTS},
        RunTag("decisions", PREFIX),
        clock,
        DEMO_MIX,
        transport=light,
    )
    return simulator, driver, light, clock


def test_the_decisions_section_sends_2000_normal_cases_and_the_driver_decides_them(
    u5_delivery: Path, dynamic_environment: guard.Environment, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Sin sockets y sin dormir: cualquiera de las dos cosas hace fallar la prueba. Menos de 60 s de reloj real."""
    simulator, driver, light, _ = _world(dynamic_environment, u5_delivery)

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("la corrida no abre sockets ni duerme")

    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(time, "sleep", forbidden)
    started = time.monotonic()
    # 2 000 filas: la entrega pequeña de la prueba tiene menos; el volumen se pide sobre una poblacion mayor repitiendo la entrega no se permite (BR-U12-01): se usa la entrega de 12 000 filas
    assert simulator._population.test_rows >= DEMO_VOLUME  # noqa: SLF001
    result = run_decisions(simulator, driver, 20261101, environment=dynamic_environment, volume=DEMO_VOLUME)
    assert time.monotonic() - started < 60
    assert (
        result.simulation.report.sent == 2000
        and result.record.sent == 2000
        and result.record.accepted == 2000
        and result.record.decided == 2000
    )
    assert result.driver.cases_seen == 2000 and result.driver.not_decided == 0 and len(light.cases) == 2000


def test_three_cases_in_409_are_sent_2000_and_decided_1997_and_both_numbers_are_recorded(
    u5_delivery: Path, dynamic_environment: guard.Environment
) -> None:
    simulator, driver, light, _ = _world(dynamic_environment, u5_delivery)
    light.conflict_next = 3
    result = run_decisions(simulator, driver, 20261101, environment=dynamic_environment, volume=DEMO_VOLUME)
    assert (result.record.sent, result.record.decided) == (2000, 1997) and result.driver.conflicts_409 == 3


def test_the_first_1000_case_ids_in_send_order_are_identified_for_case_size(
    u5_delivery: Path, dynamic_environment: guard.Environment
) -> None:
    simulator, driver, light, _ = _world(dynamic_environment, u5_delivery)
    result = run_decisions(simulator, driver, 20261101, environment=dynamic_environment, volume=DEMO_VOLUME)
    ids = result.simulation.report.case_ids
    assert (
        CASE_SIZE_CASES == 1000
        and result.record.case_size_case_ids == ids[:1000]
        and len(result.record.case_size_case_ids) == 1000
    )
    sent_order = [case for case in (light.requests and list(light.cases)) or []]
    assert list(ids) == sent_order[: len(ids)] or set(ids) == set(sent_order)


def test_the_driver_decides_only_the_case_ids_of_the_run_report_not_other_ready_cases(
    u5_delivery: Path, dynamic_environment: guard.Environment
) -> None:
    simulator, driver, light, _ = _world(dynamic_environment, u5_delivery)
    foreign = [f"00000000-0000-4000-8000-0000000000{i:02d}" for i in range(5)]
    for case_id in foreign:
        light.cases[case_id] = case_detail_json(case_id, "listo", "favorable")
    result = run_decisions(simulator, driver, 20261101, environment=dynamic_environment, volume=50)
    assert result.record.decided == 50 and all(light.decision_posts[c] == 0 for c in foreign)
    assert all(light.cases[c]["state"] == "listo" for c in foreign)


def test_the_volume_is_a_named_constant_and_the_guard_lowers_it_to_100_in_staging(u5_delivery: Path) -> None:
    assert (
        DEMO_VOLUME == 2000
        and default_volume(KIND) == 2000
        and default_volume(STAGING) == guard.STAGING_MAX_DECISIONS == 100
    )
    simulator, driver, light, _ = _world(STAGING, u5_delivery)
    with pytest.raises(GuardError, match="decisions_volume_over_100_in_staging"):
        run_decisions(
            simulator, driver, 1, environment=STAGING, volume=DEMO_VOLUME
        )  # en staging la barrera niega 2 000
    assert light.requests == []
    assert run_decisions(simulator, driver, 1, environment=STAGING).record.sent == 100


def test_guard_clock_at_22_30_utc_nothing_is_sent_for_the_decisions_section(
    u5_delivery: Path, dynamic_environment: guard.Environment
) -> None:
    simulator, driver, light, _ = _world(
        dynamic_environment, u5_delivery, FakeClock(datetime(2026, 11, 13, 22, 30, tzinfo=UTC))
    )
    with pytest.raises(GuardError, match="decisions_would_end_after_23_utc"):
        run_decisions(simulator, driver, 1, environment=dynamic_environment, volume=DEMO_VOLUME)
    assert light.requests == []
