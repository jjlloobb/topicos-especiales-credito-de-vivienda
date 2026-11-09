"""Calibracion del umbral de baja confianza contra RT-4 (BR-U5-13) y politica de referencia.

El umbral es un cuantil de la confianza en `train` (bajado a Decimal4); despues se comprueba que los 18 casos
RT-4 quedan por debajo y que al menos el 95 % de `test` queda sobre el. «Por debajo» es `confidence < umbral`
(la regla del predictor); «sobre» es `confidence >= umbral`. Si no se cumple, la entrega falla.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import ROUND_FLOOR, Decimal
from typing import Any

import numpy as np
from vectra_contracts.models.governance import PolicyDraft

_FOUR = Decimal("0.0001")


class CalibrationError(Exception):
    """BR-U5-13 no se cumple: la entrega falla."""


@dataclass(frozen=True)
class Calibration:
    threshold: str
    rt4_max: str
    test_above: float
    train_quantile: float


def calibrate_threshold(
    train: Sequence[str],
    test: Sequence[str],
    rt4: Sequence[str],
    *,
    quantile: float,
    min_test_above: float,
) -> Calibration:
    """Umbral = cuantil `quantile` de `train`; exige RT-4 < umbral y `test >= umbral` en >= `min_test_above`."""
    q = Decimal(repr(float(np.quantile([float(c) for c in train], quantile)))).quantize(
        _FOUR, rounding=ROUND_FLOOR
    )
    threshold = str(q)
    rt4_max = max(Decimal(c) for c in rt4)
    above = sum(Decimal(c) >= q for c in test) / len(test)
    if not rt4_max < q:
        raise CalibrationError(f"rt4_not_below_threshold: max RT-4 {rt4_max} >= umbral {threshold}")
    if above < min_test_above:
        raise CalibrationError(
            f"test_below_minimum: {above:.4f} < {min_test_above} sobre el umbral {threshold}"
        )
    return Calibration(threshold, str(rt4_max), above, quantile)


def build_policy(config: Mapping[str, Any], threshold: str) -> PolicyDraft:
    """`reference-policy.json`: `PolicyDraft` de U0 con el umbral calibrado y la normativa sintetica."""
    ref = config["reference_policy"]
    return PolicyDraft.model_validate_json(
        json.dumps(
            {
                "cutoff": ref["cutoff"],
                "low_confidence_threshold": threshold,
                "channel_rules": [],
                "normative": ref["normative"],
            },
            sort_keys=True,
        )
    )
