---
name: weekly-review
description: The founder-ops cadence — a portfolio review across all projects under ~/Documents/Projects/ that updates each active project's roadmap, checks PRD success criteria and docs freshness, reviews the risk register, and picks the coming week's focus. Use when the user says "weekly review", "what should I work on", "portfolio check", "where is everything", or via the /weekly-review command.
---

# Weekly Review

The program-management layer for a solo founder: one deliberate pass instead of drifting between projects. Keep the whole thing to one focused conversation — this is a steering ritual, not an audit.

## Process

1. **Portfolio snapshot.** Run `python3 "${CLAUDE_PLUGIN_ROOT:-$HOME/Documents/Projects/_harness}/scripts/harness_status.py"` for the cross-project table. Note anything alarming (stale gates on a shipped project, heavy uncommitted changes).
2. **Per active project** (ask which are active rather than grinding through all of them):
   - `ROADMAP.md`: what moved out of "Now", what enters it. Stale "Now" items (3+ weeks) get demoted or a reason.
   - **Success-criteria check** (post-launch projects): fill a row in the ROADMAP table against the PRD's criteria, with real evidence — user reports, sales, store stats — not vibes.
   - **Risk register:** any "Review by" dates due? Re-accept, mitigate, or close each.
   - **Docs-freshness spot check:** skim the project `CLAUDE.md` stack/gotchas against reality (one targeted question — "is Firebase still listed but gone?" — not a re-read of the codebase). Stale claims get fixed now; they're cheap now and expensive mid-incident.
   - `COST_LOG.md` anomalies: a project quietly eating tokens is a signal.
3. **Cross-project decision.** End with one explicit priority call: which project gets the coming week's focus and why — trade-offs stated, not implied. Log it in that project's ROADMAP "Now".
4. Durable strategy shifts (pausing a project, killing an idea, pivoting) go to project memory; suggest `/sunset-project` when a project is actually done rather than letting it decay.

## Example

**Output (closing decision):** "Focus this week: Saarthi v1.0.35 download-stall fix (3 of 5 recent reviews hit it, and it blocks the success criterion 'first-run completion >80%'). Mandi-tracker stays paused — risk register updated, next review 2026-08-01. Docs drift fixed: removed the stale Firebase line from Saarthi's CLAUDE.md."
