# TraceProof: video edit plan (target 2:45, max 3:00)

Clips you have:
- **A** = `s6_audit_raw.mp4` (audit)
- **B** = `s7_remediation_raw.mp4` (remediation)
- **C** = new ~30 s screen recording of PR #1 (red check) and the Actions tab (green on main)

| Time | Visual | Voice-over (read calmly) |
|---|---|---|
| 0:00–0:10 | Terminal showing `11 passed` in green (clip A start, or type `cd demo\payflow; python -m pytest -q`) | "All eleven tests pass. CI is green. This payments service is ready to ship… right?" |
| 0:10–0:30 | Spec PDF (`demo/specs/PayFlow_SRS_v1.2.pdf`) zoomed on the requirements table, then slide 3 ("Slow · Stale · Wrong") | "In payments and banking, software must follow a written spec: numbered rules like 'refunds only within 30 days'. Before every release, auditors want proof that every rule is implemented and tested. Today that proof is a spreadsheet someone fills in by hand. It's slow, it's stale by the next commit, and it's often wrong, because teams assume passing tests mean the rules are met." |
| 0:30–0:37 | Title card: **TraceProof**, "Proof, not trust", "Built with IBM Bob" | "TraceProof does it in minutes, with IBM Bob." |
| 0:37–1:15 | Clip A at 4–6× speed: Compliance Auditor mode selected → `/audit` typed → "Used skill trace-audit" → MCP tools → verdicts appearing. Label on screen: "⏩ 6×" | "I pick my custom Compliance Auditor mode and run one command. Bob loads our trace-audit skill, reads the spec and the code, and checks each requirement literally, down to thresholds and error codes. Every verdict goes through our own MCP server, which rejects any file-and-line reference that doesn't exist, so Bob can't invent evidence." |
| 1:15–1:45 | Clip A, dashboard at 50%: zoom on PF-002 (green ✓ test but DRIFT), PF-008 VIOLATION | "Result: only half the spec is actually proven. Here, the test passes, but it asserts the wrong limit. And here, full card numbers are being written to logs. That's a PCI violation. Green CI missed all of it. Bob's verdicts matched our answer key: fourteen out of fourteen." |
| 1:45–2:15 | Clip B at 4–6×: Remediator mode → workstreams A/B/C → tests written → "27/27 pass" → table | "Now the Remediator mode fixes each gap test-first: a failing test named after the requirement, the smallest fix, then the whole suite. Twenty-seven of twenty-seven pass." |
| 2:15–2:30 | Clip B dashboard: 100%, "Coverage history 50% → 100%" | "Proven coverage goes from fifty to a hundred percent, with a signed audit pack ready for the auditor." |
| 2:30–2:42 | Clip C: PR #1 with red ❌ TraceProof check, then Details: "Coverage 92.9% below 100%" | "And it stays that way. When someone quietly changes the refund window back to sixty days, the TraceProof gate blocks the pull request." |
| 2:42–2:50 | End card: results table + github.com/TanishqCh07/traceproof | "Days become minutes, and evidence replaces assumptions. TraceProof, built with IBM Bob." |

## Editing in Clipchamp (built into Windows)

1. Create a new video at 16:9 and drag in clips A, B and C.
2. Trim each clip to the segments above. Select a clip, then **Speed** → 4× or 6× for the waiting parts.
3. Zoom into readable areas: select the clip, **Crop**, or **Transform** → scale 150–200%.
4. Add the title and end cards: **Text** or a Templates card with a dark background.
5. Record the voice-over: **Record & create** → **Audio**, or record on your phone and import it.
6. Add captions: **Captions** → Auto-generate (judges often watch muted).
7. Export at 1080p MP4 and check it's **3:00 or less**.
