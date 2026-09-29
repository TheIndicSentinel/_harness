# {{PROJECT_NAME}} — Session / Cost Log

Auto-appended by the harness's SessionEnd hook (one line per Claude Code session ended with cwd in this project). "in" is uncached input plus cache writes; cache reads (billed at a small fraction of the input rate) get their own column and are excluded from the monthly budget. Token counts are a best-effort estimate parsed from the session transcript, not an authoritative dollar figure — see `docs/OTEL.md` in the harness root for the full ranking of sources (this log, OTel, and the Admin API, in order of trust — OTel's own cost metric is also an approximation, not authoritative). Optional monthly token budget: `python3 hooks/budget_write.py <project_root> <tokens>` (harness root) — `harness-status` and session start will flag 50/80/100% crossings.

| Date | Session ID | Duration | Est. tokens (in/out) | Cache read |
|------|-----------|----------|------------------------|------------|

## Cost per useful outcome (optional, manual)
Raw token counts don't say whether the spend was worth it. Fill this in at a release or a `weekly-review`, not automatically — "useful outcome" is a per-project judgment call (a shipped release, an accepted PR, a resolved support item, a qualified lead), not something the harness can infer.

| Period | Tokens spent | Outcome | Notes |
|--------|-------------|---------|-------|
