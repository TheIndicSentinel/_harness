# OpenTelemetry token/cost tracking (optional, off by default)

`session_log.py` (the Stop hook) gives every project a best-effort, zero-infrastructure token estimate by parsing the session transcript. That's the default and it stays the default — it needs no setup and produces the per-project `docs/COST_LOG.md` rollups `/cost-report` reads.

Claude Code also natively supports exporting **authoritative** usage/cost metrics via OpenTelemetry. This is the official mechanism to reach for if `session_log.py`'s transcript parsing ever breaks (it depends on an undocumented JSONL shape) or if you want real dollar figures instead of estimates.

## Why this is off by default
This harness's own non-negotiable default is "no telemetry, analytics, or data collection beyond what a feature explicitly requires" (see the umbrella CLAUDE.md). Enabling OTel unconditionally would violate that rule. So: **it's documented here, not switched on anywhere.** Turning it on is an explicit, per-machine choice you make — and even then, point it at a local exporter so nothing leaves the machine, consistent with the harness's privacy-by-default posture.

## Enabling it (locally, nothing leaves your machine)
Set these environment variables (e.g. in your shell profile, or a project's `.env` if your workflow supports that — never commit them):

```bash
export CLAUDE_CODE_ENABLE_TELEMETRY=1
export OTEL_METRICS_EXPORTER=console        # prints metrics to stderr — simplest, fully local
# or, to send to a local collector you run yourself:
# export OTEL_METRICS_EXPORTER=otlp
# export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318
```

`console` requires zero additional infrastructure and is the right starting point. `otlp` needs a collector (e.g. a local `otel-collector` container) — only reach for that if you actually want to query historical metrics later (Prometheus, Grafana, etc.), which is more infrastructure than most solo projects need.

## What this does and doesn't replace
- **Replaces:** the "best-effort estimate" caveat on token counts — OTel's `claude_code.token.usage` and `claude_code.cost.usage` metrics are authoritative.
- **Does NOT replace:** the per-project `docs/COST_LOG.md` rollup that `/cost-report` reads. OTel metrics aren't natively scoped to "which harness project" the way this harness's own directory-based tracking is — turning OTel on gives you a second, more accurate source to cross-check against, not a drop-in replacement for `/cost-report`. Keep `session_log.py` running either way.

## An even more authoritative option: the Anthropic Admin API
If you use Claude Code (or the Anthropic API directly) under an organization/workspace with Console admin access, Anthropic's Admin API usage report is more authoritative than either OTel or `session_log.py` — it's billing-system-derived, broken down by workspace, API key, model, and service tier, not client-side telemetry. This harness doesn't integrate with it (no admin/org credentials to build or test against, and this harness governs Claude Code usage only — see the README's scope section), but if you have that access, it's the number to trust over anything in this file. Check Anthropic's Console documentation for current endpoint details.

## Reference
Full environment variable list and metric names: run `claude --help` or see Claude Code's own telemetry documentation — this file intentionally doesn't duplicate the full spec, since that's Anthropic's to keep current, not this harness's.
