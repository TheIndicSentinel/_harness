# Local (symlink) install

The original single-machine install, kept working alongside the plugin install. Source of truth is this repo; `~/.claude` points into it.

- `~/.claude/{skills,agents,commands}` are symlinks into this repo, and the umbrella `CLAUDE.md` is symlinked to `~/Documents/Projects/CLAUDE.md` (or wherever `CLAUDE_HARNESS_PROJECTS_ROOT` points). Hooks are wired through `settings.json`.
- **`settings.json` is a real file, not a symlink, since 0.5.1.** Personal preferences (model, theme) stay in your live `~/.claude/settings.json` and out of the repo. The repo copy is the shared template (hooks and secrets denies). Changes to it don't propagate by themselves: diff and merge them into your live file by hand. `harness-status` reports drift.
- **Desktop-synced skills** (`skills/synced/`) and anything you install by hand appear under the symlinked `skills/`. They are not tracked: exclude them locally with `.git/info/exclude`.
- Edit files in this repo, not the symlink targets under `~/.claude/`, and use `"${CLAUDE_PLUGIN_ROOT:-$HOME/Documents/Projects/_harness}"` in Bash commands so both install modes resolve.
- A plugin install does not load the umbrella `CLAUDE.md`; run `/harness-init` for that.
- **Status line (user level):** `settings.json` carries a `statusLine` entry that runs `scripts/statusline.py` (context %, prompt-cache hit %, session cost, model; fields that Claude Code does not send are left out). A plugin install cannot set it: add `{"statusLine": {"type": "command", "command": "python3 \"/path/to/_harness/scripts/statusline.py\""}}` to your own `~/.claude/settings.json`. The prompt-cache figure needs Claude Code 2.1.251 or later. If you already have a `statusLine`, keep yours.
