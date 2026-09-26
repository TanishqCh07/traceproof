# Video script (target 2:50; ≥90 s live demo)

| Time | Screen | Narration |
|---|---|---|
| 0:00–0:12 | Black screen, then a terminal: `11 passed` in green | "All eleven tests pass. CI is green. This payments service is ready to ship… right?" |
| 0:12–0:30 | Spec PDF scrolling; a messy Excel RTM | "Not in a regulated industry. Before release, someone has to prove every requirement in this spec is implemented and tested. Today that's a spreadsheet, built by hand, for days, and it's stale by the next commit." |
| 0:30–0:40 | Title card: **TraceProof** + one-liner | "TraceProof does it in minutes, with IBM Bob." |
| 0:40–1:25 | Bob IDE: select 🛡️ Compliance Auditor, type `/audit …`; the parallel subagents panel expands | "One command. Bob reads the spec, splits it by area and runs parallel subagents. Each one traces its requirements to the exact line of code and the test that proves it." |
| 1:25–1:55 | Dashboard: 50% coverage, red chips. Zoom on PF-008 (full PAN in logs) and PF-002 (the test asserts the wrong limit) | "Half the spec isn't proven. The limit is double what the spec allows, and a passing test locks the bug in. Full card numbers are being logged: a PCI violation. Green CI missed all of it." |
| 1:55–2:25 | Switch to 🔧 Remediator, `/remediate critical`; failing tests appear, then fixes, then green | "Remediator mode fixes each gap test-first: a failing test named after the requirement, then the smallest fix, then the whole suite." |
| 2:25–2:40 | Dashboard before → after: 50% → 100%; download the audit pack; a PR check going red when the refund window drifts | "Coverage goes from 50 to 100 percent, with a signed audit pack for the auditor, and the CI gate keeps it that way on every pull request." |
| 2:40–2:50 | Results table (time saved, accuracy, 4 bugs) + repo URL | "Weeks become minutes, and evidence replaces opinions. TraceProof, built with IBM Bob." |

**Production tips:** record at 1080p and speed up waiting segments 4–8× with a small "⏩ 6×" label. Zoom into the key chips. Record narration separately and keep it calm. Add captions. Put the 1:25 "PCI violation" reveal on the cover image too.
