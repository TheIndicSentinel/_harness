#!/usr/bin/env python3
"""Numbers behind the atlas panel "Harness cost vs measured benefit".

Data only; the HTML is built in generate_atlas.py. Four inputs:

1. COST: the context the harness injects into a session. A live estimate from the
   files themselves (bytes / 4, which undercounts by roughly 40% against
   `/context`) next to the last real `/context` snapshot (context_snapshot.py).
2. ORIENT TREND: rows from the cost log written by the SessionEnd hook. Only the
   current 6-column format carries Orient; the legacy log rows do not.
3. TOKENS PER TASK: from session_data.summarize (a task is a git branch).
4. BASELINE DELTAS: a measurement pilot, read from <data dir>/baseline/<project>-compare.json,
   with the sample size and a stated noise rule.

Noise rule (deliberately simple and conservative for one run per cell): the
control variant differs from "before" only by time and memory drift, so its
relative change against "before" is an empirical noise floor. A delta is
"within noise" when |after - before| / before <= max(|control - before| / before, 10%).
With n = 5 tasks and one run per cell, "beyond noise" is a lead to test, not a result.

Concentration check: when one task accounts for at least 60% of the summed absolute
per-task change (and there are 3+ tasks), the result is marked "one task drives it":
a single slow or fast run is an outlier, not a pattern.
"""
import glob
import json
import os
import re
import sys
from typing import Dict, List, Optional

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "..", "hooks"))
sys.path.insert(0, _HERE)

from cost_log_lib import latest_per_session, read_rows  # noqa: E402
from gate_lib import data_dir  # noqa: E402
from memory_lib import memory_dir  # noqa: E402
import context_budget  # noqa: E402
import session_start  # noqa: E402

CHARS_PER_TOKEN = 4
NOISE_FLOOR = 0.10
CONCENTRATION = 0.60
MEMORY_INDEX_CAP_BYTES = 25_000   # documented limit on what loads from MEMORY.md

# (key in the compare file, label, summed over, lower is better)
METRICS = [
    ("wall_s", "Wall time (s)", "all"),
    ("in_out", "Tokens, in + out", "all"),
    ("cache_read", "Cache-read tokens", "all"),
    ("cost_usd", "Cost ($)", "all"),
    ("turns", "Turns", "all"),
    ("orient_old", "Orient, original definition", "edit"),
    ("orient_new", "Orient, incl. shell reads", "edit"),
]


def est_tokens(nbytes: int) -> int:
    return int(round(nbytes / CHARS_PER_TOKEN))


def _size(path: str) -> int:
    try:
        return os.path.getsize(path)
    except OSError:
        return 0


# ---------------------------------------------------------------- 1. cost
def injected_context(root: str, names: List[str], harness_root: str) -> dict:
    """Estimated tokens the harness (umbrella + listings) and each project add at session start."""
    cb = context_budget.measure(harness_root)
    projects = []
    for name in names:
        pr = os.path.join(root, name)
        claude_md = os.path.join(pr, "CLAUDE.md")
        imports = 0
        try:
            with open(claude_md, errors="replace") as f:
                for line in f:
                    m = re.match(r"^@(\S+)", line)
                    if m:
                        imports += _size(os.path.join(pr, m.group(1)))
        except OSError:
            pass
        try:
            lines = session_start.collect_lines(pr, record_alerts=False)
        except Exception:
            lines = []
        projects.append({
            "name": name,
            "claude_md": est_tokens(_size(claude_md)),
            "imports": est_tokens(imports),
            "memory_index": est_tokens(min(_size(os.path.join(memory_dir(pr), "MEMORY.md")), MEMORY_INDEX_CAP_BYTES)),
            "session_start": est_tokens(len("\n".join(lines).encode())),
            "session_start_lines": len(lines),
        })
    return {
        "umbrella_est": est_tokens(cb["claude_md_bytes"]),
        "listing_est": est_tokens(cb["listed_description_chars"]),
        "projects": projects,
    }


# ---------------------------------------------------------------- 2. orient
def real_orient_rows() -> List[dict]:
    """Orient values from real sessions: the latest row of each session, rows that carry a
    number (original-format rows have none, and sessions without an edit log '-')."""
    rows = []
    for path in glob.glob(os.path.join(data_dir(), "cost", "*.md")):
        stem = os.path.splitext(os.path.basename(path))[0]
        if stem.startswith("zz-"):          # measurement worktrees and probes, not real work
            continue
        for r in latest_per_session(read_rows(path)):
            if r["orient"].isdigit():
                rows.append({"date": r["date"], "project": stem, "orient": int(r["orient"]), "branch": r["branch"]})
    return sorted(rows, key=lambda r: r["date"])


# ---------------------------------------------------------------- 3. per-task tokens
def top_tasks(work: dict, k: int = 8) -> List[dict]:
    out = []
    for project, p in (work or {}).items():
        if project in ("baseline", "other"):
            continue
        for branch, t in p["tasks"].items():
            out.append({"project": project, "task": branch, "tokens": t["tin"] + t["tout"], "sessions": len(t["sessions"])})
    return sorted(out, key=lambda r: -r["tokens"])[:k]


# ---------------------------------------------------------------- 4. baseline deltas
def load_compare(project: str) -> Optional[dict]:
    try:
        with open(os.path.join(data_dir(), "baseline", "%s-compare.json" % project)) as f:
            data = json.load(f)
        return data if data.get("schema") == 1 and "cells" in data else None
    except (OSError, json.JSONDecodeError):
        return None


def find_compare() -> Optional[dict]:
    """The most recently modified valid <project>-compare.json in the baseline folder, or None."""
    paths = sorted(glob.glob(os.path.join(data_dir(), "baseline", "*-compare.json")), key=os.path.getmtime, reverse=True)
    for path in paths:
        data = load_compare(os.path.basename(path)[: -len("-compare.json")])
        if data:
            return data
    return None


def provenance(compare: dict) -> dict:
    """Where the comparison's numbers came from. A file is only 'generated' when it says which
    script generated it; otherwise it is hand-entered and the panel says so."""
    generated_by = compare.get("generated_by")
    return {
        "hand_entered": not generated_by,
        "generated_by": generated_by,
        "text": compare.get("provenance") or "No provenance recorded for this file.",
        "cross_checked": set(compare.get("cross_checked", [])),
    }


def label_delta(before: float, control: float, after: float, floor: float = NOISE_FLOOR) -> dict:
    """Relative change of `after` against `before`, judged against the control's drift."""
    if not before:
        return {"rel_after": None, "rel_control": None, "noise": None, "verdict": "n/a"}
    rel_a = (after - before) / before
    rel_c = (control - before) / before
    noise = max(abs(rel_c), floor)
    return {"rel_after": rel_a, "rel_control": rel_c, "noise": noise,
            "verdict": "within noise" if abs(rel_a) <= noise else "beyond noise"}


def delta_table(compare: dict) -> List[dict]:
    """One row per metric: totals per variant, deltas and the noise label."""
    cells = compare["cells"]
    tasks = sorted(cells["before"])
    rows = []
    for key, label, scope in METRICS:
        use = tasks
        if scope == "edit":     # Orient is only defined for tasks that edit, in every variant
            use = [t for t in tasks if all(cells[v].get(t, {}).get(key) is not None for v in ("before", "control", "after"))]
        if not use:
            continue
        tot = {v: sum(cells[v][t][key] for t in use) for v in ("before", "control", "after")}
        d = label_delta(tot["before"], tot["control"], tot["after"])
        per_task = [cells["after"][t][key] - cells["before"][t][key] for t in use]
        spread = sum(abs(x) for x in per_task)
        share = (max(abs(x) for x in per_task) / spread) if spread else 0.0
        concentrated = len(use) >= 3 and share >= CONCENTRATION
        rows.append({"key": key, "metric": label, "n_tasks": len(use), "totals": tot, **d,
                     "top_task_share": share, "concentrated": concentrated})
    return rows


def task_tokens(compare: dict) -> List[dict]:
    cells = compare["cells"]
    return [{"task": t, **{v: cells[v][t]["in_out"] for v in ("before", "control", "after")}} for t in sorted(cells["before"])]


def reading(delta_rows: List[dict], snapshot: Optional[dict], orient_real: int, runs_per_cell: int, n_tasks: int,
            hand_entered: bool = False) -> List[str]:
    """Plain sentences computed from the data. They state what was and was not shown."""
    out = []
    if snapshot:
        h = snapshot["harness"]
        out.append("Cost: harness-owned context at session start was %s tokens, %s%% of a %s-token start (measured with /context, %s)."
                   % (format(h["harness_total"], ","), h["harness_share_pct"], format(h["session_total"], ","), snapshot["captured_at"][:10]))
    else:
        out.append("Cost: no /context snapshot yet; only the file-size estimate is available.")
    if delta_rows:
        beyond = [r for r in delta_rows if r["verdict"] == "beyond noise"]
        solid = [r for r in beyond if not r["concentrated"]]
        out.append("Benefit: of %d baseline metrics, %d moved beyond the noise floor (%d of those driven by a single task) and %d stayed within it (n = %d tasks, %d run per cell%s)."
                   % (len(delta_rows), len(beyond), len(beyond) - len(solid), len(delta_rows) - len(beyond), n_tasks, runs_per_cell,
                      "; the figures are hand-entered from the pilot" if hand_entered else ""))
        if solid:
            out.append("Beyond noise across several tasks: %s. With one run per cell this is a lead to test, not a result." % ", ".join(r["metric"] for r in solid))
        elif beyond:
            out.append("Every beyond-noise result is one task's change (%s): outliers, not a pattern." % ", ".join(r["metric"] for r in beyond))
            out.append("Measured benefit: not demonstrated by this baseline.")
        else:
            out.append("Measured benefit: not demonstrated by this baseline.")
    else:
        out.append("Benefit: no baseline comparison recorded.")
    out.append("Orient trend: %s." % ("%d real-session row(s)" % orient_real if orient_real else
                                       "no real-session rows yet (the cost log fills as sessions end under the current hook)"))
    return out
