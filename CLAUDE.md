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

## Stage-gates (placeholder — Phase 2)
A hard-block release gate (`/ship` + a privacy/security review pair) is planned but not yet built. Until it exists, treat `docs/RELEASE_CHECKLIST.md` in each project as an honor-system checklist, not an enforced one.

## Where this harness lives
Source of truth: `~/Documents/Projects/_harness/` (a local git repo). It's symlinked into `~/.claude/{skills,agents,commands,settings.json}` and this file is symlinked to `~/Documents/Projects/CLAUDE.md`. To extend the harness (new skill, agent, command, or hook), edit the files in `_harness/` directly — don't edit the symlink targets in `~/.claude/`.
