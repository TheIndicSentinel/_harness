---
description: Run the pre-launch checklist (including the privacy/guardrails gate) and report whether the project is clear to release
---

Run the `launch-checklist` skill against the current project. That skill ensures the `privacy_guardrails_review` gate is passing for the current commit (running `privacy-guardrails-review` now if it's missing or stale), then walks the remaining checklist items.

Report back clearly:
- Overall status: clear to ship, or blocked (and on what)
- If clear: name the actual release command for this project (check `docs/OPERATIONS.md`'s "Release command" field first, then `.harness/gates.json`'s declared `release_commands`, then the project's own `CLAUDE.md` "Key commands" section) and say the harness's release-gate hook will now allow it — but do not run it yourself. Deploy/publish/release actions always get an explicit confirmation in the same turn they're run, regardless of gate status; a passing gate means the hook won't block it, not that it's pre-approved to run unattended.
- If blocked: the specific outstanding items, in the order to tackle them.
