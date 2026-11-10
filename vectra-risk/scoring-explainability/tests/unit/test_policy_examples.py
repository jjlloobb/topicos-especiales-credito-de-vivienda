"""Ejemplos de `policy` (PBT-10): US-103, US-106 (caso RT-4 de U5), US-207, cutoff por canal y normativa nula (BR-U7-06)."""

from datetime import date
from decimal import Decimal

from scoring.policy import PolicyEvaluationInput, effective_cutoff, evaluate
from vectra_contracts.catalog import Outcome, ReasonCode
from vectra_contracts.models.governance import ChannelRule, NormativeParams
from vectra_reference.release import Release

NORMATIVE = NormativeParams(
    vis_max_property_value=150_000_000, usury_cap_ea="0.2400", effective_from=date(2026, 1, 1), source_ref="x"
)


def make(**changes: object) -> PolicyEvaluationInput:
    values: dict[str, object] = {
        "policy_version_id": "pol-7",
        "score": "0.1200",
        "confidence": "0.9100",
        "property_value": 120_000_000,
        "proposed_rate_ea": "0.1500",
        "channel": "web",
        "cutoff": "0.3000",
        "low_confidence_threshold": "0.5000",
        "channel_rules": [],
        "normative": NORMATIVE,
    }
    values.update(changes)
    return PolicyEvaluationInput.model_validate(values, strict=False)


def test_us103_a_clean_case_is_favorable_with_its_reasons_in_table_order() -> None:
    result = evaluate(make())
    assert result.policy_version_id == "pol-7"
    assert result.outcome is Outcome.FAVORABLE
    assert result.reasons == [ReasonCode.SCORE_BAJO_CORTE, ReasonCode.VIS]


def test_a_score_over_the_cutoff_and_a_house_over_the_vis_limit_is_unfavorable() -> None:
    result = evaluate(make(score="0.7000", property_value=150_000_001))
    assert result.outcome is Outcome.DESFAVORABLE
    assert result.reasons == [ReasonCode.SCORE_SOBRE_CORTE, ReasonCode.NO_VIS]


def test_us207_rate_over_usury_and_missing_normative_give_review_with_both_reasons_not_fail_closed() -> None:
    # Con normativa vigente: la tasa sobre el tope fuerza la revision.
    over = evaluate(make(proposed_rate_ea="0.2401"))
    assert over.outcome is Outcome.REVISION_REQUERIDA
    assert over.reasons == [ReasonCode.TASA_SOBRE_USURA, ReasonCode.SCORE_BAJO_CORTE, ReasonCode.VIS]
    # Sin normativa vigente (BR-U7-06): sale un `PolicyResult` completo; la regla 2 no puede evaluarse y la 5 no clasifica.
    none = evaluate(make(normative=None, proposed_rate_ea="0.9900"))
    assert none.outcome is Outcome.REVISION_REQUERIDA
    assert none.reasons == [ReasonCode.PARAMETRO_NORMATIVO_NO_VIGENTE, ReasonCode.SCORE_BAJO_CORTE]


def test_all_the_forcing_reasons_accumulate_in_order_without_duplicates() -> None:
    result = evaluate(make(confidence="0.1000", proposed_rate_ea="0.3000", score="0.9000", property_value=1))
    assert result.outcome is Outcome.REVISION_REQUERIDA
    assert result.reasons == [
        ReasonCode.TASA_SOBRE_USURA,
        ReasonCode.BAJA_CONFIANZA,
        ReasonCode.SCORE_SOBRE_CORTE,
        ReasonCode.VIS,
    ]


def test_the_channel_cutoff_overrides_the_general_one_only_for_its_channel() -> None:
    rules = [ChannelRule(channel="web", cutoff="0.1000"), ChannelRule(channel="sucursal", cutoff=None)]
    assert evaluate(make(channel="web", channel_rules=rules)).outcome is Outcome.DESFAVORABLE  # 0.12 >= 0.10
    assert (
        evaluate(make(channel="sucursal", channel_rules=rules)).outcome is Outcome.FAVORABLE
    )  # sin corte propio: 0.30
    assert evaluate(make(channel="otro", channel_rules=rules)).outcome is Outcome.FAVORABLE
    assert effective_cutoff("web", "0.3000", rules) == "0.1000"
    assert effective_cutoff("sucursal", "0.3000", rules) == "0.3000"


def test_us106_an_rt4_case_from_u5_is_low_confidence_and_review(reference_release: Release) -> None:
    """Los 18 casos RT-4 de U5 caen bajo el umbral calibrado; la politica los manda a revision con `baja_confianza`."""
    threshold = reference_release.policy.low_confidence_threshold
    assert len(reference_release.rt4) == len(reference_release.rt4_confidence) == 18
    for case, confidence in zip(reference_release.rt4, reference_release.rt4_confidence, strict=True):
        assert case["expected"] == {
            "confidence": "below_low_confidence_threshold",
            "recommendation": "revision_requerida",
            "reason": "baja_confianza",
        }
        assert Decimal(confidence) < Decimal(threshold)
        result = evaluate(make(confidence=confidence, low_confidence_threshold=threshold))
        assert result.outcome is Outcome.REVISION_REQUERIDA, case["case_id"]
        assert ReasonCode.BAJA_CONFIANZA in result.reasons, case["case_id"]
        assert result.outcome.value == case["expected"]["recommendation"]
        assert ReasonCode.BAJA_CONFIANZA.value == case["expected"]["reason"]
