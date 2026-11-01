"""`deps`: ventana de tiempo del breaker, token de servicio y propagacion (revision del 2026-11-01). Entra en la mutacion."""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from vectra_contracts.errors import ContractViolation

from vectra_common import deps, process
from vectra_common import logging as vlog
from vectra_common.deps import BreakerConfig, CircuitBreaker, CircuitState, DependencyClient
from vectra_common.errors import DependencyTimeout, DependencyUnavailable


@pytest.fixture(autouse=True)
def reset() -> Iterator[None]:
    process.reset_for_tests()
    yield
    process.reset_for_tests()


# --- Breaker con ventana de tiempo


def test_old_failures_leave_the_window():
    now = {"value": 0.0}
    config = BreakerConfig(open_for=10, window_size=4, failure_ratio=0.5, window_seconds=30)
    breaker = CircuitBreaker("tiempo", config, clock=lambda: now["value"])
    for _ in range(3):
        breaker.on_failure()
    now["value"] = 31.0
    breaker.on_success()
    breaker.on_success()
    breaker.on_failure()
    assert breaker.state is CircuitState.CLOSED  # sin la ventana, 4 de 6 ya lo habria abierto


def test_failures_within_the_window_still_open():
    now = {"value": 0.0}
    config = BreakerConfig(open_for=10, window_size=4, failure_ratio=0.5, window_seconds=30)
    breaker = CircuitBreaker("tiempo2", config, clock=lambda: now["value"])
    for _ in range(4):
        breaker.on_failure()
        now["value"] += 1
    assert breaker.state is CircuitState.OPEN


def test_window_seconds_excludes_consecutive():
    with pytest.raises(ContractViolation):
        BreakerConfig(open_for=1, consecutive_failures=2, window_seconds=30)


class StaticSource:
    def __init__(self) -> None:
        self.tokens = ["viejo", "nuevo"]
        self.invalidated = 0

    async def token(self) -> str:
        return self.tokens[0]

    def invalidate(self) -> None:
        self.invalidated += 1
        self.tokens.pop(0)


def dependency_client(handler, source=None) -> DependencyClient:
    process.ensure_service()
    return DependencyClient(
        "dep",
        "http://dep",
        BreakerConfig(open_for=1, consecutive_failures=5),
        10,
        transport=httpx.MockTransport(handler),
        token_source=source,
    )


async def test_401_retries_once_with_a_new_token():
    seen: list[str] = []

    def handler(request):
        seen.append(request.headers["authorization"])
        return httpx.Response(401 if len(seen) == 1 else 200)

    source = StaticSource()
    response = await deps.call(dependency_client(handler, source), "GET", "/x", timeout=1)
    assert response.status_code == 200
    assert seen == ["Bearer viejo", "Bearer nuevo"]
    assert source.invalidated == 1


async def test_second_401_is_returned_and_not_retried_forever():
    calls = {"n": 0}

    def handler(_):
        calls["n"] += 1
        return httpx.Response(401)

    source = StaticSource()
    source.tokens = ["a", "b", "c"]
    response = await deps.call(dependency_client(handler, source), "GET", "/x", timeout=1)
    assert response.status_code == 401 and calls["n"] == 2


async def test_without_token_source_there_is_no_authorization_or_retry():
    calls: list[httpx.Request] = []

    def handler(request):
        calls.append(request)
        return httpx.Response(401)

    response = await deps.call(dependency_client(handler), "GET", "/x", timeout=1)
    assert response.status_code == 401 and len(calls) == 1
    assert "authorization" not in calls[0].headers


async def test_post_form_once_translates_errors():
    def ok(request):
        assert b"grant_type=x" in request.content
        return httpx.Response(200, json={"access_token": "t"})

    assert (await deps.post_form_once("http://kc/t", {"grant_type": "x"}, 1, httpx.MockTransport(ok))) == {
        "access_token": "t"
    }
    with pytest.raises(DependencyUnavailable):
        await deps.post_form_once(
            "http://kc/t", {"grant_type": "x"}, 1, httpx.MockTransport(lambda _: httpx.Response(500))
        )


async def test_post_form_uses_the_timeout_and_verifies_tls(monkeypatch):
    seen = {}
    real = deps.httpx.AsyncClient

    def spy(**kwargs):
        seen.update(kwargs)
        return real(**kwargs)

    monkeypatch.setattr(deps.httpx, "AsyncClient", spy)
    transport = httpx.MockTransport(lambda _: httpx.Response(200, json={"a": 1}))
    assert await deps.post_form_once("http://kc/t", {"a": "b"}, 1.5, transport) == {"a": 1}
    assert seen["timeout"] == 1.5 and seen["verify"] is True and seen["transport"] is transport


async def test_post_form_refuses_https_without_a_ca(monkeypatch):
    monkeypatch.delenv(deps.CA_BUNDLE_ENV, raising=False)
    with pytest.raises(ContractViolation):
        await deps.post_form_once("https://kc/t", {"a": "b"}, 1)


def test_failure_exactly_at_the_edge_stays_in_the_window():
    now = {"value": 0.0}
    config = BreakerConfig(open_for=10, window_size=2, failure_ratio=1.0, window_seconds=30)
    breaker = CircuitBreaker("borde", config, clock=lambda: now["value"])
    breaker.on_failure()
    now["value"] = 30.0
    breaker.on_failure()
    assert breaker.state is CircuitState.OPEN


def test_only_the_expired_calls_are_dropped():
    now = {"value": 0.0}
    config = BreakerConfig(open_for=10, window_size=3, failure_ratio=1.0, window_seconds=30)
    breaker = CircuitBreaker("parcial", config, clock=lambda: now["value"])
    breaker.on_failure()
    now["value"] = 20.0
    breaker.on_failure()
    now["value"] = 31.0  # solo vencio la primera
    breaker.on_failure()
    assert breaker.state is CircuitState.CLOSED
    breaker.on_failure()
    assert breaker.state is CircuitState.OPEN


async def test_arguments_reach_the_request_on_both_attempts():
    seen: list[httpx.Request] = []

    def handler(request):
        seen.append(request)
        return httpx.Response(401 if len(seen) == 1 else 200)

    source = StaticSource()
    client = dependency_client(handler, source)
    deadline = datetime.now(UTC) + timedelta(seconds=30)
    await deps.call(client, "POST", "/ruta", timeout=1, deadline=deadline, headers={"x-a": "b"}, content=b"cuerpo")
    assert [r.method for r in seen] == ["POST", "POST"]
    assert [r.url.path for r in seen] == ["/ruta", "/ruta"]
    assert [r.content for r in seen] == [b"cuerpo", b"cuerpo"]
    assert [r.headers["x-a"] for r in seen] == ["b", "b"]
    assert all("x-vectra-deadline" in r.headers for r in seen)


async def test_a_spent_budget_stops_the_retry():
    now = {"value": datetime(2026, 1, 1, tzinfo=UTC)}
    deadline = now["value"] + timedelta(seconds=5)

    def handler(_):
        now["value"] = deadline + timedelta(seconds=1)
        return httpx.Response(401)

    process.ensure_service()
    client = DependencyClient(
        "dep",
        "http://dep",
        BreakerConfig(open_for=1, consecutive_failures=5),
        10,
        wall_clock=lambda: now["value"],
        transport=httpx.MockTransport(handler),
        token_source=StaticSource(),
    )
    with pytest.raises(DependencyTimeout):
        await deps.call(client, "GET", "/x", timeout=1, deadline=deadline)


async def test_sampled_flag_is_01():
    seen: list[str] = []

    def handler(request):
        seen.append(request.headers["traceparent"])
        return httpx.Response(200)

    correlation = vlog.correlation_id_var.set("a" * 32)
    span = vlog.span_id_var.set("b" * 16)
    try:
        await deps.call(dependency_client(handler), "GET", "/x", timeout=1)
    finally:
        vlog.correlation_id_var.reset(correlation)
        vlog.span_id_var.reset(span)
    assert seen == [f"00-{'a' * 32}-{'b' * 16}-01"]


async def test_outgoing_call_propagates_the_sampling_decision():
    seen: list[str] = []

    def handler(request):
        seen.append(request.headers["traceparent"])
        return httpx.Response(200)

    correlation = vlog.correlation_id_var.set("a" * 32)
    span = vlog.span_id_var.set("b" * 16)
    sampled = vlog.trace_sampled_var.set(False)
    try:
        await deps.call(dependency_client(handler), "GET", "/x", timeout=1)
    finally:
        vlog.correlation_id_var.reset(correlation)
        vlog.span_id_var.reset(span)
        vlog.trace_sampled_var.reset(sampled)
    assert seen == [f"00-{'a' * 32}-{'b' * 16}-00"]
