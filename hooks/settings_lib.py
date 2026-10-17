#!/usr/bin/env python3
"""Detect drift between the repo's shared settings.json template and the live
~/.claude/settings.json (they stopped being the same file in 0.5.1, so a hook
or deny-rule change in the repo no longer propagates by itself).

Only the template-is-a-subset-of-live direction is checked: the live file is
allowed to carry extra personal settings. Plugin installs (no harness hooks in
the live file) are not checked: they get hooks from hooks.json instead.
"""
import json
import os
from typing import List, Optional

HARNESS_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load(path: str) -> Optional[dict]:
    try:
        with open(path) as f:
            data = json.load(f)
        return data if isinstance(data, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def _hook_keys(settings: dict) -> set:
    keys = set()
    hooks = settings.get("hooks")
    if not isinstance(hooks, dict):
        return keys
    for event, entries in hooks.items():
        for entry in entries if isinstance(entries, list) else []:
            for h in entry.get("hooks", []) if isinstance(entry, dict) else []:
                if isinstance(h, dict):
                    keys.add((event, entry.get("matcher", ""), h.get("command", ""),
                              h.get("onFailure", ""), h.get("timeout", "")))
    return keys


def _live_path() -> str:
    base = os.environ.get("CLAUDE_CONFIG_DIR") or "~/.claude"
    return os.path.join(os.path.abspath(os.path.expanduser(base)), "settings.json")


def settings_drift(template_path: Optional[str] = None, live_path: Optional[str] = None) -> Optional[List[str]]:
    """None: not applicable (no template/live file, or a plugin-style install).
    []: in sync. Otherwise: human-readable differences."""
    template = _load(template_path or os.path.join(HARNESS_ROOT, "settings.json"))
    live = _load(live_path or _live_path())
    if template is None or live is None:
        return None
    live_keys = _hook_keys(live)
    if not any("release_gate.py" in k[2] or "_harness" in k[2] for k in live_keys):
        return None
    problems = []
    for event, matcher, command, on_failure, timeout in sorted(_hook_keys(template) - live_keys):
        script = command.rsplit("/", 1)[-1].strip('"') or command
        problems.append(f"hook {event}:{script} is missing or differs in the live settings.json")
    for kind in ("deny", "allow"):
        want = (template.get("permissions") or {}).get(kind) or []
        have = set((live.get("permissions") or {}).get(kind) or [])
        missing = [r for r in want if r not in have]
        if missing:
            problems.append(f"{len(missing)} permissions.{kind} rule(s) from the template are not in the live file (e.g. {missing[0]})")
    return problems
