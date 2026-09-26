"""Input validation for payment requests."""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from .models import PaymentError

SUPPORTED_CURRENCIES = {"INR", "USD", "EUR"}

# Maximum single-transaction amount in INR-equivalent major units.
# PF-002: 1,00,000 INR = 100 000 INR
MAX_TXN_AMOUNT_INR = Decimal("100000.00")


def validate_currency(currency: str) -> str:
    code = (currency or "").upper()
    if code not in SUPPORTED_CURRENCIES:
        raise PaymentError("UNSUPPORTED_CURRENCY", code)
    return code


def to_minor_units(amount: str | Decimal) -> int:
    """Convert a decimal major-unit amount to integer minor units.

    Floats are rejected so we never introduce binary rounding errors.
    """
    if isinstance(amount, float):
        raise PaymentError("INVALID_AMOUNT", "floats are not accepted")
    value = Decimal(str(amount)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return int(value * 100)


def validate_amount(amount_inr_equivalent: Decimal) -> None:
    if amount_inr_equivalent <= 0:
        raise PaymentError("INVALID_AMOUNT", "amount must be positive")
    if amount_inr_equivalent > MAX_TXN_AMOUNT_INR:
        raise PaymentError("AMOUNT_LIMIT_EXCEEDED", str(amount_inr_equivalent))
