# Data retention — what this harness stores, where, and how to clear it

On-brand for a privacy-first harness: know what you're keeping. This covers what the **harness itself** writes (not what a product built with it collects — that's each project's own `docs/COMPLIANCE.md` and `docs/PRD.md` "Privacy & guardrails considerations").

## What's stored, and where

| What | Where | Contains | Lifespan |
|---|---|---|---|
| Gate records | `<project>/.harness/gates.json` | Pass/fail status, reviewed commit SHA, timestamp, a one-line review summary — no code, no user data | Kept indefinitely (small, append-by-overwrite JSON); delete the file to reset a project's gate history |
| Token budget | `<project>/.harness/budget.json` | A monthly token number you set — nothing else | Until you delete it or reset the budget |
| Session/cost log | `<project>/docs/COST_LOG.md` | Date, an 8-character session ID prefix, duration, best-effort token counts | Grows one row per Claude Code session in that project; trim or archive old rows manually if it gets long |
| Claude Code session transcripts | `~/.claude/projects/<project-path>/` (native Claude Code storage, not harness-managed) | Full conversation content — prompts, tool calls, file contents touched during the session | Governed by Claude Code itself, not this harness — see Claude Code's own settings/docs for retention controls |
| Project memory | `~/.claude/projects/<project-path>/memory/*.md` (native Claude Code storage) | Durable facts, feedback, accepted-risk decisions the harness's skills write there (e.g. `privacy-guardrails-review`'s accepted-risk notes) | Persists across sessions by design — this is memory's whole purpose; edit or delete individual `.md` files there directly to remove something |

## What this harness deliberately does NOT store
No copy of your code, no prompt/response content, no user data from any product built with it. `gates.json` and `budget.json` are metadata only — a session ID, a commit SHA, a pass/fail, a number. The one place actual conversation content lives is Claude Code's own transcript storage, which this harness doesn't manage or duplicate.

## Clearing it
- **A single project's harness state:** delete `<project>/.harness/` — gates and budget both reset. This does not affect Claude Code's own transcripts or memory for that project.
- **A project's session/cost history:** delete or truncate `<project>/docs/COST_LOG.md`.
- **Claude Code transcripts and memory:** these live under `~/.claude/`, outside this harness's control — refer to Claude Code's own documentation for how to clear them.
- **End of a project's life:** `/sunset-project` handles the deliberate wind-down (final changelog entry, support-status note, roadmap close-out) but does not delete data by itself — that's a separate, explicit choice if you want it.
