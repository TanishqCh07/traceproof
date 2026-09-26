"""Client for the upstream card-network gateway."""
from __future__ import annotations

import time
from typing import Callable


class GatewayError(Exception):
    def __init__(self, status: int, message: str = ""):
        super().__init__(f"gateway {status}: {message}")
        self.status = status


class GatewayTimeout(Exception):
    pass


BACKOFF_SECONDS = (1, 2, 4)


def call_with_retry(fn: Callable[[], dict], sleep: Callable[[float], None] = time.sleep) -> dict:
    """Call the gateway, retrying transient failures with exponential backoff.

    Retries only on 5xx responses and timeouts; 4xx errors are raised immediately.
    """
    attempt = 0
    while True:
        try:
            return fn()
        except GatewayTimeout:
            pass
        except GatewayError as exc:
            if exc.status < 500:
                raise
        if attempt >= len(BACKOFF_SECONDS):
            raise GatewayError(503, "retries exhausted")
        sleep(BACKOFF_SECONDS[attempt])
        attempt += 1
