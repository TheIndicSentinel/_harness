#!/usr/bin/env python3
"""SessionStart hook: print a compact project status line into the session's
starting context — gate freshness and the roadmap's current focus — so a stale
gate or a forgotten "Now" item surfaces at session open instead of at ship time.

Hard rules: never block (always exit 0), never print more than a few short
lines (this lands in the context window every session — token discipline),
print nothing at all when there's nothing worth saying.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from budget_lib import alert_threshold_crossed, budget_status, record_alert, should_alert  # noqa: E402
from gate_lib import check_passing, load_gates, project_root_for, required_gates  # noqa: E402

MAX_NOW_ITEMS = 3


def gate_summary(project_root: str):
    gates = load_gates(project_root)
    if not gates:
        return None
    parts = []
    for name in required_gates(project_root):
        entry = gates.get(name)
        if not isinstance(entry, dict):
            parts.append(f"{name}: never run")
        elif check_passing(project_root, name):
            parts.append(f"{name}: pass (current)")
        elif entry.get("status") == "pass":
            parts.append(f"{name}: STALE (new commits since pass)")
        else:
            parts.append(f"{name}: {entry.get('status', 'unknown')}")
    return "; ".join(parts)


def roadmap_now(project_root: str):
    path = os.path.join(project_root, "docs", "ROADMAP.md")
    if not os.path.isfile(path):
        return []
    items, in_now = [], False
    try:
        with open(path) as f:
            for line in f:
                stripped = line.strip()
                if stripped.startswith("## "):
                    in_now = stripped.lower().startswith("## now")
                    continue
                if in_now and stripped.startswith("- ") and len(stripped) > 6:
                    items.append(stripped.lstrip("- [ ]xX").strip())
                    if len(items) >= MAX_NOW_ITEMS:
                        break
    except OSError:
        return []
    return [i for i in items if i]


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        cwd = payload.get("cwd") or os.getcwd()
        project_root = project_root_for(cwd)
        if not project_root or not os.path.isdir(project_root):
            return 0

        lines = []
        gates = gate_summary(project_root)
        if gates:
            lines.append(f"[harness] gates — {gates}")
        now = roadmap_now(project_root)
        if now:
            lines.append(f"[harness] roadmap Now — " + " | ".join(now))
        status = budget_status(project_root)
        if status is not None:
            used, budget, pct = status
            crossed = alert_threshold_crossed(pct)
            # Fire once per threshold per month, not every session -- a
            # SessionStart hook runs unprompted every time, so re-printing
            # the same crossing indefinitely would be noise, not signal.
            if crossed is not None and should_alert(project_root, crossed):
                lines.append(f"[harness] token budget ALERT — {used}/{budget} ({pct}%, crossed {crossed}% threshold)")
                record_alert(project_root, crossed)
        if lines:
            print("\n".join(lines))
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
