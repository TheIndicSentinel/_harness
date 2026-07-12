---
description: Roll up session/token logs across all projects under ~/Documents/Projects/
---

Build a rollup report from the harness's session logs:

1. List every directory under `~/Documents/Projects/` except `_harness` itself.
2. For each one that has a `docs/COST_LOG.md`, read it and extract the log table rows (date, session id, duration, est. tokens).
3. Print a per-project summary: number of sessions logged, and total estimated input/output tokens where parseable (skip `n/a` rows rather than treating them as zero, and say how many rows were skipped).
4. Project directories with no `docs/COST_LOG.md` yet just get a one-line "no sessions logged yet" note — don't treat that as an error.
5. End with this exact reminder, verbatim: "These are best-effort token estimates parsed from session transcripts, not authoritative dollar costs — run `/cost` in a session for the real figure."

Keep the whole report compact — a per-project table is fine, don't dump raw log file contents.
