# IBM Bob Usage Statement (draft, ≤500 words; update from docs/BUILD_LOG.md)

IBM Bob 2.0 is both how TraceProof was **built** and a core part of how it **runs**.

## Bob inside the product
- **Custom modes.** TraceProof ships two project modes in `.bob/custom_modes.yaml`. 🛡️ *Compliance Auditor* is restricted to editing only evidence, reports and tests, so an audit can never silently change production code. 🔧 *Remediator* follows a strict test-first fix loop.
- **Subagents running in parallel.** The auditor splits the specification by area and spawns one subagent per batch. Each works in its own clean context, verifying 3–5 requirements against code and tests, and the results merge into a single matrix. [On PayFlow: N subagents, M requirements, T minutes.]
- **Document understanding.** Bob reads the SRS PDF, including requirement tables that wrap across rows, and reconciles it with the output of our deterministic extractor.
- **Skills.** The `trace-audit` skill encodes the verdict definitions, the literal-comparison rules (e.g. Indian digit grouping 1,00,000 = 100000), and the release sign-off checklist. Any team can reuse it.
- **MCP.** Bob calls our own FastMCP server (`extract_requirements`, `index_repo`, `run_tests`, `record_evidence`, `get_gaps`, `render_report`). `record_evidence` rejects any code reference whose file or line doesn't exist, so Bob's findings stay grounded.
- **Slash commands.** `/audit <spec> <repo>` and `/remediate [critical]` package the whole workflow into one command each.
- **Rules.** `.bob/rules/01-project.md` enforces offline tests, typed modules, no hard-coded paths, and a build log after every task.

## Bob building the product
| Session | What Bob did | Bob features |
|---|---|---|
| S1 | `/init` → AGENTS.md; designed the architecture + mermaid flow | Plan mode, /init |
| S2 | Data model, PDF/DOCX/MD extractor, AST repo indexer + tests | Code mode, agentic iteration |
| S3 | pytest runner, matrix engine, CLI | Code mode |
| S4 | FastMCP server with an anti-hallucination guard | Code mode, MCP |
| S5 | Self-contained HTML dashboard + signed audit pack | Code mode |
| S6 | Live audit of PayFlow: [14/14] verdicts correct | Custom mode, parallel subagents, skill, MCP, document understanding |
| S7 | Remediated [7] gaps test-first: 50% → [100%] | Custom mode, parallel subagents |
| S8 | GitHub Action CI gate; Bob Review of the full diff | Code mode, Review |

All task-session summaries are in `bob_sessions/`. The files Bob generated or edited are listed in `docs/BUILD_LOG.md`.

## What Bob changed for us
Holding the full repository context across sessions mattered most. The MCP server in S4 was built directly on the models from S2 without re-explaining them, and Bob's repository awareness is also what lets the auditor follow a requirement from spec text to constant to test. [Add 1–2 honest observations: something Bob did surprisingly well and something you had to correct.]

Total Bobcoins used: [X / 40].
