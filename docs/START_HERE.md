# TraceProof: 48-hour build kit (IBM Bob 2.0 Hackathon)

> **One-liner:** TraceProof turns a spec PDF and a repo into an auditor-ready requirements traceability matrix in minutes, not weeks. Bob's parallel subagents verify every requirement against the code and tests, catch spec drift that green CI misses, then close the gaps test-first.

**Deadline: Sun 27 Sep, 8:30 PM IST. Aim to submit by 6:00 PM.**

---

## 0. What's in this kit

| Path | What it is | Who wrote it |
|---|---|---|
| `demo/payflow/` | Sample payments service to audit (11 tests, all green) | Sample data, from this kit |
| `demo/specs/PayFlow_SRS_v1.2.pdf` | The spec it is audited against (14 requirements) | Sample data, from this kit |
| `demo/ANSWER_KEY.md` | Ground truth for the 7 planted gaps. **Don't commit it to the audited folder**; keep it in `docs/` for measuring accuracy | Kit |
| `bob-config/.bob/` | Custom modes, skill, rules, MCP config, slash commands | Kit (Bob configuration) |
| `submission/` | Drafts: problem statement, Bob usage statement, video script, slide outline | Kit (edit into your voice) |

**The TraceProof product itself (`traceproof/` package, MCP server, dashboard, CI) is built by you with Bob** using the prompts below. That's what the Bob evidence rule requires.

## 1. Setup (15 min, 0 Bobcoins)

```bash
# inside your cloned `traceproof` repo
mkdir -p bob_sessions docs
# copy kit contents in:
#   kit/bob-config/.bob         -> ./.bob
#   kit/demo                    -> ./demo      (then move demo/ANSWER_KEY.md -> docs/ANSWER_KEY.md)
python -m venv .venv && .venv\Scripts\activate      # Windows  (macOS/Linux: source .venv/bin/activate)
pip install pytest pdfplumber python-docx jinja2 "mcp[cli]"
cd demo/payflow && python -m pytest -q && cd ../..  # expect 11 passed
git add . && git commit -m "chore: demo target, spec and Bob config" && git push
```

In Bob: **Settings → General**, confirm the hackathon team (`ibm-coding-challenge-…`, us-east) is selected. Then **Settings → Modes** should show 🛡️ Compliance Auditor and 🔧 Remediator.

## 2. Bobcoin budget (40 total)

Check usage after Session 1 and scale down if it cost more than about 4.

| # | Session | Mode | Budget |
|---|---|---|---|
| S1 | `/init` + architecture plan | Plan | 3 |
| S2 | Models, spec extractor, repo indexer + tests | Code | 5 |
| S3 | Test runner, matrix engine, CLI | Code | 5 |
| S4 | MCP server | Code | 4 |
| S5 | HTML dashboard + audit pack export | Code | 6 |
| S6 | ⭐ **Live audit of PayFlow** (record this!) | Compliance Auditor | 6 |
| S7 | ⭐ **Remediation** (record this too) | Remediator | 5 |
| S8 | CI gate (GitHub Action) + README polish via Bob Review | Code | 3 |
| | Buffer | | 3 |

Saving tips: one task per session and start a new task each time (keeps context small). Do trivial edits yourself. Use @-mentions for files instead of letting Bob search. After each task, **screenshot the task summary right away** → `bob_sessions/solomodel_taskNN_<name>.png`.

## 3. Session prompts (paste as-is)

### S1: Init + plan (Plan mode)
First run `/init`. Then:
```
We are building TraceProof: a tool that audits a code repository against a requirements
document (PDF/DOCX/MD) and produces a verified requirements traceability matrix (RTM).
Target users: engineering teams in regulated industries who today build RTMs by hand in Excel
before audits.

Read @.bob/rules/01-project.md, @.bob/skills/trace-audit/SKILL.md and @.bob/custom_modes.yaml.
The demo target is @demo/payflow and the spec is demo/specs/PayFlow_SRS_v1.2.pdf.

Produce docs/ARCHITECTURE.md with:
- Package layout: traceproof/{models,extract,index,runner,matrix,report,cli,mcp_server,llm}.py
- Data model (Requirement, CodeRef, TestRef, Evidence, Verdict enum COVERED/UNTESTED/DRIFT/VIOLATION/MISSING)
- Evidence store: .traceproof/evidence.json (one record per requirement, history preserved)
- MCP tools: extract_requirements, index_repo, run_tests, record_evidence, get_matrix, get_gaps, render_report
- CLI: traceproof scan | report | check --min-coverage N (exit 1 if below, for CI)
- A mermaid diagram of the flow: spec -> extract -> Bob subagents verify in parallel -> evidence -> report/CI gate
Keep it to one page. Do not write code yet.
```

### S2: Models, extractor, indexer (Code mode)
```
Implement per @docs/ARCHITECTURE.md:
1. traceproof/models.py: dataclasses + Verdict enum, JSON (de)serialisation.
2. traceproof/extract.py: extract_requirements(path) for PDF (pdfplumber, including tables), DOCX
   and Markdown. Detect IDs with a configurable regex (default r"\b[A-Z]{2,5}-\d{3}\b"), and capture
   area, priority and full text. Handle requirements whose text wraps across table rows.
3. traceproof/index.py: index_repo(path) using Python `ast`: functions/classes/module constants with
   file:line and docstrings; pytest tests with their names and asserted literals; explicit
   requirement-id mentions in comments.
4. tests/test_extract.py and tests/test_index.py run against demo/. Extract must return exactly
   14 requirements from PayFlow_SRS_v1.2.pdf.
Run the tests and fix until green.
```

### S3: Runner, matrix, CLI (Code mode)
```
Implement:
1. traceproof/runner.py: run pytest in a target repo with --junitxml, parse results into TestRef
   pass/fail.
2. traceproof/matrix.py: merge requirements + evidence + test results into a matrix; compute
   coverage % (COVERED / total), breakdown by verdict and severity; a requirement whose cited test
   is failing is downgraded from COVERED to UNTESTED.
3. traceproof/cli.py (argparse, entry point `traceproof`): `scan --spec --repo` (extract+index,
   writes .traceproof/), `report` (renders), `check --min-coverage N` (exit 1 if below, or if any
   VIOLATION exists).
4. pyproject.toml with the console script. Tests for matrix edge cases. Run them.
```

### S4: MCP server (Code mode)
```
Implement traceproof/mcp_server.py with FastMCP (package `mcp`) exposing: extract_requirements,
index_repo, run_tests, record_evidence (validates that each code_ref file:line exists and rejects
it otherwise; this is our anti-hallucination guard), get_matrix, get_gaps(severity=None),
render_report. Runnable with `python -m traceproof.mcp_server`. Add a smoke test that calls each
tool function directly. Then check that @.bob/mcp.json starts it (tell me if the path needs to be
absolute on Windows).
```

### S5: Dashboard + audit pack (Code mode)
```
Implement traceproof/report.py rendering reports/rtm.html (single self-contained file, Jinja2,
no CDN):
- Header KPIs: coverage %, counts per verdict, spec name+version, repo commit SHA, generated time
- A requirement x evidence matrix: one row per requirement, coloured verdict chip, clickable code
  refs (file:line), test refs with pass/fail, rationale, severity; filter by verdict
- "Before vs after" strip when .traceproof/evidence.json has history
- Export: reports/rtm.csv and reports/audit_pack.zip (html + csv + junit + evidence.json +
  MANIFEST.sha256)
Clean, professional, dark/light friendly. Render it for the current evidence and open it.
```

### S6: ⭐ The live audit (switch to 🛡️ Compliance Auditor; screen-record this)
```
/audit demo/specs/PayFlow_SRS_v1.2.pdf demo/payflow
```
Expected: parallel subagents per area; verdicts for 14 requirements, including PF-002 DRIFT (a test encodes the wrong limit), PF-005 DRIFT, PF-008 VIOLATION (full PAN logged), PF-011 MISSING, and PF-004/009/013 UNTESTED. Compare with `docs/ANSWER_KEY.md` and **write down the accuracy** (e.g. "14/14 verdicts correct").

### S7: ⭐ Remediation (switch to 🔧 Remediator; screen-record)
```
/remediate critical
```
then, if budget allows, `/remediate` for the rest. Target: 50% → 100%, with all 11 original tests plus the new ones green.

### S8: CI gate + review (Code mode)
```
Add .github/workflows/traceproof.yml: on pull_request, install, run `traceproof scan` and
`traceproof check --min-coverage 100` against demo/, upload reports/ as an artifact, and post
the coverage summary to the job summary. Then use Bob Review on the full diff and fix
anything critical.
```
Demo it: open a PR that changes `REFUND_WINDOW` back to 60 days → the CI check goes red.

## 4. Numbers to capture for the "impact" story
- Manual baseline: time yourself for 10 minutes building the RTM by hand for 3 requirements, then extrapolate to 14 (and note that real SRSs have 200+).
- TraceProof: wall-clock of S6 + S7.
- Accuracy vs `ANSWER_KEY.md`.
- Bugs caught that green CI missed: 4 (2 drift, 1 PCI violation, 1 missing control).

## 5. Submission checklist
- [ ] Public repo with `bob_sessions/` PNGs for every task
- [ ] README: problem, 30-sec GIF, architecture diagram, quickstart, results table, Bob usage
- [ ] Problem & Solution statement ≤ 500 words (`submission/01_problem_solution.md`)
- [ ] IBM Bob usage statement ≤ 500 words (`submission/02_bob_usage.md`)
- [ ] Video ≤ 3:00 with ≥ 90 s of live demo (`submission/03_video_script.md`)
- [ ] Slides (`submission/04_slides_outline.md`)
- [ ] Cover image (screenshot of the matrix before/after)
- [ ] Tags: IBM Bob, watsonx.ai (only if used), Developer Tools, Security, Productivity
- [ ] Post-event feedback form (for the $100 participant reward)
