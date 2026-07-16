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
   - `COST_LOG.md` anomalies: a project quietly eating tokens is a signal. If a monthly budget is set (`harness-status` shows it), note whether it's on track. If a release happened this period, consider filling in `COST_LOG.md`'s "Cost per useful outcome" row — optional, manual, only worth doing when there's a real outcome to attach a number to.
   - **Explicit continue/pause/pivot/sunset call.** For every project reviewed this session, not just the one that wins focus — pick one: **continue** (as-is priority, may or may not be this week's focus), **pause until <date>** (deliberately parked, with a re-check date so it doesn't just silently rot), **pivot** (the idea or approach is changing — say what, briefly), or **sunset** (actually done or dead — run `/sunset-project`, don't just let it decay). This is the direct answer to the largest solo-founder cost: not token spend, but attention scattered across too many half-active projects. A project that's genuinely fine getting "continue" every week is a healthy signal, not busywork — the point is that the call gets made out loud, not skipped.
3. **Cross-project decision.** End with one explicit priority call: which project gets the coming week's focus and why — trade-offs stated, not implied. Log it in that project's ROADMAP "Now".
4. Record every continue/pause/pivot/sunset call from step 2 — durable ones (pause, pivot, sunset) go to that project's memory with the reason; "continue" doesn't need a memory entry unless something about the reasoning changed since last time. Actually run `/sunset-project` for a real sunset call rather than just noting the decision and moving on.

## Example

**Output (per-project calls + closing decision):**
```
Saarthi: continue. Focus this week: v1.0.35 download-stall fix (3 of 5 recent
reviews hit it, and it blocks the success criterion "first-run completion >80%").

Mandi-tracker: pause until 2026-08-01. No user traction signal yet and it's
competing for attention with Saarthi's active bug; risk register updated,
memory entry recorded with the reasoning.

Kavach: sunset. Hasn't moved in 6 weeks, no clear next step, and the idea it
validated turned out not to hold up. Running /sunset-project now.

Focus this week: Saarthi's download-stall fix (above). Docs drift fixed:
removed the stale Firebase line from Saarthi's CLAUDE.md.
```
