---
description: Roll up session/token logs across all projects under ~/Documents/Projects/
---

Build a rollup report from the harness's session logs:

1. List every directory under `~/Documents/Projects/` except `_harness` itself.
2. For each one that has a `docs/COST_LOG.md`, read it and extract the log table rows (date, session id, duration, est. tokens).
   Rows have an optional 5th "Cache read" column (added with the SessionEnd switch); report it separately, never add it into the input total. Rows logged before that switch were written once per assistant turn with cumulative totals, so older months overcount — say so if a project's log includes them.
3. Print a per-project summary: number of sessions logged, and total estimated input/output tokens where parseable (skip `n/a` rows rather than treating them as zero, and say how many rows were skipped).
4. Project directories with no `docs/COST_LOG.md` yet just get a one-line "no sessions logged yet" note — don't treat that as an error.
5. End with this exact reminder, verbatim: "These are best-effort token estimates parsed from session transcripts. `/cost` gives Claude Code's own session estimate, which is closer but still not a guaranteed dollar-for-dollar match to your bill — see docs/OTEL.md in the harness root for the full ranking of sources by trust if you need an authoritative figure."

Keep the whole report compact — a per-project table is fine, don't dump raw log file contents.
