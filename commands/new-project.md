---
description: Scaffold a new project under ~/Documents/Projects/ from the harness template
argument-hint: <name> "<one-line idea>"
---

Scaffold a new project. Arguments: `$ARGUMENTS` — first token is the project name (filesystem-safe: letters, digits, hyphens, underscores only), the rest (optionally quoted) is a one-line idea description.

Do this directly, don't ask for confirmation on each step (creating a new local directory + local git init is low-risk and reversible):

1. Parse the name and idea from `$ARGUMENTS`. If no name was given, ask for one before proceeding.
2. Target directory: `~/Documents/Projects/<name>/`. If it already exists, stop and tell the user instead of overwriting anything.
3. Copy every file from `~/Documents/Projects/_harness/templates/new-project/` into the target directory, preserving the `docs/` subfolder structure.
4. In every copied file, replace the placeholders `{{PROJECT_NAME}}` with the name, `{{ONE_LINE_IDEA}}` with the idea (or `TBD` if none was given), and `{{DATE}}` with today's date (`YYYY-MM-DD`).
5. Run `git init` inside the new project directory (local only — no remote, do not push or create a remote).
6. Stage everything and make one commit: `Scaffold <name> via /new-project`.
7. Report back: the path created, and a short "next steps" list (fill in Stack/Structure in CLAUDE.md, flesh out docs/PRD.md, come back to `/new-project` template if you want to change the skeleton for future projects).
