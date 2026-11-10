"""PBT-U7-01 (invariante) y PBT-U7-02 (bordes) de `policy` (BR-U7-04 a 07). Aritmetica entera en unidades de 0,0001."""

from datetime import date

from hypothesis import given
from hypothesis import strategies as st
from scoring.policy import PolicyEvaluationInput, evaluate
from u7_strategies import ORDER, as_units, d4, policy_inputs
from vectra_contracts.catalog import Outcome, ReasonCode
from vectra_contracts.models.governance import ChannelRule, NormativeParams

FORCING = {ReasonCode.PARAMETRO_NORMATIVO_NO_VIGENTE, ReasonCode.TASA_SOBRE_USURA, ReasonCode.BAJA_CONFIANZA}


def _effective(data: PolicyEvaluationInput) -> int:
    for rule in data.channel_rules:
        if rule.channel == data.channel and rule.cutoff is not None:
            return as_units(rule.cutoff)
    return as_units(data.cutoff)


@given(policy_inputs())
def test_pbt_u7_01_outcome_and_reasons_invariants(data: PolicyEvaluationInput) -> None:
    result = evaluate(data)
    reasons = result.reasons
    assert result.policy_version_id == data.policy_version_id
    assert result.outcome in {Outcome.FAVORABLE, Outcome.DESFAVORABLE, Outcome.REVISION_REQUERIDA}
    # Sin duplicados y en el orden de la tabla de BR-U7-04.
    assert len(set(reasons)) == len(reasons)
    assert [ORDER.index(r) for r in reasons] == sorted(ORDER.index(r) for r in reasons)
    # Tres casos que fuerzan la revision, con un oraculo en enteros.
    over_cap = data.normative is not None and as_units(data.proposed_rate_ea) > as_units(
        data.normative.usury_cap_ea
    )
    low_conf = as_units(data.confidence) < as_units(data.low_confidence_threshold)
    if data.normative is None or over_cap or low_conf:
        assert result.outcome is Outcome.REVISION_REQUERIDA
    # La relacion entre motivos y resultado (BR-U7-05, BR-U7-07).
    forced = FORCING & set(reasons)
    assert (result.outcome is Outcome.REVISION_REQUERIDA) == bool(forced)
    if ReasonCode.BAJA_CONFIANZA in reasons:
        assert result.outcome is Outcome.REVISION_REQUERIDA
    # Regla 4: exactamente uno de los dos motivos de corte, segun el corte efectivo del canal.
    below = as_units(data.score) < _effective(data)
    assert (ReasonCode.SCORE_BAJO_CORTE in reasons) == below
    assert (ReasonCode.SCORE_SOBRE_CORTE in reasons) == (not below)
    if not forced:
        assert result.outcome is (Outcome.FAVORABLE if below else Outcome.DESFAVORABLE)
    # Regla 5: sin normativa no se clasifica; con ella, exactamente uno.
    classified = {ReasonCode.VIS, ReasonCode.NO_VIS} & set(reasons)
    assert len(classified) == (0 if data.normative is None else 1)
    assert (ReasonCode.PARAMETRO_NORMATIVO_NO_VIGENTE in reasons) == (data.normative is None)


def _base(**changes: object) -> PolicyEvaluationInput:
    values: dict[str, object] = {
        "policy_version_id": "p-1",
        "score": "0.2000",
        "confidence": "0.9000",
        "property_value": 100,
        "proposed_rate_ea": "0.2000",
        "channel": "web",
        "cutoff": "0.5000",
        "low_confidence_threshold": "0.6000",
        "channel_rules": [],
        "normative": NormativeParams(
            vis_max_property_value=100, usury_cap_ea="0.2000", effective_from=date(2026, 1, 1), source_ref="x"
        ),
    }
    values.update(changes)
    return PolicyEvaluationInput.model_validate(values, strict=False)


STEP = st.sampled_from([-1, 0, 1])


@given(st.integers(1, 9_999), STEP)
def test_pbt_u7_02_rate_equal_to_the_usury_cap_is_not_over(cap: int, delta: int) -> None:
    normative = NormativeParams(
        vis_max_property_value=100, usury_cap_ea=d4(cap), effective_from=date(2026, 1, 1), source_ref="x"
    )
    result = evaluate(_base(normative=normative, proposed_rate_ea=d4(cap + delta)))
    assert (ReasonCode.TASA_SOBRE_USURA in result.reasons) == (delta == 1)
    assert (result.outcome is Outcome.REVISION_REQUERIDA) == (delta == 1)


@given(st.integers(1, 10**9), STEP)
def test_pbt_u7_02_property_value_equal_to_vis_max_is_vis(vis_max: int, delta: int) -> None:
    normative = NormativeParams(
        vis_max_property_value=vis_max, usury_cap_ea="0.2000", effective_from=date(2026, 1, 1), source_ref="x"
    )
    result = evaluate(_base(normative=normative, property_value=vis_max + delta))
    assert (ReasonCode.VIS in result.reasons) == (delta <= 0)
    assert (ReasonCode.NO_VIS in result.reasons) == (delta == 1)


@given(st.integers(1, 9_999), STEP, st.booleans())
def test_pbt_u7_02_score_equal_to_the_cutoff_is_unfavorable(
    cutoff: int, delta: int, per_channel: bool
) -> None:
    kwargs: dict[str, object] = {"score": d4(cutoff + delta)}
    if per_channel:
        kwargs |= {"cutoff": "0.0001", "channel_rules": [ChannelRule(channel="web", cutoff=d4(cutoff))]}
    else:
        kwargs |= {"cutoff": d4(cutoff)}
    result = evaluate(_base(**kwargs))
    below = delta == -1
    assert result.outcome is (Outcome.FAVORABLE if below else Outcome.DESFAVORABLE)
    assert (ReasonCode.SCORE_BAJO_CORTE in result.reasons) == below


@given(st.integers(1, 9_999), STEP)
def test_pbt_u7_02_confidence_equal_to_the_threshold_is_not_low(threshold: int, delta: int) -> None:
    result = evaluate(_base(low_confidence_threshold=d4(threshold), confidence=d4(threshold + delta)))
    assert (ReasonCode.BAJA_CONFIANZA in result.reasons) == (delta == -1)
