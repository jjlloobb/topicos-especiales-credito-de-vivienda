"""CA-2 de U12-T09: el simulador reenvia lo que es seguro reenviar con **la misma** llave de idempotencia.

`case-management/src/vectra_case/intake.py` (`submit`, la consulta de `intake_keys` por (alcance, llave)): reenviar la misma llave con el mismo cuerpo devuelve el mismo `CaseRef` y no crea otro caso; con otro cuerpo, 409.
Por eso un 502, un 504 del gateway (la ruta `intake` corta a 5 s) o un fallo de transporte (estado 0) se reenvian. Los nombres llevan `resend` para el filtro `-k` del criterio.
"""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from contract_world import LightGateway
from fake_clock import FakeClock
from flaky_transport import FlakyTransport, submits

from vectra_verification import guard
from vectra_verification.clients._api import RunTag
from vectra_verification.clients.gateway import GatewayClient
from vectra_verification.simulator import MAX_RESENDS, RESEND_STATUSES, Simulator, read_delivery

PREFIX = "3fa9c2d1"


def _world(environment: guard.Environment, delivery: Path, flaky_args: dict):  # type: ignore[no-untyped-def,type-arg]
    clock = FakeClock()
    light = LightGateway(clock)
    flaky = FlakyTransport(light, match=submits, **flaky_args)
    population = read_delivery(delivery, clock.now())
    gateway = GatewayClient(environment, lambda: "tok", RunTag("normal", PREFIX), transport=flaky)
    return Simulator(environment, gateway, clock, population, PREFIX), light, flaky, clock


@pytest.mark.parametrize(
    "fault",
    [
        pytest.param(502, id="502"),
        pytest.param(504, id="504"),
        pytest.param(httpx.ReadTimeout("t"), id="timeout"),
        pytest.param(httpx.ConnectError("c"), id="transport"),
    ],
)
def test_resend_of_a_gateway_failure_uses_the_same_key_and_the_same_body_and_accepted_equals_sent(
    u5_delivery: Path, dynamic_environment: guard.Environment, fault: int | Exception
) -> None:
    simulator, light, flaky, _ = _world(dynamic_environment, u5_delivery, {"faults": [fault]})
    report = simulator.run("normal", 5, 11).report
    assert report.sent == 5 and report.accepted == 5 and report.rejected_by_code == {}
    assert report.resends == 1 and flaky.injected == 1
    first, second = flaky.requests[0], flaky.requests[1]
    assert first.headers["Idempotency-Key"] == second.headers["Idempotency-Key"]
    assert first.content == second.content  # el contenido de una solicitud nunca cambia
    assert (
        len(simulator.keys_used) == 5 and len(light.cases) == 5
    )  # una llave por solicitud, un caso por solicitud


def test_resend_that_keeps_failing_is_a_rejection_after_the_cap_with_one_key(
    u5_delivery: Path, dynamic_environment: guard.Environment
) -> None:
    simulator, _, flaky, _ = _world(dynamic_environment, u5_delivery, {"always": 504})
    report = simulator.run("normal", 2, 11).report
    assert report.accepted == 0 and report.rejected_by_code == {"http_504": 2}
    assert report.resends == 2 * MAX_RESENDS and flaky.injected == 2 * (MAX_RESENDS + 1)
    assert len({r.headers["Idempotency-Key"] for r in flaky.requests}) == 2


def test_resend_pauses_grow_between_attempts_when_the_gateway_gives_no_retry_after(
    u5_delivery: Path, dynamic_environment: guard.Environment
) -> None:
    simulator, _, _, clock = _world(dynamic_environment, u5_delivery, {"faults": [502, 502, 502]})
    simulator.run("normal", 1, 11)
    pauses = [s for s in clock.sleeps if s >= 1.0]
    assert len(pauses) == 3 and pauses == sorted(pauses) and pauses[-1] > pauses[0]


@pytest.mark.parametrize("status", [400, 401, 403, 409, 413, 422, 500])
def test_resend_does_not_cover_a_definitive_rejection(
    u5_delivery: Path, dynamic_environment: guard.Environment, status: int
) -> None:
    simulator, _, flaky, _ = _world(dynamic_environment, u5_delivery, {"faults": [status]})
    report = simulator.run("normal", 2, 11).report
    assert report.accepted == 1 and report.resends == 0 and report.rejected_by_code == {f"http_{status}": 1}


def test_resend_statuses_are_the_ones_that_are_safe_with_the_idempotency_key() -> None:
    assert set(RESEND_STATUSES) == {0, 429, 502, 503, 504}


def test_resend_an_invalid_idempotency_key_is_local_and_is_not_resent(
    u5_delivery: Path, dynamic_environment: guard.Environment, monkeypatch: pytest.MonkeyPatch
) -> None:
    """F-02 (c): `idempotency_key_invalid` es estado 0 pero es un error local; reenviar no lo arregla."""
    from vectra_verification.clients._api import ApiError

    simulator, _, _, _ = _world(dynamic_environment, u5_delivery, {})
    calls: list[str] = []

    def refuse(self: GatewayClient, application: object, key: str) -> None:
        calls.append(key)
        raise ApiError(0, "idempotency_key_invalid")

    monkeypatch.setattr(GatewayClient, "submit_application", refuse)
    report = simulator.run("normal", 2, 11).report
    assert (
        len(calls) == 2 and report.resends == 0 and report.rejected_by_code == {"idempotency_key_invalid": 2}
    )
