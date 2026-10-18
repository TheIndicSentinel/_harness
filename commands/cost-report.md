---
description: Roll up session/token logs across all projects under ~/Documents/Projects/
disable-model-invocation: true
---

Build a rollup report from the harness's session logs. Note to the user that this log is best-effort (it depends on the SessionEnd hook firing, so it can miss sessions); the atlas "Work & Tokens" view reads the transcripts directly and is the primary source. Steps:

1. List every directory under `~/Documents/Projects/` except `_harness` itself.
2. For each one, read its log at `~/.claude/harness/cost/<project>.md` (or `$CLAUDE_HARNESS_DATA_DIR/cost/`); if that doesn't exist but a legacy `docs/COST_LOG.md` does, read that and say it hasn't been migrated. Extract the table rows (date, session id, active time, est. tokens).
   Legacy rows may carry a 5th "Cache read" column; never add it into the input total. Rows logged before the SessionEnd switch were written once per assistant turn with cumulative totals, so older months overcount — say so if a log includes them.
3. **Per task:** newer rows carry a `Branch` column (the git branch the session ended on). Where present, add a per-branch breakdown for each project — sessions and tokens per branch — and, if the project is a git repo, the number of commits on that branch not on the default branch (`git rev-list --count <default>..<branch>`) as a rough outcome column. A branch is a proxy for a task, not a measurement of one; say so, and don't invent per-task cost for rows without a branch.
   Newer rows also carry `Orient`: Read/Grep/Glob calls plus shell reads (`cat`, `sed`, `head`, `rg`, `grep`, `ls`, `find`) before the session's first edit. Rows written before 2026-10-16 count only Read/Grep/Glob, so do not mix the two in one trend. Report it only as a trend within one project and one kind of task (a median per branch or per month is fine); never compare it across projects or call it a score.
4. Print a per-project summary: number of sessions logged, and total estimated input/output tokens where parseable (skip `n/a` rows rather than treating them as zero, and say how many rows were skipped).
5. Project directories with no cost log yet just get a one-line "no sessions logged yet" note — don't treat that as an error.
6. End with this exact reminder, verbatim: "These are best-effort token estimates parsed from session transcripts. `/cost` gives Claude Code's own session estimate, which is closer but still not a guaranteed dollar-for-dollar match to your bill — see docs/OTEL.md in the harness root for the full ranking of sources by trust if you need an authoritative figure."

Keep the whole report compact — a per-project table is fine, don't dump raw log file contents.
