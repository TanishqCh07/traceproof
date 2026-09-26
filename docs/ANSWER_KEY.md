# PayFlow planted gaps: answer key (keep OUT of the audited repo)

Use this to measure TraceProof's accuracy and quote the numbers in your video and README.
All 11 PayFlow tests pass. CI is green, yet half the spec is unproven or violated. That's your hook.

| Req | Truth | Where / why |
|---|---|---|
| PF-001 | ✅ Covered | `validation.validate_currency` + `test_rejects_unsupported_currency` |
| PF-002 | ❌ **DRIFT** | `validation.MAX_TXN_AMOUNT_INR = 200000` but spec says 1,00,000. `test_large_payment_within_limit` *passes while encoding the wrong behaviour* (150000 accepted) |
| PF-003 | ✅ Covered | `service.create_payment` idempotency + `test_idempotent_create_returns_same_payment` |
| PF-004 | 🟡 Untested | `validation.to_minor_units` rejects floats, but no test |
| PF-005 | ❌ **DRIFT** | `service.REFUND_WINDOW = timedelta(days=60)`, spec says 30. No test |
| PF-006 | ✅ Covered | `service.refund` + `test_refund_cannot_exceed_capture` |
| PF-007 | ✅ Covered | `audit.AuditLog` + `test_state_changes_are_audited` |
| PF-008 | ❌ **VIOLATION (PCI)** | `service.create_payment` logs `card=%s` with the **full PAN** |
| PF-009 | 🟡 Untested | `gateway.call_with_retry` is correct, but no test |
| PF-010 | ✅ Covered | `ratelimit.RateLimiter` + `test_rate_limit_per_merchant` |
| PF-011 | ❌ **MISSING** | No step-up / 2FA flag anywhere |
| PF-012 | ✅ Covered | `models.ALLOWED_TRANSITIONS` + `test_invalid_transition_rejected` |
| PF-013 | 🟡 Untested | `fx.RateBook.to_inr` STALE_RATE check, no test |
| PF-014 | ✅ Covered | `models.utc_now` + `test_timestamps_are_utc_iso8601` |

**Totals:** 7 covered, 3 untested, 2 drift, 1 violation, 1 missing. Traceability-proven: 7/14 = 50%.
After the TraceProof + Bob remediation run, the target is 14/14, with PF-002/005/008/011 fixed in code.
