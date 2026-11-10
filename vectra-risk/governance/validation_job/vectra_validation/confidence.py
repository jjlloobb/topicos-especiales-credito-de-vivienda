"""`confidence` de una entrada contra `domain_envelope.json` (BR-U5-12, BR-U7-04 regla 3). Solo numpy y la biblioteca estandar.

Es la misma funcion que U5 publica como `vectra_reference.envelope.confidence` (la comparten U5 y U6 y la imagen del Job no lleva
`vectra_reference`): una prueba (`test_confidence_is_the_one_u5_publishes`) las compara sobre las mismas entradas.

- `c_rango = 1 - (features numericas fuera de [p1, p99]) / (features numericas)`;
- `c_dist = 1 - F(d_M(x))`, con `F` la distribucion empirica de las distancias de Mahalanobis del entrenamiento;
- `confidence = 0` si hay una categoria no vista; si no, `min(c_rango, c_dist)` cuantizada a Decimal4.
"""

import json
import math
from collections.abc import Mapping, Sequence
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

import numpy as np

from vectra_validation.errors import ValidationJobError

_FOUR = Decimal("0.0001")


def parse_envelope(raw: bytes) -> dict[str, Any]:
    """`domain_envelope.json` del paquete; `envelope_unreadable` si no trae lo que `confidence` necesita."""
    try:
        envelope = json.loads(raw)
        for key in ("numeric", "categories", "mean", "covariance", "distance_quantiles"):
            envelope[key]
        for item in envelope["numeric"]:
            item["name"], item["p1"], item["p99"]
    except (ValueError, KeyError, TypeError) as error:
        raise ValidationJobError("envelope_unreadable") from error
    return dict(envelope)


def distances(mean: Sequence[float], covariance: Sequence[Sequence[float]], points: np.ndarray) -> np.ndarray:
    """Distancia de Mahalanobis de cada fila de `points` (n, k) al centro `mean`."""
    precision = np.linalg.inv(np.asarray(covariance, dtype=float))
    delta = np.atleast_2d(np.asarray(points, dtype=float)) - np.asarray(mean, dtype=float)
    squared = np.einsum("ij,jk,ik->i", delta, precision, delta)
    result: np.ndarray = np.sqrt(np.maximum(squared, 0.0))
    return result


def confidence_raw(envelope: Mapping[str, Any], values: Mapping[str, Any]) -> float:
    """`confidence` sin cuantizar. Falta una feature -> `feature_missing:<id>`."""
    for name, seen in envelope["categories"].items():
        if name not in values:
            raise ValidationJobError(f"feature_missing:{name}")
        if str(values[name]) not in seen:
            return 0.0
    numeric = envelope["numeric"]
    for item in numeric:
        if item["name"] not in values:
            raise ValidationJobError(f"feature_missing:{item['name']}")
    x = np.array([float(values[item["name"]]) for item in numeric], dtype=float)
    low = np.array([item["p1"] for item in numeric], dtype=float)
    high = np.array([item["p99"] for item in numeric], dtype=float)
    c_range = 1.0 - int(np.count_nonzero(~((x >= low) & (x <= high)))) / len(numeric)
    d = float(distances(envelope["mean"], envelope["covariance"], x)[0])
    if not math.isfinite(d):
        return 0.0
    grid = envelope["distance_quantiles"]
    probabilities = np.linspace(0.0, 1.0, len(grid))
    c_dist = 1.0 - float(np.interp(d, grid, probabilities, left=0.0, right=1.0))
    return float(min(c_range, c_dist))


def confidence(envelope: Mapping[str, Any], values: Mapping[str, Any]) -> str:
    """`confidence` cuantizada a Decimal4 (cadena `0.xxxx`, redondeo half-up)."""
    return str(Decimal(repr(confidence_raw(envelope, values))).quantize(_FOUR, rounding=ROUND_HALF_UP))
