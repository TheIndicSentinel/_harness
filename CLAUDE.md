# Projects Harness — Umbrella Instructions

This file loads automatically for every project under `~/Documents/Projects/` (Claude Code walks up parent directories for `CLAUDE.md`). It sets defaults that apply across all projects; it does **not** replace each project's own `CLAUDE.md`, which still owns that project's stack, architecture, and domain rules.

## Who's building this
A solo entrepreneur building privacy-first, guardrail-first applications. Every product decision defaults toward less data collection and more user control, not more.

## Scope of this harness
This governs **Claude Code usage only** — skills, commands, hooks, and locally-tracked project docs. It has no reach into and makes no claims about the Anthropic Messages API/SDK, Bedrock/Vertex, Claude.ai, Claude Desktop, other Anthropic surfaces, or MCP connectors used outside Claude Code. Don't describe it, in conversation with the user or in generated docs, as broader than that — if a request implies governing one of those other surfaces, say so explicitly rather than silently answering as if this harness already covers it.

## Non-negotiable defaults (apply to every project here, unless that project's own CLAUDE.md overrides for a stated reason)
- **Privacy-by-default.** No telemetry, analytics, or data collection beyond what a feature explicitly requires. If you're about to add a new data-collecting call (logging, crash reporting, network calls), pause and confirm it's actually needed before wiring it up silently.
- **Guardrails-first.** Safety/abuse checks are part of the feature, not a follow-up. Don't ship a user-facing input path (chat, upload, form) without at least basic validation and a guardrail review before it's called "done."
- **Confirm before external/shared actions.** Pushing, deploying, publishing, or anything that leaves the local machine always gets a check-in first — this reiterates the standing Claude Code norm, explicitly, for every project in this folder.

## Token/context discipline
- **Memory before reading.** Start from the project's `CLAUDE.md` and its `MEMORY.md` index; read targeted files for the task, not whole directories. Delegate broad exploration to a subagent (Explore/general-purpose) so raw search output stays out of the main thread.
- Avoid re-reading files already in context; trust tool results instead of re-verifying by hand.
- Use Plan Mode before large or ambiguous changes rather than iterating live.
- `/clear` between unrelated tasks — a fresh session with a good `CLAUDE.md` and memory is cheaper and sharper than a long, polluted one. When a long task nears the limit, `/compact <what to keep>` rather than leaving auto-compact to choose.
- Keep the prompt prefix stable mid-task: switching models or toggling MCP servers mid-session invalidates the prompt cache and re-bills the whole context.
- Module-specific rules go in the project's `.claude/rules/<area>.md` with a `paths:` frontmatter glob, so they load only when that code is touched instead of sitting in every session's `CLAUDE.md`.
- End a session that changed something non-trivial with `/wrap-up`, so the next one starts from memory instead of re-deriving it.

## Stage-gates (enforced)
Before any recognizable publish/deploy/release action runs in a project here (Bash ship commands and deploy-shaped MCP tools alike), the `release_gate.py` `PreToolUse` hook checks `<project>/.harness/gates.json`: every **required gate** must have a pass tied to the *current* git commit — a stale pass (from before newer commits) doesn't count. `privacy_guardrails_review` is always required; a project opts into more by listing them in gates.json `required_gates` (via `gate_write.py --require`), e.g. `qa_review` and `compliance_review`. Run the matching skill (`privacy-guardrails-review`, `qa-review`, `compliance-review` — directly, or via `launch-checklist` / `/ship`) to record a pass. This is a mechanical block, not advice — it can't be talked around by the model, only by an honest passing review. Never remove a gate from `required_gates` to unblock a ship.

## Lifecycle coverage (which skill owns what)
Setup (plugin installs only): `/harness-init`. Ideation→spec: `idea-brainstorm` → `market-research` → `prd-writer`. Build-quality: `qa-review`. Ship: `release-notes` → `launch-checklist`/`/ship` (gates above). Legal: `compliance-review`. Post-launch: `incident-response` (fires), `support-triage` (feedback), `weekly-review`/`/weekly-review` (cadence: roadmaps, success criteria, risks, docs freshness). Business: `pricing-strategy`, `gtm-marketing`, `/cost-report`. Every working session: `/wrap-up`. End-of-life: `/sunset-project`.

## Project memory
Claude Code already has a native, per-project, file-based memory system at `~/.claude/projects/<project-path-with-every-/-replaced-by-->/memory/` — it accumulates durable facts (user preferences, feedback, project decisions, references) across sessions on its own, without the harness needing to build a second one. `privacy-guardrails-review` writes review outcomes and accepted-risk decisions there explicitly (see that skill). `/wrap-up` is the general-purpose writer: at the end of a working session it records what a future session would otherwise rediscover by reading code (gotchas, decisions and why, rejected approaches). Other skills use the same judgment: a genuinely durable, non-obvious decision is worth a memory entry; routine output belongs in `docs/`, not memory.

Memory is keyed by the project's **absolute path**. Moving or renaming a project folder silently orphans its memory — move `~/.claude/projects/<old-encoded-path>/memory/` to the new encoded path along with it.

## Existing projects (not scaffolded by `/new-project`)
A project that predates the harness (or was created some other way) still gets the umbrella rules and hooks above for free — they're not tied to scaffolding. It just won't have the standard `docs/` set yet. Run `/adopt-project` once to fill in whatever's missing (PRD, MARKETING, COST_LOG, RELEASE_CHECKLIST, ROADMAP, CHANGELOG, OPERATIONS, BUSINESS, COMPLIANCE, CONNECTORS — the full template set, plus the CI gate-check workflow and CODEOWNERS if the project uses GitHub Actions) — it only creates files that don't already exist and never touches the project's own `CLAUDE.md` or an existing checklist.

## Editing the harness itself
Install layout, path conventions, and known deviations live in `_harness/.claude/rules/harness-development.md` — loaded only when working inside `_harness/`, so they cost nothing in other projects.
