"""Append-only audit trail for payment state changes."""
from __future__ import annotations

from dataclasses import dataclass

from .models import utc_now


@dataclass(frozen=True)
class AuditRecord:
    payment_id: str
    actor: str
    old_state: str | None
    new_state: str
    timestamp: str


class AuditLog:
    def __init__(self) -> None:
        self._records: list[AuditRecord] = []

    def record(self, payment_id: str, actor: str, old_state: str | None, new_state: str) -> AuditRecord:
        rec = AuditRecord(payment_id, actor, old_state, new_state, utc_now())
        self._records.append(rec)
        return rec

    def for_payment(self, payment_id: str) -> list[AuditRecord]:
        return [r for r in self._records if r.payment_id == payment_id]
