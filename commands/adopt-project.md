---
description: Retrofit an existing project (that predates the harness) with the missing docs — never overwrites anything that already exists
argument-hint: [path, defaults to current project]
---

Bring an existing project under the harness's projects root (defaults to `~/Documents/Projects/`; overridable via `CLAUDE_HARNESS_PROJECTS_ROOT`) into the harness. Target directory: `$ARGUMENTS` if given, otherwise the project root of the current working directory (walk up to the first directory directly under the projects root if cwd is nested deeper).

This command is purely additive — never overwrite, edit, or touch a file that already exists. Its whole point is to be safe to run on a project with real, valuable existing docs (e.g. one that already has its own detailed `RELEASE_CHECKLIST.md`).

## Process

1. Confirm the target is a directory under the projects root (not `_harness` itself). If it's not a git repo yet, run `git init` there (this doesn't touch any existing file, just adds `.git/`) — mention this happened, don't ask permission for it specifically since it's non-destructive.
2. For each of these, check if it already exists; if and only if it's missing, create it from the matching file in `templates/new-project/docs/` in the harness root (`$CLAUDE_PLUGIN_ROOT` if installed as a plugin, otherwise `~/Documents/Projects/_harness`), filling `{{PROJECT_NAME}}` (directory basename), `{{DATE}}` (today), and `{{ONE_LINE_IDEA}}` (pull from the project's existing `CLAUDE.md` "What this product is" section if there is one, otherwise ask the user for a one-liner rather than inventing one):
   - `docs/PRD.md`
   - `docs/MARKETING.md`
   - `docs/COST_LOG.md`
   - `docs/RELEASE_CHECKLIST.md`
   - `docs/ROADMAP.md`
   - `docs/CHANGELOG.md`
   - `docs/OPERATIONS.md`
   - `docs/BUSINESS.md`
   - `docs/COMPLIANCE.md`
   - `docs/CONNECTORS.md`
   - `.github/workflows/harness-gate-check.yml` (only if the project already uses GitHub Actions and doesn't have this file — it's an inert reusable workflow until another workflow calls it, so it's safe to add even if unused yet; see `docs/CI_GATE_CHECK.md` in the harness root for wiring instructions)
3. Do not touch the project's own `CLAUDE.md` under any circumstances — it stays exactly as the project already has it.
4. Do not create or modify `.harness/gates.json` — that gets created automatically the first time `privacy-guardrails-review` records a result.
5. Report clearly, as two lists: files created, and files that already existed and were left untouched. Then suggest next steps: `prd-writer` to flesh out a freshly-created `docs/PRD.md`, or `privacy-guardrails-review` directly if the project is close to shipping and docs are already solid.
