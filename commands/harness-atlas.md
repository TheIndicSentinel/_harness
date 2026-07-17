---
description: Open a LIVE version of the mind-tree — same tree UI as /harness-map, but regenerated fresh from current gates/docs/memory/git every run
---

Run this from any directory — it works the same whether you're inside a project or at the harness root:

```
open "$(python3 "${CLAUDE_PLUGIN_ROOT:-$HOME/Documents/Projects/_harness}/scripts/generate_atlas.py")"
```

What this is: the exact same visual/interaction engine as `harness-map.html` (tree navigation, kind badges, relationship links, evidence footers — extracted from that file at generation time, not a duplicated copy), but with every category rebuilt from live data instead of hand-authored narrative.

What's live vs. what it can't do:
- **Live**: current gate status, docs adopted, project health, token usage, recent commits (raw, verbatim), project memory (raw file contents, not summarized).
- **Missing on purpose**: gate-round-by-round *history* (`gates.json` only retains the current record — there's nothing to read for past rounds) and any "why this mattered / what was saved" narrative synthesis. Both require reading and judgment, not just data — that's what the hand-authored `harness-map.html` (`/harness-map`) is for.

Report back that it opened — don't paste the HTML content into the conversation.
