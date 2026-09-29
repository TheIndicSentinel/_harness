#!/usr/bin/env python3
"""Shared helpers for reading/writing <project>/.harness/gates.json.

Used by gate_write.py (called from skills via Bash), release_gate.py (the
PreToolUse hard-block hook), and session_start.py, so the record format
never drifts.

gates.json shape:
  {
    "<gate_name>": {"status", "reviewed_commit", "timestamp", "notes"},
    ...
    "required_gates": ["privacy_guardrails_review", "qa_review", ...],  # optional
    "release_commands": ["make release", "./scripts/deploy.sh"]        # optional
  }

"required_gates" and "release_commands" are reserved top-level keys, not
gate records (see RESERVED_KEYS). The privacy gate is ALWAYS required
regardless of required_gates' contents — editing it out of gates.json does
not un-require it. release_commands supplements (never replaces) the
built-in regex patterns in release_gate.py.
"""
import json
import os
import subprocess
from datetime import datetime, timezone
from typing import List, Optional

REQUIRED_GATES_KEY = "required_gates"
RELEASE_COMMANDS_KEY = "release_commands"
RESERVED_KEYS = (REQUIRED_GATES_KEY, RELEASE_COMMANDS_KEY)
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


MIN_NOTES_LENGTH = 15


def record_gate(project_root: str, check: str, status: str, notes: str = "") -> dict:
    if check in RESERVED_KEYS:
        raise ValueError(f"'{check}' is reserved — use the matching set_*() helper")
    if status not in ("pass", "fail"):
        raise ValueError("status must be 'pass' or 'fail'")
    if len(notes.strip()) < MIN_NOTES_LENGTH:
        # Not real protection against a determined bad actor -- a fabricated
        # pass can still write a plausible-sounding fake summary. But it
        # closes the cheapest failure mode (an empty or one-word "pass",
        # accidental or not) and forces at least a sentence a human can
        # sanity-check later. See docs/CI_GATE_CHECK.md's "honest limit"
        # section for what this does and doesn't protect against.
        raise ValueError(
            f"notes must be a real summary (at least {MIN_NOTES_LENGTH} characters after "
            f"trimming, got {len(notes.strip())}) -- an empty or trivial note is the "
            f"cheapest way to fabricate a pass, don't make that path easy"
        )

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


def release_commands(project_root: str) -> List[str]:
    """Project-declared release command substrings (e.g. "make release",
    "./scripts/deploy.sh"), checked by release_gate.py IN ADDITION TO the
    built-in generic regex patterns -- not instead of them. Exists because a
    generic pattern list can't know about a project's own custom deploy
    script, and building a bespoke adapter per cloud provider doesn't scale;
    letting a project just declare its own command(s) does. Empty by
    default -- most projects rely on the built-in patterns alone."""
    gates = load_gates(project_root)
    declared = gates.get(RELEASE_COMMANDS_KEY)
    if not isinstance(declared, list):
        return []
    return [c for c in declared if isinstance(c, str) and c.strip()]


def set_release_commands(project_root: str, commands: List[str]) -> List[str]:
    cleaned = sorted({c.strip() for c in commands if isinstance(c, str) and c.strip()})
    gates = load_gates(project_root)
    gates[RELEASE_COMMANDS_KEY] = cleaned
    _save_gates(project_root, gates)
    return release_commands(project_root)


def is_working_tree_dirty(project_root: str) -> bool:
    """True if there are uncommitted changes (staged or not) OUTSIDE the
    harness's own .harness/ bookkeeping directory. A passing gate only
    vouches for the reviewed commit's committed content -- a release command
    run against a dirty tree can ship code that was never reviewed even
    though HEAD still matches the gate record. .harness/ is excluded because
    it's routinely untracked-by-design (gates.json/budget.json are local
    sidecar files, not committed by default -- see docs/CI_GATE_CHECK.md) so
    its mere presence isn't unreviewed code. docs/COST_LOG.md is excluded too:
    session_log.py appends to it at the end of every session, so counting it
    would make every ship blocked-by-default (commit it -> gate goes stale ->
    re-review -> another session -> dirty again). It's a local log, not
    shipped code. Fails safe: a git error (e.g.
    not a repo) counts as dirty, since "unknown" shouldn't read as clean.
    """
    try:
        result = subprocess.run(
            ["git", "-C", project_root, "status", "--porcelain", "--",
             ".", ":(exclude).harness", ":(exclude)docs/COST_LOG.md"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            return True
        return bool(result.stdout.strip())
    except (OSError, subprocess.SubprocessError):
        return True
