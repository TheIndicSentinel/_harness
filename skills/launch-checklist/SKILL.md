---
name: launch-checklist
description: Walks the current project's docs/RELEASE_CHECKLIST.md end to end, including ensuring the privacy_guardrails_review gate is passing for the current commit, and reports whether the release-gate hook will currently allow a real ship command. Use when the user asks "ready to launch", "pre-launch check", "can I ship this", or via the /ship command.
---

# Launch Checklist

This is the pre-launch walkthrough — the human-facing companion to the mechanical `release_gate.py` hook. Running this skill doesn't itself unblock anything (only a passing `privacy-guardrails-review` does that); this skill's job is to make sure that gate gets run, and to sanity-check everything else the hook can't check mechanically.

## Process

1. Locate `docs/RELEASE_CHECKLIST.md` in the current project. If it doesn't exist, use the template shape from `~/Documents/Projects/_harness/templates/new-project/docs/RELEASE_CHECKLIST.md`.
2. **Gate check first.** Check whether `privacy_guardrails_review` is passing for the current commit (read `.harness/gates.json`, compare `reviewed_commit` to `git rev-parse HEAD`). If missing or stale, run the `privacy-guardrails-review` skill now rather than telling the user to go run it separately.
3. Walk the remaining checklist items conversationally — these aren't code-verifiable, so ask/confirm rather than assume:
   - Secrets check (spot-check, the `secrets_guard` hook only catches attempted edits, not what's already committed)
   - Crash/error monitoring in place, or explicitly deferred with a reason
   - Rollback plan if the release breaks something
   - Marketing/GTM plan reviewed (point at `gtm-marketing` skill / `docs/MARKETING.md` if not done yet)
   - Support channel ready for feedback/bug reports
4. Report a clear final status: which items are done, which are outstanding, and an explicit statement of whether `release_gate.py` will currently allow a matched release command to proceed (it will, if and only if step 2 ended in a fresh pass).

## Example

**Output (final status report):**
```
Clear to ship: NO — blocked.
- [x] privacy_guardrails_review: pass (current, commit a3f9c21)
- [ ] Crash/error monitoring: not set up, no reason given — resolve before shipping
- [x] Rollback plan: confirmed (previous APK kept for manual rollback)
- [ ] Marketing/GTM: not started — run gtm-marketing, not release-blocking but do it before announcing
- [x] Support channel: GitHub Issues linked in-app

Outstanding, in order: set up crash monitoring, then re-run this checklist.
```

## Scope
This skill checks readiness — it does not run the actual release command itself. That stays a separate, explicitly-confirmed action (see `/ship`).
