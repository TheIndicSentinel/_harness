---
name: privacy-guardrails-review
description: Runs a privacy and guardrails review of the current project and records a pass/fail gate that the harness's release-gate hook checks before allowing any publish/deploy/release command to run. Use whenever the user asks for a "privacy review", "guardrails review", "is this safe to ship", or as a prerequisite step inside launch-checklist / /ship. This is a hard gate, not just advice — a failing or missing review here mechanically blocks shipping.
---

# Privacy & Guardrails Review

This is the review that the harness's `release_gate.py` hook checks before it allows a real publish/deploy/release command to run (see `~/Documents/Projects/CLAUDE.md`). Do not treat this as a formality — the gate is only as good as this review is honest.

## Process

1. Confirm you're inside a project under `~/Documents/Projects/` that's a git repo (the gate is tied to a commit hash — an uncommitted working tree can't be gated meaningfully; tell the user to commit first if there are uncommitted changes relevant to what's being reviewed).
2. Launch the `security-privacy-auditor` subagent to do the actual code scan (data collection points, hardcoded secrets, unguarded input surfaces, guardrail gaps — see that agent's definition for the full list). Let it do the context-heavy file reading; don't duplicate that work in the main thread.
3. Read the subagent's verdict and findings. You make the final PASS/FAIL call, not the subagent — use its findings as input, but apply judgment (e.g. a finding in a test fixture file isn't the same severity as one in production code).
4. Record the result:
   ```
   python3 ~/Documents/Projects/_harness/hooks/gate_write.py <project_root> privacy_guardrails_review <pass|fail> "<one-line summary>"
   ```
   Always use this script rather than hand-writing `.harness/gates.json` — it stamps the current commit hash automatically, which is what makes the gate detect stale reviews after new commits.
5. Report back to the user: PASS/FAIL, the findings that mattered, and — if FAIL — the specific fixes needed before re-running this skill.

## On a FAIL
Don't record a "pass" to unblock the user faster. The entire point of a hard gate is that it can't be talked around. If the user pushes back on a finding, that's a conversation about whether the finding is actually right (re-examine it, maybe it's a false positive) — not a reason to record pass anyway.
