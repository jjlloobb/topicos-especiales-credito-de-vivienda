"""Funcion confidence compartida con U6 (BR-U5-12). Solo numpy y la biblioteca estandar (NFR-U5-32).

Para una entrada `x` y la envolvente de `domain_envelope.json`:
- `c_rango = 1 - (features numericas fuera de [p1, p99]) / (features numericas)`;
- `c_dist = 1 - F(d_M(x))`, con `F` la distribucion empirica de las distancias de Mahalanobis del entrenamiento;
- `confidence = 0` si hay una categoria no vista; si no, `min(c_rango, c_dist)` cuantizada a Decimal4 (BR-U0-07).
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

import numpy as np

_FOUR = Decimal("0.0001")


def distances(mean: Sequence[float], covariance: Sequence[Sequence[float]], points: np.ndarray) -> np.ndarray:
    """Distancia de Mahalanobis de cada fila de `points` (n, k) al centro `mean`."""
    precision = np.linalg.inv(np.asarray(covariance, dtype=float))
    delta = np.atleast_2d(np.asarray(points, dtype=float)) - np.asarray(mean, dtype=float)
    squared = np.einsum("ij,jk,ik->i", delta, precision, delta)
    return np.sqrt(np.maximum(squared, 0.0))


def _numeric(envelope: Mapping[str, Any], values: Mapping[str, Any]) -> tuple[np.ndarray, float]:
    """Vector numerico de la entrada y `c_rango`. Falta una feature -> `ValueError("feature_missing:<id>")`."""
    numeric = envelope["numeric"]
    for item in numeric:
        if item["name"] not in values:
            raise ValueError(f"feature_missing:{item['name']}")
    x = np.array([float(values[item["name"]]) for item in numeric], dtype=float)
    low = np.array([item["p1"] for item in numeric], dtype=float)
    high = np.array([item["p99"] for item in numeric], dtype=float)
    outside = int(np.count_nonzero(~((x >= low) & (x <= high))))
    return x, 1.0 - outside / len(numeric)


def range_confidence(envelope: Mapping[str, Any], values: Mapping[str, Any]) -> float:
    """`c_rango` = 1 - (features numericas fuera de [p1, p99]) / (features numericas)."""
    return _numeric(envelope, values)[1]


def confidence_raw(envelope: Mapping[str, Any], values: Mapping[str, Any]) -> float:
    """`confidence` sin cuantizar, en [0, 1]. Falta una feature -> `ValueError("feature_missing:<id>")`."""
    for name, seen in envelope["categories"].items():
        if name not in values:
            raise ValueError(f"feature_missing:{name}")
        if str(values[name]) not in seen:
            return 0.0
    x, c_range = _numeric(envelope, values)
    d = float(distances(envelope["mean"], envelope["covariance"], x)[0])
    if not math.isfinite(d):
        return 0.0
    grid = envelope["distance_quantiles"]
    probabilities = np.linspace(0.0, 1.0, len(grid))
    c_dist = 1.0 - float(np.interp(d, grid, probabilities, left=0.0, right=1.0))
    return float(min(c_range, c_dist))


def confidence(envelope: Mapping[str, Any], values: Mapping[str, Any]) -> str:
    """`confidence` cuantizada a Decimal4 (cadena `0.xxxx`, redondeo half-up como `quantize4` de U0)."""
    return str(Decimal(repr(confidence_raw(envelope, values))).quantize(_FOUR, rounding=ROUND_HALF_UP))
