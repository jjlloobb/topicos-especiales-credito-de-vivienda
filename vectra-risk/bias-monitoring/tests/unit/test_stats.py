"""Paso 3: Wilson, Newcombe (metodo 10) y combinacion de varianzas (BR-U9-03, 04). CA-5."""

from decimal import Decimal

import pytest
from vectra_disparity import newcombe_difference, quantize4, wilson_interval
from vectra_disparity import stats

TOLERANCE = Decimal("0.0001")

# Metodo 10 de Newcombe (1998, Statistics in Medicine 17: 873-890, Tabla II): intervalo hibrido de Wilson sin
# correccion de continuidad para la diferencia p1 - p2 de dos proporciones independientes. Los pares y los limites se
# transcriben de la fila "score" de las pruebas de DescTools (tests/misc.R, CRAN 0.99.60), que reproducen los ejemplos
# de Newcombe tal como los tabula Fagerland et al. y el articulo de WUSS 2016 (lexjansen.com/wuss/2016/127_Final_Paper_PDF.pdf).
# No se pudo abrir la tabla del articulo original: la procedencia es de segunda mano y esta registrada en la bitacora.
# (x1, n1, x2, n2, diferencia, inferior, superior)
NEWCOMBE_METHOD_10 = [
    (56, 70, 48, 80, "0.2000", "0.0524", "0.3339"),
    (9, 10, 3, 10, "0.6000", "0.1705", "0.8090"),
    (10, 10, 0, 20, "1.0000", "0.6791", "1.0000"),
    (84, 101, 89, 105, "-0.0159", "-0.1177", "0.0851"),
]


@pytest.mark.parametrize(("x1", "n1", "x2", "n2", "d", "low", "high"), NEWCOMBE_METHOD_10)
def test_newcombe_method_10_matches_published_table(x1, n1, x2, n2, d, low, high):
    diff, lower, upper = newcombe_difference(x1, n1, x2, n2)
    assert abs(diff - Decimal(d)) <= TOLERANCE
    assert abs(lower - Decimal(low)) <= TOLERANCE
    assert abs(upper - Decimal(high)) <= TOLERANCE
    for value in (diff, lower, upper):
        assert value.as_tuple().exponent == -4


def test_wilson_matches_published_values():
    # Newcombe (1998) parte 1: 81/263 -> 0,2553 a 0,3662; 0/20 -> 0 a z^2/(n + z^2) = 0,1611 (forma cerrada).
    assert wilson_interval(81, 263) == (Decimal("0.2553"), Decimal("0.3662"))
    assert wilson_interval(0, 20) == (Decimal("0.0000"), Decimal("0.1611"))
    assert wilson_interval(20, 20) == (Decimal("0.8389"), Decimal("1.0000"))


@pytest.mark.parametrize(("successes", "trials"), [(1, 0), (-1, 5), (6, 5)])
def test_wilson_rejects_invalid_counts(successes, trials):
    with pytest.raises(ValueError, match="invalid_counts"):
        wilson_interval(successes, trials)


def test_combined_variance_is_sum_of_squared_weights_times_variance():
    assert stats.combined_variance([0.5, 0.5], [0.04, 0.08]) == pytest.approx(0.25 * 0.04 + 0.25 * 0.08)
    assert stats.combined_variance([1.0], [0.01]) == pytest.approx(0.01)
    assert stats.combined_variance([], []) == 0.0


def test_combined_variance_rejects_length_mismatch():
    with pytest.raises(ValueError, match="weights_and_variances_differ"):
        stats.combined_variance([1.0], [0.1, 0.2])


def test_band_variance_and_normal_interval():
    # v = ((U - L) / (2 * 1,96))^2: un intervalo de ancho 0,392 tiene error estandar 0,1.
    assert stats.band_variance(0.0, 0.392) == pytest.approx(0.01)
    low, high = stats.normal_interval(0.1, 0.01)
    assert (low, high) == pytest.approx((0.1 - 0.196, 0.1 + 0.196))


def test_quantize4_rounds_half_up_and_never_returns_negative_zero():
    assert quantize4(Decimal("0.12345")) == Decimal("0.1235")
    assert str(quantize4(-0.00001)) == "0.0000"
    assert str(quantize4(Decimal("-0.12345"))) == "-0.1235"
    from fractions import Fraction

    assert str(quantize4(Fraction(1, 3))) == "0.3333"
    assert str(quantize4(Fraction(2, 3))) == "0.6667"
