---
name: remediate
description: 'Close traceability gaps test-first, in parallel'
metadata:
  user-invocable: true
  disable-model-invocation: true
---

Switch to the Remediator mode. Fetch gaps with `get_gaps` (filter by the argument if given).
For each gap, in parallel subagents where files do not overlap: write a failing test named after the
requirement id, apply the minimal fix, run the full suite, and record COVERED evidence.
Finish by rendering the report and showing before -> after coverage.
