"""Paso 6: ejemplos de US-108 y US-502 y de BR-U0-35 (BR-U8-16)."""

import json

import pytest
from pydantic import ValidationError

from case_strategies import recommendation_from_wire
from vectra_case.decision import Rechazo, validate_decision
from vectra_contracts.catalog import PROBLEM_STATUS, Outcome, ProblemCode
from vectra_contracts.models.api import DecisionIn

LONG = "El analista justifica la decision con un motivo suficiente."


def din(decision, final, factors, justification=LONG):
    raw = {
        "decision": decision,
        "final_outcome": final,
        "used_factors": factors,
        "justification": justification,
    }
    return DecisionIn.model_validate_json(json.dumps(raw))  # `StrictModel` se valida con JSON


FAV = recommendation_from_wire(Outcome.FAVORABLE)
REV = recommendation_from_wire(Outcome.REVISION_REQUERIDA)


def test_se_aparta_without_factors_nor_ninguno_is_422():
    """US-502: `DecisionIn` ya rechaza `used_factors` vacio (422, `validation_error`)."""
    with pytest.raises(ValidationError):
        din("se_aparta", "desfavorable", [])


def test_se_aparta_with_a_foreign_factor_is_validation_error():
    result = validate_decision(din("se_aparta", "desfavorable", ["zona"]), FAV)
    assert isinstance(result, Rechazo)
    assert result.code is ProblemCode.VALIDATION_ERROR
    assert PROBLEM_STATUS[result.code] == 422


def test_sigue_with_ninguno_is_accepted():
    """US-502: `sigue` con `["ninguno"]` (sin uso de la explicacion) se acepta, sin justificacion."""
    assert validate_decision(din("sigue", "favorable", ["ninguno"], ""), FAV) is None


def test_se_aparta_with_ninguno_and_justification_is_accepted():
    assert validate_decision(din("se_aparta", "desfavorable", ["ninguno"]), FAV) is None


def test_se_aparta_with_shap_factors_is_accepted():
    assert validate_decision(din("se_aparta", "desfavorable", ["loan_to_value"]), FAV) is None


def test_resuelve_revision_on_revision_requerida_is_accepted():
    assert validate_decision(din("resuelve_revision", "desfavorable", ["age_years"]), REV) is None


def test_sigue_on_revision_requerida_is_conflict_state_409():
    result = validate_decision(din("sigue", "favorable", ["ninguno"]), REV)
    assert isinstance(result, Rechazo)
    assert result.code is ProblemCode.CONFLICT_STATE
    assert PROBLEM_STATUS[result.code] == 409


def test_br_u0_35_violations_are_conflict_state():
    for decision, final in [("sigue", "desfavorable"), ("se_aparta", "favorable")]:
        result = validate_decision(din(decision, final, ["ninguno"]), FAV)
        assert isinstance(result, Rechazo)
        assert result.code is ProblemCode.CONFLICT_STATE


def test_resuelve_revision_on_a_non_revision_outcome_is_409():
    result = validate_decision(din("resuelve_revision", "favorable", ["ninguno"]), FAV)
    assert isinstance(result, Rechazo)
    assert result.code is ProblemCode.CONFLICT_STATE


def test_both_violations_answer_422_first():
    result = validate_decision(din("sigue", "desfavorable", ["zona"]), FAV)
    assert isinstance(result, Rechazo)
    assert result.code is ProblemCode.VALIDATION_ERROR


def test_justification_is_stripped_before_measuring():
    with pytest.raises(ValidationError):
        din("se_aparta", "desfavorable", ["ninguno"], " " * 10 + "corta" + " " * 30)
    assert (
        validate_decision(din("se_aparta", "desfavorable", ["ninguno"], " " * 5 + "x" * 20 + " " * 5), FAV)
        is None
    )
