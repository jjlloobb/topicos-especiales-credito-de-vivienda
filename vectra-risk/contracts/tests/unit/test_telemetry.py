"""BR-U0-62, P-U0-11, NFR-U0-16."""

from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from vectra_common import telemetry


def test_br_u0_62_traceparent_parsing():
    trace, span = "a" * 32, "b" * 16
    assert telemetry.parse_traceparent(f"00-{trace}-{span}-01") == (trace, span)
    assert telemetry.parse_traceparent(None) is None
    assert telemetry.parse_traceparent("basura") is None
    assert telemetry.parse_traceparent(f"00-{'0' * 32}-{span}-01") is None
    assert telemetry.parse_traceparent(f"00-{trace}-{'0' * 16}-01") is None


def test_nfr_u0_16_no_export_without_destination(monkeypatch):
    monkeypatch.delenv("VECTRA_OTLP_ENDPOINT", raising=False)
    assert telemetry.configure("svc") is False
    assert telemetry.start_span("x", "a" * 32, "b" * 16) is None


def test_p_u0_11_span_attributes_allowlisted():
    exporter = InMemorySpanExporter()
    assert telemetry.configure("svc", SimpleSpanProcessor(exporter)) is True
    span = telemetry.start_span("POST", "a" * 32, "b" * 16)
    span.set_attribute("route_template", "/v1/x")
    span.set_attribute("email", "ana@example.com")
    span.add_event("con pii", {"doc": "1020304050"})
    span.end()
    exported = exporter.get_finished_spans()[0]
    assert dict(exported.attributes) == {"route_template": "/v1/x"}
    assert not exported.events
    assert format(exported.context.trace_id, "032x") == "a" * 32
    processor = telemetry._tracer_holder["tracer"]
    assert processor is not None
    telemetry._tracer_holder["tracer"] = None


def test_format_traceparent():
    assert telemetry.format_traceparent("a" * 32, "b" * 16) == f"00-{'a' * 32}-{'b' * 16}-01"
    assert len(telemetry.new_trace_id()) == 32 and len(telemetry.new_span_id()) == 16
