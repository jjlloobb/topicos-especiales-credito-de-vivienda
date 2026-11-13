"""PBT-U12-03, la mezcla del conductor (U12 Paso 6; BR-U12-03; NFR-U12-10, 41): para toda `DecisionMix`, las decisiones generadas cumplen BR-U0-35 y 36 y BR-U8-16, y con N grande las proporciones
convergen a las de la mezcla. El oraculo son los validadores reales (`DecisionIn`, `decision_is_coherent` de U0 y `validate_decision` de U8), no una copia."""

import math
import random
from typing import Any

from contract_world import recommendation_json
from hypothesis import given, settings
from hypothesis import strategies as st
from vectra_case.decision import validate_decision
from vectra_contracts.catalog import Decision, Outcome
from vectra_contracts.models.api import DecisionIn
from vectra_contracts.outcome import Recommendation, RecommendResult
from vectra_contracts.validation import decision_is_coherent

from vectra_verification.driver import CaseFacts, DecisionMix, plan

CASE_ID = "3fa85f64-5717-4562-b3fc-2c963f66afa6"
probabilities = st.one_of(st.sampled_from([0.0, 1.0]), st.floats(0.0, 1.0))  # los extremos 0 y 1 incluidos
mixes = st.builds(
    DecisionMix,
    p_view=probabilities,
    p_sigue=probabilities,
    p_se_aparta=probabilities,
    p_resuelve_revision=probabilities,
    p_factors=probabilities,
    seed=st.integers(0, 2**32 - 1),
)
outcomes = st.sampled_from(list(Outcome))
feature_ids = st.lists(
    st.from_regex(r"[a-z][a-z0-9_]{2,20}", fullmatch=True), min_size=1, max_size=40, unique=True
)  # mas de 20: se prueba el tope de `check_used_factors`
facts = st.builds(CaseFacts, outcome=outcomes, feature_ids=feature_ids.map(tuple))


def recommendation_of(case: CaseFacts) -> Recommendation:
    result = RecommendResult.from_wire(
        __import__("json").dumps(recommendation_json(case.outcome.value, CASE_ID, case.feature_ids))
    )
    assert isinstance(result, Recommendation)
    return result


def many(mix: DecisionMix, case: CaseFacts, count: int) -> list[Any]:
    rng = random.Random(mix.seed)
    return [plan(mix, case, rng) for _ in range(count)]


@given(mixes, facts)
def test_valid_every_generated_decision_passes_the_real_validators(mix: DecisionMix, case: CaseFacts) -> None:
    recommendation = recommendation_of(case)
    for chosen in many(mix, case, 12):
        if chosen.decision is None:
            assert case.outcome is Outcome.REVISION_REQUERIDA  # solo ahi la mezcla puede no decidir
            continue
        decision = chosen.decision
        assert DecisionIn.model_validate_json(decision.model_dump_json()) == decision
        assert decision_is_coherent(decision.decision, decision.final_outcome, case.outcome)
        assert (
            validate_decision(decision, recommendation) is None
        )  # BR-U8-16 y BR-U0-35 contra la recomendacion del caso


@given(mixes, facts)
def test_the_options_follow_the_outcome(mix: DecisionMix, case: CaseFacts) -> None:
    for chosen in many(mix, case, 12):
        if chosen.decision is None:
            continue
        kind = chosen.decision.decision
        if case.outcome is Outcome.REVISION_REQUERIDA:
            assert kind is Decision.RESUELVE_REVISION  # con `revision_requerida` nunca `sigue` ni `se_aparta`
        else:
            assert kind in (Decision.SIGUE, Decision.SE_APARTA)  # sin ella nunca `resuelve_revision`
            assert (chosen.decision.final_outcome.value == case.outcome.value) == (kind is Decision.SIGUE)


@given(mixes, facts)
def test_used_factors_are_a_subset_of_the_shap_vector_without_repeats_or_exactly_ninguno(
    mix: DecisionMix, case: CaseFacts
) -> None:
    for chosen in many(mix, case, 12):
        if chosen.decision is None:
            continue
        factors = chosen.decision.used_factors
        if factors == ["ninguno"]:
            continue
        assert (
            "ninguno" not in factors
            and 1 <= len(factors) <= 20
            and len(set(factors)) == len(factors)
            and set(factors) <= set(case.feature_ids)
        )


@given(mixes, facts)
def test_justification_is_20_to_2000_characters_when_the_decision_departs_or_resolves(
    mix: DecisionMix, case: CaseFacts
) -> None:
    for chosen in many(mix, case, 12):
        if chosen.decision is not None and chosen.decision.decision is not Decision.SIGUE:
            assert 20 <= len(chosen.decision.justification.strip()) <= 2000


@given(mixes, facts)
def test_determinism_same_mix_same_seed_same_cases_same_decisions(mix: DecisionMix, case: CaseFacts) -> None:
    assert many(mix, case, 8) == many(mix, case, 8)


@given(mixes)
def test_the_mix_never_uses_the_global_generator(mix: DecisionMix) -> None:
    random.seed(1)
    first = many(mix, CaseFacts(Outcome.FAVORABLE, ("a_feature", "b_feature", "c_feature")), 6)
    random.seed(2)
    random.random()
    assert first == many(mix, CaseFacts(Outcome.FAVORABLE, ("a_feature", "b_feature", "c_feature")), 6)


N = 5000
SIGMAS = 5.0  # tolerancia declarada: 5 desviaciones estandar de la binomial


def _within(observed: int, p: float) -> bool:
    spread = SIGMAS * math.sqrt(p * (1 - p) / N)
    return abs(observed / N - p) <= spread + 1e-12


@settings(max_examples=20)  # cada ejemplo corre 3 estratos de 5 000 casos
@given(mixes)
def test_convergence_the_observed_proportions_match_the_mix_per_outcome_stratum(mix: DecisionMix) -> None:
    ids = tuple(f"feature_{i}" for i in range(30))
    for outcome in Outcome:
        chosen = many(mix, CaseFacts(outcome, ids), N)
        assert _within(sum(c.open_explanation for c in chosen), mix.p_view)  # consulta de la explicacion
        decided = [c.decision for c in chosen if c.decision is not None]
        if outcome is Outcome.REVISION_REQUERIDA:
            assert _within(
                len(decided), mix.p_resuelve_revision
            )  # lo que fija P-6 (a): decide con p_resuelve_revision
        else:
            assert len(decided) == N
            weight = mix.p_sigue + mix.p_se_aparta
            follows = 1.0 if weight == 0 else mix.p_sigue / weight
            assert _within(
                sum(d.decision is Decision.SIGUE for d in decided), follows
            )  # `sigue` frente a `se_aparta`
        with_factors = sum(d.used_factors != ["ninguno"] for d in decided)
        if decided:
            spread = SIGMAS * math.sqrt(mix.p_factors * (1 - mix.p_factors) / len(decided))
            assert (
                abs(with_factors / len(decided) - mix.p_factors) <= spread + 1e-12
            )  # factores frente a «ninguno»
    if mix.p_view in (0.0, 1.0):
        assert sum(c.open_explanation for c in many(mix, CaseFacts(Outcome.FAVORABLE, ids), 50)) in (
            0,
            50,
        )  # con 0 ninguna; con 1 todas
