"""Reglas puras de `append` sin base de datos (Paso 7 del plan de U3; BR-U3-03, 05, 06, 16; domain-entities §6)."""

import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from entries import BUSINESS_TYPES, CRO, NOW, entry_dict, make, payload_for
from vectra_common.errors import Forbidden, ValidationFailed
from vectra_contracts.catalog import Scope
from vectra_registry import append, locks

SCORING, CASE_SCOPE, GOVERNANCE = (
    Scope.REGISTRY_APPEND_SCORING,
    Scope.REGISTRY_APPEND_CASE,
    Scope.REGISTRY_APPEND_GOVERNANCE,
)
ESCALATION = {"local_cause": "scoring_rejected", "retryable": False, "attempt": 3, "escalated_at": "2026-11-08T12:00:00.000000Z"}
PER_ATTEMPT = {"cause": "timeout", "retryable": True, "attempt": 1}


def test_las_llaves_de_advisory_lock_son_distintas_y_las_del_diseno() -> None:
    assert locks.APPEND_LOCK != locks.REBUILD_LOCK
    assert (locks.APPEND_LOCK, locks.REBUILD_LOCK) == (0x56520001, 0x56520002)


@pytest.mark.parametrize("scope", [SCORING, CASE_SCOPE, GOVERNANCE])
@pytest.mark.parametrize("entry_type", [t for t in BUSINESS_TYPES if t != "fail_closed"])
def test_br_u3_03_la_tabla_de_scopes_y_tipos(scope: Scope, entry_type: str) -> None:
    expected = entry_type in {s.value for s in append.SCOPE_TYPES[scope]} or entry_type in append.SCOPE_TYPES[scope]
    assert append.scope_permits(scope, make(entry_type)) is expected


@pytest.mark.parametrize(
    ("payload", "scoring", "case"),
    [(PER_ATTEMPT, True, False), (ESCALATION, False, True)],
    ids=["por_intento", "escalamiento"],
)
def test_br_u3_03_fail_closed_es_simetrico(payload: dict[str, Any], scoring: bool, case: bool) -> None:
    entry = make("fail_closed", payload=payload)
    assert append.scope_permits(SCORING, entry) is scoring
    assert append.scope_permits(CASE_SCOPE, entry) is case
    assert append.scope_permits(GOVERNANCE, entry) is False


def test_br_u3_03_authorize_basta_con_un_scope_que_lo_permita() -> None:
    entry = make("human_decision")
    append.authorize([SCORING, CASE_SCOPE], entry)
    with pytest.raises(Forbidden):
        append.authorize([SCORING, GOVERNANCE], entry)
    with pytest.raises(Forbidden):
        append.authorize([], entry)


def test_br_u3_03_el_registro_es_el_unico_que_escribe_genesis_y_checkpoint() -> None:
    assert not any(t in scope_types for scope_types in append.SCOPE_TYPES.values() for t in ("genesis", "checkpoint"))


@pytest.mark.parametrize(
    ("entry_type", "payload", "actor", "allowed"),
    [
        ("freeze", None, {"kind": "system", "id": "bias-monitoring-job"}, True),
        ("freeze", None, CRO, True),
        ("freeze", None, {"kind": "system", "id": "otro"}, False),
        ("model_event", {"event": "informe_validacion", "details": {}}, {"kind": "service", "id": "model-validation-job"}, True),
        ("model_event", {"event": "validacion_fallida", "details": {}}, {"kind": "system", "id": "governance-service"}, True),
        ("model_event", {"event": "transicion_descartada", "details": {}}, {"kind": "system", "id": "governance-service"}, True),
        ("model_event", {"event": "transicion_descartada", "details": {}}, {"kind": "service", "id": "model-validation-job"}, False),
        ("model_event", {"event": "aprobado", "details": {}}, {"kind": "system", "id": "governance-service"}, False),
        ("policy_event", None, {"kind": "service", "id": "model-validation-job"}, False),
        ("recommendation", None, {"kind": "service", "id": "cualquiera"}, True),  # no es de gobierno: no aplica
    ],
)
def test_br_u3_16_actores_de_los_eventos_de_gobierno(entry_type: str, payload: Any, actor: dict[str, Any], allowed: bool) -> None:
    entry = make(entry_type, payload=payload, actor=actor)
    if allowed:
        append.check_governance_actor(entry)
    else:
        with pytest.raises(Forbidden):
            append.check_governance_actor(entry)


def test_br_u3_16_una_persona_sin_rol_es_422() -> None:
    entry = make("policy_event", actor={k: v for k, v in CRO.items() if k != "role"})
    with pytest.raises(ValidationFailed):
        append.check_governance_actor(entry)


def test_br_u3_05_check_window_en_el_borde() -> None:
    append.check_window(NOW + timedelta(seconds=300), NOW)
    append.check_window(NOW - timedelta(seconds=300), NOW)
    for beyond in (timedelta(seconds=300, microseconds=1), -timedelta(seconds=300, microseconds=1)):
        with pytest.raises(ValidationFailed):
            append.check_window(NOW + beyond, NOW)


def test_br_u3_05_next_recorded_at_nunca_retrocede() -> None:
    head = NOW
    assert append.next_recorded_at(NOW - timedelta(hours=1), head) == head
    assert append.next_recorded_at(NOW + timedelta(seconds=1), head) == NOW + timedelta(seconds=1)


def test_br_u3_05_received_at_no_es_un_momento_de_negocio() -> None:
    entry = make("recommendation", payload=payload_for("recommendation", NOW, received_at="2026-10-09T12:00:00.000000Z"))
    append.check_business(entry)  # hace 30 dias: no entra en check_business_time


def test_br_u3_05_un_momento_de_negocio_viejo_o_futuro_es_422() -> None:
    for field, moment in (("viewed_at", NOW - timedelta(days=7, seconds=1)), ("viewed_at", NOW + timedelta(seconds=1))):
        payload = payload_for("explanation_view", NOW, **{field: moment.isoformat().replace("+00:00", "Z")})
        with pytest.raises(ValidationFailed):
            append.check_business(make("explanation_view", payload=payload))
    append.check_business(make("explanation_view", payload=payload_for("explanation_view", NOW, viewed_at=(NOW - timedelta(days=7)).isoformat().replace("+00:00", "Z"))))


def body_of(entry: Any, seq: int = 5, at: datetime = NOW) -> dict[str, Any]:
    return json.loads(append.build_canonical(entry, seq, at))


def test_br_u3_06_los_campos_de_negocio_ignoran_occurred_at_correlation_id_y_contract_version() -> None:
    key = uuid.uuid4()
    first = make("recommendation", key=key)
    stored = append.build_canonical(first, 7, NOW)
    other_trace = make("recommendation", key=key, occurred_at=NOW + timedelta(minutes=9), payload=json.loads(first.model_dump_json())["payload"])
    other_trace = other_trace.model_copy(update={"correlation_id": "f" * 32})
    assert append.same_business(other_trace, stored)
    assert append.business_of(body_of(first)) == append.business_of(json.loads(stored))


@pytest.mark.parametrize("field", ["model_version_id", "case_id", "policy_version_id"])
def test_br_u3_06_un_campo_de_negocio_distinto_no_es_el_mismo_contenido(field: str) -> None:
    key = uuid.uuid4()
    first = make("recommendation", key=key)
    stored = append.build_canonical(first, 7, NOW)
    changed = first.model_copy(update={field: uuid.uuid4() if field == "case_id" else "otro"})
    assert not append.same_business(changed, stored)


def test_br_u3_06_un_campo_nulo_y_uno_ausente_son_lo_mismo() -> None:
    assert append.business_of({"entry_type": "x", "case_id": None}) == append.business_of({"entry_type": "x"})


def test_br_u3_09_canonical_omite_los_opcionales_ausentes_y_lleva_seq_y_recorded_at() -> None:
    body = body_of(make("model_event", case_id=None))
    assert "case_id" not in body and "policy_version_id" not in body
    assert body["seq"] == 5 and body["recorded_at"] == "2026-11-08T12:00:00.000000Z"
    assert body["contract_version"] == "0.1.0" and body["actor"] == {k: v for k, v in body["actor"].items() if v is not None}


def test_br_u3_09_un_date_del_payload_sale_en_iso() -> None:
    body = body_of(make("freeze"))
    assert body["payload"]["context_package"]["window_start"] == "2026-10-01"


def test_entry_dict_es_json_valido() -> None:
    assert json.loads(json.dumps(entry_dict("recommendation")))["entry_type"] == "recommendation" and UTC
