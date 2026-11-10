"""Paso 6: PBT-U8-03 (BR-U8-16; BR-U0-35, 36). Oraculo por tabla de verdad, escrito aparte de la implementacion.

Evalua la cadena completa: `DecisionIn.model_validate_json(json.dumps(raw))` y despues `validate_decision(...)`.
"""

import json

from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from case_strategies import SHAP_IDS, recommendation_from_wire
from vectra_case.decision import Rechazo, validate_decision
from vectra_contracts.catalog import Outcome, ProblemCode
from vectra_contracts.models.api import DecisionIn

# BR-U0-35 como tabla: (decision, final_outcome, outcome de la recomendacion) -> coherente.
COHERENT = {
    ("sigue", "favorable", "favorable"): True,
    ("sigue", "favorable", "desfavorable"): False,
    ("sigue", "favorable", "revision_requerida"): False,
    ("sigue", "desfavorable", "favorable"): False,
    ("sigue", "desfavorable", "desfavorable"): True,
    ("sigue", "desfavorable", "revision_requerida"): False,
    ("se_aparta", "favorable", "favorable"): False,
    ("se_aparta", "favorable", "desfavorable"): True,
    ("se_aparta", "favorable", "revision_requerida"): False,
    ("se_aparta", "desfavorable", "favorable"): True,
    ("se_aparta", "desfavorable", "desfavorable"): False,
    ("se_aparta", "desfavorable", "revision_requerida"): False,
    ("resuelve_revision", "favorable", "favorable"): False,
    ("resuelve_revision", "favorable", "desfavorable"): False,
    ("resuelve_revision", "favorable", "revision_requerida"): True,
    ("resuelve_revision", "desfavorable", "favorable"): False,
    ("resuelve_revision", "desfavorable", "desfavorable"): False,
    ("resuelve_revision", "desfavorable", "revision_requerida"): True,
}
RECS = {o: recommendation_from_wire(o) for o in Outcome}
OUTSIDE = "zona_ajena"

justifications = st.builds(
    lambda stripped_len, left, right: " " * left + "x" * stripped_len + " " * right,
    st.one_of(st.sampled_from([0, 1, 19, 20, 21, 1999, 2000]), st.integers(0, 2001)),
    st.integers(0, 4),
    st.integers(0, 4),
)
shap_subsets = st.lists(st.sampled_from(SHAP_IDS), unique=True, max_size=3)
factors = st.one_of(
    shap_subsets,  # subconjunto (vacio incluido)
    shap_subsets.map(lambda xs: [*xs, OUTSIDE]),  # ajeno
    st.just([OUTSIDE]),
    st.just(["ninguno"]),  # ninguno solo
    shap_subsets.map(lambda xs: ["ninguno", *xs[:1]]),  # ninguno combinado (o repetido)
    st.just([]),
    st.lists(st.sampled_from(SHAP_IDS), min_size=2, max_size=3).map(lambda xs: [xs[0], *xs]),  # repetido
)


def oracle(raw: dict[str, object], outcome: Outcome) -> int | None:
    """422, 409 o `None` (acepta), sin usar nada de la implementacion."""
    just = str(raw["justification"])
    used = list(raw["used_factors"])  # type: ignore[call-overload]
    decision = str(raw["decision"])
    if len(just) > 2000:
        return 422
    if decision != "sigue" and not 20 <= len(just.strip()) <= 2000:
        return 422
    if used != ["ninguno"]:
        if "ninguno" in used or not 1 <= len(used) <= 20 or len(set(used)) != len(used):
            return 422
        if any(f not in SHAP_IDS for f in used):
            return 422
    if not COHERENT[(decision, str(raw["final_outcome"]), outcome.value)]:
        return 409
    return None


def chain(raw: dict[str, object], outcome: Outcome) -> int | None:
    try:
        parsed = DecisionIn.model_validate_json(json.dumps(raw))
    except ValidationError:
        return 422
    result = validate_decision(parsed, RECS[outcome])
    if result is None:
        return None
    assert isinstance(result, Rechazo)
    return {ProblemCode.VALIDATION_ERROR: 422, ProblemCode.CONFLICT_STATE: 409}[result.code]


@given(
    decision=st.sampled_from(["sigue", "se_aparta", "resuelve_revision"]),
    final=st.sampled_from(["favorable", "desfavorable"]),
    outcome=st.sampled_from(list(Outcome)),
    used=factors,
    justification=justifications,
)
def test_validate_decision_matches_the_truth_table(decision, final, outcome, used, justification):
    raw = {"decision": decision, "final_outcome": final, "used_factors": used, "justification": justification}
    assert chain(raw, outcome) == oracle(raw, outcome)


def test_truth_table_covers_the_18_triples():
    assert len(COHERENT) == 18
