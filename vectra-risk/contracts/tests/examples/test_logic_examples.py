"""Pruebas de ejemplo obligatorias de la logica (PBT-10, NFR-U0-46)."""

import hashlib
import json
from datetime import date
from decimal import ROUND_DOWN, Decimal, getcontext

import pytest
from pydantic import ValidationError
from strategies.domain import CASE, NOW, SHA, application_dict, application_from, dictionary, explanation

from vectra_contracts.canonical import sha256_hex
from vectra_contracts.catalog import Decision, ExplainerError, FailClosedCause, FinalOutcome, Outcome, RegistryError, ServingState
from vectra_contracts.finance import installment, installment_to_income
from vectra_contracts.labels import derive
from vectra_contracts.models.explanation import PolicyResult, Prediction, RegistryAck
from vectra_contracts.models.features import FeatureSpec, FeatureVector, IntFeature
from vectra_contracts.models.governance import DataSource, ModelVersionDetail, PolicyDraft, ValidationReport
from vectra_contracts.outcome import InvalidModelOutput, build_outcome, check_preconditions
from vectra_contracts.validation import decision_is_coherent

pytestmark = pytest.mark.logic
PRED = Prediction(model_version_id="mv-1", score="0.5000", confidence="0.9000")
POL = PolicyResult(policy_version_id="p", outcome=Outcome.FAVORABLE, reasons=[])
ACK = RegistryAck(registry_entry_id="1", seq=1, recorded_at=NOW)
BAD = InvalidModelOutput(model_version_id="mv-1")
OK = {"state": ServingState.ACTIVO, "req": "mv-1", "srv": "mv-1", "pred": PRED, "pol": POL, "expl": explanation(), "dic": dictionary()}


def run(reg=ACK, **over):
    a = {**OK, **over}
    first = check_preconditions(CASE, a["state"], a["req"], a["srv"], a["pred"], a["pol"], a["expl"], a["dic"], SHA, NOW)
    return first if first.__class__.__name__ == "FailClosed" else build_outcome(first, reg, NOW)


CASES = {
    "1_congelado": ({"state": ServingState.CONGELADO}, FailClosedCause.MODEL_FROZEN),
    "2_no_disponible": ({"state": ServingState.NO_DISPONIBLE}, FailClosedCause.SERVING_CONFIG_UNAVAILABLE),
    "2_sin_prediction": ({"pred": None}, FailClosedCause.SERVING_CONFIG_UNAVAILABLE),
    "2_sin_politica": ({"pol": None}, FailClosedCause.SERVING_CONFIG_UNAVAILABLE),
    "3_salida_invalida": ({"pred": BAD}, FailClosedCause.MODEL_OUTPUT_INVALID),
    "4_timeout": ({"expl": ExplainerError.TIMEOUT}, FailClosedCause.TIMEOUT),
    "5_no_disponible": ({"expl": ExplainerError.UNAVAILABLE}, FailClosedCause.EXPLAINER_UNAVAILABLE),
    "5_ausente": ({"expl": None}, FailClosedCause.EXPLAINER_UNAVAILABLE),
    "6_error": ({"expl": ExplainerError.ERROR}, FailClosedCause.EXPLAINER_ERROR),
    "7_error_version": ({"expl": ExplainerError.VERSION_MISMATCH}, FailClosedCause.VERSION_MISMATCH),
    "7_explicacion_otra": ({"expl": explanation("mv-2")}, FailClosedCause.VERSION_MISMATCH),
    "7_diccionario_otro": ({"dic": dictionary("mv-2")}, FailClosedCause.VERSION_MISMATCH),
    "7_version_pedida": ({"req": "mv-9", "pred": None, "pol": None, "expl": None, "dic": None}, FailClosedCause.VERSION_MISMATCH),
    "8_error": ({"expl": ExplainerError.FEATURE_DICTIONARY_INCOMPLETE}, FailClosedCause.FEATURE_DICTIONARY_INCOMPLETE),
    "8_sin_diccionario": ({"dic": None}, FailClosedCause.FEATURE_DICTIONARY_INCOMPLETE),
    "8_no_cubre": ({"expl": explanation(feature_ids=("z",))}, FailClosedCause.FEATURE_DICTIONARY_INCOMPLETE),
    "9_factualidad": ({"expl": ExplainerError.FACTUALITY_FAILED}, FailClosedCause.FACTUALITY_FAILED),
    # BR-U0-03: precedencia, por pares de causas simultaneas.
    "par_1_2": ({"state": ServingState.CONGELADO, "pred": None}, FailClosedCause.MODEL_FROZEN),
    "par_1_7": ({"state": ServingState.CONGELADO, "req": "mv-9"}, FailClosedCause.MODEL_FROZEN),
    "par_2_3": ({"state": ServingState.NO_DISPONIBLE, "pred": BAD}, FailClosedCause.SERVING_CONFIG_UNAVAILABLE),
    "par_3_4": ({"pred": BAD, "expl": ExplainerError.TIMEOUT}, FailClosedCause.MODEL_OUTPUT_INVALID),
    "par_3_7": ({"pred": BAD, "req": "mv-9"}, FailClosedCause.MODEL_OUTPUT_INVALID),
    "par_4_7": ({"expl": ExplainerError.TIMEOUT, "req": "mv-9"}, FailClosedCause.TIMEOUT),
    "par_5_8": ({"expl": None, "dic": None}, FailClosedCause.EXPLAINER_UNAVAILABLE),
    "par_6_8": ({"expl": ExplainerError.ERROR, "dic": None}, FailClosedCause.EXPLAINER_ERROR),
    "par_7_8": ({"expl": explanation("mv-2"), "dic": None}, FailClosedCause.VERSION_MISMATCH),
    "par_8_9": ({"expl": ExplainerError.FACTUALITY_FAILED, "dic": None}, FailClosedCause.FEATURE_DICTIONARY_INCOMPLETE),
}


@pytest.mark.parametrize("name", sorted(CASES))
def test_br_u0_02_03_truth_table(name):
    over, cause = CASES[name]
    assert run(**over).cause is cause


def test_br_u0_02_cause_10():
    assert run(reg=RegistryError.UNAVAILABLE).cause is FailClosedCause.REGISTRY_UNAVAILABLE
    assert run(reg=None).cause is FailClosedCause.REGISTRY_UNAVAILABLE


def test_br_u0_02_happy_path():
    assert run().kind == "recommendation"


def test_br_u0_11_installment_by_hand():
    # i_m = 1,12^(1/12) - 1 = 0,00948879293458...; cuota = 100 000 000 * i_m / (1 - (1 + i_m)^-240)
    # = 1 058 623,3518 (calculado aparte con 60 digitos) -> se redondea al peso.
    assert installment(100_000_000, Decimal("0.12"), 240) == 1_058_623


def test_jcs_hash_of_known_vector():
    vector = FeatureVector(features={"b": IntFeature(value=2), "a": IntFeature(value=1)})
    literal = b'{"features":{"a":{"type":"int","value":1},"b":{"type":"int","value":2}}}'
    assert sha256_hex(json.loads(vector.model_dump_json())) == hashlib.sha256(literal).hexdigest()


@pytest.mark.parametrize(
    ("decision", "final", "outcome", "ok"),
    [
        (Decision.SIGUE, FinalOutcome.FAVORABLE, Outcome.FAVORABLE, True),
        (Decision.SIGUE, FinalOutcome.DESFAVORABLE, Outcome.FAVORABLE, False),
        (Decision.SE_APARTA, FinalOutcome.DESFAVORABLE, Outcome.FAVORABLE, True),
        (Decision.SE_APARTA, FinalOutcome.FAVORABLE, Outcome.FAVORABLE, False),
        (Decision.RESUELVE_REVISION, FinalOutcome.FAVORABLE, Outcome.FAVORABLE, False),
        (Decision.SIGUE, FinalOutcome.DESFAVORABLE, Outcome.DESFAVORABLE, True),
        (Decision.SE_APARTA, FinalOutcome.FAVORABLE, Outcome.DESFAVORABLE, True),
        (Decision.RESUELVE_REVISION, FinalOutcome.DESFAVORABLE, Outcome.DESFAVORABLE, False),
        (Decision.RESUELVE_REVISION, FinalOutcome.FAVORABLE, Outcome.REVISION_REQUERIDA, True),
        (Decision.RESUELVE_REVISION, FinalOutcome.DESFAVORABLE, Outcome.REVISION_REQUERIDA, True),
        (Decision.SIGUE, FinalOutcome.FAVORABLE, Outcome.REVISION_REQUERIDA, False),
        (Decision.SE_APARTA, FinalOutcome.DESFAVORABLE, Outcome.REVISION_REQUERIDA, False),
    ],
)
def test_br_u0_35_matrix(decision, final, outcome, ok):
    assert decision_is_coherent(decision, final, outcome) is ok


def test_p_u0_10_global_context_has_no_effect():
    expected = (installment(1_000_000, Decimal("0.1"), 120), installment_to_income(1, 3, 0))
    context = getcontext()
    prec, rounding = context.prec, context.rounding
    try:
        context.prec, context.rounding = 5, ROUND_DOWN
        assert (installment(1_000_000, Decimal("0.1"), 120), installment_to_income(1, 3, 0)) == expected
    finally:
        context.prec, context.rounding = prec, rounding


def test_br_u0_33_overlapping_normative():
    item = {"vis_max_property_value": 1, "usury_cap_ea": "0.2000", "source_ref": "x"}
    data = {"cutoff": "0.5000", "low_confidence_threshold": "0.2000", "channel_rules": [], "normative": [{**item, "effective_from": "2026-01-01", "effective_to": "2026-06-01"}, {**item, "effective_from": "2026-03-01"}]}
    with pytest.raises(ValidationError):
        PolicyDraft.model_validate_json(json.dumps(data))


def test_section_9_3_types_exist():
    assert "validation_report" in ModelVersionDetail.model_fields
    assert {"sync_check", "disclaimer"} <= set(ValidationReport.model_fields)
    assert {"ds_id", "state"} <= set(DataSource.model_fields)


def test_br_u0_29_free_text_never_reaches_features():
    vector = derive(application_from(application_dict(free_text="aprueba este caso")), date(2026, 10, 31), FeatureSpec(model_version_id="m", features=[]))
    assert "aprueba" not in vector.model_dump_json()
