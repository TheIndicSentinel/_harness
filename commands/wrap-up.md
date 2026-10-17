---
description: End-of-session capture — turn what changed this session into durable project memory (and CHANGELOG lines), so the next session starts informed instead of re-reading the codebase
---

Close out the current working session. This is cheap by design: work from the conversation and git, never re-scan the codebase to do it.

## Process

1. **What changed.** Use the conversation first — files already read or edited are in context, don't re-read them. Fill gaps with `git status --short`, `git diff --stat`, and `git log --oneline` for commits made this session.
2. **Propose at most ~5 candidate memories, then apply the admission test to each.** Keep one only if **both** are true:
   - a fresh session would likely get it wrong, or waste time, without it; and
   - it was **confirmed this session** (a passing/failing test, an error you reproduced, or the user said so). An untested guess is a hypothesis: store it with `status: hypothesis` or don't store it.

   What qualifies: non-obvious gotchas **and their root cause** (symptom → cause → fix, when you debugged one), decisions and *why*, approaches tried and rejected, where something lives when names don't make it obvious, corrections the user made to how you work.
   **Never store** what git, ROADMAP or the code already answers: PR/issue numbers, "X is done" lists, task status, file inventories, test counts. Status goes in `docs/ROADMAP.md`; history goes in git. Zero memories is a valid outcome — say so rather than padding.
3. **Write survivors to native project memory** at `~/.claude/projects/<project-path-with-every-non-alphanumeric-replaced-by-->/memory/`, one fact per file, keeping that directory's existing frontmatter convention and adding to `metadata`: `verified: <today, YYYY-MM-DD>` and `source: <commit, test name, or "user">`. Body: the fact, then **Why** and **How to apply**. Keep each file under ~3 KB. Check `MEMORY.md` first — update an existing entry instead of duplicating, and delete any entry this session proved wrong or whose `verified` date you just re-confirmed (refresh it). Index lines stay one short hook (under ~150 chars); `MEMORY.md` stays under ~60 lines.
4. **Handoff, only if work is unfinished.** Overwrite (never append) a single `handoff.md` in that same memory directory, max ~20 lines: goal; done and verified; the next step; decisions and why; open questions; the command that verifies it. If the task is finished, delete `handoff.md`.
5. **Promote stable rules, with confirmation.** A learning that has bitten twice, or is clearly a lasting rule, becomes a one-line proposal for the project's `CLAUDE.md` ("Non-obvious gotchas") or a path-scoped `.claude/rules/<area>.md`. Show the exact line and ask; never edit `CLAUDE.md` silently. Decisions with real trade-offs go in `docs/adr/` (use the `engineering:architecture` skill if installed), also with confirmation.
6. **User-visible changes** → one user-facing line each under `docs/CHANGELOG.md` `[Unreleased]`, if that file exists (same wording standard as `release-notes`).
7. **Lint.** Run `python3 "${CLAUDE_PLUGIN_ROOT:-$HOME/Documents/Projects/_harness}/scripts/memory_lint.py"` and mention only findings caused or left by this session.
8. **Report** in a few lines: memories written / refreshed / deleted (one line each), handoff written or cleared, CHANGELOG lines added, proposed `CLAUDE.md`/ADR edits awaiting a yes. Suggest `/clear` before starting an unrelated task.
