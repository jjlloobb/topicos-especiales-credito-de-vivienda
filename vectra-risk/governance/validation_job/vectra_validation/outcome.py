"""`outcome` de la recomendacion (BR-U7-04 y BR-U7-05) con la politica activa que el lanzador pasa al Job.

`revision_requerida` si `normative` es nulo (ninguna vigencia cubre `evaluated_on`), si la tasa supera la usura (igual no es
sobre) o si `confidence < low_confidence_threshold`; si no, `favorable` cuando `score < cutoff_efectivo` y `desfavorable` en otro
caso. `cutoff_efectivo` es el de la regla del canal de la solicitud si existe, y si no el general. BR-U9-01: `revision_requerida`
cuenta como NO favorable al medir la disparidad.
"""

from datetime import date
from decimal import Decimal
from typing import Final

from vectra_contracts.models.governance import NormativeParams, PolicyDraft

FAVORABLE: Final = "favorable"
UNFAVORABLE: Final = "desfavorable"
REVIEW: Final = "revision_requerida"


def normative_at(policy: PolicyDraft, on: date) -> NormativeParams | None:
    return next(
        (n for n in policy.normative if n.effective_from <= on and (n.effective_to is None or on <= n.effective_to)),
        None,
    )


def effective_cutoff(policy: PolicyDraft, channel: str) -> Decimal:
    rule = next((r for r in policy.channel_rules if r.channel == channel and r.cutoff is not None), None)
    return Decimal(policy.cutoff if rule is None or rule.cutoff is None else rule.cutoff)


def outcome_of(
    probability: float, confidence: str, proposed_rate_ea: str, channel: str, policy: PolicyDraft, evaluated_on: date
) -> str:
    normative = normative_at(policy, evaluated_on)
    if normative is None:
        return REVIEW
    if Decimal(proposed_rate_ea) > Decimal(normative.usury_cap_ea):
        return REVIEW
    if Decimal(confidence) < Decimal(policy.low_confidence_threshold):
        return REVIEW
    return FAVORABLE if probability < float(effective_cutoff(policy, channel)) else UNFAVORABLE
