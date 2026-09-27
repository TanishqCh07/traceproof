In regulated software (payments, banking, healthcare, automotive), shipping code is not enough. Teams must prove that every requirement in the approved specification is implemented and tested. That proof is a Requirements Traceability Matrix (RTM), and today it is built by hand. It takes days before every audit or release, it is stale after the next commit, and it is dangerously error-prone, because green CI creates false confidence. Tests only check what developers remembered to test, and sometimes they lock in the wrong behaviour.

Our sample payments service, PayFlow, shows this. All 11 of its tests pass. Yet against its 14-requirement spec, the transaction limit was ₹2,00,000 instead of ₹1,00,000, and a passing test asserted the wrong value. The refund window was 60 days instead of 30. Full card numbers were written to logs, a PCI-DSS violation. The mandatory 2FA step-up for payments above ₹50,000 did not exist, and three more requirements were implemented but never tested. Only 50% of the spec was actually proven, and nothing in the pipeline noticed.

TraceProof turns a spec document and a repository into a verified, auditor-ready RTM, and keeps it verified on every pull request.

1. Understand the spec. It extracts every requirement (ID, area, priority, text) from PDF, DOCX or Markdown.
2. Map the code. It AST-indexes functions, constants and tests with file:line, and runs the real test suite.
3. Verify with IBM Bob. A custom Compliance Auditor mode compares code literally against the spec and returns one of five verdicts: COVERED, UNTESTED, DRIFT, VIOLATION or MISSING.
4. Evidence, not opinions. Every verdict is recorded through TraceProof's own MCP server, which rejects any file:line reference that does not exist, so AI cannot invent proof. History is append-only for auditors.
5. Close the gaps. A Remediator mode fixes each gap test-first: a failing test named after the requirement, the minimal fix, then the full suite.
6. Ship and guard. It produces an interactive HTML matrix, a CSV and a SHA-256-manifested audit pack, and a GitHub Action fails any pull request that drops coverage or introduces a violation.

Measured impact on PayFlow:
- Audit accuracy: 14 of 14 verdicts matched our ground-truth answer key.
- Defects found that green CI missed: 4 (two drifts, one PCI violation, one missing control), plus 3 untested requirements.
- Proven coverage: 50% → 100% after Bob's remediation. PayFlow tests grew from 11 to 27, all passing.
- Speed: the Bob audit took about 5 minutes and remediation about 6, versus a manual, spreadsheet-driven review.
- Continuous protection: a pull request that silently changed the refund window back to 60 days was blocked by the CI gate. The gate also caught a flaky boundary test that passed on Windows but failed on Linux.

Real specifications have hundreds of requirements, so the saving grows with the size of the spec. The RTM stops being a pre-audit scramble and becomes a living artifact. It serves engineering, QA and compliance teams, and external auditors.
