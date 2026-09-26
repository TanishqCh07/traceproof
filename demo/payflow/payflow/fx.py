"""Foreign-exchange rates used to compute INR-equivalent amounts."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from .models import PaymentError

MAX_RATE_AGE = timedelta(minutes=15)


@dataclass
class Rate:
    currency: str
    inr_per_unit: Decimal
    fetched_at: datetime


class RateBook:
    def __init__(self) -> None:
        self._rates: dict[str, Rate] = {
            "INR": Rate("INR", Decimal("1"), datetime.now(timezone.utc)),
        }

    def set_rate(self, currency: str, inr_per_unit: Decimal, fetched_at: datetime | None = None) -> None:
        self._rates[currency] = Rate(currency, inr_per_unit, fetched_at or datetime.now(timezone.utc))

    def to_inr(self, amount: Decimal, currency: str) -> Decimal:
        rate = self._rates.get(currency)
        if rate is None:
            raise PaymentError("NO_RATE", currency)
        if currency != "INR" and datetime.now(timezone.utc) - rate.fetched_at > MAX_RATE_AGE:
            raise PaymentError("STALE_RATE", currency)
        return (amount * rate.inr_per_unit).quantize(Decimal("0.01"))
