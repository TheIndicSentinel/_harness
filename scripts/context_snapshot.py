#!/usr/bin/env python3
"""Measure what a fresh Claude Code session actually starts with, using the
real `/context` report, and keep the latest result for the atlas panel
"Harness cost vs measured benefit".

`claude -p "/context"` makes no model call (checked: 0 turns, $0), so this costs
no tokens. It must run under the projects root so the umbrella CLAUDE.md is
part of the session; it therefore creates a throwaway project directory there
and removes its traces afterwards. Every deletion is limited to what this one
probe created:
  - the directory is made with mkdtemp (a fresh, uniquely named path that did not
    exist) and only that exact path is removed;
  - in the transcript folder Claude Code keys by that path, only entries that
    appeared during the run are removed, and the folder itself only if it ends up
    empty;
  - in the cost log named after the probe, only rows carrying the probe
    session's id are removed, and the file only if no rows remain.
Anything else (other sessions, other projects, other cost rows) is left alone.

What counts as "harness-owned": the umbrella CLAUDE.md, the harness's own
skills and commands (matched by name against what is on disk) and its
subagents. Everything else in the report (system prompt, tools, MCP, plugin and
built-in skills) is shown for scale, not attributed to the harness.

The report's numbers are Claude Code's own estimates, rounded ("~150", "9.2k").
Snapshots are stored in gate_lib.data_dir()/measurements/.

Usage: context_snapshot.py [--show]
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from typing import Dict, List, Optional

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "..", "hooks"))

from gate_lib import data_dir, projects_root  # noqa: E402
from memory_lib import claude_home  # noqa: E402

SCHEMA = 1
PROBE_PREFIX = "zz-context-probe-"   # the directory itself is made unique per run with mkdtemp


def _num(text: str) -> int:
    """'23.9k' -> 23900, '865' -> 865, '~150' -> 150, '< 20' -> 20, '1m' -> 1000000."""
    m = re.search(r"(\d+(?:\.\d+)?)\s*([km]?)", text.replace(",", ""))
    if not m:
        return 0
    value = float(m.group(1))
    return int(round(value * {"": 1, "k": 1000, "m": 1_000_000}[m.group(2)]))


def _section(text: str, heading: str) -> str:
    i = text.find("### " + heading)
    if i < 0:
        return ""
    j = text.find("\n### ", i + 5)
    return text[i: j if j > 0 else len(text)]


def _rows(section: str, columns: int) -> List[List[str]]:
    out = []
    for line in section.splitlines():
        if not line.startswith("|") or line.startswith("|--") or line.startswith("|-"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) == columns and cells[0] not in ("Category", "Type", "Tool", "Agent", "Skill", "Name"):
            out.append(cells)
    return out


def parse_context(text: str) -> dict:
    """Parse the markdown `/context` report into plain numbers."""
    total = re.search(r"\*\*Tokens:\*\*\s*([\d.,]+\s*[km]?)", text)
    categories = {c[0]: _num(c[1]) for c in _rows(_section(text, "Estimated usage by category"), 3)}
    memory = [{"type": r[0], "path": r[1], "tokens": _num(r[2])} for r in _rows(_section(text, "Memory Files"), 3)]
    agents = [{"name": r[0], "source": r[1], "tokens": _num(r[2])} for r in _rows(_section(text, "Custom Agents"), 3)]
    skills = [{"name": r[0], "source": r[1], "tokens": _num(r[2])} for r in _rows(_section(text, "Skills"), 3)]
    return {
        "total_tokens": _num(total.group(1)) if total else 0,
        "categories": categories,
        "memory_files": memory,
        "agents": agents,
        "skills": skills,
    }


def harness_share(parsed: dict, owned_names: List[str], umbrella_path: str) -> dict:
    """Split the report into what the harness contributes and the rest."""
    owned = set(owned_names)
    umbrella = sum(m["tokens"] for m in parsed["memory_files"]
                   if os.path.abspath(m["path"]) == os.path.abspath(umbrella_path))
    listing = sum(s["tokens"] for s in parsed["skills"] if s["name"] in owned)
    agents = sum(a["tokens"] for a in parsed["agents"])
    total = parsed["total_tokens"]
    mine = umbrella + listing + agents
    return {
        "umbrella_claude_md": umbrella,
        "skills_and_commands": listing,
        "agents": agents,
        "harness_total": mine,
        "session_total": total,
        "harness_share_pct": round(100.0 * mine / total, 1) if total else None,
    }


def snapshot_path() -> str:
    return os.path.join(data_dir(), "measurements", "context-latest.json")


def load_latest() -> Optional[dict]:
    try:
        with open(snapshot_path()) as f:
            data = json.load(f)
        return data if isinstance(data, dict) and data.get("schema") == SCHEMA else None
    except (OSError, json.JSONDecodeError):
        return None


def age_hours(snapshot: dict, now: Optional[datetime] = None) -> Optional[float]:
    try:
        taken = datetime.fromisoformat(snapshot["captured_at"])
    except (KeyError, ValueError):
        return None
    return ((now or datetime.now(timezone.utc)) - taken).total_seconds() / 3600.0


def save(snapshot: dict) -> None:
    path = snapshot_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(snapshot, f, indent=2)
        f.write("\n")
    with open(os.path.join(os.path.dirname(path), "context-history.jsonl"), "a") as f:
        f.write(json.dumps(snapshot) + "\n")


def _enc(path: str) -> str:
    """Claude Code's folder name for a working directory."""
    return re.sub(r"[^A-Za-z0-9]", "-", os.path.abspath(path))


def _inside(path: str, root: str) -> bool:
    """True if `path` is strictly inside `root` once symlinks are resolved."""
    real, base = os.path.realpath(path), os.path.realpath(root)
    return real != base and real.startswith(base + os.sep)


def _remove(path: str) -> None:
    if os.path.islink(path) or os.path.isfile(path):
        os.remove(path)
    elif os.path.isdir(path):
        shutil.rmtree(path, ignore_errors=True)


def _cleanup_probe(probe: str, enc_dir: str, before: set) -> None:
    """Remove only what the probe created (see the module docstring)."""
    # 1. the probe directory: the exact mkdtemp path, and only if it is where we made it
    if os.path.basename(probe).startswith(PROBE_PREFIX) and _inside(probe, projects_root()) and not os.path.islink(probe):
        shutil.rmtree(probe, ignore_errors=True)

    # 2. the transcript folder for that path: only entries that appeared during the run
    projects_dir = os.path.join(claude_home(), "projects")
    session_ids = set()
    if os.path.basename(enc_dir) == _enc(probe) and _inside(enc_dir, projects_dir) and os.path.isdir(enc_dir):
        for entry in sorted(set(os.listdir(enc_dir)) - before):
            if entry.endswith(".jsonl"):
                session_ids.add(entry[: -len(".jsonl")])
            _remove(os.path.join(enc_dir, entry))
        try:
            os.rmdir(enc_dir)           # only succeeds if nothing else is in it
        except OSError:
            pass

    # 3. the cost-log rows this probe's session wrote
    cost = os.path.join(data_dir(), "cost", os.path.basename(probe) + ".md")
    if session_ids and os.path.isfile(cost) and _inside(cost, data_dir()):
        mine = {sid[:8] for sid in session_ids}
        try:
            lines = open(cost).read().splitlines()
        except OSError:
            return
        kept = []
        for line in lines:
            cells = [c.strip() for c in line.strip().strip("|").split("|")] if line.startswith("| 20") else []
            if cells and len(cells) > 1 and cells[1] in mine:
                continue
            kept.append(line)
        if any(l.startswith("| 20") for l in kept):
            with open(cost, "w") as f:
                f.write("\n".join(kept) + "\n")
        else:
            os.remove(cost)


def capture(owned_names: List[str], harness_root: str, timeout: int = 40, claude_bin: str = "claude") -> Optional[dict]:
    """Run `claude -p /context` under the projects root and return a snapshot, or
    None if claude is missing, times out or returns nothing parseable."""
    if not shutil.which(claude_bin):
        return None
    probe = tempfile.mkdtemp(prefix=PROBE_PREFIX, dir=projects_root())     # fresh path: never an existing directory
    enc_dir = os.path.join(claude_home(), "projects", _enc(probe))
    before = set(os.listdir(enc_dir)) if os.path.isdir(enc_dir) else set()
    try:
        try:
            r = subprocess.run([claude_bin, "-p", "/context"], cwd=probe, capture_output=True, text=True,
                               timeout=timeout, stdin=subprocess.DEVNULL)
        except (OSError, subprocess.SubprocessError):
            return None
        parsed = parse_context(r.stdout)
        if not parsed["total_tokens"] or not parsed["categories"]:
            return None
        version = ""
        try:
            version = subprocess.run([claude_bin, "--version"], capture_output=True, text=True, timeout=10).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            pass
        share = harness_share(parsed, owned_names, os.path.join(projects_root(), "CLAUDE.md"))
        return {
            "schema": SCHEMA,
            "captured_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "claude_version": version,
            "total_tokens": parsed["total_tokens"],
            "categories": parsed["categories"],
            "harness": share,
            "skills_listed": len(parsed["skills"]),
        }
    finally:
        _cleanup_probe(probe, enc_dir, before)


def main(argv: List[str]) -> int:
    if "--show" in argv:
        snap = load_latest()
        print(json.dumps(snap, indent=2) if snap else "No snapshot yet.")
        return 0
    sys.path.insert(0, _HERE)
    import generate_atlas as ga  # noqa: E402  (inventory of the harness's own names)

    skills, commands, agents = ga.harness_inventory()
    snap = capture(skills + commands, ga.HARNESS_ROOT)
    if not snap:
        print("Could not capture /context (claude missing, timed out, or unparseable).", file=sys.stderr)
        return 1
    save(snap)
    h = snap["harness"]
    print("Session starts at %d tokens; harness-owned %d (%s%%): CLAUDE.md %d, skills/commands %d, agents %d."
          % (snap["total_tokens"], h["harness_total"], h["harness_share_pct"], h["umbrella_claude_md"],
             h["skills_and_commands"], h["agents"]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
