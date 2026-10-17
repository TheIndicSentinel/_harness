# Projects Harness — Umbrella Instructions

Loads for every project under `~/Documents/Projects/`. Each project's own `CLAUDE.md` owns its stack, architecture and domain rules; this file only sets shared defaults.

Solo founder building privacy-first, guardrail-first apps: default toward less data collection and more user control.

## Scope
Governs **Claude Code usage only** (skills, commands, hooks, local docs). It makes no claims about the Messages API/SDK, Bedrock/Vertex, Claude.ai/Desktop, or MCP connectors used outside Claude Code — if a request implies those, say so instead of answering as if covered.

## Defaults (a project's own CLAUDE.md may override with a stated reason)
- **Privacy-by-default.** No telemetry, analytics or data collection beyond what a feature requires. Before adding any logging, crash reporting or network call, pause and confirm it's needed.
- **Guardrails-first.** Any user-facing input path (chat, upload, form) gets validation and a guardrail review before it's "done".
- **Confirm before anything that leaves the machine** (push, deploy, publish).

## Release gates (enforced by hook, not advice)
Ship-shaped commands and deploy/publish MCP tools are blocked unless every required gate in `<project>/.harness/gates.json` passed for the *current* commit and the tree is clean. `privacy_guardrails_review` is always required; projects opt into `qa_review` / `compliance_review`. Record passes through the matching skill or `/ship`. Never remove a gate from `required_gates` to unblock a ship.

## Context & memory
- Start from the project's `CLAUDE.md` and `MEMORY.md`; read targeted files; send broad exploration to a subagent.
- Auto-memory is keyed by the project's **absolute path** — moving a project orphans it; move `~/.claude/projects/<encoded-path>/memory/` too.
- Durable decisions and non-obvious gotchas go to memory (via `/wrap-up`); routine output goes in `docs/`.
- When compacting, preserve: modified files, test/lint commands, gate status, open decisions.
- Don't switch models or toggle MCP servers mid-task (invalidates the prompt cache).

## More
Skill-by-phase map, gate details, adopting existing projects: `docs/LIFECYCLE.md` in the harness root (`$CLAUDE_PLUGIN_ROOT` or `~/Documents/Projects/_harness`) — read only when needed.
