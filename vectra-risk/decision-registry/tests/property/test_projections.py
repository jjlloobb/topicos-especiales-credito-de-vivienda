"""PBT-U3-06 sobre `projections` (Paso 5 del plan de U3; BR-U3-15; domain-entities §3; US-403).

`HYPOTHESIS_PROFILE=ci uv run pytest decision-registry/tests/property/test_projections.py` (500 ejemplos, semilla impresa).

La lista de campos permitidos de este archivo se transcribe de domain-entities §3 y es independiente del codigo: la prueba
falla si el codigo permite un campo de mas o de menos.
"""

import json
import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest
from chain_builder import entry_fields, row_of
from hypothesis import given
from hypothesis import strategies as st
from vectra_contracts.models.monitoring import MonitoringQuery, MonitoringWindow
from vectra_contracts.models.registry import FrozenResolutionProjection, MetricsProjection

from vectra_registry.chain import GENESIS_PREV_HASH, Row
from vectra_registry.projections import (
    Consumer,
    DailyCount,
    EntryTotals,
    Forbidden,
    InvalidEntry,
    project,
    project_all,
    project_monitoring_daily,
)

CONSUMERS = list(Consumer)
PROJECTIONS = ["full", "explanation", "metrics", "monitoring_daily", "monitoring_freezes"]
PERMITTED = {
    Consumer.FULL: {"full"},
    Consumer.EXPLANATION: {"explanation"},
    Consumer.METRICS: {"metrics"},
    Consumer.MONITORING: {"monitoring_daily", "monitoring_freezes"},
}
FULL_FIELDS = {
    "seq", "idempotency_key", "entry_type", "case_id", "model_version_id", "policy_version_id", "actor", "occurred_at",
    "recorded_at", "correlation_id", "contract_version", "payload", "prev_hash", "hash", "canonical",
}  # fmt: skip
METRICS_COMMON = {
    "entry_type", "case_id", "outcome", "decision", "final_outcome", "used_factors", "explanation_viewed_before",
    "actor_role", "recorded_at", "seq", "recommendation_entry_id", "evaluated_at", "decided_at", "viewed_at",
}  # fmt: skip
ALLOWED: dict[tuple[str, str], set[str]] = {
    ("explanation", "recommendation"): {"seq", "case_id", "model_version_id", "payload"},
    ("metrics", "recommendation"): METRICS_COMMON | {"model_version_id", "channel", "received_at", "attempt", "first_evaluation", "delivery_status"},
    ("metrics", "human_decision"): METRICS_COMMON | {"recommendation"},
    ("metrics", "explanation_view"): METRICS_COMMON,
    ("monitoring_freezes", "freeze"): {"seq", "freeze_id", "model_version_id", "frozen_at", "recorded_at", "context_package"},
    ("monitoring_freezes", "frozen_resolution"): {"seq", "model_version_id", "action", "recorded_at"},
}  # fmt: skip
_METRICS_BASE = {"entry_type", "case_id", "recorded_at", "seq", "actor_role"}
REQUIRED = {
    "recommendation": _METRICS_BASE | {"outcome", "evaluated_at", "model_version_id", "channel", "received_at", "attempt", "first_evaluation"},
    "human_decision": _METRICS_BASE | {"decision", "final_outcome", "used_factors", "explanation_viewed_before", "decided_at", "recommendation_entry_id", "recommendation"},
    "explanation_view": _METRICS_BASE | {"viewed_at", "recommendation_entry_id"},
}  # fmt: skip
SENSITIVE = {"feature_vector", "justification", "actor_id"}
TYPES = [
    "recommendation", "fail_closed", "human_decision", "explanation_view", "model_event", "policy_event",
    "data_source_event", "freeze", "frozen_resolution", "genesis", "checkpoint",
]  # fmt: skip

texts = st.text(min_size=1, max_size=20)
STAMP = "2026-11-08T10:00:00.000000Z"


def payload_of(entry_type: str, draw: st.DrawFn) -> dict[str, Any]:
    secret = draw(texts)
    extras = {"feature_vector": {"ingreso": secret}, "justification": secret, "actor_id": secret, "narrative": secret}
    match entry_type:
        case "recommendation":
            body: dict[str, Any] = {
                "score": "0.5000", "confidence": "0.9000", "outcome": draw(st.sampled_from(["favorable", "desfavorable", "revision_requerida"])),
                "reasons": [], "feature_vector_hash": "a" * 64, "evaluated_at": STAMP, "monitoring_labels": {"sexo": "F"},
                "explanation": {"narrative": draw(texts), "method": "shap", "shap_vector": []}, "received_at": STAMP,
                "channel": draw(texts), "attempt": draw(st.integers(1, 5)), "first_evaluation": draw(st.booleans()),
            }  # fmt: skip
        case "human_decision":
            body = {
                "decision": draw(st.sampled_from(["sigue", "se_aparta", "resuelve_revision"])), "final_outcome": "favorable",
                "used_factors": [draw(texts)], "explanation_viewed_before": draw(st.booleans()), "decided_at": STAMP,
                "recommendation_entry_id": draw(texts),
            }  # fmt: skip
        case "explanation_view":
            body = {"viewed_at": STAMP, "recommendation_entry_id": draw(texts)}
        case "freeze":
            body = {"freeze_id": draw(texts), "frozen_at": STAMP, "context_package": {"data_sources": [], "n_min": 30}}
        case "frozen_resolution":
            body = {"action": draw(st.sampled_from(["reactivar", "descartar", "investigar"]))}
        case _:
            body = {"detalle": draw(texts)}
    return {**body, **extras}


@st.composite
def rows(draw: st.DrawFn) -> Row:
    entry_type = draw(st.sampled_from(TYPES))
    seq = draw(st.integers(1, 10**6))
    extra: dict[str, object] = {}
    if entry_type != "genesis":
        extra["case_id"] = str(draw(st.uuids()))
        extra["model_version_id"] = draw(texts)
    fields = entry_fields(
        seq, entry_type, payload_of(entry_type, draw), datetime(2026, 11, 8, 10, tzinfo=UTC) + timedelta(seconds=draw(st.integers(0, 10**5))),
        **extra,
    )  # fmt: skip
    fields["actor"] = {"kind": "user", "id": draw(texts), "role": draw(st.sampled_from(["analista", "cro", "cumplimiento"])), "acr": "2", "auth_time": STAMP}
    return row_of(fields, GENESIS_PREV_HASH)


def keys_below(value: object) -> set[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        for key, inner in value.items():
            found.add(key)
            if key != "explanation":  # `narrative` solo puede salir bajo `explanation` (domain-entities §3)
                found |= keys_below(inner)
            else:
                found |= {k for k in keys_below(inner) if k != "narrative"}
    elif isinstance(value, list):
        for inner in value:
            found |= keys_below(inner)
    return found


@given(rows(), st.sampled_from(CONSUMERS), st.sampled_from(PROJECTIONS))
def test_pbt_u3_06_solo_los_campos_permitidos(row: Row, consumer: Consumer, projection: str) -> None:
    """PBT-U3-06 (BR-U3-15): la proyeccion contiene solo los campos permitidos de su fila de domain-entities §3 y
    `feature_vector`, `justification` y `actor_id` nunca aparecen fuera de `full`."""
    if projection not in PERMITTED[consumer]:
        with pytest.raises(Forbidden):
            project(consumer, projection, row)
        return
    out = project(consumer, projection, row)
    if projection == "monitoring_daily":
        assert out is None  # sus datos son conteos de la tabla derivada, no entradas
        return
    if projection == "full":
        assert out is not None and set(out) == FULL_FIELDS
        return
    allowed = ALLOWED.get((projection, row.entry_type))
    if allowed is None:
        assert out is None  # la entrada no pertenece a esa proyeccion
        return
    assert out is not None
    assert set(out) <= allowed
    if projection == "metrics":
        assert REQUIRED[row.entry_type] <= set(out), REQUIRED[row.entry_type] - set(out)
    else:
        assert set(out) == allowed  # ningun campo permitido se omite
    assert not (keys_below(out) & SENSITIVE), keys_below(out) & SENSITIVE
    assert "narrative" not in keys_below(out) or projection == "explanation"


@given(rows(), st.sampled_from(CONSUMERS), st.sampled_from(PROJECTIONS), st.sets(texts | st.sampled_from(sorted(FULL_FIELDS)), max_size=4))
def test_un_campo_no_permitido_da_forbidden_sin_datos_parciales(
    row: Row, consumer: Consumer, projection: str, fields: set[str]
) -> None:
    """BR-U3-15: pedir un campo fuera de lo permitido es `Forbidden` y no devuelve ni una entrada parcial."""
    if projection not in PERMITTED[consumer] or projection == "monitoring_daily":
        with pytest.raises(Forbidden):
            project(consumer, projection, row, fields=fields)
        return
    allowed = FULL_FIELDS if projection == "full" else set().union(*(v for (p, _), v in ALLOWED.items() if p == projection))
    if fields <= allowed:
        out = project(consumer, projection, row, fields=fields)
        assert out is None or set(out) <= fields
    else:
        with pytest.raises(Forbidden):
            project(consumer, projection, row, fields=fields)


@given(st.lists(rows(), min_size=1, max_size=6), st.sampled_from(CONSUMERS), st.sampled_from(PROJECTIONS))
def test_project_all_es_todo_o_nada(entries: list[Row], consumer: Consumer, projection: str) -> None:
    """Una pagina con un campo o una proyeccion no permitidos falla entera: no se devuelve una lista parcial."""
    bad = {"feature_vector"}
    with pytest.raises(Forbidden):
        project_all(consumer, projection, entries, fields=bad)
    if projection in PERMITTED[consumer] and projection != "monitoring_daily":
        page = project_all(consumer, projection, entries)
        assert len(page) == sum(project(consumer, projection, r) is not None for r in entries)


def test_las_proyecciones_son_compatibles_con_los_tipos_de_u0() -> None:
    """La forma de `metrics` y de `frozen_resolution` valida contra los modelos de U0 (`extra = forbid`)."""
    import chain_builder

    case = chain_builder.CASES[0]
    base = dict(case_id=str(case), model_version_id="m1")
    rec = row_of(entry_fields(5, "recommendation", {
        "outcome": "favorable", "evaluated_at": STAMP, "received_at": STAMP, "channel": "web", "attempt": 1,
        "first_evaluation": True, "feature_vector": {"x": 1}, "explanation": {"narrative": "n"},
    }, datetime(2026, 11, 8, 10, tzinfo=UTC), **base), GENESIS_PREV_HASH)  # fmt: skip
    dec = row_of(entry_fields(6, "human_decision", {
        "decision": "sigue", "final_outcome": "favorable", "used_factors": ["ingreso"], "justification": "secreto",
        "explanation_viewed_before": True, "decided_at": STAMP, "recommendation_entry_id": "5",
    }, datetime(2026, 11, 8, 11, tzinfo=UTC), case_id=str(case)), GENESIS_PREV_HASH)  # fmt: skip
    for row, kwargs in ((rec, {"delivery_status": "entregada"}), (dec, {"referenced": rec}), (dec, {"referenced": None})):
        out = project(Consumer.METRICS, "metrics", row, **kwargs)
        assert out is not None
        parsed = MetricsProjection.model_validate_json(json.dumps(out))
        assert parsed.seq == row.seq and "justification" not in out
    resolved = project(Consumer.METRICS, "metrics", dec, referenced=rec)
    assert resolved is not None and resolved["recommendation"]["seq"] == 5 and resolved["recommendation"]["outcome"] == "favorable"
    assert project(Consumer.METRICS, "metrics", dec, referenced=dec)["recommendation"] is None  # type: ignore[index]
    res = row_of(entry_fields(7, "frozen_resolution", {"action": "reactivar", "justification": "x"}, datetime(2026, 11, 8, 12, tzinfo=UTC), model_version_id="m1"), GENESIS_PREV_HASH)
    out = project(Consumer.MONITORING, "monitoring_freezes", res)
    assert out is not None
    assert FrozenResolutionProjection.model_validate_json(json.dumps(out)).action == "reactivar"
    assert out["recorded_at"] == "2026-11-08T12:00:00.000000Z"


def test_explanation_devuelve_la_explicacion_y_nada_mas() -> None:
    row = row_of(entry_fields(9, "recommendation", {
        "outcome": "favorable", "feature_vector": {"x": 1}, "explanation": {"narrative": "n", "method": "shap"}, "score": "0.1000",
    }, datetime(2026, 11, 8, 10, tzinfo=UTC), case_id=str(uuid.UUID(int=1)), model_version_id="m1"), GENESIS_PREV_HASH)  # fmt: skip
    assert project(Consumer.EXPLANATION, "explanation", row) == {
        "seq": 9, "case_id": str(uuid.UUID(int=1)), "model_version_id": "m1",
        "payload": {"explanation": {"narrative": "n", "method": "shap"}},
    }  # fmt: skip


def test_ninguna_proyeccion_de_entradas_expone_monitoring_por_filas() -> None:
    """La proyeccion `monitoring` por filas se retiro (domain-entities §3): pedirla es `Forbidden`."""
    row = row_of(entry_fields(1, "recommendation", {}, datetime(2026, 11, 8, tzinfo=UTC)), GENESIS_PREV_HASH)
    for consumer in CONSUMERS:
        with pytest.raises(Forbidden):
            project(consumer, "monitoring", row)
        with pytest.raises(Forbidden):
            project(consumer, "inexistente", row)


# --- monitoring_daily: la suma en el servidor --------------------------------------------------------------------------------


def daily(day: int, count: int, *, population: str = "modelo", version: str = "m1", group: str = "F", result: str = "favorable", decision: str = "-") -> DailyCount:
    return DailyCount(population, version, date(2026, 11, day), "sexo", group, "lt_20", result, decision, count)  # type: ignore[arg-type]


def query(**ranges: Any) -> MonitoringQuery:
    return MonitoringQuery.model_validate(
        {"ranges": [{"range_id": rid, "population": "modelo", "from_day": f, "to_day": t} for rid, (f, t) in ranges.items()],
         "include_versions": True, "unattributable_range": None},
        strict=False,
    )  # fmt: skip


def test_monitoring_daily_suma_en_el_servidor_por_rango() -> None:
    data = [daily(1, 2), daily(2, 3), daily(3, 4), daily(2, 5, result="desfavorable"), daily(2, 7, population="humana", decision="sigue")]
    totals = [EntryTotals("modelo", "m1", date(2026, 11, d), 10, 1) for d in (1, 2, 3)]
    window = project_monitoring_daily(
        Consumer.MONITORING, query(a=("2026-11-01", "2026-11-02"), b=("2026-11-03", "2026-11-03")), data, totals, [],
        watermark_seq=40, lag_seconds=3,
    )  # fmt: skip
    MonitoringWindow.model_validate_json(window.model_dump_json())
    by_range = {(c.range_id, c.result): c.count for c in window.counts}
    assert by_range == {("a", "favorable"): 5, ("a", "desfavorable"): 5, ("b", "favorable"): 4}
    assert all(c.decision is None for c in window.counts)  # '-' en `modelo` sale como nulo
    assert {(t.range_id, t.total_entries, t.invalid_entries) for t in window.totals} == {("a", 20, 2), ("b", 10, 1)}
    assert [(v.model_version_id, v.population, v.first_day, v.last_day) for v in window.versions] == [
        ("m1", "humana", date(2026, 11, 2), date(2026, 11, 2)), ("m1", "modelo", date(2026, 11, 1), date(2026, 11, 3)),
    ]  # fmt: skip
    assert (window.watermark_seq, window.lag_seconds, window.unattributable_invalid) == (40, 3, 0)


def test_monitoring_daily_unattributable_invalid_es_un_solo_valor_y_no_entra_en_totals() -> None:
    totals = [EntryTotals("humana", "-", date(2026, 11, 2), 4, 3), EntryTotals("humana", "-", date(2026, 11, 9), 9, 9), EntryTotals("modelo", "m1", date(2026, 11, 2), 5, 0)]
    invalid = [InvalidEntry(seq, "humana", "-", date(2026, 11, 2), "sin_recomendacion") for seq in (30, 10, 20)]
    q = MonitoringQuery.model_validate({
        "ranges": [{"range_id": "a", "population": "modelo", "from_day": "2026-11-01", "to_day": "2026-11-05"}],
        "include_versions": False, "unattributable_range": {"from_day": "2026-11-01", "to_day": "2026-11-05"},
    }, strict=False)  # fmt: skip
    window = project_monitoring_daily(Consumer.MONITORING, q, [], totals, invalid, watermark_seq=1, lag_seconds=0)
    assert window.unattributable_invalid == 3
    assert [t.range_id for t in window.totals] == ["a"] and window.totals[0].total_entries == 5
    assert window.versions == [] and window.invalid_seqs == [10, 20, 30]
    without = project_monitoring_daily(Consumer.MONITORING, query(a=("2026-11-01", "2026-11-05")), [], totals, [], watermark_seq=1, lag_seconds=0)
    assert without.unattributable_invalid == 0


def test_monitoring_daily_solo_para_el_consumidor_de_monitoreo_y_con_100_invalidos_como_maximo() -> None:
    for consumer in (Consumer.FULL, Consumer.EXPLANATION, Consumer.METRICS):
        with pytest.raises(Forbidden):
            project_monitoring_daily(consumer, query(a=("2026-11-01", "2026-11-02")), [], [], [], watermark_seq=0, lag_seconds=0)
    invalid = [InvalidEntry(seq, "modelo", "m1", date(2026, 11, 1), "x") for seq in range(250, 0, -1)]
    window = project_monitoring_daily(Consumer.MONITORING, query(a=("2026-11-01", "2026-11-02")), [], [], invalid, watermark_seq=0, lag_seconds=0)
    assert window.invalid_seqs == list(range(1, 101))
