"""Paso 5 (CA-1): los clientes de los cinco destinos (P-U10-03, 04; NFR-U10-11, 30, 31, 32, 33; US-602).

Con dobles: timeout por operacion, cabecera de plazo, breaker por destino, una sola llamada ante un 5xx, aislamiento por vista
(E1, E2 y E3 de P-U10-05 §5) y pool agotado. Los timeouts son reales: la prueba de corte espera 1,5 s de verdad.
"""

import asyncio
import json
import threading
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

import bff_tokens
import bff_world as w
import httpx
import pytest
from bff_doubles import Doubles
from bff_support import Bff
from vectra_common import deps
from vectra_contracts.routes import REGISTRY

from console_bff import config
from console_bff.clients import DESTINATIONS, Upstreams

ALL = bff_tokens.bearer(
    bff_tokens.ROLES
)  # los cuatro roles y MFA reciente: pasa los controles de cualquier endpoint


async def call(bff: Bff, endpoint: w.Endpoint, headers: dict[str, str] | None = None) -> httpx.Response:
    url = endpoint.path + (f"?{endpoint.query}" if endpoint.query else "")
    return await bff.client.request(
        endpoint.method,
        url,
        headers={**ALL, **endpoint.headers, **(headers or {})},
        json=endpoint.body,
    )


def request(operation_id: str) -> w.Endpoint:
    return w.REQUESTS[operation_id]


# --- timeout por operacion y plazo -----------------------------------------------------------------------------------

TIMEOUT_CASES = [
    ("get_api_console_cases", "case", "GET", "/v1/cases", "case.list_cases"),
    ("get_api_console_cases_failures", "case", "GET", "/v1/cases/failures", "case.list_persistent_failures"),
    ("get_api_console_cases_id", "case", "GET", "/v1/cases/{id}", "case.get_case"),
    ("post_api_console_cases", "case", "POST", "/v1/cases", "case.create_manual_application"),
    (
        "post_api_console_cases_id_explanation-views",
        "case",
        "POST",
        "/v1/cases/{id}/explanation-views",
        "case.record_explanation_view",
    ),
    ("post_api_console_cases_id_decision", "case", "POST", "/v1/cases/{id}/decision", "case.record_decision"),
    ("post_api_console_cases_id_retry", "case", "POST", "/v1/cases/{id}/retry", "case.retry_case"),
    (
        "post_api_console_cases_id_applicant-summary",
        "explainability",
        "POST",
        "/v1/applicant-summaries",
        "explainability.applicant_summary",
    ),
    (
        "post_api_console_integrity-checks",
        "registry",
        "POST",
        "/v1/integrity-checks",
        "registry.run_integrity_check",
    ),
    (
        "get_api_console_integrity-checks_id",
        "registry",
        "GET",
        "/v1/integrity-checks/{id}",
        "registry.get_integrity_check",
    ),
    ("get_api_console_models", "governance", "GET", "/v1/models", "governance.read"),
    ("get_api_console_policies", "governance", "GET", "/v1/policies", "governance.read"),
    ("post_api_console_models", "governance", "POST", "/v1/models", "governance.transition"),
    (
        "post_api_console_models_id_approval",
        "governance",
        "POST",
        "/v1/models/{id}/approval",
        "governance.transition",
    ),
    ("get_api_console_freezes", "bias", "GET", "/v1/freezes", "bias.list_freezes"),
    ("get_api_console_freezes_id", "bias", "GET", "/v1/freezes/{id}", "bias.get_context_package"),
]


@pytest.mark.parametrize(("operation_id", "destination", "method", "template", "key"), TIMEOUT_CASES)
async def test_every_destination_call_carries_its_operation_timeout(
    bff: Bff, operation_id: str, destination: str, method: str, template: str, key: str
) -> None:
    """P-U10-04: el timeout efectivo que recibe el doble es el de `config` para esa operacion."""
    response = await call(bff, request(operation_id))
    assert response.status_code < 300, response.text
    double = getattr(bff.doubles, destination)
    matching = [c for c in double.calls if (c.method, c.template) == (method, template)]
    assert matching, (method, template, [(c.method, c.template) for c in double.calls])
    assert matching[-1].timeout == config.OPERATION_TIMEOUT_SECONDS[key]


async def test_dossier_calls_use_their_timeouts(bff: Bff) -> None:
    response = await call(bff, request("get_api_console_cases_id_dossier"))
    assert response.status_code == 200
    assert (
        bff.doubles.registry.calls[0].timeout
        == config.OPERATION_TIMEOUT_SECONDS["registry.get_case_dossier"]
        == 5.0
    )
    assert (
        bff.doubles.case.calls[0].timeout
        == config.OPERATION_TIMEOUT_SECONDS["case.get_case_identifiers"]
        == 1.5
    )


async def test_disparity_calls_use_their_timeouts(bff: Bff) -> None:
    response = await call(bff, request("get_api_console_disparity"))
    assert response.status_code == 200
    assert bff.doubles.governance.calls[0].timeout == config.OPERATION_TIMEOUT_SECONDS["governance.read"]
    assert bff.doubles.bias.calls[0].timeout == config.OPERATION_TIMEOUT_SECONDS["bias.get_dashboard"] == 5.0


async def test_a_destination_that_does_not_answer_is_cut_at_its_timeout_for_real(bff: Bff) -> None:
    """Un corte real: `list_cases` (1,5 s) contra un doble que no responde -> 503 `dependency_unavailable` (P-2 (a)), no 504."""
    bff.doubles.case.hang()
    started = time.monotonic()
    response = await call(bff, request("get_api_console_cases"))
    elapsed = time.monotonic() - started
    assert response.status_code == 503 and response.json()["code"] == "dependency_unavailable"
    assert 1.4 <= elapsed < 3.0, elapsed  # cortó en su timeout de 1,5 s, no esperó al del plazo de 9 s
    assert bff.doubles.case.count() == 1  # y no reintentó


async def test_the_deadline_header_reaches_the_double_as_entry_plus_nine_seconds(
    make_bff: Callable[..., Bff],
) -> None:
    fixed = datetime.now(UTC)
    bff = make_bff(clock=lambda: fixed)
    response = await call(bff, request("get_api_console_cases"))
    assert response.status_code == 200
    header = bff.doubles.case.calls[0].headers["x-vectra-deadline"]
    assert datetime.fromisoformat(header) == (
        fixed + timedelta(seconds=config.DEADLINE_BUDGET_SECONDS)
    ).replace(microsecond=(fixed + timedelta(seconds=9)).microsecond // 1000 * 1000)
    # el timeout efectivo es el menor entre el de la operacion y lo que queda del plazo
    assert bff.doubles.case.calls[0].timeout == 1.5


async def test_an_incoming_smaller_deadline_wins_and_cuts_the_call_short(
    make_bff: Callable[..., Bff],
) -> None:
    """NFR-U0-23 (b): si la solicitud ya trae un plazo menor, rige el menor; el timeout efectivo se recorta a lo que queda."""
    fixed = datetime.now(UTC)
    bff = make_bff(clock=lambda: fixed)
    incoming = fixed + timedelta(seconds=1)
    response = await call(
        bff,
        request("get_api_console_cases"),
        {"x-vectra-deadline": incoming.isoformat().replace("+00:00", "Z")},
    )
    assert response.status_code == 200
    seen = bff.doubles.case.calls[0]
    assert datetime.fromisoformat(seen.headers["x-vectra-deadline"]) == incoming.replace(
        microsecond=incoming.microsecond // 1000 * 1000
    )
    assert seen.timeout == pytest.approx(1.0, abs=0.01)


async def test_the_user_token_correlation_and_idempotency_key_are_forwarded_untouched(bff: Bff) -> None:
    endpoint = request("post_api_console_cases")
    response = await call(bff, endpoint, {"traceparent": "00-" + "a" * 32 + "-" + "b" * 16 + "-01"})
    assert response.status_code == 200
    seen = bff.doubles.case.calls[0]
    assert seen.headers["authorization"] == ALL["authorization"]
    assert seen.headers["idempotency-key"] == endpoint.headers["idempotency-key"]
    assert seen.headers["traceparent"].split("-")[1] == "a" * 32  # el correlation_id viaja
    assert seen.headers["content-type"] == "application/json"


async def test_the_query_is_forwarded_from_the_validated_model(bff: Bff) -> None:
    response = await bff.client.get(
        "/api/console/cases?state=listo,decidido&model_frozen_after_recommendation=true&page_size=5",
        headers=ALL,
    )
    assert response.status_code == 200
    query = bff.doubles.case.calls[0].query
    assert sorted(query["state"]) == ["decidido", "listo"] and query["model_frozen_after_recommendation"] == [
        "true"
    ]
    assert query["page_size"] == ["5"] and query["page"] == [
        "1"
    ]  # el valor por omision del modelo, no los bytes de entrada


@pytest.mark.parametrize(
    "path",
    [
        "/cases/%2e%2e",
        "/cases/%2e",
        "/models/%2e%2e",
        "/policies/%2e%2e/approval",
        "/integrity-checks/%2e%2e",
        "/freezes/%2e%2e",
    ],
)
async def test_an_id_that_climbs_the_path_never_reaches_the_destination(bff: Bff, path: str) -> None:
    """`..` como `{id}` (codificado, para que el cliente no lo normalice) no sube de nivel en el destino: 404 y 0 llamadas."""
    method = "POST" if path.endswith("approval") else "GET"
    body = {"decision": "aprobada"} if method == "POST" else None
    response = await bff.client.request(method, "/api/console" + path, headers=ALL, json=body)
    assert response.status_code == 404 and response.json()["code"] == "not_found", response.text
    calls = [c for d in bff.doubles.transports().values() for c in d.calls]
    assert all(".." not in c.path for c in calls)
    # las politicas no se leen por id: la regla lee la lista, que no lleva el `{id}`; el resto no llama a nadie
    assert len(calls) == (1 if "policies" in path else 0)


# --- circuit breaker, sin reintentos ---------------------------------------------------------------------------------


async def test_an_open_circuit_answers_503_at_once_with_zero_calls(bff: Bff) -> None:
    """Tras 20 llamadas fallidas el circuito del destino se abre; la siguiente no llega al doble (P-U10-03)."""
    case = bff.doubles.case
    case.down()
    breaker = bff.app.state.upstreams.clients["case"].breaker
    for n in range(19):
        assert (await call(bff, request("get_api_console_cases"))).status_code == 503
        assert breaker.state.name == "CLOSED", n
    assert (await call(bff, request("get_api_console_cases"))).status_code == 503  # la 20.a abre
    assert breaker.state.name == "OPEN"
    assert case.count() == 20
    started = time.monotonic()
    response = await call(bff, request("get_api_console_cases"))
    assert response.status_code == 503 and response.json()["code"] == "dependency_unavailable"
    assert time.monotonic() - started < 0.5
    assert case.count() == 20  # 0 llamadas con el circuito abierto
    # y el circuito de case no tumba a los otros cuatro
    others = [name for name in DESTINATIONS if name != "case"]
    assert all(bff.app.state.upstreams.clients[name].breaker.state.name == "CLOSED" for name in others)
    assert (await call(bff, request("get_api_console_models"))).status_code == 200
    assert (await call(bff, request("get_api_console_freezes"))).status_code == 200


async def test_a_4xx_of_the_destination_does_not_count_for_the_breaker(bff: Bff) -> None:
    bff.doubles.case.reply(
        "GET",
        "/v1/cases",
        403,
        {
            "type": "urn:vectra:problem:forbidden",
            "title": "x",
            "status": 403,
            "code": "forbidden",
            "correlation_id": "0" * 32,
        },
    )
    for _ in range(25):
        assert (await call(bff, request("get_api_console_cases"))).status_code == 403
    assert bff.app.state.upstreams.clients["case"].breaker.state.name == "CLOSED"
    assert bff.doubles.case.count() == 25


@pytest.mark.parametrize(
    ("operation_id", "destination"),
    [
        ("post_api_console_models", "governance"),  # una transicion de U4
        ("post_api_console_cases", "case"),  # un alta
        ("post_api_console_integrity-checks", "registry"),
        ("get_api_console_cases", "case"),  # ni los GET se reintentan (NFR-U10-33)
    ],
)
async def test_a_503_of_the_destination_is_one_call_and_never_a_retry(
    bff: Bff, operation_id: str, destination: str
) -> None:
    double = getattr(bff.doubles, destination)
    double.fail(503)
    response = await call(bff, request(operation_id))
    assert response.status_code == 503 and response.json()["code"] == "dependency_unavailable"
    assert double.count() == 1


async def test_a_401_of_the_destination_is_not_retried(bff: Bff) -> None:
    """Sin `token_source`, `deps.call` no reintenta ante un 401: el BFF no reintenta (NFR-U10-33)."""
    bff.doubles.case.reply(
        "GET",
        "/v1/cases",
        401,
        {
            "type": "urn:vectra:problem:unauthenticated",
            "title": "x",
            "status": 401,
            "code": "unauthenticated",
            "correlation_id": "0" * 32,
        },
    )
    response = await call(bff, request("get_api_console_cases"))
    assert response.status_code == 401 and response.json()["code"] == "unauthenticated"
    assert bff.doubles.case.count() == 1


async def test_a_timeout_on_a_post_is_503_dependency_unavailable_with_one_call(bff: Bff) -> None:
    """P-U10-03: «Timeout de un POST: 503»; el doble recibe un solo intento (el usuario recarga el caso)."""
    bff.doubles.governance.hang()
    started = time.monotonic()
    response = await call(bff, request("post_api_console_models"))
    assert response.status_code == 503 and response.json()["code"] == "dependency_unavailable"
    assert bff.doubles.governance.count("POST") == 1
    assert time.monotonic() - started < 6.0  # el timeout de una transicion es de 4 s


# --- aislamiento por vista (NFR-U10-32): E1, E2 y E3 de P-U10-05 §5 ----------------------------------------------------------------

# Destinos que usa cada endpoint (tabla «Endpoints de paso» de la tarea). El expediente solo **necesita** al registro.
NEEDS: dict[str, set[str]] = {
    "get_api_console_me": set(),
    "post_api_console_client-errors": set(),
    "post_api_console_cases_id_applicant-summary": {"case", "explainability"},
    "get_api_console_cases_id_dossier": {"registry"},
    "post_api_console_integrity-checks": {"registry"},
    "get_api_console_integrity-checks_id": {"registry"},
    "get_api_console_disparity": {"governance", "bias"},
    "get_api_console_freezes": {"bias"},
    "get_api_console_freezes_id": {"bias"},
}
CASE_OPS = {op for op in w.REQUESTS if "_cases" in op and op not in NEEDS}
GOVERNANCE_OPS = {
    op
    for op in w.REQUESTS
    if any(k in op for k in ("models", "policies", "data-sources")) and op not in NEEDS
}
for _op in CASE_OPS:
    NEEDS[_op] = {"case"}
for _op in GOVERNANCE_OPS:
    NEEDS[_op] = {"governance"}


def test_the_dependency_table_covers_the_30_endpoints() -> None:
    assert set(NEEDS) == {r.operation_id for r in REGISTRY["console-bff"]}


@pytest.mark.parametrize("down", DESTINATIONS)
async def test_with_one_destination_down_only_its_endpoints_fail(bff: Bff, down: str) -> None:
    """E1 (case), E2 (registro) y E3 (bias) y, ademas, governance y explainability, cada uno caido por turno."""
    getattr(bff.doubles, down).down()
    failed, served = [], []
    for operation_id, endpoint in w.REQUESTS.items():
        response = await call(bff, endpoint)
        (failed if response.status_code == 503 else served).append((operation_id, response.status_code))
        if down in NEEDS[operation_id]:
            assert response.status_code == 503, (operation_id, response.status_code, response.text)
            assert response.json()["code"] == "dependency_unavailable"
        else:
            assert response.status_code < 300, (operation_id, response.status_code, response.text)
    assert failed and served


async def test_e1_with_case_down_the_dossier_comes_back_without_identifiers(bff: Bff) -> None:
    bff.doubles.case.down()
    response = await call(bff, request("get_api_console_cases_id_dossier"))
    assert response.status_code == 200
    body = response.json()
    assert (
        body["identifiers_unavailable"] is True and "identifiers" not in body and body["anonymized"] is False
    )


async def test_e3_with_bias_down_the_inbox_and_the_decision_still_answer_2xx(bff: Bff) -> None:
    bff.doubles.bias.down()
    assert (await call(bff, request("get_api_console_cases"))).status_code == 200
    assert (await call(bff, request("post_api_console_cases_id_decision"))).status_code == 200
    assert (await call(bff, request("get_api_console_disparity"))).status_code == 503
    assert (await call(bff, request("get_api_console_freezes"))).status_code == 503


# --- pool agotado, con sockets reales --------------------------------------------------------------------------------


class _Slow(BaseHTTPRequestHandler):
    hold = 3.0

    def do_GET(self) -> None:  # noqa: N802
        time.sleep(self.hold)
        body = json.dumps({"items": []}).encode()
        try:
            self.send_response(200)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except OSError:  # el cliente ya corto
            pass

    def log_message(self, *_: Any) -> None:
        return


async def test_an_exhausted_pool_ends_in_a_timeout_within_the_deadline() -> None:
    """P-U10-04: con las 20 conexiones de case ocupadas, la llamada 21 espera el pool y termina en su timeout (1,5 s)."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Slow)
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{server.server_address[1]}"
    doubles = Doubles()
    urls = {**doubles.urls(), "case": url}
    upstreams = Upstreams(
        urls
    )  # sin transporte propio: el cliente real de `httpx` con su limite de conexiones
    client = upstreams.clients["case"]
    try:
        holders = [
            asyncio.create_task(
                deps.call(client, "GET", "/v1/cases", timeout=config.CASE_WRITE_TIMEOUT_SECONDS)
            )
            for _ in range(config.CONNECTIONS_PER_REPLICA["case"])
        ]
        await asyncio.sleep(0.5)  # las 20 ya tienen su conexion
        started = time.monotonic()
        with pytest.raises(Exception) as error:  # noqa: PT011 - `DependencyTimeout` de U0: el BFF lo vuelve 503
            await deps.call(client, "GET", "/v1/cases", timeout=config.CASE_READ_TIMEOUT_SECONDS)
        elapsed = time.monotonic() - started
        assert type(error.value).__name__ == "DependencyTimeout"
        assert 1.3 <= elapsed < 2.5, elapsed  # termina en su timeout, mucho antes del plazo de 9 s
        await asyncio.gather(*holders, return_exceptions=True)
    finally:
        await upstreams.aclose()
        server.shutdown()
        server.server_close()
