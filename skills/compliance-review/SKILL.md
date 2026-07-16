---
name: compliance-review
description: Legal/compliance pass for the current project — privacy policy vs. actual code behavior, terms of service, store policy obligations, applicable regulation (DPDP/GDPR), third-party licenses, and a basic accessibility check — recorded in docs/COMPLIANCE.md and as a compliance_review gate result. Use when the user asks "am I legally covered", "check compliance", "store policy check", "license audit", or before a first store submission.
---

# Compliance Review

Fills and re-verifies `docs/COMPLIANCE.md` (template: `templates/new-project/docs/COMPLIANCE.md` in the harness root — `$CLAUDE_PLUGIN_ROOT` if installed as a plugin, otherwise `~/Documents/Projects/_harness` — create it from that shape if missing). Records a `compliance_review` gate entry — advisory by default, hard-gated if the project adds it to `required_gates` in `.harness/gates.json`. Proportionate to a solo indie product: real obligations, not enterprise compliance theater.

## Process

1. **Privacy policy vs. reality.** Confirm a privacy policy exists (file or URL). Verify its claims against actual code behavior — cross-reference the latest `privacy-guardrails-review` findings in project memory instead of re-scanning code. A policy that overclaims ("we collect nothing") against real behavior (a debug log, a pack-update fetch) fails this review.
2. **Store/platform obligations.** For the target store(s): data-safety/privacy-label answers consistent with the policy, account-deletion requirements if there are accounts, content-rating honesty.
3. **Regulation triage.** Decide what applies from user base + data touched (India market → DPDP Act; EU users → GDPR; minors → consent rules). For on-device-only apps the position is usually short — write it down anyway; "considered, minimal obligations because X" is the artifact.
4. **Licenses.** Enumerate direct dependencies' licenses (from lockfile/version catalog). Flag copyleft in shipped code and any attribution-notice requirements.
5. **Accessibility quick pass.** Main flows only: contrast, touch-target size, screen-reader labels. Gaps go to `ROADMAP.md`, not into a blocked release — a11y findings are follow-ups unless egregious.
6. Update `docs/COMPLIANCE.md` with dates/commits, record the gate: `python3 "${CLAUDE_PLUGIN_ROOT:-$HOME/Documents/Projects/_harness}/hooks/gate_write.py" <project_root> compliance_review <pass|fail> "<summary>"`, and save durable decisions (e.g. "DPDP position: X because Y") to project memory.

## What fails this review
A missing privacy policy on a store-bound build; a policy claim the code contradicts; a copyleft license in shipped code with no compliance plan. Most other findings are recorded follow-ups, not blockers.
