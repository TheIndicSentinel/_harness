---
name: support-triage
description: Turns raw user feedback — bug reports, reviews, feature requests, support emails — into triaged decisions in docs/OPERATIONS.md, roadmap items, and drafted replies. Use when the user pastes feedback or bug reports, says "users are saying X", "triage my inbox/reviews", or wants to synthesize what users actually need.
---

# Support Triage

Intake → classify → decide → (optionally) reply. The intake record lives in `docs/OPERATIONS.md` ("Feedback / bug triage log"); accepted work moves to `ROADMAP.md`. This doubles as lightweight user research: patterns across entries are signal the PRD's assumptions can be checked against.

## Process

1. For each piece of feedback: classify `bug` / `feature` / `question`, and judge severity/frequency (one user annoyed ≠ ten users blocked).
2. Log one row per item in the OPERATIONS.md triage table with a decision: `fix now` (→ ROADMAP "Now"), `backlog` (→ "Next/Later"), `won't do` (with the reason recorded — future-you will re-litigate otherwise), or `answered`.
3. Crash/debug logs attached to reports get normal debugging; if it's a live-release fire, switch to the `incident-response` skill instead of triaging it as a row.
4. Draft replies when asked — plain, honest about timelines, no committing to dates the user hasn't agreed to. Sending is the user's action, not yours.
5. **Pattern check** (when processing a batch): 3+ entries pointing at the same friction is a finding — say so explicitly, check it against the PRD's success criteria and target-user assumptions, and suggest a ROADMAP entry or a PRD correction rather than three separate fixes.

## Example

**Input:** five pasted Play Store reviews.

**Output:** "Logged 5 rows in OPERATIONS.md. Pattern: 3 of 5 mention the model download stalling on mobile data — that's your top friction, added to ROADMAP Now (the other two: one feature request → Later, one 5-star). Drafted a reply for the 1-star review asking for the debug log via the in-app report flow — ready to paste if you approve."
