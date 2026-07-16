#!/usr/bin/env python3
"""Shared helpers for reading/writing <project>/.harness/gates.json.

Used by gate_write.py (called from skills via Bash), release_gate.py (the
PreToolUse hard-block hook), and session_start.py, so the record format
never drifts.

gates.json shape:
  {
    "<gate_name>": {"status", "reviewed_commit", "timestamp", "notes"},
    ...
    "required_gates": ["privacy_guardrails_review", "qa_review", ...]   # optional
  }

"required_gates" is a reserved top-level key, not a gate record. The
privacy gate is ALWAYS required regardless of that list's contents —
editing it out of gates.json does not un-require it.
"""
import json
import os
import subprocess
from datetime import datetime, timezone
from typing import List, Optional

REQUIRED_GATES_KEY = "required_gates"
ALWAYS_REQUIRED = ["privacy_guardrails_review"]
DEFAULT_PROJECTS_ROOT = "~/Documents/Projects"


def projects_root() -> str:
    """Where this harness looks for projects. Override via
    CLAUDE_HARNESS_PROJECTS_ROOT so other developers installing this as a
    plugin aren't locked into one person's folder convention; defaults to
    the harness's original layout for backward compatibility.
    """
    return os.path.abspath(
        os.path.expanduser(
            os.environ.get("CLAUDE_HARNESS_PROJECTS_ROOT") or DEFAULT_PROJECTS_ROOT
        )
    )


def project_root_for(cwd: str) -> Optional[str]:
    """Shared cwd -> project-root resolver used by every hook and script.
    Returns None if cwd isn't under projects_root(), or is the harness itself.
    """
    root = projects_root()
    cwd = os.path.abspath(cwd)
    if not cwd.startswith(root + os.sep):
        return None
    rest = cwd[len(root) + 1 :]
    if not rest or rest.startswith("_harness"):
        return None
    return os.path.join(root, rest.split(os.sep)[0])


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
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def _save_gates(project_root: str, gates: dict) -> None:
    path = gates_path(project_root)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(gates, f, indent=2)
        f.write("\n")


def record_gate(project_root: str, check: str, status: str, notes: str = "") -> dict:
    if check == REQUIRED_GATES_KEY:
        raise ValueError(f"'{REQUIRED_GATES_KEY}' is reserved — use set_required_gates()")
    if status not in ("pass", "fail"):
        raise ValueError("status must be 'pass' or 'fail'")

    gates = load_gates(project_root)
    gates[check] = {
        "status": status,
        "reviewed_commit": current_commit(project_root),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "notes": notes,
    }
    _save_gates(project_root, gates)
    return gates


def required_gates(project_root: str) -> List[str]:
    """Gates that must pass before a ship command. Privacy is always in."""
    gates = load_gates(project_root)
    extra = gates.get(REQUIRED_GATES_KEY)
    result = list(ALWAYS_REQUIRED)
    if isinstance(extra, list):
        for g in extra:
            if isinstance(g, str) and g and g not in result:
                result.append(g)
    return result


def set_required_gates(project_root: str, names: List[str]) -> List[str]:
    """Persist the opt-in required-gates list (privacy is implicit, always on)."""
    cleaned = sorted({n for n in names if isinstance(n, str) and n and n not in ALWAYS_REQUIRED})
    gates = load_gates(project_root)
    gates[REQUIRED_GATES_KEY] = cleaned
    _save_gates(project_root, gates)
    return required_gates(project_root)


def check_passing(project_root: str, check: str) -> bool:
    gates = load_gates(project_root)
    entry = gates.get(check)
    if not isinstance(entry, dict) or entry.get("status") != "pass":
        return False
    reviewed = entry.get("reviewed_commit")
    head = current_commit(project_root)
    if reviewed is None or head is None:
        return False
    return reviewed == head


def failing_required(project_root: str) -> List[str]:
    """Required gates NOT currently passing for HEAD — empty list means clear."""
    return [g for g in required_gates(project_root) if not check_passing(project_root, g)]
