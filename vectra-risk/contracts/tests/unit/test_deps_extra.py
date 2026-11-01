"""Ramas restantes de `deps` y `logging` (NFR-U0-40: 100 %)."""

import json
import io

import httpx
import pytest

from vectra_common import logging as vlog
from vectra_common import process
from vectra_common.deps import BreakerConfig, CircuitBreaker, CircuitState, DependencyClient, _propagated_headers, _verify_context, call, fetch_json_once
from vectra_common.errors import DependencyUnavailable
from vectra_contracts.errors import ContractViolation


@pytest.fixture(autouse=True)
def service():
    process.reset_for_tests()
    process.ensure_service()
    yield
    process.reset_for_tests()


def test_half_open_needs_close_after_successes():
    now = {"t": 0.0}
    breaker = CircuitBreaker("half", BreakerConfig(open_for=1, consecutive_failures=1, close_after=2), lambda: now["t"])
    breaker.on_failure()
    now["t"] = 1
    assert breaker.allow()
    breaker.on_success()
    assert breaker.state is CircuitState.HALF_OPEN
    assert breaker.allow()
    breaker.on_success()
    assert breaker.state is CircuitState.CLOSED


async def test_aclose_and_real_send():
    client = DependencyClient("c", "http://dep", BreakerConfig(open_for=1, consecutive_failures=1), 1, transport=httpx.MockTransport(lambda r: httpx.Response(200)))
    assert (await call(client, "POST", "/", timeout=1, headers={"x": "1"}, content=b"{}")).status_code == 200
    await client.aclose()


def test_headers_without_trace_context():
    assert _propagated_headers({"a": "b"}, None) == {"a": "b"}


async def test_batch_errors_do_not_touch_a_breaker():
    process.reset_for_tests()
    process.init("batch")

    def boom(_):
        raise httpx.ConnectError("x")

    def slow(_):
        raise httpx.ReadTimeout("x")

    for backend in (boom, slow):
        client = DependencyClient("b", "http://dep", "disabled", 1, transport=httpx.MockTransport(backend))
        with pytest.raises(DependencyUnavailable):
            await call(client, "GET", "/", timeout=1)


async def test_fetch_json_once_errors_become_503():
    bad = httpx.MockTransport(lambda r: httpx.Response(500))
    with pytest.raises(DependencyUnavailable):
        await fetch_json_once("http://dep/certs", 1, transport=bad)
    text = httpx.MockTransport(lambda r: httpx.Response(200, content=b"no json"))
    with pytest.raises(DependencyUnavailable):
        await fetch_json_once("http://dep/certs", 1, transport=text)
    assert await fetch_json_once("http://dep/certs", 1, transport=httpx.MockTransport(lambda r: httpx.Response(200, json={"keys": []}))) == {"keys": []}


def test_foreign_extra_key_is_dropped_even_in_strict(monkeypatch):
    monkeypatch.setenv("VECTRA_LOG_STRICT", "1")
    assert vlog.allowlist_filter(None, "", {"event": "texto", "otro": 1}) == {}


def test_own_extra_key_raises_in_strict(monkeypatch):
    monkeypatch.setenv("VECTRA_LOG_STRICT", "1")
    with pytest.raises(vlog.LogContractViolation):
        vlog.allowlist_filter(None, "", {"_vectra_own": True, "otro": 1})


def test_context_without_correlation():
    out = io.StringIO()
    vlog.configure("x", out)
    vlog.log_access(status=200)
    record = json.loads(out.getvalue())
    assert "correlation_id" not in record and "span_id" not in record
    token = vlog.correlation_id_var.set("c" * 32)
    try:
        out.truncate(0)
        out.seek(0)
        vlog.log_access(status=200)
    finally:
        vlog.correlation_id_var.reset(token)
    record = json.loads(out.getvalue())
    assert record["correlation_id"] == "c" * 32 and "span_id" not in record
    vlog.configure("x")


def test_window_successes_do_not_count_as_failures():
    breaker = CircuitBreaker("w", BreakerConfig(open_for=1, window_size=4, failure_ratio=0.5))
    for _ in range(3):
        breaker.on_success()
    breaker.on_failure()
    assert breaker.state is CircuitState.CLOSED


def test_window_slides():
    breaker = CircuitBreaker("w", BreakerConfig(open_for=1, window_size=3, failure_ratio=0.6))
    for _ in range(3):
        breaker.on_success()
    breaker.on_failure()
    assert breaker.state is CircuitState.CLOSED
    breaker.on_failure()
    assert breaker.state is CircuitState.OPEN


def test_window_not_evaluated_until_full():
    breaker = CircuitBreaker("w", BreakerConfig(open_for=1, window_size=3, failure_ratio=0.1))
    breaker.on_failure()
    assert breaker.state is CircuitState.CLOSED


@pytest.mark.parametrize("kwargs", [{"window_size": 5, "consecutive_failures": 3}, {"failure_ratio": 0.5, "consecutive_failures": 3}])
def test_partial_window_with_consecutive_is_rejected(kwargs):
    with pytest.raises(ContractViolation):
        BreakerConfig(open_for=1, **kwargs)


def test_metric_uses_dependency_label():
    from uuid import uuid4

    from vectra_common.metrics import CIRCUIT_STATE

    label = f"etiqueta-{uuid4()}"  # unica: mutmut hace fork de un proceso con el registro ya poblado
    DependencyClient(label, "http://dep", BreakerConfig(open_for=1, consecutive_failures=1), 1, transport=httpx.MockTransport(lambda r: httpx.Response(200)))
    assert (label,) in CIRCUIT_STATE._metrics


def test_connection_limits_are_applied():
    client = DependencyClient("l", "http://dep", BreakerConfig(open_for=1, consecutive_failures=1), 3)
    pool = client._client._transport._pool
    assert pool._max_connections == 3 and pool._max_keepalive_connections == 3


async def test_timeout_applies_to_every_phase_including_pool():
    seen = {}

    def backend(request):
        seen.update(request.extensions["timeout"])
        return httpx.Response(200)

    client = DependencyClient("t", "http://dep", BreakerConfig(open_for=1, consecutive_failures=1), 1, transport=httpx.MockTransport(backend))
    await call(client, "GET", "/", timeout=0.5)
    assert seen == {"connect": 0.5, "read": 0.5, "write": 0.5, "pool": 0.5}


async def test_body_and_headers_are_sent():
    seen = []

    def backend(request):
        seen.append(request)
        return httpx.Response(200)

    client = DependencyClient("s", "http://dep", BreakerConfig(open_for=1, consecutive_failures=1), 1, transport=httpx.MockTransport(backend))
    await call(client, "POST", "/x", timeout=1, headers={"x-prueba": "1"}, content=b'{"a":1}')
    assert seen[0].content == b'{"a":1}' and seen[0].headers["x-prueba"] == "1" and seen[0].method == "POST" and seen[0].url.path == "/x"


def test_traceparent_needs_both_ids():
    token = vlog.correlation_id_var.set("c" * 32)
    try:
        assert "traceparent" not in _propagated_headers(None, None)
    finally:
        vlog.correlation_id_var.reset(token)
    token = vlog.span_id_var.set("d" * 16)
    try:
        assert "traceparent" not in _propagated_headers(None, None)
    finally:
        vlog.span_id_var.reset(token)


async def test_fetch_json_once_applies_timeout():
    seen = {}

    def backend(request):
        seen.update(request.extensions["timeout"])
        return httpx.Response(200, json={})

    await fetch_json_once("http://dep/certs", 2, transport=httpx.MockTransport(backend))
    assert seen["read"] == 2


def test_failure_count_resets_after_closing():
    now = {"t": 0.0}
    breaker = CircuitBreaker("r", BreakerConfig(open_for=1, consecutive_failures=2), lambda: now["t"])
    breaker.on_failure()
    breaker.on_failure()
    now["t"] = 1
    assert breaker.allow()
    breaker.on_success()
    assert breaker.state is CircuitState.CLOSED
    breaker.on_failure()
    assert breaker.state is CircuitState.CLOSED


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"window_size": 5, "failure_ratio": 0.5, "consecutive_failures": 3}, "ventana y consecutive_failures son excluyentes"),
        ({}, "el breaker necesita ventana o consecutive_failures"),
        ({"window_size": 5}, "la ventana necesita window_size y failure_ratio"),
    ],
)
def test_breaker_config_messages(kwargs, message):
    with pytest.raises(ContractViolation) as error:
        BreakerConfig(open_for=1, **kwargs)
    assert str(error.value) == message


def test_disabled_message():
    with pytest.raises(ContractViolation) as error:
        DependencyClient("m", "http://dep", "disabled", 1)
    assert str(error.value) == 'breaker="disabled" solo en procesos batch'


def test_verify_context_messages_and_http_default(monkeypatch):
    assert _verify_context("http://dep") is True
    monkeypatch.delenv("VECTRA_CA_BUNDLE", raising=False)
    with pytest.raises(ContractViolation) as error:
        _verify_context("https://dep")
    assert str(error.value) == "VECTRA_CA_BUNDLE no apunta a un archivo: nunca se desactiva la verificacion"


def test_traceparent_header_name_is_exact():
    tokens = vlog.correlation_id_var.set("c" * 32), vlog.span_id_var.set("d" * 16)
    try:
        assert _propagated_headers(None, None) == {"traceparent": f"00-{'c' * 32}-{'d' * 16}-01"}
    finally:
        vlog.correlation_id_var.reset(tokens[0])
        vlog.span_id_var.reset(tokens[1])


def test_probe_counter_is_reset_to_zero():
    now = {"t": 0.0}
    breaker = CircuitBreaker("p", BreakerConfig(open_for=1, consecutive_failures=1, close_after=2), lambda: now["t"])
    breaker.on_failure()
    now["t"] = 1
    assert breaker.state is CircuitState.HALF_OPEN and breaker._probes_in_flight == 0
    assert breaker.allow() and breaker._probes_in_flight == 1
    breaker.on_success()
    assert breaker._probes_in_flight == 0
