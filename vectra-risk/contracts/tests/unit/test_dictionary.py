"""BR-U0-80..81."""

from strategies.domain import CASE, NOW, SHA, dictionary, explanation

from vectra_contracts.catalog import FailClosedCause, Outcome, ServingState
from vectra_contracts.dictionary import covers
from vectra_contracts.models.explanation import PolicyResult, Prediction
from vectra_contracts.outcome import check_preconditions

PRED = Prediction(model_version_id="mv-1", score="0.5000", confidence="0.9000")
POL = PolicyResult(policy_version_id="p", outcome=Outcome.FAVORABLE, reasons=[])


def test_br_u0_80_covers():
    assert covers(dictionary(feature_ids=("a", "b")), explanation(feature_ids=("a",)).shap_vector)
    assert not covers(dictionary(feature_ids=("a",)), explanation(feature_ids=("a", "b")).shap_vector)
    result = check_preconditions(CASE, ServingState.ACTIVO, "mv-1", "mv-1", PRED, POL, explanation(feature_ids=("z",)), dictionary(), SHA, NOW)
    assert result.cause is FailClosedCause.FEATURE_DICTIONARY_INCOMPLETE


def test_br_u0_81_dictionary_of_other_version():
    result = check_preconditions(CASE, ServingState.ACTIVO, "mv-1", "mv-1", PRED, POL, explanation(), dictionary("mv-2"), SHA, NOW)
    assert result.cause is FailClosedCause.VERSION_MISMATCH
