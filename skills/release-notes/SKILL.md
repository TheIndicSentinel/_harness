---
name: release-notes
description: Version bump, CHANGELOG.md update from git history, and user-facing release notes for the current project. Use when the user says "cut a release", "bump the version", "update the changelog", "write release notes", or when launch-checklist finds the changelog stale.
---

# Release Notes

Maintains `docs/CHANGELOG.md` (Keep a Changelog format; create from the harness template if missing) and drafts the user-facing notes. This is the paper trail between releases — it's also what makes rollback targets identifiable.

## Process

1. Find the last released version: latest tag (`git tag --sort=-v:refname`) or the top released section of `CHANGELOG.md`. If they disagree, flag it — don't silently pick one.
2. Read `git log <last>..HEAD --oneline` and sort commits into Added/Changed/Fixed. Write entries for a *user*, not a committer — "Reminders now fire on time on Samsung devices", not the commit subject. Internal-only changes (CI, refactors) get one line or none.
3. Recommend the bump per semver (breaking/user-visible behavior → MAJOR, feature → MINOR, fix → PATCH) and confirm with the user. Update the version wherever this project defines it (check `CLAUDE.md` — e.g. `versionName`/`versionCode` in Gradle).
4. Rename `[Unreleased]` to the new version + date; open a fresh `[Unreleased]` block.
5. Draft the user-facing notes (store listing "what's new" / GitHub release body) — shorter and plainer than the changelog, no internal jargon.
6. Tagging and publishing stay explicit user-confirmed actions; note that a tag push is a ship command and will hit the release gate.

## Example

**Changelog entry (good):** "### Fixed — Model downloads now resume correctly after a network drop instead of restarting from zero."
**Not this:** "fix(download): handle HTTP 416 on stale Range header".
