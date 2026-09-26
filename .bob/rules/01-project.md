# TraceProof project rules

- Language: Python 3.11. Keep runtime dependencies minimal: pdfplumber, python-docx, mcp (FastMCP), jinja2, pytest.
- Every module gets type hints and a module docstring. No network calls in core logic. The optional LLM judge lives in `traceproof/llm.py` behind an interface and must have a no-LLM fallback.
- Never hard-code file paths from the demo. Everything takes a `--spec` and `--repo` argument.
- Tests live in `tests/` and must run offline in under 10 seconds.
- Data model is the single source of truth: `traceproof/models.py` (Requirement, CodeRef, TestRef, Evidence, Verdict).
- After finishing a task, append a 2-line entry to `docs/BUILD_LOG.md`: what changed and which Bob feature was used (mode, subagents, skill, MCP, review). This feeds the "IBM Bob Usage Statement".
- Do not touch `demo/payflow/` unless the task explicitly says remediation.
