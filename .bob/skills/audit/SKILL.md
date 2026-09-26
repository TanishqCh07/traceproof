---
name: audit
description: Audit a repo against a spec and build the traceability matrix
metadata:
  user-invocable: true
  disable-model-invocation: true
  argument-hint: <spec-path> <repo-path>
---

Switch to the Compliance Auditor mode and use the trace-audit skill.
Audit the repository at the second argument against the specification at the first argument.
Spawn parallel subagents per requirement area, record every verdict with the traceproof MCP tools,
run the tests, render the report, and end with a table of gaps sorted by severity.
