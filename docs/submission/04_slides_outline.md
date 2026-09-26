# Slide outline (7 slides)

1. **TraceProof**: "Green CI isn't compliance." Team SoloModel · IBM Bob 2.0 Hackathon
2. **The problem.** Regulated teams hand-build requirements traceability matrices. Days per release, stale instantly, and tests can lock in wrong behaviour.
3. **The proof.** PayFlow: 11/11 tests green, but only 7/14 requirements proven. A 4-item callout: limit drift, refund drift, PAN in logs, missing 2FA.
4. **How it works.** Diagram: Spec PDF → extract → Bob Compliance Auditor → parallel subagents → MCP `record_evidence` (grounded) → matrix / audit pack / CI gate → Remediator.
5. **IBM Bob at the core.** Custom modes · parallel subagents · document understanding · skill · MCP · slash commands · Review. Plus a Bobcoins-used figure.
6. **Impact.** Results table: time, accuracy, bugs caught, coverage 50% → 100%.
7. **What's next.** Jira/Polarion requirement import, multi-language indexers (Java/Go), ISO 26262 / IEC 62304 templates, watsonx Orchestrate approval flow for sign-off. Repo link + QR.
