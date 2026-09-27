PROBLEM

Regulated software (payments, banking, medical devices, automotive) must follow a written specification of numbered rules, such as "a refund SHALL only be permitted within 30 days" or "card numbers SHALL NEVER be written to logs." Auditors and standards (PCI DSS, IEC 62304, ISO 26262) require proof that every rule is implemented and tested. That proof is a Requirements Traceability Matrix (RTM): one row per requirement, linking it to the code that implements it and the test that proves it.

Today it is built by hand: before each release, an engineer reads each requirement, searches the code, finds a test, judges whether it proves the rule, and fills in a spreadsheet. This workflow fails in three ways:

1. Slow: days of work, repeated every release.
2. Stale: the next commit can silently invalidate a row.
3. Wrong: teams treat "all tests pass" as proof. Tests only check what someone remembered, and a test can assert the wrong behaviour and still pass.

Problem statement: proving that code does what its specification says is manual, slow and unreliable, and passing tests are mistaken for proof.

Our sample payments service, PayFlow, shows the gap. All 11 of its tests pass, yet against its 14-requirement spec: the transaction limit is ₹2,00,000 instead of ₹1,00,000 (and a passing test asserts the wrong value); refunds are allowed for 60 days instead of 30; full card numbers are written to logs (a PCI DSS violation); the mandatory 2FA check above ₹50,000 does not exist; and three more rules are never tested. Only 7 of 14 requirements are proven, while CI is green.

SOLUTION

TraceProof turns a spec and a repository into a verified RTM, fixes the gaps, and keeps them fixed.

1. Read the spec: extracts every requirement (ID, area, priority, text) from PDF, DOCX or Markdown.
2. Map the code: indexes code and tests with file:line and runs the real test suite.
3. Verify with IBM Bob: a custom Compliance Auditor mode compares code literally with the spec (30 vs 60 days) and assigns one of five verdicts: COVERED, UNTESTED, DRIFT, VIOLATION or MISSING.
4. Record evidence safely: verdicts go through TraceProof's own MCP server, which rejects any file:line that does not exist, so AI cannot invent proof.
5. Fix test-first: a Remediator mode writes a failing requirement-named test, applies the minimal fix, and re-runs the suite.
6. Report and guard: an interactive RTM dashboard, CSV and hashed audit pack for auditors, plus a GitHub Action that blocks any pull request that breaks a requirement.

RESULTS ON PAYFLOW

- 14 of 14 audit verdicts matched our ground-truth answer key, in about 5 minutes.
- 4 defects found that green CI missed, plus 3 untested rules.
- Proven coverage rose from 50% to 100%; tests grew from 11 to 27, all passing.
- A pull request reverting the refund window to 60 days is blocked from merging. The gate also caught a flaky Windows-vs-Linux test.
