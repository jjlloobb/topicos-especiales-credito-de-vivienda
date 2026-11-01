"""Trazas con allowlist y `traceparent` (P-U0-11, BR-U0-62, NFR-U0-16)."""

import os
import re
import secrets
from contextvars import ContextVar
from typing import Any, Final

from opentelemetry import trace
from opentelemetry.context import Context
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import ReadableSpan, Span, SpanProcessor, TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.id_generator import IdGenerator, RandomIdGenerator
from opentelemetry.sdk.trace.sampling import ParentBased, TraceIdRatioBased
from opentelemetry.trace import NonRecordingSpan, SpanContext, TraceFlags
from vectra_contracts.catalog import LOG_RECORD_FIELDS
from vectra_contracts.errors import ContractViolation

TRACEPARENT: Final = re.compile(r"^00-([0-9a-f]{32})-([0-9a-f]{16})-([0-9a-f]{2})$")
ENDPOINT_ENV: Final = "VECTRA_OTLP_ENDPOINT"
RATIO_ENV: Final = "VECTRA_TRACE_RATIO"
_tracer_holder: dict[str, Any] = {"tracer": None}
_request_ids: ContextVar[tuple[str, str] | None] = ContextVar("vectra_request_ids", default=None)


class _RequestIds(IdGenerator):
    """El span exportado lleva los ids de los logs y del `traceparent` de la respuesta."""

    def __init__(self) -> None:
        self._random = RandomIdGenerator()

    def generate_span_id(self) -> int:
        ids = _request_ids.get()
        return int(ids[1], 16) if ids else self._random.generate_span_id()

    def generate_trace_id(self) -> int:
        ids = _request_ids.get()
        return int(ids[0], 16) if ids else self._random.generate_trace_id()


def parse_traceparent(value: str | None) -> tuple[str, str] | None:
    """Devuelve `(trace_id, parent_span_id)`; invalido o todo en ceros → `None`."""
    if not value:
        return None
    match = TRACEPARENT.fullmatch(value)
    if match is None or set(match.group(1)) == {"0"} or set(match.group(2)) == {"0"}:
        return None
    return match.group(1), match.group(2)


def traceparent_sampled(value: str | None) -> bool:
    """La marca `sampled` de un `traceparent` valido; sin el, decide el muestreo de la raiz."""
    match = TRACEPARENT.fullmatch(value) if value else None
    return bool(int(match.group(3), 16) & 1) if match else True


def new_trace_id() -> str:
    return secrets.token_hex(16)


def new_span_id() -> str:
    return secrets.token_hex(8)


def format_traceparent(trace_id: str, span_id: str, sampled: bool = True) -> str:
    return f"00-{trace_id}-{span_id}-{'01' if sampled else '00'}"


class SpanAllowlist(SpanProcessor):
    """Aplica a los atributos de span la misma allowlist que a los logs."""

    def __init__(self, next_processor: SpanProcessor) -> None:
        self._next = next_processor

    def on_start(self, span: Span, parent_context: Any = None) -> None:
        self._next.on_start(span, parent_context)

    def on_end(self, span: ReadableSpan) -> None:
        attributes = {k: v for k, v in (span.attributes or {}).items() if k in LOG_RECORD_FIELDS}
        filtered = ReadableSpan(
            name=span.name,
            context=span.context,
            parent=span.parent,
            resource=span.resource,
            attributes=attributes,
            events=(),
            links=(),
            kind=span.kind,
            instrumentation_scope=span.instrumentation_scope,
            status=span.status,
            start_time=span.start_time,
            end_time=span.end_time,
        )
        self._next.on_end(filtered)

    def shutdown(self) -> None:
        self._next.shutdown()

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        return bool(self._next.force_flush(timeout_millis))


def configure(service: str, processor: SpanProcessor | None = None) -> bool:
    """Sin destino configurado no exporta: no hay valores por defecto externos (NFR-U0-16)."""
    endpoint = os.environ.get(ENDPOINT_ENV)
    if processor is None and not endpoint:
        _tracer_holder["tracer"] = None
        return False
    if endpoint and not endpoint.startswith(("http://", "https://")):
        # Sin esquema, el exportador usa TLS en silencio y el Collector escucha en claro.
        raise ContractViolation(f"{ENDPOINT_ENV} debe empezar por http:// o https://")
    ratio = float(os.environ.get(RATIO_ENV, "1.0"))
    provider = TracerProvider(sampler=ParentBased(TraceIdRatioBased(ratio)), id_generator=_RequestIds())
    inner = processor or BatchSpanProcessor(
        OTLPSpanExporter(endpoint=endpoint, insecure=bool(endpoint and endpoint.startswith("http://")))
    )
    provider.add_span_processor(SpanAllowlist(inner))
    _tracer_holder["tracer"] = provider.get_tracer(service)
    return True


def start_span(
    name: str,
    trace_id: str,
    parent_span_id: str | None,
    span_id: str | None = None,
    parent_sampled: bool = True,
) -> Any:
    """Abre el span de la solicitud; `None` si no hay exportador. Sin padre, es la raiz y la muestrea el ratio."""
    tracer = _tracer_holder["tracer"]
    if tracer is None:
        return None
    context = None
    if parent_span_id is not None:
        flags = TraceFlags(TraceFlags.SAMPLED if parent_sampled else TraceFlags.DEFAULT)
        parent = SpanContext(int(trace_id, 16), int(parent_span_id, 16), is_remote=True, trace_flags=flags)
        context = trace.set_span_in_context(NonRecordingSpan(parent))
    token = _request_ids.set((trace_id, span_id or new_span_id()))
    try:
        return tracer.start_span(name, context=context or Context())
    finally:
        _request_ids.reset(token)
