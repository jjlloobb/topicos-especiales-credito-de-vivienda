"""Calculos financieros con `Decimal` (BR-U0-10..14, P-U0-10). Sin flotantes."""

from decimal import ROUND_HALF_UP, Decimal, localcontext

from vectra_contracts.decimal_ctx import VECTRA_DECIMAL_CTX

_FOUR = Decimal("0.0001")


def quantize4(value: Decimal) -> Decimal:
    """BR-U0-14: idempotente."""
    with localcontext(VECTRA_DECIMAL_CTX) as ctx:
        return ctx.quantize(value, _FOUR)


def to_decimal4_str(value: Decimal) -> str:
    return str(quantize4(value))


def monthly_rate(rate_ea: Decimal) -> Decimal:
    """BR-U0-10: `i_m = (1 + tasa_ea)^(1/12) - 1`."""
    with localcontext(VECTRA_DECIMAL_CTX) as ctx:
        return ctx.subtract(
            ctx.power(ctx.add(Decimal(1), rate_ea), ctx.divide(Decimal(1), Decimal(12))), Decimal(1)
        )


def installment(amount: int, rate_ea: Decimal, term_months: int) -> int:
    """BR-U0-11: redondeada al peso con `ROUND_HALF_UP`."""
    with localcontext(VECTRA_DECIMAL_CTX) as ctx:
        i_m = monthly_rate(rate_ea)
        factor = ctx.power(ctx.add(Decimal(1), i_m), Decimal(-term_months))
        value = ctx.divide(ctx.multiply(Decimal(amount), i_m), ctx.subtract(Decimal(1), factor))
        return int(value.quantize(Decimal(1), rounding=ROUND_HALF_UP, context=ctx))


def installment_to_income(installment_cop: int, monthly_income: int, other_income: int) -> Decimal:
    """BR-U0-12: un ingreso total de 0 hace la solicitud invalida."""
    total = monthly_income + other_income
    if total == 0:
        raise ValueError("income_zero")
    with localcontext(VECTRA_DECIMAL_CTX) as ctx:
        return quantize4(ctx.divide(Decimal(installment_cop), Decimal(total)))


def loan_to_value(requested_amount: int, property_value: int) -> Decimal:
    """BR-U0-13."""
    with localcontext(VECTRA_DECIMAL_CTX) as ctx:
        return quantize4(ctx.divide(Decimal(requested_amount), Decimal(property_value)))
