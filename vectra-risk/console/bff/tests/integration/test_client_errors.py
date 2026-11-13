"""Paso 6 (CA-3): `POST /api/console/client-errors` (BR-U10-22; P-U10-09; NFR-U10-34; US-611).

`ClientErrorReport` (`extra = "forbid"`), evento `console.client_error`, metrica `vectra_console_client_errors_total{error_code}`
y 204. La validacion del cuerpo la hace U0 antes del handler: lo que no valida es 422 sin evento ni metrica.
"""

import asyncio
import re
import subprocess
import sys
from collections.abc import Iterator
from typing import Any

import bff_metrics
import bff_tokens
import pytest
from bff_doubles import Doubles
from bff_support import Bff, EventLog
from bff_world import populate
from hypothesis import given
from hypothesis import strategies as st
from vectra_contracts.catalog import LOG_RECORD_FIELDS

from console_bff.app import build
from console_bff.client_errors import principal_role
from console_bff.metrics import CLIENT_ERROR_CODES

ANALISTA = bff_tokens.bearer(["analista"])
URL = "/api/console/client-errors"
VALID = {"error_code": "chunk_load_failed", "route_template": "/casos/:id", "app_version": "1.4.2"}
SERIES = "vectra_console_client_errors_total"


def totals(series: dict[str, list[tuple[dict[str, str], float]]]) -> dict[str, float]:
    return {labels["error_code"]: number for labels, number in series[SERIES]}


async def test_a_valid_report_is_204_one_event_and_the_series_goes_up_by_one(
    bff: Bff, events: EventLog
) -> None:
    before = totals(await bff_metrics.scrape(bff))
    response = await bff.client.post(URL, headers=ANALISTA, json=VALID)
    assert response.status_code == 204 and response.content == b""
    after = totals(await bff_metrics.scrape(bff))  # lectura de vuelta en /metrics, no el 204
    assert after["chunk_load_failed"] == before["chunk_load_failed"] + 1
    assert {k: v for k, v in after.items() if k != "chunk_load_failed"} == {
        k: v for k, v in before.items() if k != "chunk_load_failed"
    }
    [event] = events.named("console.client_error")
    assert event == {
        "error_code": "chunk_load_failed",
        "route_template": "/casos/:id",
        "app_version": "1.4.2",
        "principal_subject": "user-1",
        "principal_role": "analista",
    }


async def test_the_body_correlation_id_is_validated_and_not_emitted(bff: Bff, events: EventLog) -> None:
    """P-7 (a): el del registro es el de la solicitud al BFF; el del cuerpo no se emite (candidata de U0)."""
    sent = {**VALID, "correlation_id": "c" * 32}
    assert (await bff.client.post(URL, headers=ANALISTA, json=sent)).status_code == 204
    [event] = events.named("console.client_error")
    assert "correlation_id" not in event
    assert (
        await bff.client.post(URL, headers=ANALISTA, json={**VALID, "correlation_id": "XYZ"})
    ).status_code == 422


async def test_principal_role_is_the_first_alphabetically_like_case_and_bias(
    bff: Bff, events: EventLog
) -> None:
    await bff.client.post(URL, headers=bff_tokens.bearer(["cro", "analista"]), json=VALID)
    assert events.named("console.client_error")[0]["principal_role"] == "analista"


def test_principal_role_without_roles_is_empty() -> None:
    from datetime import UTC, datetime

    from vectra_contracts.models.api import Principal

    assert (
        principal_role(Principal(subject="s", kind="service", token_expiry=datetime(2030, 1, 1, tzinfo=UTC)))
        == ""
    )


@pytest.mark.parametrize(
    "bad",
    [
        {**VALID, "message": "Uncaught TypeError: x is undefined"},  # un mensaje libre
        {**VALID, "stack": "at foo (bundle.js:1)"},  # una traza
        {**VALID, "error_code": "boom"},  # fuera del catalogo cerrado
        {**VALID, "app_version": "v1"},  # no es SemVer
        {**VALID, "app_version": "1.2"},
        {**VALID, "route_template": "x" * 201},
        {"route_template": "/", "app_version": "1.0.0"},  # sin error_code
    ],
)
async def test_an_invalid_body_is_422_without_event_or_metric(
    bff: Bff, events: EventLog, bad: dict[str, Any]
) -> None:
    before = totals(await bff_metrics.scrape(bff))
    response = await bff.client.post(URL, headers=ANALISTA, json=bad)
    assert response.status_code == 422 and response.json()["code"] == "validation_error"
    assert events.named("console.client_error") == []
    assert totals(await bff_metrics.scrape(bff)) == before
    assert (
        "Uncaught" not in response.text and "bundle.js" not in response.text
    )  # el cuerpo no vuelve en el error


async def test_a_role_outside_the_business_roles_cannot_report(bff: Bff, events: EventLog) -> None:
    response = await bff.client.post(URL, headers=bff_tokens.bearer([]), json=VALID)
    assert response.status_code == 403 and events.named("console.client_error") == []


async def test_the_six_series_exist_and_are_closed_over_the_catalog(bff: Bff) -> None:
    assert set(CLIENT_ERROR_CODES) == {
        "render_error",
        "chunk_load_failed",
        "unhandled_rejection",
        "api_contract_mismatch",
        "stepup_failed",
        "csp_violation",
    }
    assert set(totals(await bff_metrics.scrape(bff))) == set(CLIENT_ERROR_CODES)


FRESH = """
import asyncio, httpx, os
from console_bff.app import build_app

async def main():
    app = build_app()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app.state.ops_app), base_url="http://ops.test") as ops:
        print((await ops.get("/metrics")).text)
    await app.state.upstreams.aclose()

asyncio.run(main())
"""


def test_a_freshly_started_bff_shows_the_six_series_at_zero() -> None:
    """P-U10-09: `GET /metrics` recien iniciado (proceso nuevo, sin una sola solicitud) muestra las seis series en 0."""
    env = {
        "PATH": "/usr/bin",
        "VECTRA_OIDC_ISSUER": "http://kc.test/auth/realms/vectra",
        "VECTRA_JWKS_URL": "http://kc.test/certs",
        "VECTRA_CASE_URL": "http://case.test",
        "VECTRA_GOVERNANCE_URL": "http://gov.test",
        "VECTRA_REGISTRY_URL": "http://reg.test",
        "VECTRA_EXPLAINABILITY_URL": "http://exp.test",
        "VECTRA_BIAS_URL": "http://bias.test",
    }
    done = subprocess.run(
        [sys.executable, "-c", FRESH], env=env, capture_output=True, text=True, timeout=60, check=True
    )  # noqa: S603
    lines = re.findall(rf'^{SERIES}\{{error_code="(\w+)"\}} (\S+)$', done.stdout, flags=re.MULTILINE)
    assert sorted(code for code, _ in lines) == sorted(CLIENT_ERROR_CODES)
    assert {float(number) for _, number in lines} == {0.0}


# --- PBT-U0-07 en modo estricto: ningun campo del evento sale de la allowlist ---------------------------------------


@pytest.fixture(scope="module")
def strict_runner() -> Iterator[tuple[asyncio.Runner, Bff]]:
    import os

    os.environ["VECTRA_LOG_STRICT"] = "1"
    doubles = Doubles()
    populate(doubles)
    app = build(doubles.urls(), authenticator=bff_tokens.authenticator(), transports=doubles.transports())
    import httpx

    client = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app, raise_app_exceptions=False), base_url="http://bff.test"
    )
    with asyncio.Runner() as runner:
        yield runner, Bff(client, app, doubles)
        runner.run(client.aclose())
        runner.run(app.state.upstreams.aclose())
    del os.environ["VECTRA_LOG_STRICT"]


_report = st.fixed_dictionaries(
    {
        "error_code": st.sampled_from(CLIENT_ERROR_CODES),
        "route_template": st.text(max_size=200),
        "app_version": st.from_regex(r"\A\d{1,3}\.\d{1,3}\.\d{1,3}\Z"),
    },
    optional={"correlation_id": st.from_regex(r"\A[0-9a-f]{32}\Z")},
)


@given(report=_report, roles=st.lists(st.sampled_from(bff_tokens.ROLES), min_size=1, max_size=4, unique=True))
def test_pbt_u0_07_console_client_error_never_leaves_the_log_allowlist(
    strict_runner: tuple[asyncio.Runner, Bff], report: dict[str, Any], roles: list[str]
) -> None:
    """Con `VECTRA_LOG_STRICT=1`, un campo fuera de la allowlist hace fallar el handler (500); aqui siempre 204."""
    runner, bff = strict_runner
    recorded: list[dict[str, Any]] = []
    from vectra_common import logging as vlog

    original = vlog.log_event

    def spy(event: Any, **fields: Any) -> None:
        recorded.append(fields)
        original(event, **fields)

    vlog.log_event = spy  # type: ignore[assignment]
    try:
        response = runner.run(bff.client.post(URL, headers=bff_tokens.bearer(roles), json=report))
    finally:
        vlog.log_event = original  # type: ignore[assignment]
    assert response.status_code == 204
    [fields] = [f for f in recorded if f.get("error_code") == report["error_code"]][-1:]
    assert set(fields) <= LOG_RECORD_FIELDS
    assert set(fields) == {
        "error_code",
        "route_template",
        "app_version",
        "principal_subject",
        "principal_role",
    }
