"""Lo que U2 a U12 esperan de U0: revision de consistencia entre unidades (2026-11-01)."""

import asyncio
import json
import socket
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from pydantic import ValidationError
from starlette.requests import Request
from strategies import auth as a

from tools.codegen import spec_for, ts_enums
from vectra_common import ops_server, process, telemetry
from vectra_common.app_factory import create_app, parse_query, respond
from vectra_common.authn import principal_from_claims
from vectra_common.errors import DependencyTimeout, DependencyUnavailable, ValidationFailed, to_problem
from vectra_common.metrics import REGISTRY as METRICS
from vectra_contracts import catalog
from vectra_contracts.catalog import SCOPE_HOLDERS, LogEvent, Role, Scope
from vectra_contracts.errors import ContractViolation
from vectra_contracts.models import explanation as e
from vectra_contracts.models.api import CaseDetail
from vectra_contracts.models.application import CaseFilter
from vectra_contracts.models.governance import ModelFilter, PolicyDecisionIn
from vectra_contracts.models.monitoring import AffectedVolume, DisparityFilter, PrePostDelta
from vectra_contracts.models.registry import EntryFilter, ExplanationProjection, MetricsProjection
from vectra_contracts.routes import REGISTRY, RouteContract


def route(service: str, method: str, path: str) -> RouteContract:
    return next(r for r in REGISTRY[service] if (r.method, r.path) == (method, path))


def request_with(query: str) -> Request:
    return Request({"type": "http", "method": "GET", "path": "/", "headers": [], "query_string": query.encode()})


@pytest.fixture(autouse=True)
def reset():
    process.reset_for_tests()
    yield
    process.reset_for_tests()


# --- Respuestas que los consumidores leen


def test_scope_and_role_together_would_lock_out_users():
    """`authorize` exige los dos si se declaran: la lista de modelos es solo por rol (F11 y F08)."""
    listing = route("governance-service", "GET", "/v1/models")
    assert listing.roles and not listing.scopes and not listing.any_scopes
    entries = route("decision-registry-service", "GET", "/v1/entries")
    assert entries.any_scopes and not entries.roles


def test_explanation_and_registry_ack_are_published():
    assert route("explainability-service", "POST", "/v1/explanations").response_model is e.Explanation
    assert route("decision-registry-service", "POST", "/v1/entries").response_model is e.RegistryAck
    spec = spec_for("decision-registry-service", REGISTRY["decision-registry-service"])
    assert "200" in spec["paths"]["/v1/entries"]["post"]["responses"]


def test_integrity_check_declares_202_with_body():
    for service, path in (
        ("decision-registry-service", "/v1/integrity-checks"),
        ("console-bff", "/api/console/integrity-checks"),
    ):
        responses = spec_for(service, REGISTRY[service])["paths"][path]["post"]["responses"]
        assert responses["202"]["content"] == responses["200"]["content"]


def test_serving_config_declares_if_none_match_and_304():
    spec = spec_for("governance-service", REGISTRY["governance-service"])
    operation = spec["paths"]["/v1/serving-config"]["get"]
    assert {"name": "If-None-Match", "in": "header", "required": False, "schema": {"type": "string"}} in operation[
        "parameters"
    ]
    assert "content" not in operation["responses"]["304"]


@pytest.mark.parametrize(
    ("service", "path"),
    [
        ("case-service", "/v1/intake/applications"),
        ("case-service", "/v1/cases"),
        ("console-bff", "/api/console/cases"),
    ],
)
def test_idempotency_key_is_required_where_u8_demands_it(service, path):
    operation = spec_for(service, REGISTRY[service])["paths"][path]["post"]
    assert [p["required"] for p in operation["parameters"] if p["name"] == "Idempotency-Key"] == [True]


# --- Parametros de consulta


@pytest.mark.parametrize(
    ("service", "path", "names"),
    [
        ("case-service", "/v1/cases", {"state", "channel", "page", "page_size"}),
        ("console-bff", "/api/console/cases", {"state", "model_frozen_after_recommendation"}),
        ("governance-service", "/v1/models", {"state"}),
        ("console-bff", "/api/console/models", {"state"}),
        ("bias-monitoring-service", "/v1/disparity", {"version", "attribute", "window"}),
        ("console-bff", "/api/console/disparity", {"attribute", "window"}),
        ("decision-registry-service", "/v1/entries", {"projection", "entry_type", "seq_after", "limit"}),
    ],
)
def test_filters_are_in_the_spec(service, path, names):
    parameters = spec_for(service, REGISTRY[service])["paths"][path]["get"]["parameters"]
    assert names <= {p["name"] for p in parameters if p["in"] == "query"}


def test_query_values_are_converted_and_lists_accept_commas():
    parsed = parse_query(request_with("state=activo,congelado&page=2"), ModelFilter)
    assert parsed == ModelFilter(state=["activo", "congelado"], page=2)
    parsed = parse_query(request_with("state=listo&state=decidido"), CaseFilter)
    assert [s.value for s in parsed.state] == ["listo", "decidido"]
    assert parse_query(request_with("window=30"), DisparityFilter).window == 30


@pytest.mark.parametrize(
    ("model", "query"),
    [
        (EntryFilter, "limit=1001"),
        (EntryFilter, "projection=monitoring"),
        (CaseFilter, "desconocido=1"),
        (CaseFilter, "page=dos"),
        (CaseFilter, "channel=a&channel=b"),
        (DisparityFilter, "window=31"),
    ],
)
def test_bad_query_is_validation_error(model, query):
    with pytest.raises(ValidationFailed):
        parse_query(request_with(query), model)


async def test_query_reaches_the_handler_and_bad_query_is_422():
    seen: dict[str, Any] = {}

    async def handler(context):
        seen["query"] = context.query
        return None

    contract = RouteContract(
        "svc", "GET", "/v1/items", roles=frozenset({Role.ANALISTA}), query_model=EntryFilter
    )
    async with a.client_for([contract], handler=handler) as client:
        ok = await client.get("/v1/items?limit=5", headers=a.bearer())
        bad = await client.get("/v1/items?limit=5000", headers=a.bearer())
    assert ok.status_code == 204 and seen["query"].limit == 5
    assert bad.status_code == 422


def test_respond_supports_alternate_statuses():
    body = e.RegistryAck(registry_entry_id="x", seq=1, recorded_at=datetime(2026, 1, 1, tzinfo=UTC))
    assert respond(body, 202).status_code == 202
    not_modified = respond(None, 304)
    assert not_modified.status_code == 304 and not_modified.body == b""


# --- Proyecciones de `GET /v1/entries`


def test_projections_validate_what_u3_serves():
    explanation = ExplanationProjection.model_json_schema()
    assert set(explanation["required"]) == {"seq", "case_id", "model_version_id", "payload"}
    decision = MetricsProjection.model_validate_json(
        json.dumps(
            {
                "entry_type": "human_decision",
                "seq": 7,
                "recorded_at": "2026-01-01T00:00:00Z",
                "case_id": "00000000-0000-4000-8000-000000000001",
                "actor_role": "analista",
                "recommendation": None,
                "delivery_status": "entregada",
            }
        )
    )
    assert decision.seq == 7
    with pytest.raises(ValidationError):
        MetricsProjection.model_validate_json('{"entry_type":"genesis","seq":1}')


def test_entries_page_publishes_every_projection():
    schemas = spec_for("decision-registry-service", REGISTRY["decision-registry-service"])["components"]["schemas"]
    assert {"RegistryEntry", "ExplanationProjection", "MetricsProjection", "FreezeProjection"} <= set(schemas)


# --- Tipos que U9 y U4 necesitan


def test_affected_volume_has_total_and_favorable():
    assert AffectedVolume(total=10, favorable=3).favorable == 3
    with pytest.raises(ValidationError):
        AffectedVolume(total=1, favorable=2)


def test_pre_post_delta_has_one_per_aggregate():
    delta = PrePostDelta(attributes=[{"attribute": "sexo", "delta": "0.0100"}], model_aggregate="0.0200")
    assert delta.attributes[0].attribute == "sexo"


def test_policy_rejection_needs_justification():
    assert PolicyDecisionIn(decision="aprobada").justification is None
    with pytest.raises(ValidationError):
        PolicyDecisionIn(decision="rechazada", justification=" ")


def test_case_detail_recommendation_is_typed():
    field = CaseDetail.model_fields["recommendation"]
    assert "Recommendation" in str(field.annotation)


# --- Identidad, eventos y enumerados


def test_azp_reaches_principal():
    principal = principal_from_claims(
        {"sub": "s", "exp": 1_900_000_000, "azp": "channel-simulator", "scope": "intake:submit"}
    )
    assert principal.client_id == "channel-simulator"


def test_verification_reader_is_a_holder():
    assert "verification-reader" in SCOPE_HOLDERS[Scope.REGISTRY_READ_METRICS]
    assert "verification-reader" in SCOPE_HOLDERS[Scope.REGISTRY_READ_MONITORING]


def test_idempotency_conflict_event_exists():
    assert LogEvent("registry.idempotency_conflict") is LogEvent.REGISTRY_IDEMPOTENCY_CONFLICT


def test_every_catalog_enum_reaches_typescript():
    text = ts_enums()
    for name in ("CASE_STATES", "OUTCOMES", "FINAL_OUTCOMES", "DECISIONS", "ENTRY_TYPES", "LOCAL_CAUSES"):
        assert f"export const {name} = [" in text
    for member in catalog.ExplainerError:
        assert json.dumps(member.value) in text


# --- Puerto 8081


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def test_shutdown_wait_is_bounded():
    assert ops_server.GRACEFUL_SHUTDOWN == 10


async def test_ops_port_is_8081():
    assert ops_server.OPS_PORT == 8081 and ops_server.APP_PORT == 8080


async def test_serve_exposes_both_ports():
    contract = RouteContract("svc", "GET", "/v1/ping", roles=frozenset({Role.ANALISTA}))

    async def handler(_):
        return None

    app = create_app(
        "svc",
        [contract],
        {("GET", "/v1/ping"): handler},
        authenticator=a.authenticator() if hasattr(a, "authenticator") else None,
    )
    app_port, ops_port = free_port(), free_port()
    task = asyncio.create_task(ops_server.serve(app, host="127.0.0.1", port=app_port, ops_port=ops_port))
    try:
        async with httpx.AsyncClient() as client:
            for _ in range(100):
                try:
                    health = await client.get(f"http://127.0.0.1:{ops_port}/healthz")
                    business = await client.get(f"http://127.0.0.1:{app_port}/v1/ping")
                    break
                except httpx.TransportError:
                    await asyncio.sleep(0.05)
        assert health.status_code == 200
        assert business.status_code == 401  # 8080 autentica; las sondas van por 8081
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


# --- Metricas de proceso


def test_process_metrics_are_published():
    names = {metric.name for metric in METRICS.collect()}
    assert {"python_gc_objects_collected", "python_info"} <= names


# --- Timeouts


def test_dependency_timeout_is_504_and_unavailable_is_503():
    assert to_problem(DependencyTimeout(), "c" * 32).status == 504
    assert to_problem(DependencyUnavailable(), "c" * 32).status == 503
    assert issubclass(DependencyTimeout, DependencyUnavailable)


# --- Trazas


@pytest.fixture
def exporter(monkeypatch):
    monkeypatch.setenv(telemetry.RATIO_ENV, "1.0")
    memory = InMemorySpanExporter()
    telemetry.configure("svc", SimpleSpanProcessor(memory))
    yield memory
    telemetry._tracer_holder["tracer"] = None  # noqa: SLF001


def test_ratio_zero_samples_nothing_at_the_root(monkeypatch):
    monkeypatch.setenv(telemetry.RATIO_ENV, "0")
    memory = InMemorySpanExporter()
    telemetry.configure("svc", SimpleSpanProcessor(memory))
    span = telemetry.start_span("GET", "a" * 32, None, "b" * 16)
    span.end()
    telemetry._tracer_holder["tracer"] = None  # noqa: SLF001
    assert memory.get_finished_spans() == ()
    assert not span.get_span_context().trace_flags.sampled


def test_incoming_unsampled_flag_is_respected(exporter):
    telemetry.start_span("GET", "a" * 32, "c" * 16, "b" * 16, parent_sampled=False).end()
    assert exporter.get_finished_spans() == ()


def test_exported_span_has_the_log_ids(exporter):
    telemetry.start_span("GET", "a" * 32, "c" * 16, "b" * 16).end()
    span = exporter.get_finished_spans()[0]
    assert format(span.context.trace_id, "032x") == "a" * 32
    assert format(span.context.span_id, "016x") == "b" * 16
    assert format(span.parent.span_id, "016x") == "c" * 16


def test_root_span_has_no_invented_parent(exporter):
    telemetry.start_span("GET", "a" * 32, None, "b" * 16).end()
    span = exporter.get_finished_spans()[0]
    assert span.parent is None and format(span.context.trace_id, "032x") == "a" * 32


def test_traceparent_sampled_flag():
    trace, parent = "a" * 32, "b" * 16
    assert telemetry.traceparent_sampled(f"00-{trace}-{parent}-01") is True
    assert telemetry.traceparent_sampled(f"00-{trace}-{parent}-00") is False
    assert telemetry.traceparent_sampled(None) is True
    assert telemetry.format_traceparent(trace, parent, False).endswith("-00")


def test_otlp_endpoint_without_scheme_is_rejected(monkeypatch):
    monkeypatch.setenv(telemetry.ENDPOINT_ENV, "otel-collector:4317")
    with pytest.raises(ContractViolation):
        telemetry.configure("svc")
