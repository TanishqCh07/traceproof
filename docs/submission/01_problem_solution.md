# TraceProof: Problem & Solution Statement (draft, ≤500 words; fill the [brackets])

## The problem
In regulated software (payments, banking, healthcare, automotive), shipping code isn't enough. Teams must *prove* that every requirement in the approved specification is implemented and tested. That proof is a **requirements traceability matrix (RTM)**, and today it is built by hand. An engineer or QA lead reads the spec, hunts through the codebase, finds a test, and pastes file names into a spreadsheet, one row at a time.

It is slow (days to weeks before every audit or release), it goes stale the moment code changes, and it is error-prone in a dangerous way: **green CI creates false confidence.** Tests only check what developers remembered to test, and sometimes they lock in the wrong behaviour.

Our sample payments service, PayFlow, shows this. All 11 tests pass, yet against its 14-requirement spec:
- the transaction limit is 2,00,000 instead of 1,00,000, and a passing test *asserts the wrong value*;
- the refund window is 60 days instead of 30;
- full card numbers are written to logs (a PCI-DSS violation);
- the mandatory 2FA step-up for high-value payments doesn't exist;
- three more requirements are implemented but never tested.

Only 50% of the spec is actually proven. No existing tool in the pipeline noticed.

## The solution
**TraceProof** turns a spec document and a repository into a verified, auditor-ready RTM, and keeps it verified on every pull request.

1. **Understand the spec.** It extracts every requirement (ID, area, priority, text) from PDF, DOCX or Markdown.
2. **Verify in parallel.** In IBM Bob's custom *Compliance Auditor* mode, Bob spawns one subagent per requirement area. Each one finds the implementing code, compares thresholds and error codes literally against the spec, checks whether tests assert the right behaviour, and returns a verdict: COVERED, UNTESTED, DRIFT, VIOLATION or MISSING.
3. **Evidence, not opinions.** Every verdict is recorded through the TraceProof MCP server, which rejects any `file:line` reference that doesn't exist. This guards against hallucinated evidence. Test results come from a real pytest run.
4. **Close the gaps test-first.** The *Remediator* mode writes a failing test named after each requirement, applies the minimal fix and re-runs the suite, in parallel across files.
5. **Ship the audit pack and gate the pipeline.** It produces an interactive HTML matrix, a CSV and a signed audit pack (SHA-256 manifest). A GitHub Action fails any PR that drops coverage or introduces a violation.

## Impact (measured on PayFlow)
| | Manual | TraceProof + Bob |
|---|---|---|
| Time to build RTM (14 reqs) | [~X h, extrapolated from timed sample] | [Y min] |
| Verdict accuracy vs ground truth | n/a | [14/14] |
| Defects found that green CI missed | 0 | 4 (incl. 1 PCI violation) |
| Proven coverage | 50% (unknown to the team) | 50% → [100%] after remediation |

Real specifications have hundreds of requirements, so the saving grows with the size of the spec. The RTM also stops being a pre-audit scramble and becomes a live artifact updated on every PR.

**Who it's for:** engineering and QA teams, compliance officers and external auditors in any organisation that ships software against a written specification.
