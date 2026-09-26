from datetime import datetime

import pytest

from payflow.models import PaymentError, PaymentStatus
from payflow.ratelimit import RateLimiter
from payflow.service import PaymentService

CARD = "4111111111111111"


@pytest.fixture
def svc():
    return PaymentService()


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


def test_large_payment_within_limit(svc):
    p = svc.create_payment("m1", "150000.00", "INR", CARD, "k-big")
    assert p.amount_minor == 15_000_000


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


def test_happy_path_lifecycle(svc):
    p = svc.create_payment("m1", "100.00", "INR", CARD, "k6")
    svc.authorize(p.id)
    svc.capture(p.id)
    svc.refund(p.id, "100.00")
    assert p.status == PaymentStatus.REFUNDED
