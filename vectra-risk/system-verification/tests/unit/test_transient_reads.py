"""CA-1 de U12-T09: las lecturas de `decisions` (la espera, `read_cases`, y la bandeja del conductor, `_ready`) aguantan los errores transitorios del BFF.

Estado 0 (transporte), 429, 502, 503 y 504 se reintentan con espera creciente y un tope que controla el reloj inyectado; agotado el tope, la seccion termina con una causa propia (`lectura_agotada`), no con una traza.
Los nombres llevan `transient` para el filtro `-k` del criterio.
"""

from __future__ import annotations

import httpx
import pytest
from contract_world import LightGateway, case_detail_json
from fake_clock import FakeClock
from flaky_transport import FlakyTransport, reads_of_cases

from vectra_verification import guard
from vectra_verification.clients._api import ApiError, RunTag
from vectra_verification.clients.bff import BffClient
from vectra_verification.driver import ANALYSTS, DEMO_MIX, Driver
from vectra_verification.scenarios import sim_normal

TAG = RunTag("decisions", "3fa9c2d1")
IDS = [f"00000000-0000-4000-8000-{n:012d}" for n in range(1, 4)]


class Session:
    def __init__(self, user: str) -> None:
        self.user, self.step_up = user, False

    def bearer(self) -> str:
        return f"tok-{self.user}"

    def refresh(self) -> None:  # pragma: no cover
        raise AssertionError("no se esperaba un 401")


def _light(clock: FakeClock, state: str = "listo") -> LightGateway:
    light = LightGateway(clock)
    for case_id in IDS:
        light.cases[case_id] = case_detail_json(case_id, state, "favorable")
    return light


def _bff(env: guard.Environment, transport: httpx.BaseTransport) -> BffClient:
    return BffClient(env, Session("analista-1"), TAG, transport=transport)


FAULTS = [
    pytest.param(429, id="429"),
    pytest.param(502, id="502"),
    pytest.param(503, id="503"),
    pytest.param(504, id="504"),
    pytest.param(httpx.ReadTimeout("t"), id="timeout"),
    pytest.param(httpx.ConnectError("c"), id="transport"),
]


@pytest.mark.parametrize("fault", FAULTS)
def test_transient_error_in_the_wait_is_retried_with_growing_sleeps_and_the_cases_are_read(
    dynamic_environment: guard.Environment, fault: int | Exception
) -> None:
    clock = FakeClock()
    flaky = FlakyTransport(_light(clock), [fault, fault, fault], match=reads_of_cases)
    reads = sim_normal.read_cases(_bff(dynamic_environment, flaky), clock, IDS)
    assert {r.state for r in reads.values()} == {"listo"} and set(reads) == set(IDS)
    assert flaky.injected == 3
    backoff = [s for s in clock.sleeps if s >= 1.0]  # los de ritmo (1/15 s) quedan fuera
    assert len(backoff) == 3 and backoff == sorted(backoff) and backoff[-1] > backoff[0]


def test_transient_429_with_retry_after_waits_at_least_that_long(
    dynamic_environment: guard.Environment,
) -> None:
    clock = FakeClock()
    flaky = FlakyTransport(_light(clock), [429], match=reads_of_cases, retry_after="7")
    sim_normal.read_cases(_bff(dynamic_environment, flaky), clock, IDS)
    assert max(clock.sleeps) >= 7.0


def test_transient_error_that_never_recovers_ends_with_its_own_cause_inside_the_budget(
    dynamic_environment: guard.Environment,
) -> None:
    from vectra_verification.retry import READ_BUDGET, ReadUnavailable

    clock = FakeClock()
    flaky = FlakyTransport(_light(clock), match=reads_of_cases, always=503)
    start = clock.monotonic()
    with pytest.raises(ReadUnavailable) as stop:
        sim_normal.read_cases(_bff(dynamic_environment, flaky), clock, IDS)
    assert stop.value.code == "lectura_agotada" and stop.value.status == 503
    assert clock.monotonic() - start <= READ_BUDGET + 1.0  # el tope lo controla el reloj inyectado


def test_transient_error_that_is_not_in_the_list_is_not_retried(
    dynamic_environment: guard.Environment,
) -> None:
    clock = FakeClock()
    flaky = FlakyTransport(_light(clock), [500], match=reads_of_cases)
    with pytest.raises(ApiError) as stop:
        sim_normal.read_cases(_bff(dynamic_environment, flaky), clock, IDS)
    assert stop.value.status == 500 and flaky.injected == 1


def test_transient_error_in_the_listing_of_the_driver_is_retried_and_the_cases_are_decided(
    dynamic_environment: guard.Environment,
) -> None:
    clock = FakeClock()
    light = _light(clock)
    flaky = FlakyTransport(light, [503, 504, httpx.ReadTimeout("t"), 429], match=reads_of_cases)
    driver = Driver(
        dynamic_environment, {u: Session(u) for u in ANALYSTS}, TAG, clock, DEMO_MIX, transport=flaky
    )
    report = driver.run(IDS)
    assert report.cases_seen == 3 and flaky.injected == 4 and report.not_ready == 0


def test_transient_error_in_the_listing_of_the_driver_that_never_recovers_ends_with_its_own_cause(
    dynamic_environment: guard.Environment,
) -> None:
    from vectra_verification.retry import ReadUnavailable

    clock = FakeClock()
    flaky = FlakyTransport(_light(clock), match=reads_of_cases, always=504)
    driver = Driver(
        dynamic_environment, {u: Session(u) for u in ANALYSTS}, TAG, clock, DEMO_MIX, transport=flaky
    )
    with pytest.raises(ReadUnavailable) as stop:
        driver.run(IDS)
    assert stop.value.code == "lectura_agotada"


@pytest.mark.parametrize("status", [400, 401, 403, 409, 422])
def test_transient_a_definitive_4xx_in_the_wait_is_not_retried(
    dynamic_environment: guard.Environment, status: int
) -> None:
    """F-02 (a): solo 0, 429, 502, 503 y 504 se reintentan; un 4xx distinto de 429 llega a quien llama a la primera."""
    from vectra_verification import retry

    assert set(retry.READ_RETRY_STATUSES) == {0, 429, 502, 503, 504}
    clock = FakeClock()
    flaky = FlakyTransport(_light(clock), [status], match=reads_of_cases)
    with pytest.raises(ApiError) as stop:
        sim_normal.read_cases(_bff(dynamic_environment, flaky), clock, IDS)
    assert stop.value.status == status and flaky.injected == 1 and not any(s >= 1.0 for s in clock.sleeps)
