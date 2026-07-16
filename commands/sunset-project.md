---
description: Deliberately wind down a project — user-data obligations, final release note, archive — instead of letting it silently decay
argument-hint: [project-name, defaults to current project]
---

Wind down the project named in `$ARGUMENTS` (or the current project). This is deliberate end-of-life, not deletion — nothing here removes code or data without explicit per-step confirmation.

## Process

1. Confirm intent: sunset means no further feature work and a final user-facing state. Restate what the project is and get an explicit yes before anything else.
2. **User obligations first.** If the app has users: what do they lose, and what do they get to keep? For local-data apps confirm data stays usable/exportable on-device after the app stops being updated. If there's any server component or store listing, plan the notice period and listing update. Draft the user-facing sunset notice if one is needed.
3. **Final release note.** Add a final entry to `docs/CHANGELOG.md` ("final release — project sunset, YYYY-MM-DD") and a closing section to `docs/OPERATIONS.md` stating support status going forward (e.g. "no further updates; critical security fixes only until <date>, then none").
4. **Roadmap close-out.** Mark `ROADMAP.md` items as closed/won't-do; move any still-valuable ideas to a note the user can carry to a future project.
5. **Record the decision.** Write a project-type memory entry: why it was sunset, what was learned, what a future revival would need to know. This is the part future-you actually reads.
6. Report what was done and what remains manual for the user (store listing changes, domain expiry, repo archival on the remote — all external actions stay theirs to confirm).
