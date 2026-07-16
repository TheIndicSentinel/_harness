# Projects Harness — Umbrella Instructions

This file loads automatically for every project under `~/Documents/Projects/` (Claude Code walks up parent directories for `CLAUDE.md`). It sets defaults that apply across all projects; it does **not** replace each project's own `CLAUDE.md`, which still owns that project's stack, architecture, and domain rules.

## Who's building this
A solo entrepreneur building privacy-first, guardrail-first applications. Every product decision defaults toward less data collection and more user control, not more.

## Non-negotiable defaults (apply to every project here, unless that project's own CLAUDE.md overrides for a stated reason)
- **Privacy-by-default.** No telemetry, analytics, or data collection beyond what a feature explicitly requires. If you're about to add a new data-collecting call (logging, crash reporting, network calls), pause and confirm it's actually needed before wiring it up silently.
- **Guardrails-first.** Safety/abuse checks are part of the feature, not a follow-up. Don't ship a user-facing input path (chat, upload, form) without at least basic validation and a guardrail review before it's called "done."
- **Confirm before external/shared actions.** Pushing, deploying, publishing, or anything that leaves the local machine always gets a check-in first — this reiterates the standing Claude Code norm, explicitly, for every project in this folder.

## Token/context discipline
- Prefer subagents (Explore, general-purpose, or task-specific ones once added) for research- or exploration-heavy work so raw search/read output doesn't bloat the main thread.
- Avoid re-reading files already in context; trust tool results instead of re-verifying by hand.
- Use Plan Mode before large or ambiguous changes rather than iterating live.

## Stage-gates (enforced)
Before any recognizable publish/deploy/release action runs in a project here (Bash ship commands and deploy-shaped MCP tools alike), the `release_gate.py` `PreToolUse` hook checks `<project>/.harness/gates.json`: every **required gate** must have a pass tied to the *current* git commit — a stale pass (from before newer commits) doesn't count. `privacy_guardrails_review` is always required; a project opts into more by listing them in gates.json `required_gates` (via `gate_write.py --require`), e.g. `qa_review` and `compliance_review`. Run the matching skill (`privacy-guardrails-review`, `qa-review`, `compliance-review` — directly, or via `launch-checklist` / `/ship`) to record a pass. This is a mechanical block, not advice — it can't be talked around by the model, only by an honest passing review. Never remove a gate from `required_gates` to unblock a ship.

## Lifecycle coverage (which skill owns what)
Setup (plugin installs only): `/harness-init`. Ideation→spec: `idea-brainstorm` → `market-research` → `prd-writer`. Build-quality: `qa-review`. Ship: `release-notes` → `launch-checklist`/`/ship` (gates above). Legal: `compliance-review`. Post-launch: `incident-response` (fires), `support-triage` (feedback), `weekly-review`/`/weekly-review` (cadence: roadmaps, success criteria, risks, docs freshness). Business: `pricing-strategy`, `gtm-marketing`, `/cost-report`. End-of-life: `/sunset-project`.

## Project memory
Claude Code already has a native, per-project, file-based memory system at `~/.claude/projects/<project-path-with-every-/-replaced-by-->/memory/` — it accumulates durable facts (user preferences, feedback, project decisions, references) across sessions on its own, without the harness needing to build a second one. `privacy-guardrails-review` writes review outcomes and accepted-risk decisions there explicitly (see that skill). Other skills aren't required to write there, but should use the same judgment Claude already applies elsewhere: a genuinely durable, non-obvious decision is worth a memory entry; routine output belongs in `docs/`, not memory.

## Existing projects (not scaffolded by `/new-project`)
A project that predates the harness (or was created some other way) still gets the umbrella rules and hooks above for free — they're not tied to scaffolding. It just won't have the standard `docs/` set yet. Run `/adopt-project` once to fill in whatever's missing (PRD, MARKETING, COST_LOG, RELEASE_CHECKLIST, ROADMAP, CHANGELOG, OPERATIONS, BUSINESS, COMPLIANCE — the full template set) — it only creates files that don't already exist and never touches the project's own `CLAUDE.md` or an existing checklist.

## Where this harness lives
Source of truth: `~/Documents/Projects/_harness/` (a local git repo, also published at github.com/TheIndicSentinel/_harness). This repo now installs two ways, kept deliberately parallel so neither breaks the other:
- **Local symlink install** (this machine, today): symlinked into `~/.claude/{skills,agents,commands,settings.json}`, and this file is symlinked to `~/Documents/Projects/CLAUDE.md`. Hooks are wired via `settings.json`.
- **Claude Code plugin install** (other developers, via `/plugin marketplace add TheIndicSentinel/_harness` then `/plugin install solo-founder-harness`): driven by `.claude-plugin/plugin.json` and `hooks/hooks.json`, using `$CLAUDE_PLUGIN_ROOT` instead of a hardcoded path. A plugin install does **not** auto-load this CLAUDE.md the way the symlink does — run `/harness-init` once after installing to add the philosophy block above to your own project's CLAUDE.md and to set `CLAUDE_HARNESS_PROJECTS_ROOT` if your projects don't live under `~/Documents/Projects/`.

To extend the harness (new skill, agent, command, or hook), edit the files in `_harness/` directly — don't edit the symlink targets in `~/.claude/`, and don't hardcode `~/Documents/Projects/_harness` in new content; use `"${CLAUDE_PLUGIN_ROOT:-$HOME/Documents/Projects/_harness}"` in Bash commands so both install modes keep working.

## Known deviations from official packaging (deliberate, revisit when touched)
- **Token tracking is best-effort homegrown.** `session_log.py` parses transcript JSONL (undocumented format) into COST_LOG.md. The authoritative path is `/cost`, `/usage`, or Claude Code's OpenTelemetry metrics — see `docs/OTEL.md` for the opt-in, privacy-preserving (local-exporter, off-by-default) setup. If session_log breaks after a Claude Code update, switch to OTel rather than patching the parser.
