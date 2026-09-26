"""Core data models for the PayFlow payments service."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class PaymentStatus(str, Enum):
    CREATED = "CREATED"
    AUTHORIZED = "AUTHORIZED"
    CAPTURED = "CAPTURED"
    PARTIALLY_REFUNDED = "PARTIALLY_REFUNDED"
    REFUNDED = "REFUNDED"
    FAILED = "FAILED"


# PF-012: allowed state machine transitions
ALLOWED_TRANSITIONS: dict[PaymentStatus, set[PaymentStatus]] = {
    PaymentStatus.CREATED: {PaymentStatus.AUTHORIZED, PaymentStatus.FAILED},
    PaymentStatus.AUTHORIZED: {PaymentStatus.CAPTURED, PaymentStatus.FAILED},
    PaymentStatus.CAPTURED: {PaymentStatus.PARTIALLY_REFUNDED, PaymentStatus.REFUNDED},
    PaymentStatus.PARTIALLY_REFUNDED: {PaymentStatus.PARTIALLY_REFUNDED, PaymentStatus.REFUNDED},
    PaymentStatus.REFUNDED: set(),
    PaymentStatus.FAILED: set(),
}


def utc_now() -> str:
    """Return the current time as a UTC ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Payment:
    id: str
    merchant_id: str
    amount_minor: int  # integer minor units (paise / cents)
    currency: str
    card_last4: str
    status: PaymentStatus = PaymentStatus.CREATED
    created_at: str = field(default_factory=utc_now)
    captured_at: str | None = None
    refunded_minor: int = 0


class PaymentError(Exception):
    def __init__(self, code: str, message: str = ""):
        super().__init__(f"{code}: {message}" if message else code)
        self.code = code
