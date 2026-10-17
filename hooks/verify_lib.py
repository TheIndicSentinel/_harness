#!/usr/bin/env python3
"""Shared state for the opt-in Stop verification hook (verify_before_stop.py).

The verify command is stored OUTSIDE the project repo, in the harness data
dir (gate_lib.data_dir()/verify/<project>.json). A repo-supplied file would
let any cloned repository run an arbitrary command at the end of every turn;
keeping it per-user and set by you (verify_write.py) closes that.
"""
import hashlib
import json
import os
import subprocess
from typing import Optional

from gate_lib import data_dir

DEFAULT_TIMEOUT = 300
MAX_TIMEOUT = 800  # must stay under the Stop hook's own timeout in hooks.json
MAX_CONSECUTIVE_BLOCKS = 3
SLOW_SECONDS = 60  # advisory: above this the hook is a drag on interactive work


def _base(project_root: str) -> str:
    return os.path.join(data_dir(), "verify", os.path.basename(project_root))


def config_path(project_root: str) -> str:
    return _base(project_root) + ".json"


def state_path(project_root: str) -> str:
    return _base(project_root) + ".state.json"


def _read_json(path: str) -> dict:
    try:
        with open(path) as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def load_config(project_root: str) -> dict:
    cfg = _read_json(config_path(project_root))
    cmd = cfg.get("command")
    if not isinstance(cmd, str) or not cmd.strip():
        return {}
    timeout = cfg.get("timeout_seconds", DEFAULT_TIMEOUT)
    if not isinstance(timeout, int) or timeout <= 0:
        timeout = DEFAULT_TIMEOUT
    return {"command": cmd.strip(), "timeout_seconds": min(timeout, MAX_TIMEOUT)}


def save_config(project_root: str, command: str, timeout: int = DEFAULT_TIMEOUT) -> dict:
    os.makedirs(os.path.dirname(config_path(project_root)), exist_ok=True)
    cfg = {"command": command.strip(), "timeout_seconds": min(max(1, timeout), MAX_TIMEOUT)}
    with open(config_path(project_root), "w") as f:
        json.dump(cfg, f, indent=2)
        f.write("\n")
    return cfg


def clear_config(project_root: str) -> None:
    for p in (config_path(project_root), state_path(project_root)):
        try:
            os.remove(p)
        except OSError:
            pass


def load_state(project_root: str) -> dict:
    return _read_json(state_path(project_root))


def save_state(project_root: str, state: dict) -> None:
    os.makedirs(os.path.dirname(state_path(project_root)), exist_ok=True)
    with open(state_path(project_root), "w") as f:
        json.dump(state, f)


def _git(project_root: str, *args: str) -> Optional[bytes]:
    try:
        r = subprocess.run(["git", "-C", project_root, *args], capture_output=True, timeout=15)
        return r.stdout if r.returncode == 0 else None
    except (OSError, subprocess.SubprocessError):
        return None


def fingerprint(project_root: str) -> Optional[dict]:
    """HEAD + a hash of the dirty working tree. None when not a git repo."""
    head = _git(project_root, "rev-parse", "HEAD")
    if head is None:
        return None
    status = _git(project_root, "status", "--porcelain=v1", "-z") or b""
    diff = _git(project_root, "diff", "HEAD") or b""
    dirty = bool(status.strip(b"\0"))
    h = hashlib.sha256(head + b"\0" + status + b"\0" + diff).hexdigest()
    return {"head": head.decode().strip(), "dirty": dirty, "hash": h}
