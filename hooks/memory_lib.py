#!/usr/bin/env python3
"""Helpers for a project's native Claude Code memory directory
(~/.claude/projects/<encoded-abs-path>/memory/). Read-only: the harness never
writes memory from a hook -- /wrap-up (with the user in the loop) does.
"""
import os
import re
import subprocess
import time
from typing import List, Optional


def claude_home() -> str:
    return os.path.abspath(os.path.expanduser(os.environ.get("CLAUDE_CONFIG_DIR") or "~/.claude"))


def memory_dir(project_root: str) -> str:
    """Claude Code keys memory by the project's absolute path with every
    non-alphanumeric character replaced by '-'."""
    encoded = re.sub(r"[^A-Za-z0-9]", "-", os.path.abspath(project_root))
    return os.path.join(claude_home(), "projects", encoded, "memory")


def memory_files(project_root: str) -> List[str]:
    d = memory_dir(project_root)
    if not os.path.isdir(d):
        return []
    return sorted(
        os.path.join(d, n) for n in os.listdir(d) if n.endswith(".md") and n != "MEMORY.md"
    )


def newest_memory_mtime(project_root: str) -> Optional[float]:
    files = memory_files(project_root)
    return max((os.path.getmtime(f) for f in files), default=None)


def last_commit_time(project_root: str) -> Optional[float]:
    try:
        r = subprocess.run(
            ["git", "-C", project_root, "log", "-1", "--format=%ct"],
            capture_output=True, text=True, timeout=5,
        )
        return float(r.stdout.strip()) if r.returncode == 0 and r.stdout.strip() else None
    except (OSError, subprocess.SubprocessError, ValueError):
        return None


def parse_frontmatter(text: str) -> dict:
    """Flat key -> value view of the YAML frontmatter, including keys nested
    one level under `metadata:`. Deliberately tiny; not a YAML parser."""
    m = re.match(r"---\n(.*?)\n---", text, re.S)
    out = {}
    if not m:
        return out
    for line in m.group(1).splitlines():
        km = re.match(r"^\s*([A-Za-z_][\w-]*):\s*(.*)$", line)
        if km:
            out[km.group(1)] = km.group(2).strip().strip('"')
    return out


def age_days(ts: float, now: Optional[float] = None) -> int:
    return int(((now or time.time()) - ts) // 86400)


def handoff_path(project_root: str) -> str:
    return os.path.join(memory_dir(project_root), "handoff.md")


def memory_nudge(project_root: str, now: Optional[float] = None) -> Optional[str]:
    """One short SessionStart line, or None when there's nothing worth saying.
    Mechanical, from file times only -- no content is read into context."""
    now = now or time.time()
    parts = []
    hp = handoff_path(project_root)
    if os.path.isfile(hp):
        parts.append(f"handoff.md present ({age_days(os.path.getmtime(hp), now)}d old)")
    commit_t = last_commit_time(project_root)
    mem_t = newest_memory_mtime(project_root)
    if commit_t and now - commit_t < 7 * 86400:  # only for recently active projects
        if mem_t is None:
            parts.append("no memory recorded yet; /wrap-up after non-trivial work")
        elif commit_t - mem_t > 86400:
            parts.append(f"memory is {age_days(mem_t, commit_t)}d behind the last commit; /wrap-up captures the gap")
    return ("[harness] memory — " + "; ".join(parts)) if parts else None
