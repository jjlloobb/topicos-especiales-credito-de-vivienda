"""Regla de congelamiento (BR-U9-11, regla R4 sobre todos los atributos; PBT-U9-04). Pura: sin E/S.

Una version se congela si y solo si es de la poblacion `modelo` y **algun** atributo con agregada tiene un limite R4 (la
agregada menos `Z_FREEZE` desviaciones, `vectra_disparity.aggregate_lower_limit`) mayor que el umbral (F-03 opcion (b),
decision del usuario del 2026-11-10). El atributo disparador (BR-U9-05) es el de la mayor agregada y solo se muestra en el
paquete: ya no decide. Las cifras estan en la escala de la libreria (proporciones): el umbral en pp se divide entre 100.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal

from vectra_disparity import ATTRIBUTES, CountTable, aggregate_lower_limit

MODEL = "modelo"
HUMAN = "humana"


@dataclass(frozen=True)
class AttributeLimit:
    attribute: str
    limit: Decimal


@dataclass(frozen=True)
class FreezeDecision:
    freeze: bool
    rule_met: bool
    reason: str
    met: tuple[AttributeLimit, ...]


def attribute_limits(counts: Mapping[str, CountTable], n_min: int) -> dict[str, Decimal | None]:
    """El limite R4 de **cada** atributo (`None` si su agregada es «muestra insuficiente»), con la libreria y `Z_FREEZE`."""
    return {a: aggregate_lower_limit(counts, a, n_min) for a in ATTRIBUTES}


def decide(population: str, threshold_pp: Decimal, limits: Mapping[str, Decimal | None]) -> FreezeDecision:
    """`FreezeDecision` (domain-entities §2.6). `limits` son los limites R4 por atributo ya calculados con la libreria."""
    threshold = Decimal(threshold_pp) / 100
    present = {a: v for a, v in limits.items() if v is not None}
    if not present:
        return FreezeDecision(False, False, "muestra_insuficiente", ())
    met = tuple(
        AttributeLimit(a, v)
        for a, v in sorted(present.items(), key=lambda kv: (-kv[1], kv[0]))
        if v > threshold
    )
    top = max(present.values())
    if met:
        reason = "supera_umbral"
    elif top <= 0:
        reason = "intervalo_incluye_cero"
    else:
        reason = "bajo_umbral"
    return FreezeDecision(population == MODEL and bool(met), bool(met), reason, met)
