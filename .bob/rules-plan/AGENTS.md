# AGENTS.md

This file provides guidance to agents when working with code in this repository.

## Architecture Constraints (Non-Obvious Only)

- The `traceproof/` package is the deliverable being built — it does not exist yet. The demo target (`demo/payflow/`) is a separate, pre-existing codebase to audit, not part of the tool.
- `traceproof/models.py` must be created first — it is the single source of truth that all other modules import from. Plan any feature work assuming this constraint.
- The MCP server (`traceproof/mcp_server.py`) must expose exactly these tools: `extract_requirements`, `index_repo`, `get_matrix`, `get_gaps`, `record_evidence`, `run_tests`, `render_report`. The `.bob/mcp.json` config already declares them with `alwaysAllow` for a subset.
- Audit workflow is strictly read-only: Compliance Auditor mode is restricted by `fileRegex` to only write evidence/reports/tests — production code changes are blocked at the mode level.
- The LLM judge (`traceproof/llm.py`) is optional but architecturally isolated: core audit logic must work without it. Plan any implementation to not assume LLM availability.
- Tests must complete offline in under 10 seconds total — plan against any approach requiring network I/O or slow file parsing in the hot path.
- `demo/payflow/` has an intentional DRIFT (60-day refund window vs. 30-day spec). Any planning for the remediation flow should account for test-first fixes: failing test → minimal fix → evidence recording.
