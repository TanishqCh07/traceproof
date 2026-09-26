# AGENTS.md

This file provides guidance to agents when working with code in this repository.

## Documentation Context (Non-Obvious Only)

- `demo/payflow/` is the **target** being audited, not the tool itself. The TraceProof tool lives in `traceproof/` (not yet created).
- `docs/ANSWER_KEY.md` and `docs/START_HERE.md` are blocked by `.bobignore` — they are instructor materials and must not be read or referenced.
- The five verdict strings (`COVERED`, `UNTESTED`, `DRIFT`, `VIOLATION`, `MISSING`) are canonical — defined in `.bob/skills/trace-audit/SKILL.md` and must be used verbatim everywhere, including in test names and reports.
- `.bob/commands/audit.md` and `.bob/commands/remediate.md` are slash command definitions (`/audit`, `/remediate`) wired to specific Bob modes — not general documentation.
- `demo/payflow/payflow/service.py` has an intentional bug: `REFUND_WINDOW = timedelta(days=60)` where the spec says 30 days. This is a known DRIFT gap for demonstration purposes.
