---
description: Open the LIVE mind-tree — projects worked on, tokens per project and per task, gates, docs, memory, hooks and history, regenerated from current data every run
disable-model-invocation: true
---

Run this from any directory — it works the same whether you're inside a project or at the harness root:

```
python3 "${CLAUDE_PLUGIN_ROOT:-$HOME/Documents/Projects/_harness}/scripts/generate_atlas.py" --open
```

From a plain terminal the same thing is `harness-ui` (a one-line wrapper in `~/.local/bin`, see README). The page is written to `~/.claude/harness-atlas.html`.

What this is: a tree UI (navigation, kind badges, relationship links, evidence footers) whose engine lives in `scripts/atlas_engine.html`; `scripts/generate_atlas.py` fills it with data rebuilt from live sources on every run. There is no hand-written version any more.

What's live vs. what it can't do:
- **Live**: current gate status, docs adopted, project health, recent commits (raw, verbatim), project memory (raw file contents, not summarized), the harness's own hooks and capabilities, and **Work & Tokens**: tokens per project and per task (a task is a git branch), main sessions and subagents kept apart, read from Claude Code's session transcripts (no prompt text), plus the baseline pilot per task when one is recorded. One panel, **Harness cost vs measured benefit** (first node under `_harness`, linked from the root node), puts the cost next to the evidence: tokens the harness injects into every session (file estimate and a real `/context` measurement, refreshed at no token cost when over 6 hours old; skip with `--no-refresh`), the Orient trend, per-task tokens, and the baseline deltas with the sample size and a noise label.
- **Missing on purpose**: gate-round-by-round *history* (`gates.json` only retains the current record — there's nothing to read for past rounds) and any "why this mattered / what was saved" narrative synthesis. Both require reading and judgment, not just data.

Report back that it opened — don't paste the HTML content into the conversation.
