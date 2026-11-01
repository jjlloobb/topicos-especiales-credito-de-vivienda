"""NFR-U0-01..03 (P-U0-09): percentiles propios sobre 2000 muestras."""

import asyncio
import json
import statistics
import time
from datetime import date

import pytest
from strategies import auth as a
from strategies.domain import CASE, NOW, SHA, application_dict, application_from, dictionary, explanation

from vectra_common import process
from vectra_contracts.catalog import Outcome, Role, ServingState
from vectra_contracts.labels import derive, derive_monitoring_labels
from vectra_contracts.models.api import DecisionIn, DecisionRef
from vectra_contracts.models.explanation import PolicyResult, Prediction, RegistryAck
from vectra_contracts.models.features import FeatureSpec
from vectra_contracts.outcome import build_outcome, check_preconditions
from vectra_contracts.routes import RouteContract

pytestmark = pytest.mark.benchmark
SAMPLES = 2000


def percentiles(samples, benchmark):
    cuts = statistics.quantiles(samples, n=100)
    benchmark.extra_info.update(p95_ms=cuts[94] * 1000, p99_ms=cuts[98] * 1000)


def sample(fn):
    out = []
    for _ in range(SAMPLES):
        start = time.perf_counter()
        fn()
        out.append(time.perf_counter() - start)
    return out


def test_bench_outcome(benchmark):
    pred = Prediction(model_version_id="mv-1", score="0.5000", confidence="0.9000")
    pol = PolicyResult(policy_version_id="p", outcome=Outcome.FAVORABLE, reasons=[])
    ack = RegistryAck(registry_entry_id="1", seq=1, recorded_at=NOW)
    expl, dic = explanation(), dictionary()

    def run():
        ready = check_preconditions(CASE, ServingState.ACTIVO, "mv-1", "mv-1", pred, pol, expl, dic, SHA, NOW)
        build_outcome(ready, ack, NOW)

    percentiles(benchmark.pedantic(lambda: sample(run), rounds=1, iterations=1), benchmark)


def test_bench_derive(benchmark):
    app = application_from(application_dict())
    spec = FeatureSpec(model_version_id="m", features=[])
    day = date(2026, 10, 31)

    def run():
        derive(app, day, spec)
        derive_monitoring_labels(app, day)

    percentiles(benchmark.pedantic(lambda: sample(run), rounds=1, iterations=1), benchmark)


def test_bench_pipeline(benchmark):
    process.reset_for_tests()
    route = RouteContract("svc", "POST", "/v1/y", DecisionIn, DecisionRef, roles=frozenset({Role.ANALISTA}))
    from vectra_common.app_factory import create_app

    app = create_app("svc", [route], {("POST", "/v1/y"): a.ok_handler}, authenticator=a.authenticator())
    import logging

    logging.getLogger().handlers[:] = [logging.NullHandler()]
    body = json.dumps({"decision": "sigue", "final_outcome": "favorable", "used_factors": ["ninguno"], "justification": ""}).encode()
    body = body + b" " * (32 * 1024 - len(body))
    headers = [(b"authorization", f"Bearer {a.token()}".encode()), (b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())]
    scope = {"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": "POST", "path": "/v1/y", "raw_path": b"/v1/y", "query_string": b"", "headers": headers, "server": ("t", 80), "client": ("t", 1), "scheme": "http", "root_path": ""}

    async def once():
        sent = {"done": False}

        async def receive():
            if sent["done"]:
                return {"type": "http.disconnect"}
            sent["done"] = True
            return {"type": "http.request", "body": body, "more_body": False}

        async def send(_message):
            return None

        await app(dict(scope), receive, send)

    async def run_all():
        out = []
        for _ in range(SAMPLES):
            start = time.perf_counter()
            await once()
            out.append(time.perf_counter() - start)
        return out

    percentiles(benchmark.pedantic(lambda: asyncio.run(run_all()), rounds=1, iterations=1), benchmark)
    process.reset_for_tests()
