# Solo-Founder Harness

A full-lifecycle **Claude Code** harness for solo/indie founders building privacy-first, guardrail-first software — idea through sunset, with a release gate that's mechanically enforced, not just advice.

## Scope (read this before assuming more than it does)
This is a **Claude Code solo-founder project harness** — not a general Anthropic governance, monitoring, or token-accounting platform. It has no visibility into and does not govern: the Messages API used directly or via an SDK, Bedrock/Vertex, Claude.ai (web/subscription), Claude Desktop, Claude for Sheets, other extensions, or MCP connectors used outside Claude Code. Its release gate (`release_gate.py`) only sees Bash commands and MCP tool calls made *through Claude Code* — it cannot see or block a deploy triggered any other way. If you build a product that calls the Anthropic API directly, or operate in an organization with multiple engineers, most of this harness's assumptions (one operator, one machine, git as the audit trail) stop holding and a different design is warranted.

Covers: idea validation, market research, PRD writing, QA, legal/compliance, release notes, launch checklists, incident response, support triage, pricing, weekly portfolio review, and end-of-life — each backed by a Claude Code skill, and the ship-blocking gate backed by an actual `PreToolUse` hook, not a prompt someone can talk past.

## Install (Claude Code plugin)

```
/plugin marketplace add TheIndicSentinel/_harness
/plugin install solo-founder-harness
```

Then run `/harness-init` once — a plugin install doesn't auto-load an always-on CLAUDE.md the way this repo's own symlink-based install does, so `/harness-init` sets that up deliberately (projects-root location, the non-negotiable-defaults block) instead of leaving it silently missing.

## What you get

| Layer | Skills / commands |
|---|---|
| Idea → spec | `idea-brainstorm`, `market-research`, `prd-writer` |
| Build quality | `qa-review` |
| Privacy / security | `privacy-guardrails-review` (hard-gated by default) |
| Legal / compliance | `compliance-review` |
| Release | `release-notes`, `launch-checklist` / `/ship` |
| Ops | `incident-response`, `support-triage` |
| Business | `pricing-strategy`, `gtm-marketing`, `/cost-report` |
| Program mgmt | `weekly-review` / `/weekly-review` |
| Scaffolding | `/new-project`, `/adopt-project`, `/harness-status`, `/sunset-project` |

Every project gets a standard `docs/` set (PRD, MARKETING, ROADMAP, CHANGELOG, OPERATIONS, BUSINESS, COMPLIANCE, CONNECTORS, RELEASE_CHECKLIST, COST_LOG) scaffolded from `templates/new-project/`.

## The release gate (the actual point of this harness)

`privacy_guardrails_review` is always required before a recognizable publish/deploy/release command (or an MCP tool that looks like one) is allowed to run — checked by `hooks/release_gate.py` against `<project>/.harness/gates.json`, tied to the current git commit. A project can opt into hard-gating `qa_review` and/or `compliance_review` too:

```
python3 hooks/gate_write.py <project_root> --require qa_review,compliance_review
```

A stale pass (from before newer commits) doesn't count. This can't be talked around by the model — only by an honest passing review.

This local hook is a fast nudge, not a trust boundary — it only sees actions taken *through Claude Code*. For projects releasing via GitHub Actions, `templates/new-project/.github/workflows/harness-gate-check.yml` adds a real CI-side check on the same gate records; see [`docs/CI_GATE_CHECK.md`](docs/CI_GATE_CHECK.md) for the convention and wiring.

## Token budgets (optional)

`python3 hooks/budget_write.py <project_root> <monthly_token_budget>` sets a best-effort monthly token budget per project, computed from `COST_LOG.md`. `/harness-status` shows the current percentage, and a SessionStart alert fires once usage crosses 50/80/100%. Same caveat as the rest of `COST_LOG.md`: an estimate, not authoritative billing — see [`docs/OTEL.md`](docs/OTEL.md).

## Configuration

- **`CLAUDE_HARNESS_PROJECTS_ROOT`** — where the harness looks for projects. Defaults to `~/Documents/Projects`. Set this in your shell profile (not just exported mid-session — hooks run as subprocesses of the Claude Code CLI, not of anything the Bash tool runs) if your projects live elsewhere.
- **OpenTelemetry token/cost tracking** — optional, off by default, documented in [`docs/OTEL.md`](docs/OTEL.md). The default `session_log.py` best-effort transcript-based logging needs no setup and stays on regardless.

## Philosophy

Privacy-by-default and guardrails-first aren't features here — they're defaults every skill in this bundle assumes. If that's not the product philosophy you want, this harness will actively push back on decisions that contradict it (see `privacy-guardrails-review`'s explicit "don't record pass to unblock the user faster" rule). That's by design, not a bug to route around.

## Development

Source of truth for this plugin is this repo. The same content also installs via a local symlink setup (see `CLAUDE.md`'s "Where this harness lives") for the original single-machine use case — both paths are kept working; new content should use `"${CLAUDE_PLUGIN_ROOT:-$HOME/Documents/Projects/_harness}"` in any Bash command so it resolves correctly under either.

## License

See `.claude-plugin/plugin.json` — pick and set a real license before treating this as publicly reusable; it currently ships as a placeholder.
