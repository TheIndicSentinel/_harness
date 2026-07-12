---
description: Retrofit an existing project (that predates the harness) with the missing docs — never overwrites anything that already exists
argument-hint: [path, defaults to current project]
---

Bring an existing project under `~/Documents/Projects/` into the harness. Target directory: `$ARGUMENTS` if given, otherwise the project root of the current working directory (walk up to the first directory directly under `~/Documents/Projects/` if cwd is nested deeper).

This command is purely additive — never overwrite, edit, or touch a file that already exists. Its whole point is to be safe to run on a project with real, valuable existing docs (e.g. one that already has its own detailed `RELEASE_CHECKLIST.md`).

## Process

1. Confirm the target is a directory under `~/Documents/Projects/` (not `_harness` itself). If it's not a git repo yet, run `git init` there (this doesn't touch any existing file, just adds `.git/`) — mention this happened, don't ask permission for it specifically since it's non-destructive.
2. For each of these, check if it already exists; if and only if it's missing, create it from the matching file in `~/Documents/Projects/_harness/templates/new-project/docs/`, filling `{{PROJECT_NAME}}` (directory basename), `{{DATE}}` (today), and `{{ONE_LINE_IDEA}}` (pull from the project's existing `CLAUDE.md` "What this product is" section if there is one, otherwise ask the user for a one-liner rather than inventing one):
   - `docs/PRD.md`
   - `docs/MARKETING.md`
   - `docs/COST_LOG.md`
   - `docs/RELEASE_CHECKLIST.md`
3. Do not touch the project's own `CLAUDE.md` under any circumstances — it stays exactly as the project already has it.
4. Do not create or modify `.harness/gates.json` — that gets created automatically the first time `privacy-guardrails-review` records a result.
5. Report clearly, as two lists: files created, and files that already existed and were left untouched. Then suggest next steps: `prd-writer` to flesh out a freshly-created `docs/PRD.md`, or `privacy-guardrails-review` directly if the project is close to shipping and docs are already solid.
