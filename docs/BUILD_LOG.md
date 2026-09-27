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

## 2025 — Step 3: report generator (HTML/CSV/ZIP)
Added traceproof/report.py (render_report: Jinja2 HTML with inline CSS/JS, CSV, audit_pack.zip with MANIFEST.sha256), traceproof/templates/rtm.html.j2 (light/dark, coverage ring, KPI tiles, before→after history strip, filter/search/sort matrix table), updated traceproof/cli.py (`report --repo --spec --open`), updated traceproof/mcp_server.py (render_report returns paths+summary dict), updated tests/test_cli.py and tests/test_mcp_server.py to match new API, added tests/test_report.py (34 tests: PENDING-only, mixed verdicts, history, zip contents, manifest hash verification, CLI, MCP); 125 tests total, all green in 14 s. Preview rendered with 6-req mixed fixture.
Bob feature used: Agent mode.

## 2025 — Live audit fixes (5 issues)
Fixed: (1) runner.py resolves repo_path to absolute + resolves junit XML path to absolute (Windows fix); (2) store.py uses threading.Lock + atomic rename for concurrent-safe record(); added record_batch() for all-or-nothing writes; added record_evidence_batch MCP tool; (3) report.py loads tests.json and passes to build_matrix so test_refs show ✓/✗ instead of ?; matrix.py normalises backslash paths and enriches TestRef.passed; (4) rtm.html.j2 priority chips: High→orange (#fed7aa/#c2410c), Medium→amber (#fef08a/#854d0e), distinct from Critical red; (5) .bob/custom_modes.yaml compliance-auditor: run_tests before batching, main agent delegates all verification to parallel subagents, subagents return results to main which calls record_evidence_batch. Added 3 regression test files (test_runner_regression.py, test_store_regression.py, test_matrix_regression.py, 57 new tests); 148 total, all green; `traceproof report --repo demo/payflow` shows 10 test-pass icons.
Bob feature used: Agent mode.

## 2025 — Remediate all 7 PayFlow gaps (PF-002, PF-004, PF-005, PF-008, PF-009, PF-011, PF-013)
Fixed: PF-002 MAX_TXN_AMOUNT_INR 200000→100000; PF-005 REFUND_WINDOW 60→30 days; PF-008 mask full PAN to last-4 in log.info; PF-011 added STEP_UP_THRESHOLD_INR + step_up_verified param in authorize(). Replaced test_large_payment_within_limit with spec-correct test_pf002_*. Added 16 new tests covering all 7 gaps across validation.py, service.py, gateway.py, fx.py. RTM: 0/14 gaps, 100% COVERED. Bob feature used: Remediator custom mode (work split into 3 file-scoped workstreams, executed by the main agent; failing-test-first; record_evidence per gap).

## 2025 — CI compliance gate
Added .github/workflows/traceproof.yml (6 steps: root pytest, scan, report, check --min-coverage 100, upload artefact traceproof-rtm, GITHUB_STEP_SUMMARY with coverage%/verdict counts/gaps); created README.md with workflow badge. Steps 2-4 verified locally: scan 14 reqs 27/27 pass, report HTML/CSV/ZIP rendered, check PASSED 100.0%. Downgrade path confirmed in matrix.py (COVERED→UNTESTED when cited test fails, check re-runs tests fresh). 148 tests still green.
Bob feature used: Agent mode.
