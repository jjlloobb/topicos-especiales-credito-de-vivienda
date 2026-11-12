"""Paso 7 (CA-4): PBT-U10-01, la matriz rol x endpoint (BR-U10-19; NFR-U10-46; US-602).

Para todo endpoint, todo rol y todo estado de token, la respuesta es la de la matriz de C03 (2xx, 401, 403 o `mfa_required`) y cada
401/403 emite `authz.denied`. El **oraculo** son las columnas «Roles» y «MFA» de C03 (`component-methods.md`, via
`tools/role_matrix.py`), nunca `REGISTRY` ni el codigo del BFF.

Dos formas, porque 500 ejemplos de Hypothesis no garantizan cubrir las celdas: las 270 celdas (30 endpoints x las 9 columnas del
plan) como prueba parametrizada, y el muestreo de Hypothesis sobre roles arbitrarios (subconjuntos, varios roles a la vez) y los
seis estados de token, tambien la firma ajena.

Resultado esperado por celda: expirado u otra audiencia (o firma ajena) -> 401 `unauthenticated`; rol fuera de «Roles» -> 403
`forbidden`; rol valido en una ruta con MFA y sin MFA reciente -> 403 `mfa_required`; lo demas -> 2xx. El rol va antes que la MFA.
P-3 (a): `principal_subject` en cada 403 y su **ausencia** en cada 401 (no se registra el `sub` de un token sin verificar).
"""

import asyncio
from collections.abc import Iterator
from typing import Any

import bff_tokens
import bff_world as w
import httpx
import pytest
import role_matrix
from bff_doubles import Doubles
from bff_support import Bff, EventLog
from hypothesis import given
from hypothesis import strategies as st
from vectra_common import logging as vlog
from vectra_common.metrics import REGISTRY as METRICS

from console_bff.app import build

ORACLE = role_matrix.from_c03()  # (metodo, ruta) -> (roles, mfa), de C03
COLUMNS = (
    "analista",
    "ingeniero_riesgo",
    "cro",
    "cumplimiento",
    "sin_rol",
    "expirado",
    "otra_audiencia",
    "acr_pwd",
    "auth_time_vencido",
)
CELLS = [(endpoint.operation_id, column) for endpoint in w.ENDPOINTS for column in COLUMNS]
ENDPOINT = {endpoint.operation_id: endpoint for endpoint in w.ENDPOINTS}


def allowed(endpoint: w.Endpoint) -> tuple[frozenset[str], bool]:
    return ORACLE[(endpoint.method, endpoint.path_template)]


def expected(endpoint: w.Endpoint, roles: frozenset[str], state: str) -> tuple[str, str | None]:
    """El oraculo: ('2xx', None), ('401', 'unauthenticated'), ('403', 'forbidden') o ('403', 'mfa_required')."""
    permitted, mfa = allowed(endpoint)
    if state in ("expired", "other_audience", "bad_signature"):
        return "401", "unauthenticated"
    if not roles & permitted:
        return "403", "forbidden"
    if mfa and state in ("acr_pwd", "stale_auth_time"):
        return "403", "mfa_required"
    return "2xx", None


def token_for(endpoint: w.Endpoint, column: str) -> tuple[dict[str, str], frozenset[str], str]:
    """El encabezado, los roles y el estado de token de una columna de la matriz."""
    permitted, _ = allowed(endpoint)
    role = sorted(permitted)[
        0
    ]  # un rol valido de la ruta, para que el estado del token sea lo unico que cambia
    if column in bff_tokens.ROLES:
        return bff_tokens.for_state("valid", [column]), frozenset({column}), "valid"
    if column == "sin_rol":
        return bff_tokens.for_state("valid", []), frozenset(), "valid"
    state = {
        "expirado": "expired",
        "otra_audiencia": "other_audience",
        "acr_pwd": "acr_pwd",
        "auth_time_vencido": "stale_auth_time",
    }[column]
    return bff_tokens.for_state(state, [role]), frozenset({role}), state


async def send(client: httpx.AsyncClient, endpoint: w.Endpoint, headers: dict[str, str]) -> httpx.Response:
    url = endpoint.path + (f"?{endpoint.query}" if endpoint.query else "")
    return await client.request(
        endpoint.method, url, headers={**headers, **endpoint.headers}, json=endpoint.body
    )


def denied(events: EventLog) -> list[dict[str, Any]]:
    return events.named("authz.denied")


def metric(code: str, template: str) -> float:
    return (
        METRICS.get_sample_value("vectra_authz_denied_total", {"code": code, "route_template": template})
        or 0.0
    )


def check(
    response: httpx.Response,
    endpoint: w.Endpoint,
    want: tuple[str, str | None],
    recorded: list[dict[str, Any]],
) -> None:
    status, code = want
    if status == "2xx":
        assert 200 <= response.status_code < 300, (endpoint.operation_id, response.status_code, response.text)
        assert recorded == []
        return
    assert response.status_code == int(status), (endpoint.operation_id, response.status_code, response.text)
    assert response.json()["code"] == code and "detail" not in response.json()
    [event] = recorded  # cada 401/403 deja un `authz.denied`
    assert event["error_code"] == code and event["route_template"] == endpoint.path_template
    if status == "403":
        assert event["principal_subject"] == "user-1"  # P-3 (a): en cada 403
    else:
        assert (
            "principal_subject" not in event
        )  # P-3 (a): ausente en cada 401 (no se registra un `sub` sin verificar)


@pytest.mark.parametrize(("operation_id", "column"), CELLS)
async def test_each_of_the_270_cells_is_the_one_of_c03(
    bff: Bff, events: EventLog, operation_id: str, column: str
) -> None:
    endpoint = ENDPOINT[operation_id]
    headers, roles, state = token_for(endpoint, column)
    before = metric(expected(endpoint, roles, state)[1] or "none", endpoint.path_template)
    response = await send(bff.client, endpoint, headers)
    want = expected(endpoint, roles, state)
    check(response, endpoint, want, denied(events))
    if want[0] != "2xx":
        assert (
            metric(want[1] or "", endpoint.path_template) == before + 1
        )  # la metrica de BR-U0-73 tambien sube


def test_the_270_cells_are_the_product_of_the_30_endpoints_and_the_9_columns() -> None:
    assert len(CELLS) == 270 == len(w.ENDPOINTS) * len(COLUMNS)
    assert len(w.ENDPOINTS) == 30 and len(ORACLE) == 30
    assert {(e.method, e.path_template) for e in w.ENDPOINTS} == set(ORACLE)


def test_the_matrix_covers_every_outcome_of_the_oracle() -> None:
    """Guarda contra una matriz que no ejercita algun resultado: hay 2xx, 401, 403 forbidden y 403 mfa_required."""
    outcomes = set()
    for operation_id, column in CELLS:
        _, roles, state = token_for(ENDPOINT[operation_id], column)
        outcomes.add(expected(ENDPOINT[operation_id], roles, state))
    assert outcomes == {
        ("2xx", None),
        ("401", "unauthenticated"),
        ("403", "forbidden"),
        ("403", "mfa_required"),
    }


# --- Hypothesis: roles arbitrarios x seis estados de token ---------------------------------------------------------------


@pytest.fixture(scope="module")
def world() -> Iterator[tuple[asyncio.Runner, Bff, list[tuple[str, dict[str, Any]]]]]:
    """Una sola app y un solo bucle para los 500 ejemplos; un espia sobre `log_event` que no pierde el modo strict."""
    import os

    os.environ["VECTRA_LOG_STRICT"] = "1"
    doubles = Doubles()
    w.populate(doubles)
    app = build(doubles.urls(), authenticator=bff_tokens.authenticator(), transports=doubles.transports())
    client = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app, raise_app_exceptions=False), base_url="http://bff.test"
    )
    records: list[tuple[str, dict[str, Any]]] = []
    original = vlog.log_event

    def spy(event: Any, **fields: Any) -> None:
        records.append((event.value, dict(fields)))
        original(event, **fields)

    vlog.log_event = spy  # type: ignore[assignment]
    with asyncio.Runner() as runner:
        yield runner, Bff(client, app, doubles), records
        runner.run(client.aclose())
        runner.run(app.state.upstreams.aclose())
    vlog.log_event = original  # type: ignore[assignment]
    del os.environ["VECTRA_LOG_STRICT"]


@given(
    endpoint=st.sampled_from(w.ENDPOINTS),
    roles=st.frozensets(st.sampled_from(bff_tokens.ROLES)),
    state=st.sampled_from(bff_tokens.TOKEN_STATES),
)
def test_pbt_u10_01_the_response_is_the_one_of_the_c03_matrix(
    world: tuple[asyncio.Runner, Bff, list[tuple[str, dict[str, Any]]]],
    endpoint: w.Endpoint,
    roles: frozenset[str],
    state: str,
) -> None:
    runner, bff, records = world
    records.clear()
    headers = bff_tokens.for_state(state, sorted(roles))
    response = runner.run(send(bff.client, endpoint, headers))
    recorded = [fields for name, fields in records if name == "authz.denied"]
    check(response, endpoint, expected(endpoint, roles, state), recorded)
