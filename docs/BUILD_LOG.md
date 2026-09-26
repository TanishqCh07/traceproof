# TraceProof — Build Log

## 2025 — Step 1: models, extract, index
Created traceproof/__init__.py, models.py (Requirement+priority, CodeRef, TestRef, Evidence, Verdict), extract.py (PDF/DOCX/MD), index.py (AST repo indexer), tests/test_extract.py, tests/test_index.py (36 tests total, all green), root pytest.ini; updated ARCHITECTURE.md with priority field.
Bob feature used: Agent mode.

## 2025 — Step 2: runner, store, matrix, cli, pyproject.toml
Added traceproof/runner.py (pytest subprocess + JUnit XML parser), traceproof/store.py (append-only NDJSON evidence store with CodeRef anti-hallucination validation), traceproof/matrix.py (RTM builder: COVERED→UNTESTED downgrade, PENDING for no-evidence, gap ordering Critical→Low, coverage %), traceproof/cli.py (argparse: scan/check/report-stub), pyproject.toml (console script `traceproof`), tests/test_store.py, tests/test_matrix.py, tests/test_cli.py (30 new tests, 66 total, all green in 6 s); demo scan: 14 reqs, 42 symbols, 11/11 tests passing, 14 PENDING.
Bob feature used: Agent mode.

## 2025 — Step 3: MCP server
Added traceproof/mcp_server.py using mcp 2.x MCPServer (from mcp.server.mcpserver) with 7 tools: extract_requirements, index_repo, run_tests, record_evidence (anti-hallucination guard returns error string, never crashes), get_matrix, get_gaps (severity filter), render_report (stub). Updated .bob/mcp.json with absolute venv interpreter path. Added tests/test_mcp_server.py (25 tests, all green); full suite 91 tests in 10 s.
Bob feature used: Agent mode.
