"""Politica de U7 (BR-U7-04 a 07; US-103, US-106, US-207): funcion pura, sin E/S ni reloj.

Las cinco reglas se evaluan todas y sus motivos se acumulan en el orden de la tabla de BR-U7-04. Un `normative` nulo no es un
fail-closed (BR-U7-06): la recomendacion sale con `revision_requerida`.
"""

from decimal import Decimal

from vectra_contracts.catalog import Outcome, ReasonCode
from vectra_contracts.models.base import COP, Decimal4, StrictModel, UnitDecimal4
from vectra_contracts.models.explanation import PolicyResult
from vectra_contracts.models.governance import ChannelRule, NormativeParams


class PolicyEvaluationInput(StrictModel):
    """Entrada interna de scoring (domain-entities §2): prediccion, `policy_inputs`, politica activa y normativa vigente."""

    policy_version_id: str
    score: UnitDecimal4
    confidence: UnitDecimal4
    property_value: COP
    proposed_rate_ea: Decimal4
    channel: str
    cutoff: UnitDecimal4
    low_confidence_threshold: UnitDecimal4
    channel_rules: list[ChannelRule]
    normative: NormativeParams | None


def effective_cutoff(channel: str, cutoff: str, channel_rules: list[ChannelRule]) -> str:
    """El `cutoff` de la regla del canal, si existe; si no, el general (BR-U7-04)."""
    for rule in channel_rules:
        if rule.channel == channel and rule.cutoff is not None:
            return rule.cutoff
    return cutoff


def evaluate(data: PolicyEvaluationInput) -> PolicyResult:
    """Evalua las cinco reglas de BR-U7-04 y combina: gana el resultado mas conservador (BR-U7-05)."""
    reasons: list[ReasonCode] = []
    forced_review = False
    normative = data.normative

    if normative is None:  # regla 1
        reasons.append(ReasonCode.PARAMETRO_NORMATIVO_NO_VIGENTE)
        forced_review = True
    elif Decimal(data.proposed_rate_ea) > Decimal(normative.usury_cap_ea):  # regla 2: igual no es «sobre»
        reasons.append(ReasonCode.TASA_SOBRE_USURA)
        forced_review = True

    if Decimal(data.confidence) < Decimal(data.low_confidence_threshold):  # regla 3
        reasons.append(ReasonCode.BAJA_CONFIANZA)
        forced_review = True

    cutoff = effective_cutoff(data.channel, data.cutoff, data.channel_rules)
    if Decimal(data.score) < Decimal(cutoff):  # regla 4
        base = Outcome.FAVORABLE
        reasons.append(ReasonCode.SCORE_BAJO_CORTE)
    else:
        base = Outcome.DESFAVORABLE
        reasons.append(ReasonCode.SCORE_SOBRE_CORTE)

    if normative is not None:  # regla 5, informativa; sin normativa no se clasifica
        reasons.append(
            ReasonCode.VIS if data.property_value <= normative.vis_max_property_value else ReasonCode.NO_VIS
        )

    outcome = Outcome.REVISION_REQUERIDA if forced_review else base
    return PolicyResult(policy_version_id=data.policy_version_id, outcome=outcome, reasons=reasons)
