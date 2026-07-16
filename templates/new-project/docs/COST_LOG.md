# {{PROJECT_NAME}} — Session / Cost Log

Auto-appended by the harness's Stop hook (one line per Claude Code session ended with cwd in this project). Token counts are a best-effort estimate parsed from the session transcript, not an authoritative dollar figure — cross-check `/cost` for that, or see `docs/OTEL.md` in the harness root for an authoritative alternative. Optional monthly token budget: `python3 hooks/budget_write.py <project_root> <tokens>` (harness root) — `harness-status` and session start will flag 50/80/100% crossings.

| Date | Session ID | Duration | Est. tokens (in/out) |
|------|-----------|----------|------------------------|

## Cost per useful outcome (optional, manual)
Raw token counts don't say whether the spend was worth it. Fill this in at a release or a `weekly-review`, not automatically — "useful outcome" is a per-project judgment call (a shipped release, an accepted PR, a resolved support item, a qualified lead), not something the harness can infer.

| Period | Tokens spent | Outcome | Notes |
|--------|-------------|---------|-------|
