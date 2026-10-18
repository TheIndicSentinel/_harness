# Solo-Founder Harness

A **Claude Code** harness for solo founders building privacy-first, guardrail-first software, from idea to sunset, with a release gate that a hook enforces rather than a prompt someone can talk past.

## Install (Claude Code plugin)

```
/plugin marketplace add TheIndicSentinel/_harness
/plugin install solo-founder-harness
```

Then run `/harness-init` once. A plugin install doesn't load an always-on `CLAUDE.md`, so `/harness-init` adds the defaults block and sets the projects-root location instead of leaving them silently missing. Running it from a local clone with symlinks instead: see [`docs/LOCAL_INSTALL.md`](docs/LOCAL_INSTALL.md).

## Status and evidence

- **Tested:** release gating (`release_gate.py`, the gate records, the CI gate script) and secrets control (`secrets_guard.py`, the deny template) have unit tests, and the test suite runs on every push, on Linux and macOS.
- **Not demonstrated:** that the memory and handoff files make sessions cheaper or faster. The one baseline pilot (five tasks, one run per cell) was within noise. A follow-up with 27 prompts suggests a committed `CLAUDE.md` changes answers about project-specific rules, while memory detail files are read only selectively; with three runs per cell, treat that as a lead. Details and caveats: [`docs/MEASUREMENT.md`](docs/MEASUREMENT.md).
- **Untested:** the GitHub Actions gate check has not yet run on a real release tag. The local hook is a fast nudge, not a trust boundary, and gate records are self-attested.

## Scope

A Claude Code project harness for one operator on one machine, with git as the audit trail. It does not see or govern the Messages API or SDKs, Bedrock/Vertex, Claude.ai or Desktop, or MCP connectors used outside Claude Code, and its release gate cannot block a deploy triggered any other way. Teams or products that call the API directly need a different design. Token and cost figures are best-effort estimates, not billing.

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
| Memory loop | `/wrap-up` (admission-tested session learnings and a handoff), `memory_lint.py`, a SessionStart memory line, context rules in the umbrella `CLAUDE.md` |
| Verification (opt-in) | Stop hook that checks a configured command before a session ends; off by default, see [`docs/VERIFICATION.md`](docs/VERIFICATION.md) |
| Atlas | `/harness-atlas` or `harness-ui`: a local page of projects, tokens per project and task, gates, docs, memory, hooks, and a cost-vs-benefit panel |
| Scaffolding | `/new-project`, `/adopt-project`, `/harness-status`, `/sunset-project` |

Every project gets a standard `docs/` set (PRD, MARKETING, ROADMAP, CHANGELOG, OPERATIONS, BUSINESS, COMPLIANCE, CONNECTORS, RELEASE_CHECKLIST) from `templates/new-project/`.

## The release gate (the actual point of this harness)

`privacy_guardrails_review` is always required before a recognizable publish/deploy/release command (or an MCP tool that looks like one) is allowed to run — checked by `hooks/release_gate.py` against `<project>/.harness/gates.json`, tied to the current git commit. A project can opt into hard-gating `qa_review` and/or `compliance_review` too:

```
python3 hooks/gate_write.py <project_root> --require qa_review,compliance_review
```

A stale pass (from before newer commits) doesn't count, and neither does a dirty working tree — a passing gate only vouches for the reviewed commit's *committed* content, and a build reads the filesystem, not git HEAD, so uncommitted local edits on top of a passing commit block too. This can't be talked around by the model — only by an honest passing review.

This local hook is a fast nudge, not a trust boundary — it only sees actions taken *through Claude Code*, and it's self-attested (nothing stops a hand-written `"status": "pass"` from satisfying it). For projects releasing via GitHub Actions, `templates/new-project/.github/workflows/harness-gate-check.yml` adds a real CI-side check on the same gate records, and required-status-check branch protection makes that check unskippable even for a solo maintainer; see [`docs/CI_GATE_CHECK.md`](docs/CI_GATE_CHECK.md) for the convention, the wiring, and the honest limits of self-attestation.

## Monitoring: where to look

- **Primary: the atlas "Work & Tokens"** (`/harness-atlas` or `harness-ui`). It reads Claude Code's own session transcripts, so it covers every past session, splits work by git branch, keeps subagents separate, and has a "Last 7 days per project" table (sessions, in + out, cache read, cache-hit share). No prompt text is read.
- **Live, in the session:** the status line (`scripts/statusline.py`: context %, prompt-cache hit %, session cost, model), and Claude Code's own `/usage` and `/insights`. Setup: [`docs/LOCAL_INSTALL.md`](docs/LOCAL_INSTALL.md).
- **Best-effort only: the cost log** (`~/.claude/harness/cost/`, written by the SessionEnd hook). It also feeds `/cost-report` and the budget alerts below. Whether SessionEnd fires when a VS Code panel is closed is unverified (see [`docs/COMPATIBILITY.md`](docs/COMPATIBILITY.md)), so treat a missing row as "unknown", not "no session".

## Token budgets (optional, built on the best-effort cost log)

`python3 hooks/budget_write.py <project_root> <monthly_token_budget>` sets a best-effort monthly token budget per project, computed from the per-project cost log (`~/.claude/harness/cost/`), so it is only as complete as that log. `/harness-status` always shows the current live percentage; a SessionStart alert fires once per threshold crossed (50/80/100%) per calendar month, not every session after crossing — it's a nudge, not a spend-prevention mechanism (nothing can stop a session mid-flight, and this doesn't see API/subscription/Claude.ai usage at all). Same caveat as the rest of `COST_LOG.md`: an estimate, not authoritative billing — see [`docs/OTEL.md`](docs/OTEL.md) for the full source ranking. If you'd rather not bother with a budget, say so explicitly: `budget_write.py <project_root> --skip` — `/harness-status` then reports "intentionally skipped" instead of leaving it looking like an oversight.

## Custom release commands (optional)

`release_gate.py`'s built-in patterns cover common cases (`npm publish`, `./gradlew *Release*`, `docker push`, etc.), but can't know about a project's own custom deploy script. Declare it explicitly and the gate checks it too: `python3 hooks/gate_write.py <project_root> --release-commands "make release,./scripts/deploy.sh"` (substring match, not regex — these come from the project owner, not a generic pattern).

## Project health (`/harness-status <name>`)

The real risk isn't the harness failing — it's installing it and never actually wiring anything up. The per-project detail view reports whether: the CI gate template is present *and actually called* by a real workflow (not just sitting there unused); the release command and rollback runbook in `docs/OPERATIONS.md` are filled in, not template placeholders; required gates are shown as a deliberate choice; the token budget is set or explicitly marked skipped; and the connector registry has real entries. It also surfaces the project's declared stage (from `CLAUDE.md`) and risk tier (from `COMPLIANCE.md`) so both are visible at a glance instead of buried in docs nobody re-reads. This is informational, not a gate — a genuine prototype is fine leaving most of it unset; the point is that it's a visible, deliberate "not yet" instead of a silent gap.

## Configuration

- **`CLAUDE_HARNESS_PROJECTS_ROOT`** — where the harness looks for projects. Defaults to `~/Documents/Projects`. Set this in your shell profile (not just exported mid-session — hooks run as subprocesses of the Claude Code CLI, not of anything the Bash tool runs) if your projects live elsewhere.
- **OpenTelemetry token/cost tracking** — optional, off by default, documented in [`docs/OTEL.md`](docs/OTEL.md). The default `session_log.py` best-effort transcript-based logging needs no setup and stays on regardless.

## Philosophy

Privacy-by-default and guardrails-first aren't features here — they're defaults every skill in this bundle assumes. If that's not the product philosophy you want, this harness will actively push back on decisions that contradict it (see `privacy-guardrails-review`'s explicit "don't record pass to unblock the user faster" rule). That's by design, not a bug to route around.

## Development

Run the tests in a venv: `python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt && .venv/bin/pytest -q`. The hooks and scripts need only the standard library; pytest is for development, so a bare `pytest` on a Python without it fails by design.

New content should use `"${CLAUDE_PLUGIN_ROOT:-$HOME/Documents/Projects/_harness}"` in Bash commands so it resolves under both install modes. `tests/test_portability.py` fails if an author-specific absolute path creeps in. `settings.json` is the shared template (hooks and secrets denies) for the local install; a plugin install uses `hooks/hooks.json` instead.

## Reference docs
[`docs/MEASUREMENT.md`](docs/MEASUREMENT.md) (baseline protocol, what the atlas panel does and does not show) · [`docs/VERIFICATION.md`](docs/VERIFICATION.md) (making "done" mean checked) · [`docs/CI_GATE_CHECK.md`](docs/CI_GATE_CHECK.md) (CI as the authoritative release gate) · [`docs/COMPATIBILITY.md`](docs/COMPATIBILITY.md) (what we rely on in Claude Code) · [`docs/OTEL.md`](docs/OTEL.md) (token/cost sources ranked by trust) · [`docs/DATA_RETENTION.md`](docs/DATA_RETENTION.md) · [`docs/LIFECYCLE.md`](docs/LIFECYCLE.md) · [`docs/LOCAL_INSTALL.md`](docs/LOCAL_INSTALL.md) · [`SECURITY.md`](SECURITY.md)

## License

MIT, see [`LICENSE`](LICENSE).
