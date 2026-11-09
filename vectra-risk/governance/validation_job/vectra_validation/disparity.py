"""Disparidad inicial con la libreria real de U9 (`vectra_disparity`; BR-U4-07, BR-U9-01..05). Sin dobles."""

from collections.abc import Sequence
from decimal import Decimal

from vectra_contracts.models.monitoring import AttributeResult as AttributeResultModel
from vectra_contracts.models.monitoring import InitialDisparity
from vectra_disparity import (
    ATTRIBUTES,
    aggregate_lower_limit,
    counts_from_records,
    disparity_by_band,
    model_aggregate,
    to_dict,
)

FAVORABLE = "favorable"
UNFAVORABLE = "desfavorable"


def initial_disparity(
    monitoring: Sequence[dict[str, str]],
    default_probability: Sequence[float],
    cutoff: float,
    n_min: int,
    threshold_pp: str,
) -> InitialDisparity:
    """Puntua cada fila con el corte de la politica (`score < cutoff` es `favorable`, BR-U7-05) y mide la disparidad.

    `rule_met` es la regla R4 de congelamiento (limite inferior de la agregada del atributo disparador > umbral); se informa,
    no bloquea (BR-U4-07).
    """
    records = [
        {**labels, "outcome": FAVORABLE if p < cutoff else UNFAVORABLE}
        for labels, p in zip(monitoring, default_probability, strict=True)
    ]
    counts = counts_from_records(records)
    results = [disparity_by_band(counts, attribute, n_min) for attribute in ATTRIBUTES]
    top = model_aggregate(results)
    rule_met: bool | None = None
    if top is not None:
        lower = aggregate_lower_limit(counts, top[0], n_min)
        rule_met = lower is not None and lower > Decimal(threshold_pp) / 100
    return InitialDisparity.model_validate(
        {
            "attributes": [AttributeResultModel.model_validate(to_dict(r)) for r in results],
            "model_aggregate": None if top is None else str(top[1]),
            "trigger_attribute": None if top is None else top[0],
            "n_min": n_min,
            "threshold_pp": threshold_pp,
            "rule_met": rule_met,
        }
    )
