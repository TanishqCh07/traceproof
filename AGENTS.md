# AGENTS.md

This file provides guidance to agents when working with code in this repository.

## Project Overview
TraceProof — a Python 3.11 tool that builds a requirements traceability matrix (RTM) by auditing a code repository against a specification document. The `traceproof/` package is the primary deliverable and **does not yet exist** — it must be created.

## Commands

```bash
# Run all tests (must complete offline in under 10 seconds)
pytest tests/

# Run a single test
pytest tests/test_foo.py::test_function_name

# Demo target tests (do NOT touch production code here unless explicitly asked to remediate)
cd demo/payflow && pytest
cd demo/payflow && pytest tests/test_payments.py::test_happy_path_lifecycle
```

The MCP server is launched via `python -m traceproof.mcp_server` (see `.bob/mcp.json`).

## Critical Project Rules

- **Never hard-code demo paths.** Every entry point takes `--spec` and `--repo` arguments.
- **`traceproof/models.py` is the single source of truth** for: `Requirement`, `CodeRef`, `TestRef`, `Evidence`, `Verdict`. Do not define these elsewhere.
- **`traceproof/llm.py`** must live behind an interface and have a no-LLM fallback; no network calls in core logic.
- **After every task**, append a 2-line entry to `docs/BUILD_LOG.md`: what changed + which Bob feature was used (mode, subagents, skill, MCP, review).
- **Do not touch `demo/payflow/`** unless the task explicitly says remediation.
- `demo/payflow/pytest.ini` sets `pythonpath = .` — tests must be run from `demo/payflow/` for imports to resolve.

## Code Style

- Every module must have a **module docstring** and **full type hints**.
- Use `from __future__ import annotations` at the top of every module.
- Errors use a custom `PaymentError(code, message)` pattern — code strings are ALL_CAPS (e.g. `"INVALID_AMOUNT"`).
- Enums that double as strings: `class MyEnum(str, Enum)`.
- Timestamps: always UTC ISO-8601 (`datetime.now(timezone.utc).isoformat()`).
- Money: integer minor units (paise/cents), never floats. Convert with `Decimal(str(amount))`.
- Inline comments referencing spec requirements use the format `# PF-003 idempotency`.

## Runtime Dependencies (keep minimal)
`pdfplumber`, `python-docx`, `mcp` (FastMCP), `jinja2`, `pytest`

## Architecture
```
traceproof/
  models.py       ← Requirement, CodeRef, TestRef, Evidence, Verdict (source of truth)
  llm.py          ← Optional LLM judge (behind interface, no-LLM fallback required)
  mcp_server.py   ← FastMCP server exposing: extract_requirements, index_repo,
                     get_matrix, get_gaps, record_evidence, run_tests, render_report
tests/            ← All project tests (offline, <10s total)
demo/payflow/     ← Target repo for audit demos (READ-ONLY unless remediating)
docs/BUILD_LOG.md ← Append 2-line entry after every task
```

## Verdict Definitions (use exactly these strings)
| Verdict | Meaning |
|---|---|
| `COVERED` | Code implements requirement AND a passing test asserts that behaviour |
| `UNTESTED` | Code implements it, but no test asserts it |
| `DRIFT` | Code implements something close but different (wrong threshold/error code/state) |
| `VIOLATION` | Code does the opposite of a SHALL NOT requirement |
| `MISSING` | No implementation found |
