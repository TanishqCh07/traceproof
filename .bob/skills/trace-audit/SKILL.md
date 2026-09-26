---
name: trace-audit
description: Build or refresh a requirements traceability matrix (RTM) by auditing a code repository against a specification document (PDF, DOCX or Markdown). Use when asked to audit, trace, verify compliance, find spec drift, or prepare audit evidence.
---

# Trace audit

Goal: turn "we think it's compliant" into evidence an auditor accepts.

## Verdict definitions (use exactly these)
| Verdict | Meaning |
|---|---|
| COVERED | Code implements the requirement literally AND at least one passing test asserts that behaviour |
| UNTESTED | Code implements it, but no test asserts it |
| DRIFT | Code implements something close but different (threshold, window, error code, state) |
| VIOLATION | Code does the opposite of a SHALL NOT requirement (e.g. logs a full PAN) |
| MISSING | No implementation found |

## Rules
1. Compare numbers and error codes character-for-character with the spec. Indian digit grouping (1,00,000) = 100000.
2. A passing test that asserts behaviour contradicting the spec does NOT make a requirement COVERED. Flag it as DRIFT and name the test.
3. Evidence must be `path:line` references that exist. Open the file to confirm the line before recording.
4. Security and PCI requirements (logging, PAN, secrets): grep all logging calls, not just the obvious module.
5. Work in parallel: one subagent per 3-5 requirements, grouped by area.

## Evidence JSON (one object per requirement, via `record_evidence`)
```json
{
  "req_id": "PF-005",
  "verdict": "DRIFT",
  "code_refs": ["payflow/service.py:19"],
  "test_refs": [],
  "rationale": "REFUND_WINDOW is 60 days; spec requires 30 days.",
  "severity": "High"
}
```

See `checklist.md` for the pre-release sign-off checklist.
