# Verification — making "done" mean "checked"

Anthropic's top recommendation for Claude Code: give Claude a check it can run, so the loop closes without you. This harness gives you four rungs; pick the lightest that fits.

| Rung | When | How |
|---|---|---|
| **1. In the prompt** | any task | "…run `<test command>` and show the output." Put the project's real test/lint command in its `CLAUDE.md` so you don't retype it. |
| **2. `/goal`** | a task that spans turns | Set a goal condition ("all tests in `crates/x` pass and clippy is clean"); a separate evaluator re-checks it every turn. |
| **3. Stop hook (this harness, opt-in)** | long or unattended work | Below. A script runs your check and refuses to let the turn end until it passes. |
| **4. Fresh-context review** | risky or shared changes | `/code-review`, or "use a subagent to review the diff against PLAN.md; report correctness gaps only". A reviewer that didn't write the code finds different things. |

Show evidence, not assertions: the command and its output, not "tests pass".

## Rung 3: the Stop hook
Off until you configure a command for a project:

```
python3 "${CLAUDE_PLUGIN_ROOT:-$HOME/Documents/Projects/_harness}/hooks/verify_write.py" <project_root> "cargo test -p mycrate" --timeout 400
python3 .../hooks/verify_write.py <project_root>            # show current setting
python3 .../hooks/verify_write.py <project_root> --clear    # turn off
```

What it does when Claude is about to stop:
- Runs the command only if something changed since the last pass (HEAD or the dirty tree). Questions and re-stops cost nothing; a clean tree with no history just records a baseline.
- Non-zero exit or timeout blocks the stop (exit 2) and hands Claude the last ~4 KB of output; Claude keeps working.
- After 3 blocks in a row it lets the stop through and tells Claude to report the work as **not verified**, so a broken or flaky command can't trap a session.
- Hook errors fail open. This is a quality gate on the cooperative path, not a security boundary.

**Where the command lives:** `~/.claude/harness/verify/<project>.json` (`CLAUDE_HARNESS_DATA_DIR` overrides), deliberately outside the repo. A repo-supplied command would let any cloned repository run code at the end of every turn.

**Default policy: leave it off.** It is the right tool for long or unattended tasks and for fast suites. For a bounded interactive task, rung 1 or 2 is cheaper: the hook runs after *every* turn that changed files, including a mid-edit question turn that left the tree dirty. Enable it per project only when the check finishes in under ~60 s (`verify_write.py <project>` shows the last run time and warns).

**Choosing the command:** the narrowest check that would catch the mistakes you care about (affected crate/package tests + type/lint), under a minute if possible. A full-suite check that takes ten minutes every turn will teach you to turn it off. Keep long suites for CI.

## What this does not do
It doesn't judge correctness beyond your command, and it doesn't replace CI. For releases, CI is the authority (`docs/CI_GATE_CHECK.md`).
