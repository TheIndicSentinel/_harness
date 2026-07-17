---
description: Open the narrative mind-tree UI (harness-map.html) locally — the hand-built System Map/Atlas, not the live mechanical dashboard
---

Run this from any directory — it works the same whether you're inside a project (saarthi, kavach, any other) or at the harness root:

```
open "${CLAUDE_PLUGIN_ROOT:-$HOME/Documents/Projects/_harness}/harness-map.html"
```

On Linux, use `xdg-open` instead of `open`. If neither exists, just print the path and tell the user to open it manually.

What this opens, and how it differs from `/dashboard`:
- **This** (`harness-map.html`) is the narrative Atlas — kind taxonomy, relationship links, evidence footers, gate-round-by-round history, the "Features Worked On" prompt→skill→response→savings pipeline. It's a hand-assembled snapshot, not live — it does not re-read `gates.json`/`COST_LOG.md`/git on open, so it goes stale as commits land. Its own provenance banner states what commit it was last refreshed against.
- **`/dashboard`** is the deterministic live counterpart — regenerated fresh every run from current `gates.json`/`docs/`/`COST_LOG.md`/git state, but mechanical only: current gate status, not gate *history* or narrative synthesis.

Report back that it opened — don't paste the HTML content into the conversation.
