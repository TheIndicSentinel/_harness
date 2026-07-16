# Token/cost tracking: four sources, in order of trust (optional, off by default)

`session_log.py` (the Stop hook) gives every project a best-effort, zero-infrastructure token estimate by parsing the session transcript. That's the default and it stays the default — it needs no setup and produces the per-project `docs/COST_LOG.md` rollups `/cost-report` reads. It is **not** authoritative, and neither — despite what an earlier version of this file said — is OpenTelemetry. Anthropic's own documentation describes Claude Code's OTel cost metric as an approximation; the billing provider is the actual authority. Use this ranking:

1. **`session_log.py` / `COST_LOG.md` (this harness's default):** a local, client-side, best-effort estimate parsed from the session transcript. Good for trend-spotting and the per-project rollup `/cost-report` reads. Not a dollar figure to trust.
2. **OpenTelemetry (`claude_code.token.usage`, `claude_code.cost.usage`):** richer, more structured operational telemetry than the transcript parser — but Anthropic's own docs call the cost metric an *approximation*, not authoritative. Better than (1) for volume/shape of usage; still not the number to reconcile a bill against.
3. **Anthropic Admin API / Console usage report:** the actual authoritative source for API usage, if you have organization/workspace admin access — billing-system-derived, broken down by workspace, API key, model, and service tier. This harness doesn't integrate with it (no admin/org credentials to build or test against, and this harness governs Claude Code usage only — see the README's scope section) — but if you have that access, trust this over (1) and (2).
4. **Claude subscription usage (Claude.ai, Claude Code under a Pro/Max/Team plan):** a **separate billing domain**, not a per-request API dollar cost — don't represent subscription usage as if it were metered API spend; they're different products with different accounting. Anthropic's own account/subscription usage views are the source for this, not anything in this file.

## Why OTel is off by default
This harness's own non-negotiable default is "no telemetry, analytics, or data collection beyond what a feature explicitly requires" (see the umbrella CLAUDE.md). Enabling OTel unconditionally would violate that rule. So: **it's documented here, not switched on anywhere.** Turning it on is an explicit, per-machine choice you make — and even then, point it at a local exporter so nothing leaves the machine, consistent with the harness's privacy-by-default posture.

## Enabling OTel (locally, nothing leaves your machine)
Set these environment variables (e.g. in your shell profile, or a project's `.env` if your workflow supports that — never commit them):

```bash
export CLAUDE_CODE_ENABLE_TELEMETRY=1
export OTEL_METRICS_EXPORTER=console        # prints metrics to stderr — simplest, fully local
# or, to send to a local collector you run yourself:
# export OTEL_METRICS_EXPORTER=otlp
# export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318
```

`console` requires zero additional infrastructure and is the right starting point. `otlp` needs a collector (e.g. a local `otel-collector` container) — only reach for that if you actually want to query historical metrics later (Prometheus, Grafana, etc.), which is more infrastructure than most solo projects need.

## What OTel does and doesn't replace
- **Improves on:** the transcript parser's fragility (`session_log.py` depends on an undocumented JSONL shape) and gives richer per-call telemetry.
- **Does NOT replace:** the per-project `docs/COST_LOG.md` rollup that `/cost-report` reads — OTel metrics aren't natively scoped to "which harness project." Keep `session_log.py` running either way.
- **Does NOT replace:** the Admin API, for an actual dollar figure — see tier 3 above.

## Reference
Full environment variable list and metric names: run `claude --help` or see Claude Code's own telemetry documentation — this file intentionally doesn't duplicate the full spec, since that's Anthropic's to keep current, not this harness's.
