"""Paso 12 (CA-5), apagado (INF-U7-03; RESILIENCY-04): SIGTERM con una solicitud en curso no abandona el append."""

import asyncio
import json
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
from doubles.auth import service_headers
from strategies import auth as u0
from doubles.explainability import ExplainabilityDouble
from doubles.governance import GovernanceDouble
from doubles.kserve import KServeDouble
from doubles.registry import RegistryDouble
from doubles.samples import scoring_request
from doubles.servers import Server
from vectra_contracts.catalog import EntryType
from vectra_contracts.outcome import RecommendResult, Recommendation

TESTS = Path(__file__).resolve().parents[1]
ROOT = TESTS.parents[1]


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


async def wait_ready(port: int, process: subprocess.Popen[bytes]) -> None:
    async with httpx.AsyncClient() as client:
        for _ in range(300):
            assert process.poll() is None, "el proceso de scoring termino al arrancar"
            try:
                if (await client.get(f"http://127.0.0.1:{port}/readyz")).status_code == 200:
                    return
            except httpx.TransportError:
                pass
            await asyncio.sleep(0.05)
    raise AssertionError("scoring no quedo listo")


async def test_sigterm_half_a_second_into_a_request_whose_registry_answers_at_3_s_still_returns_the_recommendation() -> (
    None
):
    gov, kserve, explain, registry = (
        GovernanceDouble(),
        KServeDouble(),
        ExplainabilityDouble(),
        RegistryDouble(),
    )
    # P-U7-02: cada intento espera 2,5 s, asi que un registro que responde a los 3 s agota el primero; el reintento recupera el ack
    # original (misma llave) y la solicitud termina con su `registry_entry_id`: lo que debe sobrevivir al SIGTERM.
    registry.faults.delay = 3.0
    registry.delay_first_n = 1
    servers = [Server(double.app).start() for double in (gov, explain, registry, kserve)]
    port, ops_port = free_port(), free_port()
    env = {
        **os.environ,
        "GOV_URL": servers[0].url,
        "EXPLAIN_URL": servers[1].url,
        "REGISTRY_URL": servers[2].url,
        "KSERVE_URL": servers[3].url,  # la plantilla sin marcador: un solo host
        "JWKS_JSON": json.dumps(u0.jwks_document()),
        "PORT": str(port),
        "OPS_PORT": str(ops_port),
        "PYTHONPATH": os.pathsep.join(
            [str(TESTS), str(ROOT / "contracts" / "tests"), str(ROOT / "contracts")]
        ),
    }
    process = subprocess.Popen([sys.executable, "-m", "doubles.run_scoring"], env=env, cwd=ROOT)  # noqa: S603
    try:
        await wait_ready(ops_port, process)
        request = scoring_request()
        async with httpx.AsyncClient(timeout=15) as client:
            sent = asyncio.create_task(
                client.post(
                    f"http://127.0.0.1:{port}/v1/recommendations",
                    content=request.model_dump_json(),
                    headers={
                        "content-type": "application/json",
                        **service_headers("scoring-service", "case:recommend"),
                    },
                )
            )
            await asyncio.sleep(0.5)
            assert not sent.done()  # el registro responde a los 3 s: sigue en curso
            process.send_signal(signal.SIGTERM)
            response = await sent
        assert response.status_code == 200, response.text
        result = RecommendResult.from_wire(response.content)
        assert (
            isinstance(result, Recommendation) and result.registry_entry_id
        )  # entregada, con su entrada en el registro
        assert (
            len(registry.entries(EntryType.RECOMMENDATION)) == 1
        )  # una sola entrada: el reintento uso la misma llave
        started = time.monotonic()
        # uvicorn re-emite la senal capturada al terminar: el estado es `-SIGTERM`, no una caida
        assert await asyncio.to_thread(process.wait, 12) in (
            0,
            -signal.SIGTERM,
        )  # sale tras terminar lo en curso
        assert time.monotonic() - started < 10
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
        for server in servers:
            server.stop()


async def test_an_idle_process_exits_on_sigterm_within_the_graceful_window() -> None:
    gov, kserve, explain, registry = (
        GovernanceDouble(),
        KServeDouble(),
        ExplainabilityDouble(),
        RegistryDouble(),
    )
    servers = [Server(double.app).start() for double in (gov, explain, registry, kserve)]
    port, ops_port = free_port(), free_port()
    env = {
        **os.environ,
        "GOV_URL": servers[0].url,
        "EXPLAIN_URL": servers[1].url,
        "REGISTRY_URL": servers[2].url,
        "KSERVE_URL": servers[3].url,
        "JWKS_JSON": json.dumps(u0.jwks_document()),
        "PORT": str(port),
        "OPS_PORT": str(ops_port),
        "PYTHONPATH": os.pathsep.join(
            [str(TESTS), str(ROOT / "contracts" / "tests"), str(ROOT / "contracts")]
        ),
    }
    process = subprocess.Popen([sys.executable, "-m", "doubles.run_scoring"], env=env, cwd=ROOT)  # noqa: S603
    try:
        await wait_ready(ops_port, process)
        process.send_signal(signal.SIGTERM)
        started = time.monotonic()
        assert await asyncio.to_thread(process.wait, 12) in (0, -signal.SIGTERM)
        assert time.monotonic() - started < 10  # `GRACEFUL_SHUTDOWN` (INF-U7-03)
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
        for server in servers:
            server.stop()
