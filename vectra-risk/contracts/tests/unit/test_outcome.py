"""P-U0-03 y BR-U0-01..08."""

import json
import math

import pytest
from pydantic import ValidationError
from strategies.domain import CASE, NOW, SHA, case_detail_data, dictionary, explanation

from vectra_contracts.catalog import ExplainerError, FailClosedCause, Outcome, RegistryError, ServingState
from vectra_contracts.errors import ContractViolation
from vectra_contracts.models.api import CaseDetail
from vectra_contracts.models.base import StrictModel
from vectra_contracts.models.explanation import FailClosed, PolicyResult, Prediction, RegistryAck
from vectra_contracts.outcome import (
    Ready,
    Recommendation,
    RecommendResult,
    build_outcome,
    check_preconditions,
    quantize_prediction,
    quantize_probability,
    read_wire,
)

PRED = Prediction(model_version_id="mv-1", score="0.5000", confidence="0.9000")
POL = PolicyResult(policy_version_id="p1", outcome=Outcome.FAVORABLE, reasons=[])
ACK = RegistryAck(registry_entry_id="7", seq=7, recorded_at=NOW)


def ready():
    r = check_preconditions(CASE, ServingState.ACTIVO, "mv-1", "mv-1", PRED, POL, explanation(), dictionary(), SHA, NOW)
    assert isinstance(r, Ready)
    return r


def test_br_u0_01_direct_construction_forbidden():
    with pytest.raises(ContractViolation):
        Recommendation(case_id=CASE, score="0.5000", confidence="0.5000", outcome=Outcome.FAVORABLE, reasons=[], model_version_id="m", policy_version_id="p", explanation=explanation("m"), registry_entry_id="1", evaluated_at=NOW, feature_vector_hash=SHA)
    with pytest.raises(ContractViolation):
        Ready(case_id=CASE, prediction=PRED, policy_result=POL, explanation=explanation(), feature_vector_hash=SHA, evaluated_at=NOW)
    with pytest.raises(ContractViolation):
        Ready.model_construct()
    with pytest.raises(ContractViolation):
        Ready.model_validate({"case_id": CASE, "prediction": PRED, "policy_result": POL, "explanation": explanation(), "feature_vector_hash": SHA, "evaluated_at": NOW})


def test_br_u0_01_build_outcome_is_only_path():
    result = build_outcome(ready(), ACK, NOW)
    assert isinstance(result, Recommendation)
    assert result.registry_entry_id == "7" and result.score == "0.5000" and result.explanation == explanation()


def test_br_u0_02_registry_cause():
    for registry in (RegistryError.UNAVAILABLE, None):
        result = build_outcome(ready(), registry, NOW)
        assert isinstance(result, FailClosed) and result.cause is FailClosedCause.REGISTRY_UNAVAILABLE and result.retryable


def test_br_u0_04_frozen_not_retryable():
    result = check_preconditions(CASE, ServingState.CONGELADO, "mv-1", "mv-1", None, None, None, None, SHA, NOW)
    assert isinstance(result, FailClosed) and not result.retryable and result.status == "modelo_congelado"


def test_br_u0_05_no_substitute_explanation():
    result = check_preconditions(CASE, ServingState.ACTIVO, "mv-1", "mv-1", PRED, POL, None, dictionary(), SHA, NOW)
    assert isinstance(result, FailClosed) and result.cause is FailClosedCause.EXPLAINER_UNAVAILABLE


def test_br_u0_06_from_wire_roundtrip_by_kind():
    rec = build_outcome(ready(), ACK, NOW)
    assert RecommendResult.from_wire(rec.model_dump_json()) == rec
    failed = FailClosed(case_id=CASE, status="en_sincronizacion", cause=FailClosedCause.TIMEOUT, retryable=True, occurred_at=NOW)
    assert RecommendResult.from_wire(failed.model_dump_json()) == failed


def test_p_u0_03_from_wire_with_different_versions_fails():
    rec = json.loads(build_outcome(ready(), ACK, NOW).model_dump_json())
    rec["model_version_id"] = "otra"
    with pytest.raises(ValidationError):
        RecommendResult.from_wire(json.dumps(rec))
    bad = json.loads(build_outcome(ready(), ACK, NOW).model_dump_json())
    bad["explanation"]["factuality_check"] = "failed"
    with pytest.raises(ValidationError):
        RecommendResult.from_wire(json.dumps(bad))
    empty = json.loads(build_outcome(ready(), ACK, NOW).model_dump_json())
    empty["registry_entry_id"] = ""
    with pytest.raises(ValidationError):
        RecommendResult.from_wire(json.dumps(empty))


def test_from_wire_outcome_outside_catalog():
    """BR-U0-20, NFR-U0-14, P-U0-03 capa 1: `outcome` fuera del catalogo se rechaza."""
    rec = json.loads(build_outcome(ready(), ACK, NOW).model_dump_json())
    rec["outcome"] = "aprobado_a_ciegas"
    with pytest.raises(ValidationError):
        RecommendResult.from_wire(json.dumps(rec))


def test_from_wire_reasons_outside_catalog():
    """BR-U0-20, NFR-U0-14, P-U0-03 capa 1: `reasons` fuera del catalogo se rechaza."""
    rec = json.loads(build_outcome(ready(), ACK, NOW).model_dump_json())
    rec["reasons"] = ["cualquier_cosa"]
    with pytest.raises(ValidationError):
        RecommendResult.from_wire(json.dumps(rec))


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf, -0.1, 1.0001])
def test_br_u0_07_invalid_model_output(value):
    assert quantize_probability(value) is None
    invalid = quantize_prediction("mv-1", value, 0.5)
    result = check_preconditions(CASE, ServingState.ACTIVO, "mv-1", "mv-1", invalid, None, None, None, SHA, NOW)
    assert isinstance(result, FailClosed) and result.cause is FailClosedCause.MODEL_OUTPUT_INVALID


def test_br_u0_07_quantization_half_up():
    assert quantize_probability(0.0) == "0.0000" and quantize_probability(1.0) == "1.0000"
    assert quantize_probability(-0.0) == "0.0000"
    assert quantize_probability(0.12345678) == "0.1235"
    assert quantize_prediction("m", 0.5, 0.25).score == "0.5000"


def test_failclosed_model_coherence():
    with pytest.raises(ValidationError):
        FailClosed(case_id=CASE, status="modelo_congelado", cause=FailClosedCause.TIMEOUT, retryable=True, occurred_at=NOW)
    with pytest.raises(ValidationError):
        FailClosed(case_id=CASE, status="en_sincronizacion", cause=FailClosedCause.TIMEOUT, retryable=False, occurred_at=NOW)


def test_br_u0_08_explainer_errors_map():
    table = {
        ExplainerError.TIMEOUT: FailClosedCause.TIMEOUT,
        ExplainerError.UNAVAILABLE: FailClosedCause.EXPLAINER_UNAVAILABLE,
        ExplainerError.ERROR: FailClosedCause.EXPLAINER_ERROR,
        ExplainerError.VERSION_MISMATCH: FailClosedCause.VERSION_MISMATCH,
        ExplainerError.FEATURE_DICTIONARY_INCOMPLETE: FailClosedCause.FEATURE_DICTIONARY_INCOMPLETE,
        ExplainerError.FACTUALITY_FAILED: FailClosedCause.FACTUALITY_FAILED,
    }
    for error, cause in table.items():
        result = check_preconditions(CASE, ServingState.ACTIVO, "mv-1", "mv-1", PRED, POL, error, dictionary(), SHA, NOW)
        assert result.cause is cause


def test_p_u0_03_violation_messages():
    data = {"case_id": CASE, "prediction": PRED, "policy_result": POL, "explanation": explanation(), "feature_vector_hash": SHA, "evaluated_at": NOW}
    with pytest.raises(ContractViolation) as error:
        Ready.model_validate(data)
    assert str(error.value) == "Ready solo se construye con las fabricas de outcome"
    with pytest.raises(ContractViolation) as error:
        Recommendation.model_construct()
    assert str(error.value) == "Recommendation no admite model_construct"


class _Wrapper(StrictModel):
    r: Recommendation | None = None


class _WithReady(StrictModel):
    ready: Ready


def _rec():
    rec = build_outcome(ready(), ACK, NOW)
    assert isinstance(rec, Recommendation)
    return rec


def test_nest_instance_in_case_detail_without_token():
    """P-U0-03 capa 2: una instancia ya construida se anida sin el token."""
    rec = _rec()
    detail = CaseDetail.model_validate(case_detail_data(rec))
    assert detail.recommendation == rec


def test_nest_instance_in_wrapper_three_forms():
    rec = _rec()
    assert _Wrapper(r=rec).r == rec
    assert _Wrapper.model_validate({"r": rec}).r == rec
    assert _Wrapper(r=None).r is None


def test_nest_does_not_accept_dict_without_token():
    data = _rec().model_dump()
    with pytest.raises(ContractViolation):
        Recommendation.model_validate(data)
    with pytest.raises(ContractViolation):
        CaseDetail.model_validate(case_detail_data(data))
    with pytest.raises(ContractViolation):
        _Wrapper.model_validate({"r": data})


def test_nest_does_not_accept_json_without_token():
    payload = CaseDetail.model_validate(case_detail_data(_rec())).model_dump_json()
    with pytest.raises(ContractViolation):
        CaseDetail.model_validate_json(payload)
    with pytest.raises(ContractViolation):
        _Wrapper.model_validate_json(json.dumps({"r": json.loads(_rec().model_dump_json())}))


def test_read_wire_roundtrip_case_detail():
    detail = CaseDetail.model_validate(case_detail_data(_rec()))
    assert read_wire(CaseDetail, detail.model_dump_json()) == detail
    empty = CaseDetail.model_validate(case_detail_data(None))
    assert read_wire(CaseDetail, empty.model_dump_json()) == empty


def test_read_wire_applies_layer_1():
    base = json.loads(CaseDetail.model_validate(case_detail_data(_rec())).model_dump_json())
    mismatch = json.loads(json.dumps(base))
    mismatch["recommendation"]["explanation"]["model_version_id"] = "otra"
    with pytest.raises(ValidationError):
        read_wire(CaseDetail, json.dumps(mismatch))
    blank = json.loads(json.dumps(base))
    blank["recommendation"]["registry_entry_id"] = ""
    with pytest.raises(ValidationError):
        read_wire(CaseDetail, json.dumps(blank))


def test_read_wire_rejects_ready_and_containers_of_ready():
    payload = ready().model_dump_json()
    with pytest.raises(ContractViolation):
        read_wire(Ready, payload)
    with pytest.raises(ContractViolation):
        read_wire(_WithReady, json.dumps({"ready": json.loads(payload)}))


def test_read_wire_accepts_str_bytes_and_bare_recommendation():
    rec = _rec()
    assert read_wire(Recommendation, rec.model_dump_json().encode()) == rec


def test_construction_token_is_not_a_public_attribute_of_outcome():
    """R2-01 (ronda 2 de U08-T02): `outcome` no reexporta el token."""
    import vectra_contracts.outcome as outcome

    assert not hasattr(outcome, "CONSTRUCTION_TOKEN")
    assert "CONSTRUCTION_TOKEN" not in outcome.__all__
    with pytest.raises(ImportError):
        exec("from vectra_contracts.outcome import CONSTRUCTION_TOKEN", {})
