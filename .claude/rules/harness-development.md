# Developing the harness itself

Loaded only when working inside `_harness/` (moved out of the umbrella `CLAUDE.md`, which every project pays for in every session).

## Where this harness lives
Source of truth: `~/Documents/Projects/_harness/` (a local git repo, also published at github.com/TheIndicSentinel/_harness). This repo now installs two ways, kept deliberately parallel so neither breaks the other:
- **Local symlink install** (this machine, today): symlinked into `~/.claude/{skills,agents,commands,settings.json}`, and `_harness/CLAUDE.md` (the umbrella) is symlinked to `~/Documents/Projects/CLAUDE.md`. Hooks are wired via `settings.json`.
- **Claude Code plugin install** (other developers, via `/plugin marketplace add TheIndicSentinel/_harness` then `/plugin install solo-founder-harness`): driven by `.claude-plugin/plugin.json` and `hooks/hooks.json`, using `$CLAUDE_PLUGIN_ROOT` instead of a hardcoded path. A plugin install does **not** auto-load the umbrella CLAUDE.md the way the symlink does — run `/harness-init` once after installing to add the umbrella philosophy block to your own project's CLAUDE.md and to set `CLAUDE_HARNESS_PROJECTS_ROOT` if your projects don't live under `~/Documents/Projects/`.

To extend the harness (new skill, agent, command, or hook), edit the files in `_harness/` directly — don't edit the symlink targets in `~/.claude/`, and don't hardcode `~/Documents/Projects/_harness` in new content; use `"${CLAUDE_PLUGIN_ROOT:-$HOME/Documents/Projects/_harness}"` in Bash commands so both install modes keep working.

## Known deviations from official packaging (deliberate, revisit when touched)
- **Token tracking is best-effort homegrown, and nothing in this harness is authoritative billing.** `session_log.py` parses transcript JSONL (undocumented format) into COST_LOG.md. `docs/OTEL.md` ranks four sources in order of trust — this log, then OpenTelemetry (richer telemetry, but Anthropic's own docs call its cost metric an approximation too, not authoritative), then the Anthropic Admin API (the actual authority, for orgs with Console access), then Claude subscription usage (a separate billing domain entirely). If session_log breaks after a Claude Code update, switch to OTel rather than patching the parser — but don't describe either as "the" authoritative number.
