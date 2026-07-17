---
description: Generate a live, always-accurate HTML dashboard of every project under the harness's projects root, and open it locally
---

Run this from any directory — it works the same whether you're inside a project or at the harness root:

```
python3 "${CLAUDE_PLUGIN_ROOT:-$HOME/Documents/Projects/_harness}/scripts/generate_dashboard.py"
```

Then open the path it prints (macOS: `open <path>`; Linux: `xdg-open <path>`; otherwise just tell the user the path).

What this is, and isn't:
- **Deterministic, not LLM-generated.** Every value comes straight from `gates.json`, `docs/`, `COST_LOG.md`, `budget.json`, and `git log`, via the same functions `/harness-status` uses. No synthesis, no judgment calls — regenerate it as often as you want, for free, and it's always accurate as of that moment.
- **Not the narrative history.** `gates.json` only stores each gate's *current* status, not a log of past rounds — this dashboard can't show "6 review rounds" the way a manually-built one can, because that requires reading and synthesizing memory files and commit messages, which isn't this command's job. If a full narrative rebuild is wanted, that's a separate, deliberate ask — not something to reconstruct here.
- **Marks the current project.** Whichever project the command was run from (if any) is auto-expanded and tagged "you are here" — the rest of the fleet is still there, just collapsed.

Report back the path and confirm it opened — don't paste the HTML content into the conversation.
