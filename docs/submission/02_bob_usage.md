IBM Bob 2.0 is both how TraceProof was built and a core part of how it runs.

Bob inside the product

- Custom modes. TraceProof ships two project modes in .bob/custom_modes.yaml. The Compliance Auditor mode may only edit evidence, report and test files, so an audit can never silently change production code. The Remediator mode follows a strict test-first loop.
- Skills. The trace-audit skill encodes the five verdict definitions, literal-comparison rules (for example, Indian digit grouping: 1,00,000 = 100000; a passing test that asserts the wrong value is DRIFT, not COVERED), and a release sign-off checklist. Bob loaded it automatically during the audit.
- MCP. Bob drives our own FastMCP server with eight tools: extract_requirements, index_repo, run_tests, record_evidence, record_evidence_batch, get_matrix, get_gaps and render_report. record_evidence validates every file:line reference against the repository and rejects anything that does not exist, which keeps Bob's findings grounded. In the audit, Bob recorded all 14 verdicts through parallel MCP calls.
- Slash commands and rules. /audit <spec> <repo> and /remediate package the whole workflow into one command.
- Document understanding. Bob reads the SRS PDF, including requirement tables, and reconciles it with our extractor's output.

Bob building the product

Every step used Bob, with a task session summary in bob_sessions/:
- /init generated AGENTS.md and mode-specific rules.
- Plan mode designed the architecture (docs/ARCHITECTURE.md), including the data model and the eight-tool MCP surface.
- Agent mode built, in focused tasks, the PDF/DOCX/MD extractor and AST indexer; the pytest runner, evidence store and matrix engine; the MCP server; the self-contained dashboard with a signed audit pack; and the CI workflow. The suite has 148 tests.
- Agent mode also fixed issues found during the live audit: Windows path resolution for run_tests, concurrency-safe evidence writes with a new batch tool, and linking test pass/fail into the dashboard.
- In the Compliance Auditor mode, Bob audited PayFlow. All 14 verdicts matched our ground-truth answer key, including a drift hidden behind a passing test and a PCI card-number leak.
- In the Remediator mode, Bob split the remediation into three file-scoped workstreams (validation.py; service.py; gateway.py and fx.py), wrote 16 requirement-named tests, fixed four defects, and took proven coverage from 50% to 100%.

What Bob changed for us

Bob's full-repository context mattered most. The MCP server was built directly on the data model from an earlier task without re-explaining it, and the auditor followed each requirement from spec text to a constant to the test that asserts it. Custom modes let us turn a one-off prompt into a repeatable, permission-scoped workflow that any team can reuse.

Honest observations. Bob sometimes ran the work itself rather than spawning separate subagents, so our modes now explicitly require delegation. One Bob-written test was flaky at a time boundary (it passed on Windows and failed on Linux), and TraceProof's own CI gate caught it.

Total usage: about 28 of 40 Bobcoins across 11 task sessions.
