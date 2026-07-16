---
description: Report what the harness has done to any project (or every project) — docs adopted, gate status, sessions logged, git cleanliness
argument-hint: [project-name, defaults to a table across every project]
---

Run `python3 "${CLAUDE_PLUGIN_ROOT:-$HOME/Documents/Projects/_harness}/scripts/harness_status.py" $ARGUMENTS` and show the output as-is (it's already formatted — don't reformat or summarize it away). If no argument was given, this is a table across every project under the harness's projects root (defaults to `~/Documents/Projects/`, overridable via `CLAUDE_HARNESS_PROJECTS_ROOT`); with a project name, it's a detailed single-project report including the exact gate record and whether it's current against HEAD.

Briefly note anything that stands out (e.g. a project whose gate is stale, or one with zero docs adopted) in one or two sentences after the output — don't repeat the whole table back in prose.
