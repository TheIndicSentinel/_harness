# Compatibility policy

Claude Code changes quickly and parts of what this harness touches are not a stable public contract. This file says what we rely on, how we notice drift, and what we promise.

## What the harness relies on
| Surface | Used for | Stability |
|---|---|---|
| Hook events `SessionStart`, `PreToolUse`, `Stop`, `SessionEnd` and their stdin JSON (`cwd`, `tool_name`, `tool_input`, `transcript_path`, `session_id`) | gates, secrets guard, memory line, verification, cost log | documented |
| Hook decisions: exit 2 blocks; `hookSpecificOutput.permissionDecision` = `ask` | gates, secrets guard | documented |
| Plugin manifest + `hooks/hooks.json`, `${CLAUDE_PLUGIN_ROOT}` | plugin install | documented |
| Skill/command frontmatter: `name`, `description`, `argument-hint`, `disable-model-invocation` | skills, commands | documented |
| Native memory dir `~/.claude/projects/<non-alphanumerics → ->/memory/` and `MEMORY.md` | memory lint, SessionStart line, `/wrap-up` | directory convention observed, **not a documented contract** |
| Status line JSON on stdin (`context_window.used_percentage`, `prompt_cache.hit_ratio`, `cost.total_cost_usd`, `model.display_name`) | `scripts/statusline.py` | documented (https://code.claude.com/docs/en/statusline); `prompt_cache` needs Claude Code >= 2.1.251 and is omitted when absent; `used_percentage` and `hit_ratio` can be null |
| Session transcript JSONL (`message.usage`, timestamps) | cost log | **undocumented**; best-effort. If it breaks, switch to OpenTelemetry (`docs/OTEL.md`) rather than patch the parser |

## How drift is caught
- `tests/` runs on Ubuntu and macOS on every push, including portability and hook-behaviour tests.
- `tests/test_compat.py` is a **typo guard**: it fails if a wired hook event isn't in an event list that was copied from the docs on a known date. It cannot notice the docs changing; refreshing that list is part of each audit.
- The real drift signals are the next two: `python3 scripts/compat_check.py` reports the installed Claude Code version against the version the harness was last audited on, and which optional features it supports.
- CI runs `claude plugin validate` on a pinned Claude Code release (informational job). Note the scope: validating the folder (`.`) checks only the marketplace manifest; validating `.claude-plugin/plugin.json` is what inspects `hooks/hooks.json` (it caught an unquoted `${CLAUDE_PLUGIN_ROOT}` and would reject an unknown hook type). The job runs both.

## What we promise
- Fail-open for infrastructure errors in quality hooks; fail-closed for the release gate once a ship action is recognised.
- A harness release states the Claude Code version it was audited against in `CHANGELOG.md`.
- Optional features that need a newer Claude Code are off by default and documented here, never assumed.

## Updating Claude Code
1. Update, then run `python3 scripts/compat_check.py` and the test suite.
2. Re-read the hooks and memory pages of the official docs for changes; update `KNOWN_HOOK_EVENTS` in `tests/test_compat.py` and `AUDITED_AGAINST` in `scripts/compat_check.py` together.
3. Record the audit in `CHANGELOG.md`.

## Features gated on a Claude Code version
- **`onFailure: "block"` (>= 2.1.295): enabled on `release_gate.py` only**, in `hooks/hooks.json` and `settings.json`. A hook that can't start, exits with anything other than 0 or 2, times out, or prints unparseable JSON then blocks the tool call instead of letting it through. Older versions ignore the key (checked: 2.1.285's validator accepts it), so the fail-open hole stays there until they update.
  - Deliberately **not** on `secrets_guard.py`: a crash there would lock out Read/Edit/Grep, which is the recovery path. Documented as no effect on `Stop` hooks, so not on `verify_before_stop.py` either.
  - Trade-off accepted: if `python3` itself is missing, every Bash call is blocked until the hook is fixed or removed from settings (Edit is not matched, so Claude can still repair `settings.json`).
- **Launcher caveat:** `claude update` installs new versions under `~/.local/share/claude/versions/`. If `~/.local/bin/claude` is a copied binary rather than a symlink into that directory, it keeps running the old version; `claude --version` after updating tells you which you're on.

## Behaviour checks
- **SessionEnd when a VS Code panel is closed: UNVERIFIED (2026-10-18).** `SessionEnd` fires for `claude -p` sessions (the cost-log rows written for scripted runs show it). For VS Code, a transcript scan found 9 recent real-project sessions started from the VS Code extension and no cost-log row for any of them, but no real-project session of any kind has a row (the one CLI and one SDK session do not either), so the scan cannot tell "did not fire" from "fired but wrote nothing". A closing test needs a person: in a throw-away folder under the projects root, start a session in the VS Code panel, make one edit, close the panel, and look for a new row in `~/.claude/harness/cost/<folder>.md`. Until then, the cost log is best-effort and the atlas reads transcripts instead.

## Anthropic practices coverage (2026-10-18)
Sources: the costs page (docs/en/costs), the prompt-caching page (docs/en/prompt-caching) and the settings reference (docs/en/settings-reference). "Done" means a file in this repo or the umbrella does it; "advice only" means it is a line of guidance, not enforced.

| Practice | Status |
|---|---|
| Small CLAUDE.md, workflows in skills | Done |
| `/clear` between tasks, specific prompts, show test output | Done (umbrella lines) |
| Fresh start instead of resuming after a long idle gap; `/rewind` instead of compacting a failed path | Done (two umbrella lines, advice only) |
| Compaction guidance | Partly: a plain "preserve" line plus `/compact keep …`. A "Compact Instructions" section is not in the docs, so none is used |
| One model per session (each model has its own cache) | Done: `model` pinned in the templates; no skill or command sets `model:` |
| Effort default | Not done: the docs do not say whether the plain `effortLevel` key applies to Sonnet 5.5, and Sonnet 5.5 already defaults to `medium` |
| Live cache and context visibility | Done in code (status line, `/usage` "Prompt cache" line); not yet seen in a real session |
| Avoid mid-session cache breakers (model, MCP, plugins) | Advice only; docs say effort changes keep the cache on Sonnet 5.5 and plugin skills/commands/hooks never invalidate it |
| Prefer CLI tools over MCP; disable unused MCP servers | Not done |
| Hook that filters verbose test output (costs page example) | Not done |
| Code-intelligence plugins | Not done: `rust-analyzer-lsp` (binary present) and `kotlin-lsp` (binary missing) exist in the official marketplace |
| Delegate verbose work to subagents | Not done |
| Skill listing size (`skillListingMaxDescChars`, `skillOverrides`, `skillListingBudgetFraction`) | Not done: all unset, listing is about 9k tokens |
| Background tokens (`promptSuggestionEnabled`, `idleCompaction`) | Reviewed, not changed: both unset, so both default to on |
| Usage tracking (`/usage`, `/insights`, atlas Work & Tokens) | Done in docs |

Audit notes (no changes made): the `security-privacy-auditor` agent runs on `model: opus` while the other two agents use `sonnet`; MCP tool search defers MCP tools by default, and `claude -p /context` lists connector tools as deferred, but a large locally configured MCP server did not connect in four tries, so its behaviour in an interactive session is unverified (an earlier scripted run that restricted `--tools` sent that server's 200-odd tool definitions upfront, possibly because the tool-search tool was not available there).
