---
description: One-time setup after installing this harness as a plugin — wires up the projects root and the always-on philosophy block that a plugin install doesn't auto-load the way a symlinked CLAUDE.md does
---

Run this once, right after `/plugin install solo-founder-harness` (skip it entirely if you're the original symlink-based install — you already have this). A Claude Code plugin ships skills/agents/commands/hooks, but does **not** give you an always-loaded umbrella CLAUDE.md the way this harness's original symlink install does — this command closes that gap deliberately, with confirmation, rather than silently.

## Process

1. **Ask where projects live.** If the developer's projects already sit under `~/Documents/Projects/`, nothing to do. If not, tell them to set `CLAUDE_HARNESS_PROJECTS_ROOT` to their real root — and be precise about *where*: it must go in their persistent shell profile (`~/.zshrc`, `~/.bashrc`, or the OS environment) and a new terminal/session started, **not** just `export`ed inside a Claude Code conversation — hooks run as subprocesses of the Claude Code CLI itself, not of anything run through the Bash tool, so a session-scoped export never reaches them.
2. **Offer the philosophy block.** Show the developer this condensed version of the umbrella non-negotiables and ask where to add it — their project's own `CLAUDE.md`, or their global `~/.claude/CLAUDE.md` if they want it across every project:
   ```
   ## Solo-founder harness defaults
   - Privacy-by-default: no telemetry/analytics/data collection beyond what a feature explicitly requires; confirm before wiring up a new data-collecting call.
   - Guardrails-first: user-input surfaces (chat, upload, form) get validation + a guardrail review before "done".
   - Confirm before external/shared actions: push/deploy/publish always gets a check-in first.
   - Release gate: `qa-review`, `compliance-review`, and `privacy-guardrails-review` (always required) must pass for the current commit before a real ship command runs — enforced by this plugin's release_gate.py hook, not just advice.
   ```
   Append it only with explicit confirmation — this edits a file outside the plugin's own scope.
3. **Point at `docs/OTEL.md`** (in this plugin's install directory) if they want authoritative token/cost tracking instead of the best-effort default — mention it, don't enable anything.
4. **Verify.** Run `/harness-status` (no argument) to confirm the hooks can see their projects root correctly now.
5. Report what was changed and what the developer should do next (`/new-project` to scaffold their first tracked project, or `/adopt-project` on an existing one).
