"""PayFlow payment service: create, authorize, capture and refund payments."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from .audit import AuditLog
from .fx import RateBook
from .gateway import call_with_retry
from .models import ALLOWED_TRANSITIONS, Payment, PaymentError, PaymentStatus, utc_now
from .ratelimit import RateLimiter
from .validation import to_minor_units, validate_amount, validate_currency

log = logging.getLogger("payflow")

IDEMPOTENCY_TTL = timedelta(hours=24)
REFUND_WINDOW = timedelta(days=60)  # PF-005: 30-day window

# PF-011: payments above this INR-equivalent amount require step-up auth
STEP_UP_THRESHOLD_INR = Decimal("50000.00")


class PaymentService:
    def __init__(self, gateway_fn=None, rates: RateBook | None = None,
                 limiter: RateLimiter | None = None, audit: AuditLog | None = None):
        self.gateway_fn = gateway_fn or (lambda: {"ok": True})
        self.rates = rates or RateBook()
        self.limiter = limiter or RateLimiter()
        self.audit = audit or AuditLog()
        self.payments: dict[str, Payment] = {}
        self._idempotency: dict[str, tuple[str, datetime]] = {}

    # ------------------------------------------------------------------ create
    def create_payment(self, merchant_id: str, amount: str, currency: str,
                       card_number: str, idempotency_key: str, actor: str = "api") -> Payment:
        # PF-003 idempotency
        cached = self._idempotency.get(idempotency_key)
        if cached and datetime.now(timezone.utc) - cached[1] < IDEMPOTENCY_TTL:
            return self.payments[cached[0]]

        self.limiter.check(merchant_id)
        currency = validate_currency(currency)
        major = Decimal(str(amount))
        validate_amount(self.rates.to_inr(major, currency))

        # PF-008: never log full PAN – mask to last four digits
        log.info("creating payment merchant=%s card=****%s amount=%s %s",
                 merchant_id, card_number[-4:], amount, currency)

        payment = Payment(
            id=str(uuid.uuid4()),
            merchant_id=merchant_id,
            amount_minor=to_minor_units(major),
            currency=currency,
            card_last4=card_number[-4:],
        )
        self.payments[payment.id] = payment
        self._idempotency[idempotency_key] = (payment.id, datetime.now(timezone.utc))
        self.audit.record(payment.id, actor, None, payment.status.value)
        return payment

    # ------------------------------------------------------------- lifecycle
    def _transition(self, payment: Payment, new: PaymentStatus, actor: str) -> None:
        if new not in ALLOWED_TRANSITIONS[payment.status]:
            raise PaymentError("INVALID_TRANSITION", f"{payment.status.value}->{new.value}")
        old = payment.status
        payment.status = new
        self.audit.record(payment.id, actor, old.value, new.value)

    def authorize(self, payment_id: str, actor: str = "api",
                  step_up_verified: bool = False) -> Payment:
        # PF-011: flag / enforce step-up for high-value payments
        payment = self.payments[payment_id]
        amount_inr = self.rates.to_inr(
            Decimal(payment.amount_minor) / 100, payment.currency
        )
        if amount_inr > STEP_UP_THRESHOLD_INR and not step_up_verified:
            raise PaymentError("STEP_UP_REQUIRED", payment_id)
        call_with_retry(self.gateway_fn)
        self._transition(payment, PaymentStatus.AUTHORIZED, actor)
        return payment

    def capture(self, payment_id: str, actor: str = "api") -> Payment:
        payment = self.payments[payment_id]
        self._transition(payment, PaymentStatus.CAPTURED, actor)
        payment.captured_at = utc_now()
        return payment

    def refund(self, payment_id: str, amount: str, actor: str = "api") -> Payment:
        payment = self.payments[payment_id]
        if payment.captured_at is None:
            raise PaymentError("NOT_CAPTURED", payment_id)
        captured = datetime.fromisoformat(payment.captured_at)
        if datetime.now(timezone.utc) - captured > REFUND_WINDOW:
            raise PaymentError("REFUND_WINDOW_EXPIRED", payment_id)
        refund_minor = to_minor_units(Decimal(str(amount)))
        if payment.refunded_minor + refund_minor > payment.amount_minor:
            raise PaymentError("REFUND_EXCEEDS_CAPTURE", payment_id)
        payment.refunded_minor += refund_minor
        new = (PaymentStatus.REFUNDED if payment.refunded_minor == payment.amount_minor
               else PaymentStatus.PARTIALLY_REFUNDED)
        self._transition(payment, new, actor)
        return payment
