"""BR-U0-50..53, P-U0-04, NFR-U0-13."""

import io
import json
import logging as std

import pytest

from vectra_common import logging as vlog
from vectra_common.metrics import LOG_FIELDS_DROPPED
from vectra_contracts.catalog import LOG_RECORD_FIELDS, LogEvent
from vectra_contracts.errors import ContractViolation


@pytest.fixture
def stream():
    out = io.StringIO()
    vlog.configure("svc-log", out)
    yield out
    vlog.configure("svc-log")


def records(out):
    return [json.loads(line) for line in out.getvalue().splitlines()]


def test_br_u0_50_extra_fields_dropped(stream):
    vlog.log_event(LogEvent.CASE_VIEWED, case_id="c", full_name="Ana Gómez", email="ana@example.com")
    record = records(stream)[0]
    assert set(record) <= LOG_RECORD_FIELDS
    assert record["event"] == "case.viewed" and "Ana" not in stream.getvalue()


def test_p_u0_04_dropped_counter(stream):
    metric = LOG_FIELDS_DROPPED.labels(service="svc-log", event="case.viewed")
    before = metric._value.get()
    vlog.log_event(LogEvent.CASE_VIEWED, secreto="x")
    assert metric._value.get() == before + 1


def test_p_u0_04_strict_mode_raises(stream, monkeypatch):
    monkeypatch.setenv("VECTRA_LOG_STRICT", "1")
    with pytest.raises(vlog.LogContractViolation):
        vlog.log_event(LogEvent.CASE_VIEWED, secreto="x")
    with pytest.raises(vlog.LogContractViolation):
        vlog.log_access(secreto="x")


def test_br_u0_51_event_outside_catalog(stream):
    with pytest.raises(ContractViolation):
        vlog.log_event("evento.inventado")  # type: ignore[arg-type]


def test_catalog_contains_u9_events():
    assert {"disparity.viewed", "freeze_context.viewed"} <= {e.value for e in LogEvent}


def test_br_u0_52_exception_only_type_and_code(stream):
    vlog.log_exception(ValueError("cédula 1020304050"), "internal_error")
    assert "1020304050" not in stream.getvalue()
    record = records(stream)[0]
    assert record["exception_type"] == "ValueError" and record["error_code"] == "internal_error"


def test_br_u0_53_labels_never_logged(stream):
    vlog.log_access(sexo="F", banda_capacidad_pago="lt_20", estrato="3", region="caribe", rango_edad="26-35")
    assert not {"sexo", "banda_capacidad_pago", "estrato", "region", "rango_edad"} & set(records(stream)[0])


def test_nfr_u0_13_third_party_log_with_pii(stream, monkeypatch):
    monkeypatch.setenv("VECTRA_LOG_STRICT", "1")
    std.getLogger("httpx").info("GET /v1/cases?nombre=Ana+Gomez&doc=1020304050", extra={"email": "ana@example.com"})
    output = stream.getvalue()
    assert "Ana" not in output and "1020304050" not in output and "ana@example.com" not in output
    assert set(records(stream)[0]) <= LOG_RECORD_FIELDS


def test_third_party_exception_text_absent(stream):
    try:
        raise RuntimeError("doc 1020304050")
    except RuntimeError:
        std.getLogger("uvicorn").exception("fallo con doc 1020304050")
    assert "1020304050" not in stream.getvalue()


def test_context_fields(stream):
    token = vlog.correlation_id_var.set("c" * 32)
    span = vlog.span_id_var.set("d" * 16)
    try:
        vlog.log_access(status=200)
    finally:
        vlog.correlation_id_var.reset(token)
        vlog.span_id_var.reset(span)
    record = records(stream)[0]
    assert record["correlation_id"] == "c" * 32 and record["span_id"] == "d" * 16 and record["service"] == "svc-log" and record["level"] == "info"
    assert "timestamp" in record and "event" not in record


def test_strict_mode_accepts_allowed_fields(stream, monkeypatch):
    monkeypatch.setenv("VECTRA_LOG_STRICT", "1")
    vlog.log_access(status=200, route_template="/v1/x")
    assert records(stream)[0]["status"] == 200
