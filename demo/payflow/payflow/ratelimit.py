"""Per-merchant sliding-window rate limiter."""
from __future__ import annotations

import time
from collections import defaultdict, deque

from .models import PaymentError

MAX_REQUESTS_PER_MINUTE = 20


class RateLimiter:
    def __init__(self, limit: int = MAX_REQUESTS_PER_MINUTE, window_s: float = 60.0, clock=time.monotonic):
        self.limit = limit
        self.window_s = window_s
        self.clock = clock
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def check(self, merchant_id: str) -> None:
        now = self.clock()
        hits = self._hits[merchant_id]
        while hits and now - hits[0] >= self.window_s:
            hits.popleft()
        if len(hits) >= self.limit:
            raise PaymentError("RATE_LIMITED", merchant_id)
        hits.append(now)
