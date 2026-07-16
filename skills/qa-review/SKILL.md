---
name: qa-review
description: Runs the project's QA pass — tests, lint, changed-surface verification, and a dependency vulnerability check — and records a qa_review gate result. Use when the user asks "run QA", "is this tested enough", "quality check before release", before shipping a nontrivial change, or as a step inside launch-checklist / /ship.
---

# QA Review

The engineering-quality counterpart to `privacy-guardrails-review`. It records a `qa_review` entry in `.harness/gates.json` — advisory by default; a project opts into hard-gating it by adding `"qa_review"` to the `required_gates` list in that file (then `release_gate.py` blocks ship commands until it passes for the current commit).

## Process

1. Confirm the working tree is committed (gates are tied to a commit — same rule as the privacy review).
2. **Run what the project defines.** Test/lint commands come from the project's `CLAUDE.md` "Key commands" section — don't guess or invent. Run tests, then lint. Capture real output; a skipped suite is reported as skipped, never as passed.
3. **Exercise the change, not just the suite.** For the surfaces changed since the last release, use the built-in `verify` skill's approach: drive the affected flow end-to-end where possible, don't stop at green unit tests.
4. **Dependency check.** Run the ecosystem's audit tool if available (`npm audit`, `pip-audit`, `cargo audit`; for Gradle, check if a dependency-check task is configured — if none exists, note that as a gap, don't fabricate a result). Flag known-vulnerable versions in shipped code paths.
5. Judge the result: failures in production code paths fail the gate; a flaky test or a dev-only advisory is judgment territory — decide, and say why.
6. Record: `python3 "${CLAUDE_PLUGIN_ROOT:-$HOME/Documents/Projects/_harness}/hooks/gate_write.py" <project_root> qa_review <pass|fail> "<one-line summary>"`.
7. If the project hard-gates QA (or the user wants to), mention `required_gates` — but never edit it to *remove* a gate to unblock a ship.

## Example

**Output:** "QA: PASS. 148/148 unit tests green (`./gradlew testDebugUnitTest`), lint clean, drove the changed download-resume flow on-device via the run skill. Dependency check: no audit task configured for Gradle — noted as a gap in ROADMAP.md, not counted against the gate. Recorded qa_review=pass at commit 3f2ab91."

## On a FAIL
Same rule as the privacy gate: don't record pass to unblock the user. Report exactly what failed, with output, and what needs to change.
