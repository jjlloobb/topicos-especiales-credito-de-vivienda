"""`deps` (P-U0-07, NFR-U0-23)."""

import asyncio
import datetime as dt
import inspect
import ipaddress
import ssl
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from vectra_common import process
from vectra_common.deps import BreakerConfig, CircuitBreaker, CircuitState, DependencyClient, call, fetch_json_once
from vectra_common.errors import DependencyTimeout, DependencyUnavailable
from vectra_common.logging import correlation_id_var, span_id_var
from vectra_common.metrics import CIRCUIT_STATE
from vectra_contracts.errors import ContractViolation

NOW = datetime(2026, 10, 31, 12, tzinfo=UTC)
CONFIG = BreakerConfig(open_for=60, consecutive_failures=3)


class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


@pytest.fixture(autouse=True)
def service_process():
    process.reset_for_tests()
    process.ensure_service()
    yield
    process.reset_for_tests()


class Backend:
    def __init__(self, status=200, exc=None):
        self.status, self.exc, self.calls, self.requests = status, exc, 0, []

    def __call__(self, request):
        self.calls += 1
        self.requests.append(request)
        if self.exc:
            raise self.exc
        return httpx.Response(self.status)


def make(backend, breaker=CONFIG, clock=None, wall=lambda: NOW):
    return DependencyClient("dep", "http://dep", breaker, 5, clock=clock or Clock(), wall_clock=wall, transport=httpx.MockTransport(backend))


def test_timeout_is_required():
    assert inspect.signature(call).parameters["timeout"].default is inspect.Parameter.empty
    assert inspect.signature(call).parameters["timeout"].kind is inspect.Parameter.KEYWORD_ONLY


async def test_call_without_timeout_fails_at_runtime():
    with pytest.raises(TypeError):
        await call(make(Backend()), "GET", "/")  # type: ignore[call-arg]


async def test_effective_timeout_is_min_and_header_propagated():
    backend = Backend()
    client = make(backend)
    deadline = NOW + timedelta(milliseconds=500)
    await call(client, "GET", "/", timeout=2, deadline=deadline)
    request = backend.requests[0]
    assert request.extensions["timeout"]["read"] == pytest.approx(0.5)
    assert request.headers["x-vectra-deadline"] == "2026-10-31T12:00:00.500Z"


async def test_far_future_deadline_never_extends():
    backend = Backend()
    await call(make(backend), "GET", "/", timeout=1, deadline=NOW + timedelta(hours=1))
    assert backend.requests[0].extensions["timeout"]["read"] == 1


async def test_exhausted_budget_does_not_call():
    backend = Backend()
    with pytest.raises(DependencyTimeout):
        await call(make(backend), "GET", "/", timeout=1, deadline=NOW)
    assert backend.calls == 0


async def test_traceparent_propagated():
    backend = Backend()
    t1, t2 = correlation_id_var.set("a" * 32), span_id_var.set("b" * 16)
    try:
        await call(make(backend), "GET", "/", timeout=1)
    finally:
        correlation_id_var.reset(t1)
        span_id_var.reset(t2)
    assert backend.requests[0].headers["traceparent"] == f"00-{'a' * 32}-{'b' * 16}-01"


async def test_4xx_do_not_open():
    backend = Backend(status=404)
    client = make(backend)
    for _ in range(20):
        assert (await call(client, "GET", "/", timeout=1)).status_code == 404
    assert client.breaker.state is CircuitState.CLOSED


async def test_open_makes_no_call_and_is_fast():
    backend = Backend(status=500)
    client = make(backend)
    for _ in range(3):
        await call(client, "GET", "/", timeout=1)
    assert client.breaker.state is CircuitState.OPEN
    calls = backend.calls
    loop = asyncio.get_running_loop()
    started = loop.time()
    with pytest.raises(DependencyUnavailable):
        await call(client, "GET", "/", timeout=1)
    assert loop.time() - started < 0.01
    assert backend.calls == calls


async def test_circuit_state_metric_encoding():
    clock = Clock()
    breaker = CircuitBreaker("metric-dep", CONFIG, clock)
    gauge = CIRCUIT_STATE.labels(dependency="metric-dep")
    assert gauge._value.get() == 0
    for _ in range(3):
        breaker.on_failure()
    assert gauge._value.get() == 2
    clock.t = 60
    assert breaker.state is CircuitState.HALF_OPEN and gauge._value.get() == 1


async def test_consecutive_mode_i():
    clock = Clock()
    backend = Backend(status=500)
    client = make(backend, clock=clock)
    for status in (500, 500):
        backend.status = status
        await call(client, "GET", "/", timeout=1)
    backend.status = 200
    await call(client, "GET", "/", timeout=1)
    backend.status = 500
    for _ in range(2):
        await call(client, "GET", "/", timeout=1)
    assert client.breaker.state is CircuitState.CLOSED
    await call(client, "GET", "/", timeout=1)
    assert client.breaker.state is CircuitState.OPEN
    clock.t = 60
    # una sola llamada de prueba
    assert client.breaker.allow() and not client.breaker.allow()
    client.breaker.on_success()
    assert client.breaker.state is CircuitState.CLOSED


async def test_probe_failure_reopens_for_open_for():
    clock = Clock()
    backend = Backend(status=500)
    client = make(backend, clock=clock)
    for _ in range(3):
        await call(client, "GET", "/", timeout=1)
    clock.t = 60
    await call(client, "GET", "/", timeout=1)
    assert client.breaker.state is CircuitState.OPEN
    clock.t = 119
    assert client.breaker.state is CircuitState.OPEN
    clock.t = 120
    assert client.breaker.state is CircuitState.HALF_OPEN


async def test_consecutive_mode_4xx_do_not_count():
    backend = Backend(status=400)
    client = make(backend)
    for _ in range(3):
        await call(client, "GET", "/", timeout=1)
    assert client.breaker.state is CircuitState.CLOSED


@pytest.mark.parametrize("kwargs", [{"window_size": 5, "failure_ratio": 0.5, "consecutive_failures": 3}, {}, {"window_size": 5}])
def test_invalid_breaker_config(kwargs):
    with pytest.raises(ContractViolation):
        BreakerConfig(open_for=1, **kwargs)


async def test_window_mode():
    clock = Clock()
    backend = Backend()
    client = make(backend, BreakerConfig(open_for=10, window_size=4, failure_ratio=0.5), clock)
    for status in (200, 200, 500):
        backend.status = status
        await call(client, "GET", "/", timeout=1)
    assert client.breaker.state is CircuitState.CLOSED
    await call(client, "GET", "/", timeout=1)
    assert client.breaker.state is CircuitState.OPEN


async def test_transport_errors_wrapped_and_counted():
    client = make(Backend(exc=httpx.ConnectError("x")))
    with pytest.raises(DependencyUnavailable):
        await call(client, "GET", "/", timeout=1)
    client = make(Backend(exc=httpx.ReadTimeout("x")))
    with pytest.raises(DependencyTimeout):
        await call(client, "GET", "/", timeout=1)
    assert client.breaker._consecutive == 1


async def test_pool_exhausted_ends_in_timeout():
    class PoolLimited(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request):
            raise httpx.PoolTimeout("agotado")

    client = DependencyClient("pool", "http://dep", CONFIG, 1, transport=PoolLimited())
    with pytest.raises(DependencyTimeout):
        await call(client, "GET", "/", timeout=0.01)


def test_disabled_only_in_batch():
    with pytest.raises(ContractViolation):
        make(Backend(), "disabled")
    process.reset_for_tests()
    process.init("batch")
    assert make(Backend(), "disabled").breaker is None


async def test_disabled_never_opens_and_emits_no_state():
    process.reset_for_tests()
    process.init("batch")
    backend = Backend(status=500)
    client = DependencyClient("sin-breaker", "http://dep", "disabled", 5, transport=httpx.MockTransport(backend))
    for _ in range(11):
        await call(client, "GET", "/", timeout=1)
    assert backend.calls == 11
    assert "sin-breaker" not in {labels[0] for labels in CIRCUIT_STATE._metrics}


def test_client_before_process_init_fails():
    process.reset_for_tests()
    with pytest.raises(ContractViolation):
        make(Backend())


def test_process_init_twice_fails():
    process.reset_for_tests()
    process.init("batch")
    with pytest.raises(ContractViolation):
        process.init("batch")
    with pytest.raises(ContractViolation):
        process.ensure_service()


def _cert(name: str, tmp: Path):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, name)])
    now = dt.datetime.now(dt.UTC)
    cert = (
        x509.CertificateBuilder().subject_name(subject).issuer_name(subject).public_key(key.public_key())
        .serial_number(x509.random_serial_number()).not_valid_before(now - dt.timedelta(days=1)).not_valid_after(now + dt.timedelta(days=1))
        .add_extension(x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]), critical=False)
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(key, hashes.SHA256())
    )
    cert_path, key_path = tmp / f"{name}.crt", tmp / f"{name}.key"
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    return cert_path, key_path


async def _serve(cert, key):
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(cert, key)

    async def respond(reader, writer):
        await reader.readuntil(b"\r\n\r\n")
        writer.write(b'HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: 11\r\nConnection: close\r\n\r\n{"keys":[]}')
        await writer.drain()
        writer.close()

    return await asyncio.start_server(respond, "127.0.0.1", 0, ssl=context)


async def test_ca_bundle_verifies_and_other_ca_rejected(tmp_path, monkeypatch):
    server_cert, server_key = _cert("server", tmp_path)
    other_cert, _ = _cert("other", tmp_path)
    server = await _serve(server_cert, server_key)
    port = server.sockets[0].getsockname()[1]
    url = f"https://127.0.0.1:{port}/certs"
    async with server:
        monkeypatch.setenv("VECTRA_CA_BUNDLE", str(server_cert))
        assert await fetch_json_once(url, 2) == {"keys": []}
        monkeypatch.setenv("VECTRA_CA_BUNDLE", str(other_cert))
        with pytest.raises(DependencyUnavailable):
            await fetch_json_once(url, 2)


def test_missing_ca_bundle_fails(monkeypatch, tmp_path):
    monkeypatch.delenv("VECTRA_CA_BUNDLE", raising=False)
    with pytest.raises(ContractViolation):
        DependencyClient("d", "https://x", CONFIG, 1)
    monkeypatch.setenv("VECTRA_CA_BUNDLE", str(tmp_path / "no-existe.pem"))
    with pytest.raises(ContractViolation):
        DependencyClient("d", "https://x", CONFIG, 1)
