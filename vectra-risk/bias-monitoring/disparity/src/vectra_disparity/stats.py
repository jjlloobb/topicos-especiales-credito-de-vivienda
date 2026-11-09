"""Estadistica pura de la libreria (BR-U9-03, BR-U9-04): Wilson, Newcombe (metodo 10) y combinacion de varianzas.

Solo `math` y `decimal`. Las funciones `*_float` devuelven `float` sin redondear y las usa `disparity` para encadenar el
calculo; las publicas devuelven `Decimal` cuantizado a 4 decimales (`Decimal4` de U0 es una cadena con esa forma).
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from decimal import ROUND_HALF_UP, Context, Decimal
from fractions import Fraction

Z95 = 1.96  # BR-U9-03/04: el 95 % se fija con 1,96, no con el cuantil exacto.
_QUANTUM = Decimal("0.0001")
_CONTEXT = Context(prec=60)


def quantize4(value: Fraction | float | Decimal) -> Decimal:
    """`Decimal` con exactamente 4 decimales (mitad hacia arriba), sin cero negativo."""
    if isinstance(value, Fraction):
        exact = _CONTEXT.divide(Decimal(value.numerator), Decimal(value.denominator))
    else:
        exact = Decimal(value)
    quantized = exact.quantize(_QUANTUM, rounding=ROUND_HALF_UP, context=_CONTEXT)
    return abs(quantized) if quantized == 0 else quantized


def _check_counts(successes: int, trials: int) -> None:
    if trials <= 0 or successes < 0 or successes > trials:
        raise ValueError(f"invalid_counts:{successes}/{trials}")


def wilson_float(successes: int, trials: int, z: float = Z95) -> tuple[float, float]:
    """Intervalo de Wilson (sin correccion de continuidad) de una proporcion."""
    _check_counts(successes, trials)
    p = successes / trials
    z2 = z * z
    denominator = 1.0 + z2 / trials
    center = (p + z2 / (2.0 * trials)) / denominator
    half = z * math.sqrt(p * (1.0 - p) / trials + z2 / (4.0 * trials * trials)) / denominator
    return max(0.0, center - half), min(1.0, center + half)


def wilson_interval(successes: int, trials: int) -> tuple[Decimal, Decimal]:
    """Intervalo de Wilson del 95 %, en `Decimal4`."""
    lower, upper = wilson_float(successes, trials)
    return quantize4(lower), quantize4(upper)


def newcombe_float(x1: int, n1: int, x2: int, n2: int, z: float = Z95) -> tuple[float, float, float]:
    """Diferencia `p1 - p2` e intervalo hibrido de Wilson de Newcombe (1998), metodo 10: `(d, inferior, superior)`."""
    p1, p2 = x1 / n1, x2 / n2
    l1, u1 = wilson_float(x1, n1, z)
    l2, u2 = wilson_float(x2, n2, z)
    d = p1 - p2
    lower = d - math.sqrt((p1 - l1) ** 2 + (u2 - p2) ** 2)
    upper = d + math.sqrt((u1 - p1) ** 2 + (p2 - l2) ** 2)
    return d, lower, upper


def newcombe_difference(x1: int, n1: int, x2: int, n2: int) -> tuple[Decimal, Decimal, Decimal]:
    """Metodo 10 de Newcombe en `Decimal4`: `(diferencia, inferior, superior)` de `x1/n1 - x2/n2`."""
    d, lower, upper = newcombe_float(x1, n1, x2, n2)
    return quantize4(d), quantize4(lower), quantize4(upper)


def band_variance(lower: float, upper: float, z: float = Z95) -> float:
    """`v_b = ((U_b - L_b) / (2 * 1,96))^2` a partir del intervalo de Newcombe de una banda (BR-U9-04)."""
    return ((upper - lower) / (2.0 * z)) ** 2


def combined_variance(weights: Sequence[float], variances: Sequence[float]) -> float:
    """`Var(D_a) = sum_b w_b^2 * v_b` (BR-U9-04). Se devuelve como `float`: una varianza de ~1e-4 perderia toda su
    precision en `Decimal4`; lo que se publica es el intervalo que sale de ella."""
    if len(weights) != len(variances):
        raise ValueError("weights_and_variances_differ")
    return math.fsum(w * w * v for w, v in zip(weights, variances, strict=True))


def normal_interval(center: float, variance: float, z: float = Z95) -> tuple[float, float]:
    """`center +- z * sqrt(variance)`."""
    half = z * math.sqrt(variance)
    return center - half, center + half
