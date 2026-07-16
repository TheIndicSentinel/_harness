---
name: launch-checklist
description: Walks the current project's docs/RELEASE_CHECKLIST.md end to end, including ensuring the privacy_guardrails_review gate is passing for the current commit, and reports whether the release-gate hook will currently allow a real ship command. Use when the user asks "ready to launch", "pre-launch check", "can I ship this", or via the /ship command.
---

# Launch Checklist

This is the pre-launch walkthrough — the human-facing companion to the mechanical `release_gate.py` hook. Running this skill doesn't itself unblock anything (only a passing `privacy-guardrails-review` does that); this skill's job is to make sure that gate gets run, and to sanity-check everything else the hook can't check mechanically.

The report this produces should be **mechanically consistent** — the same facts, checked the same way, every time — not a different conversational summary each run. Get those facts from code, not from re-deriving them by hand each time.

## Process

1. **Pull the mechanical facts first.** Run `python3 "${CLAUDE_PLUGIN_ROOT:-$HOME/Documents/Projects/_harness}/scripts/harness_status.py" <project_name>`. This one call gives you: current HEAD, working-tree clean/dirty state, every gate's pass/fail/stale status, declared release commands, and the full project-health checklist (CI gate wired or not, release command documented, rollback runbook filled, budget set-or-skipped, connectors reviewed). Don't re-derive any of this by reading files by hand — read it from this output.
2. **Gate check.** From that output: for each required gate that's missing, failing, or stale, run the matching skill now (`privacy-guardrails-review`, `qa-review`, `compliance-review`) rather than telling the user to go run it separately.
3. **Dirty-tree check.** From the same output's git state: if uncommitted changes exist, `release_gate.py` will block regardless of gate status — say so explicitly, and tell the user to commit or stash before shipping.
4. **CI-wiring check.** If the project uses GitHub Actions releases, report the project-health "CI gate wired" line as-is — "not present," "present but not wired," or "wired into X" all mean something different, don't collapse them into one line.
5. **Changelog/version freshness.** Check `docs/CHANGELOG.md`'s `[Unreleased]` section — if it has real entries, run `release-notes` before shipping (or note explicitly that this release intentionally skips it, e.g. a hotfix).
6. Walk the remaining items conversationally — these aren't code-derivable, so ask/confirm rather than assume:
   - Secrets spot-check (the `secrets_guard` hook only catches attempted edits, not what's already committed)
   - Marketing/GTM plan reviewed (point at `gtm-marketing` / `docs/MARKETING.md` if not done)
   - Support channel ready (`docs/OPERATIONS.md`)
   - Post-launch success-criteria review scheduled (`docs/ROADMAP.md` table — first check ~2 weeks out)
7. Report one structured status combining steps 1–6: current commit, clean/dirty, every gate, CI-wiring state, changelog state, rollback path, and the conversational items — then an explicit final verdict on whether `release_gate.py` will currently allow a matched release command to proceed.

## Example

**Output (final status report):**
```
Project: kisan-app @ a3f9c21 (working tree: clean)

Gates:
- [x] privacy_guardrails_review: pass (current)
- [ ] qa_review: STALE (new commits since last review) — run qa-review

CI gate: wired into release.yml
Changelog: [Unreleased] has 3 entries — run release-notes before tagging
Rollback: confirmed in OPERATIONS.md (previous APK kept at ~/releases/)

Remaining (conversational):
- [ ] Crash/error monitoring: not set up, no reason given — resolve before shipping
- [x] Marketing/GTM: reviewed
- [x] Support channel: GitHub Issues linked in-app

Clear to ship: NO — blocked on qa_review (stale) and crash monitoring.
Outstanding, in order: re-run qa-review, set up crash monitoring, run release-notes, then re-check.
```

## Scope
This skill checks readiness — it does not run the actual release command itself. That stays a separate, explicitly-confirmed action (see `/ship`).
