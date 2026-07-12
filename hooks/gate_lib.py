#!/usr/bin/env python3
"""Shared helpers for reading/writing <project>/.harness/gates.json.

Used by both gate_write.py (called from skills via Bash) and release_gate.py
(the PreToolUse hard-block hook), so the record format never drifts.
"""
import json
import os
import subprocess
from datetime import datetime, timezone
from typing import Optional


def gates_path(project_root: str) -> str:
    return os.path.join(project_root, ".harness", "gates.json")


def current_commit(project_root: str) -> Optional[str]:
    try:
        result = subprocess.run(
            ["git", "-C", project_root, "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return None


def load_gates(project_root: str) -> dict:
    path = gates_path(project_root)
    if not os.path.isfile(path):
        return {}
    try:
        with open(path, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def record_gate(project_root: str, check: str, status: str, notes: str = "") -> dict:
    if status not in ("pass", "fail"):
        raise ValueError("status must be 'pass' or 'fail'")

    gates = load_gates(project_root)
    gates[check] = {
        "status": status,
        "reviewed_commit": current_commit(project_root),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "notes": notes,
    }

    path = gates_path(project_root)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(gates, f, indent=2)
        f.write("\n")

    return gates


def check_passing(project_root: str, check: str) -> bool:
    gates = load_gates(project_root)
    entry = gates.get(check)
    if not entry or entry.get("status") != "pass":
        return False
    reviewed = entry.get("reviewed_commit")
    head = current_commit(project_root)
    if reviewed is None or head is None:
        return False
    return reviewed == head
