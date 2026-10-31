"""BR-U0-10..14."""

from decimal import Decimal

import pytest

from vectra_contracts.finance import installment, installment_to_income, loan_to_value, monthly_rate, quantize4, to_decimal4_str


def test_br_u0_10_monthly_rate():
    assert abs(monthly_rate(Decimal("0.12")) - Decimal("0.00948879293458")) < Decimal("1e-13")


def test_br_u0_11_installment_is_integer_pesos():
    assert isinstance(installment(1_000_000, Decimal("0.10"), 12), int)


def test_br_u0_12_income_zero_invalid():
    with pytest.raises(ValueError, match="income_zero"):
        installment_to_income(1, 0, 0)
    assert installment_to_income(1, 2, 1) == Decimal("0.3333")


def test_br_u0_13_ltv():
    assert loan_to_value(2, 3) == Decimal("0.6667")


def test_br_u0_14_quantize_idempotent():
    assert quantize4(quantize4(Decimal("0.123456"))) == quantize4(Decimal("0.123456"))
    assert to_decimal4_str(Decimal("0.5")) == "0.5000"
