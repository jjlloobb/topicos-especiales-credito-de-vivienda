"""Contexto decimal propio (P-U0-10): nunca lee ni modifica el contexto global."""

from decimal import ROUND_HALF_UP, Context, DivisionByZero, InvalidOperation
from typing import Final

VECTRA_DECIMAL_CTX: Final = Context(prec=28, rounding=ROUND_HALF_UP, traps=[InvalidOperation, DivisionByZero])
