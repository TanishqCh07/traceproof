# AGENTS.md

This file provides guidance to agents when working with code in this repository.

## Coding Rules (Non-Obvious Only)

- `traceproof/models.py` is the ONLY place to define `Requirement`, `CodeRef`, `TestRef`, `Evidence`, `Verdict`. Import from there everywhere else — never redefine.
- Every new module needs `from __future__ import annotations` as the first import, a module docstring, and full type hints — these are enforced project rules, not style preferences.
- No network calls in any module except `traceproof/llm.py`. LLM judge must expose an interface so core logic can run without it.
- Money values are always integer minor units (`int`). Convert user input via `Decimal(str(amount))` before arithmetic — never `float`.
- Test file naming for compliance gaps must include the requirement ID: `test_pf002_rejects_amount_above_limit`.
- After every task, append 2 lines to `docs/BUILD_LOG.md` (create the file if it doesn't exist): what changed and which Bob feature was used. This is mandatory, not optional.
- Demo tests run from `demo/payflow/` — `pytest.ini` sets `pythonpath = .` there, so imports only resolve from that directory.
- The MCP server tools `record_evidence` / `render_report` must not be called unless the traceproof package (`python -m traceproof.mcp_server`) is running and registered in `.bob/mcp.json`.
