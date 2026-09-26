"""PayFlow payment service tests (PF-002 through PF-013)."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from payflow.fx import RateBook
from payflow.gateway import GatewayError, GatewayTimeout, call_with_retry
from payflow.models import PaymentError, PaymentStatus
from payflow.ratelimit import RateLimiter
from payflow.service import PaymentService

CARD = "4111111111111111"


@pytest.fixture
def svc():
    return PaymentService()


# ---------------------------------------------------------------------------
# existing tests (must keep passing)
# ---------------------------------------------------------------------------

def test_rejects_unsupported_currency(svc):
    with pytest.raises(PaymentError) as e:
        svc.create_payment("m1", "10.00", "GBP", CARD, "k1")
    assert e.value.code == "UNSUPPORTED_CURRENCY"


def test_accepts_supported_currency(svc):
    p = svc.create_payment("m1", "10.00", "inr", CARD, "k1")
    assert p.currency == "INR"


def test_rejects_non_positive_amount(svc):
    with pytest.raises(PaymentError) as e:
        svc.create_payment("m1", "0", "INR", CARD, "k1")
    assert e.value.code == "INVALID_AMOUNT"


# PF-002 ─ fixed: 150 000 INR MUST be rejected (old test had wrong expectation)
def test_pf002_rejects_amount_above_limit(svc):
    """PF-002: amount > 1,00,000 INR must be rejected with AMOUNT_LIMIT_EXCEEDED."""
    with pytest.raises(PaymentError) as e:
        svc.create_payment("m1", "150000.00", "INR", CARD, "k-big")
    assert e.value.code == "AMOUNT_LIMIT_EXCEEDED"


def test_pf002_accepts_amount_at_limit(svc):
    """PF-002: amount exactly at 1,00,000 INR must be accepted."""
    p = svc.create_payment("m1", "100000.00", "INR", CARD, "k-limit")
    assert p.amount_minor == 10_000_000


# PF-004 ─ float amounts must be rejected
def test_pf004_rejects_float_amount():
    """PF-004: float arguments to to_minor_units must raise INVALID_AMOUNT."""
    from payflow.validation import to_minor_units
    with pytest.raises(PaymentError) as e:
        to_minor_units(1234.56)
    assert e.value.code == "INVALID_AMOUNT"


def test_idempotent_create_returns_same_payment(svc):
    a = svc.create_payment("m1", "10.00", "INR", CARD, "same-key")
    b = svc.create_payment("m1", "10.00", "INR", CARD, "same-key")
    assert a.id == b.id
    assert len(svc.payments) == 1


def test_refund_cannot_exceed_capture(svc):
    p = svc.create_payment("m1", "100.00", "INR", CARD, "k2")
    svc.authorize(p.id)
    svc.capture(p.id)
    svc.refund(p.id, "60.00")
    with pytest.raises(PaymentError) as e:
        svc.refund(p.id, "50.00")
    assert e.value.code == "REFUND_EXCEEDS_CAPTURE"


def test_state_changes_are_audited(svc):
    p = svc.create_payment("m1", "100.00", "INR", CARD, "k3", actor="alice")
    svc.authorize(p.id, actor="alice")
    svc.capture(p.id, actor="bob")
    recs = svc.audit.for_payment(p.id)
    assert [(r.old_state, r.new_state) for r in recs] == [
        (None, "CREATED"), ("CREATED", "AUTHORIZED"), ("AUTHORIZED", "CAPTURED")]
    assert recs[-1].actor == "bob"


def test_invalid_transition_rejected(svc):
    p = svc.create_payment("m1", "100.00", "INR", CARD, "k4")
    with pytest.raises(PaymentError) as e:
        svc.capture(p.id)  # CREATED -> CAPTURED is not allowed
    assert e.value.code == "INVALID_TRANSITION"


def test_rate_limit_per_merchant():
    t = [0.0]
    svc = PaymentService(limiter=RateLimiter(clock=lambda: t[0]))
    for i in range(20):
        svc.create_payment("m1", "1.00", "INR", CARD, f"rl-{i}")
    with pytest.raises(PaymentError) as e:
        svc.create_payment("m1", "1.00", "INR", CARD, "rl-21")
    assert e.value.code == "RATE_LIMITED"
    svc.create_payment("m2", "1.00", "INR", CARD, "other-merchant")  # separate bucket


def test_timestamps_are_utc_iso8601(svc):
    p = svc.create_payment("m1", "1.00", "INR", CARD, "k5")
    dt = datetime.fromisoformat(p.created_at)
    assert dt.utcoffset().total_seconds() == 0
    assert svc.audit.for_payment(p.id)[0].timestamp.endswith("+00:00")


# PF-011: happy path now requires step_up_verified for amounts > 50 000 INR
def test_happy_path_lifecycle(svc):
    p = svc.create_payment("m1", "100.00", "INR", CARD, "k6")
    svc.authorize(p.id)
    svc.capture(p.id)
    svc.refund(p.id, "100.00")
    assert p.status == PaymentStatus.REFUNDED


# ---------------------------------------------------------------------------
# PF-005 ─ 30-day refund window
# ---------------------------------------------------------------------------

def test_pf005_refund_within_30_days_allowed(svc):
    """PF-005: refund inside 30 days must succeed."""
    p = svc.create_payment("m1", "100.00", "INR", CARD, "rf-ok")
    svc.authorize(p.id)
    svc.capture(p.id)
    # captured_at is set to now; refund immediately — must succeed
    svc.refund(p.id, "100.00")
    assert p.status == PaymentStatus.REFUNDED


def test_pf005_refund_after_30_days_rejected(svc):
    """PF-005: refund after 30-day window must raise REFUND_WINDOW_EXPIRED."""
    p = svc.create_payment("m1", "100.00", "INR", CARD, "rf-late")
    svc.authorize(p.id)
    svc.capture(p.id)
    # Back-date captured_at by 31 days
    past = (datetime.now(timezone.utc) - timedelta(days=31)).isoformat()
    p.captured_at = past
    with pytest.raises(PaymentError) as e:
        svc.refund(p.id, "100.00")
    assert e.value.code == "REFUND_WINDOW_EXPIRED"


def test_pf005_refund_rejected_at_old_60day_boundary(svc):
    """PF-005 regression: a 45-day-old capture that passed the old 60-day window
    must now be rejected under the corrected 30-day window."""
    p = svc.create_payment("m1", "100.00", "INR", CARD, "rf-45d")
    svc.authorize(p.id)
    svc.capture(p.id)
    past = (datetime.now(timezone.utc) - timedelta(days=45)).isoformat()
    p.captured_at = past
    with pytest.raises(PaymentError) as e:
        svc.refund(p.id, "100.00")
    assert e.value.code == "REFUND_WINDOW_EXPIRED"


# ---------------------------------------------------------------------------
# PF-008 ─ PAN never in logs
# ---------------------------------------------------------------------------

def test_pf008_full_pan_not_logged(svc, caplog):
    """PF-008: full PAN must never appear in log output."""
    with caplog.at_level(logging.INFO, logger="payflow"):
        svc.create_payment("m1", "10.00", "INR", CARD, "pan-test")
    assert CARD not in caplog.text
    # last 4 digits ARE allowed
    assert "1111" in caplog.text


# ---------------------------------------------------------------------------
# PF-011 ─ step-up authentication for payments > 50 000 INR
# ---------------------------------------------------------------------------

def test_pf011_above_50k_requires_step_up(svc):
    """PF-011: authorize on a payment > 50 000 INR without step-up must raise STEP_UP_REQUIRED."""
    p = svc.create_payment("m1", "60000.00", "INR", CARD, "su-high")
    with pytest.raises(PaymentError) as e:
        svc.authorize(p.id)
    assert e.value.code == "STEP_UP_REQUIRED"


def test_pf011_above_50k_with_step_up_succeeds(svc):
    """PF-011: authorize on a payment > 50 000 INR WITH step_up_verified=True must succeed."""
    p = svc.create_payment("m1", "60000.00", "INR", CARD, "su-pass")
    svc.authorize(p.id, step_up_verified=True)
    assert p.status == PaymentStatus.AUTHORIZED


def test_pf011_below_50k_no_step_up_needed(svc):
    """PF-011: authorize on a payment ≤ 50 000 INR must succeed without step-up."""
    p = svc.create_payment("m1", "50000.00", "INR", CARD, "su-low")
    svc.authorize(p.id)
    assert p.status == PaymentStatus.AUTHORIZED


# ---------------------------------------------------------------------------
# PF-009 ─ gateway retry: 3 attempts, exponential backoff, no retry on 4xx
# ---------------------------------------------------------------------------

def test_pf009_retries_3_times_on_5xx():
    """PF-009: transient 5xx errors must be retried at most 3 times."""
    calls = []

    def flaky():
        calls.append(1)
        if len(calls) <= 3:
            raise GatewayError(503, "unavailable")
        return {"ok": True}

    sleeps = []
    call_with_retry(flaky, sleep=sleeps.append)
    assert len(calls) == 4  # 3 failures + 1 success


def test_pf009_exponential_backoff_sequence():
    """PF-009: backoff must follow the sequence 1s, 2s, 4s."""
    calls = []

    def flaky():
        calls.append(1)
        if len(calls) <= 3:
            raise GatewayError(503, "err")
        return {"ok": True}

    sleeps: list[float] = []
    call_with_retry(flaky, sleep=sleeps.append)
    assert sleeps == [1, 2, 4]


def test_pf009_4xx_not_retried():
    """PF-009: 4xx responses must NOT be retried."""
    calls = []

    def client_error():
        calls.append(1)
        raise GatewayError(400, "bad request")

    with pytest.raises(GatewayError) as e:
        call_with_retry(client_error, sleep=lambda _: None)
    assert e.value.status == 400
    assert len(calls) == 1


def test_pf009_timeout_triggers_retry():
    """PF-009: gateway timeouts must be retried."""
    calls = []

    def timeout_then_ok():
        calls.append(1)
        if len(calls) == 1:
            raise GatewayTimeout()
        return {"ok": True}

    result = call_with_retry(timeout_then_ok, sleep=lambda _: None)
    assert result == {"ok": True}
    assert len(calls) == 2


# ---------------------------------------------------------------------------
# PF-013 ─ stale exchange rates rejected after 15 minutes
# ---------------------------------------------------------------------------

def test_pf013_stale_rate_rejected():
    """PF-013: converting with a rate older than 15 minutes must raise STALE_RATE."""
    book = RateBook()
    stale_time = datetime.now(timezone.utc) - timedelta(minutes=16)
    book.set_rate("USD", Decimal("83.50"), fetched_at=stale_time)
    with pytest.raises(PaymentError) as e:
        book.to_inr(Decimal("100"), "USD")
    assert e.value.code == "STALE_RATE"


def test_pf013_fresh_rate_accepted():
    """PF-013: converting with a rate younger than 15 minutes must succeed."""
    book = RateBook()
    fresh_time = datetime.now(timezone.utc) - timedelta(minutes=5)
    book.set_rate("USD", Decimal("83.50"), fetched_at=fresh_time)
    result = book.to_inr(Decimal("100"), "USD")
    assert result == Decimal("8350.00")


def test_pf013_rate_exactly_15min_accepted():
    """PF-013: a rate exactly at the 15-minute boundary must be accepted (boundary is exclusive)."""
    book = RateBook()
    at_boundary = datetime.now(timezone.utc) - timedelta(minutes=15)
    book.set_rate("USD", Decimal("83.50"), fetched_at=at_boundary)
    # Should not raise — boundary is exclusive (> not >=)
    result = book.to_inr(Decimal("1"), "USD")
    assert result > 0
