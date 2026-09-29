---
description: End-of-session capture — turn what changed this session into durable project memory (and CHANGELOG lines), so the next session starts informed instead of re-reading the codebase
---

Close out the current working session. This is cheap by design: work from the conversation and git, never re-scan the codebase to do it.

## Process

1. **What changed.** Use the conversation first — files already read or edited are in context, don't re-read them. Fill gaps with `git status --short`, `git diff --stat`, and `git log --oneline` for commits made this session.
2. **Pick at most ~5 learnings** a future session would otherwise rediscover by reading code or repeating a mistake:
   - non-obvious gotchas and their cause ("X crashes on device Y because Z")
   - decisions and *why*, plus approaches tried and rejected
   - where something lives when names don't make it obvious
   - corrections the user made to how you work
   Skip what git, the diff, or the project's `CLAUDE.md` already records, and routine edits. Zero learnings is a valid outcome — say so rather than padding.
3. **Write them to native project memory** at `~/.claude/projects/<project-path-with-every-/-replaced-by-->/memory/` (create the directory if missing), following that directory's existing file/frontmatter convention: one fact per file, `project` or `feedback` type, with **Why** and **How to apply** lines. Check `MEMORY.md` first — update an existing entry instead of adding a duplicate, and delete any entry this session proved wrong. Keep `MEMORY.md` one line per memory.
4. **Promote stable rules, with confirmation.** If a learning is a lasting project rule rather than a fact that may change, propose the exact line for the project's `CLAUDE.md` ("Non-obvious gotchas") or a path-scoped `.claude/rules/<area>.md` — show it and ask; never edit `CLAUDE.md` silently.
5. **User-visible changes** → one user-facing line each under `docs/CHANGELOG.md` `[Unreleased]`, if that file exists (same wording standard as `release-notes`).
6. **Report** in a few lines: memories written / updated / deleted (one line each), CHANGELOG lines added, any proposed `CLAUDE.md` edits awaiting a yes. Suggest `/clear` before starting an unrelated task.
