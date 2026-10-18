#!/usr/bin/env python3
"""Token usage per project and per task, read from Claude Code's own session
transcripts (~/.claude/projects/*/*.jsonl and the subagent transcripts nested
under each session).

Why transcripts and not the cost log: they exist for every past session, carry
`cwd` and `gitBranch` on each entry (so a long session that moved across many
branches is split into tasks), and keep subagent usage separate. A "task" here
is a git branch, which matches a one-branch-per-PR workflow; it is a proxy, not
a measurement of intent.

Counting rules (same as hooks/session_log.py): usage is counted once per API
message id, the last record of an id wins; "in" = input_tokens +
cache_creation_input_tokens, "out" = output_tokens, cache reads are reported
separately because they re-count the whole context every turn. Days are UTC.

No prompt or message text is read into the result. The transcript format is
undocumented, so this is best-effort like the rest of the harness's accounting.
Per-file results are cached outside any repo (gate_lib.data_dir()/cache/) keyed
by size and mtime, so a regeneration re-reads only transcripts that changed.
"""
import datetime
import glob
import json
import os
import statistics
import sys
from collections import defaultdict
from typing import Dict, List, Optional

CACHE_VERSION = 1


def project_for(cwd: Optional[str], root: str, names: List[str]) -> str:
    """Map a working directory to a harness project name, 'harness' for the
    tool itself, 'baseline' for the measurement worktrees, else 'other'."""
    if not cwd:
        return "other"
    cwd = os.path.abspath(cwd)
    root = os.path.abspath(root)
    if cwd == root or not cwd.startswith(root + os.sep):
        # Outside the projects root (e.g. a project's old location): match by name.
        base = os.path.basename(cwd)
        return base if base in names else "other"
    first = cwd[len(root) + 1:].split(os.sep)[0]
    if first.startswith("_harness"):
        return "harness"
    if first.startswith("zz-baseline"):
        return "baseline"
    return first if first in names else "other"


def _parse_file(path: str, root: str, names: List[str]) -> List[list]:
    """Aggregate one transcript to rows [project, branch, day, in, out, cache_read, messages]."""
    by_id: Dict[str, list] = {}
    cwd = branch = None
    cwd_cache: Dict[str, str] = {}
    n_anon = 0
    try:
        with open(path, "r", errors="replace") as f:
            for line in f:
                try:
                    e = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if e.get("cwd"):
                    cwd = e["cwd"]
                if e.get("gitBranch"):
                    branch = e["gitBranch"]
                msg = e.get("message")
                if not isinstance(msg, dict):
                    continue
                usage = msg.get("usage")
                if not isinstance(usage, dict):
                    continue
                mid = msg.get("id")
                if not mid:
                    n_anon += 1
                    mid = "anon:%d" % n_anon
                if cwd not in cwd_cache:
                    cwd_cache[cwd] = project_for(cwd, root, names)
                ts = str(e.get("timestamp") or "")
                by_id[mid] = [
                    cwd_cache[cwd],
                    branch if branch and branch != "HEAD" else ("(detached)" if branch else "(no git)"),
                    ts[:10] or "unknown",
                    int(usage.get("input_tokens", 0) or 0) + int(usage.get("cache_creation_input_tokens", 0) or 0),
                    int(usage.get("output_tokens", 0) or 0),
                    int(usage.get("cache_read_input_tokens", 0) or 0),
                ]
    except OSError:
        return []
    agg: Dict[tuple, list] = {}
    for proj, br, day, tin, tout, cr in by_id.values():
        a = agg.setdefault((proj, br, day), [0, 0, 0, 0])
        a[0] += tin
        a[1] += tout
        a[2] += cr
        a[3] += 1
    return [[k[0], k[1], k[2], *v] for k, v in agg.items()]


def _load_cache(cache_path: str) -> dict:
    try:
        with open(cache_path) as f:
            data = json.load(f)
        if data.get("version") == CACHE_VERSION and isinstance(data.get("files"), dict):
            return data
    except (OSError, json.JSONDecodeError):
        pass
    return {"version": CACHE_VERSION, "files": {}}


def scan(claude_home: str, root: str, names: List[str], cache_path: Optional[str] = None) -> List[dict]:
    """One dict per (file, project, branch, day):
    {project, branch, day, sid, sub, tin, tout, cr, msgs}. `sub` marks subagent transcripts."""
    pattern_main = os.path.join(claude_home, "projects", "*", "*.jsonl")
    pattern_sub = os.path.join(claude_home, "projects", "*", "*", "**", "*.jsonl")
    files = [(p, False) for p in glob.glob(pattern_main)]
    files += [(p, True) for p in glob.glob(pattern_sub, recursive=True)]
    cache = _load_cache(cache_path) if cache_path else {"version": CACHE_VERSION, "files": {}}
    fresh: Dict[str, dict] = {}
    out: List[dict] = []
    for path, is_sub in files:
        try:
            st = os.stat(path)
        except OSError:
            continue
        key = "%d:%d:%s" % (st.st_size, int(st.st_mtime), ",".join(sorted(names)) + "|" + root)
        hit = cache["files"].get(path)
        if hit and hit.get("key") == key:
            rows = hit["rows"]
        else:
            rows = _parse_file(path, root, names)
        fresh[path] = {"key": key, "rows": rows}
        # session id: the transcript's own id (main), or its parent session dir (subagent)
        if is_sub:
            rel = os.path.relpath(path, os.path.join(claude_home, "projects")).split(os.sep)
            sid = rel[1] if len(rel) > 1 else os.path.basename(path)
        else:
            sid = os.path.splitext(os.path.basename(path))[0]
        for proj, br, day, tin, tout, cr, n in rows:
            out.append({"project": proj, "branch": br, "day": day, "sid": sid, "sub": is_sub,
                        "tin": tin, "tout": tout, "cr": cr, "msgs": n})
    if cache_path:
        try:
            os.makedirs(os.path.dirname(cache_path), exist_ok=True)
            with open(cache_path, "w") as f:
                json.dump({"version": CACHE_VERSION, "files": fresh}, f)
        except OSError:
            pass
    return out


def summarize(rows: List[dict]) -> dict:
    """Roll rows up per project: totals, per-task (branch), per-day, per-session.
    Main-session and subagent tokens are kept apart."""
    projects: Dict[str, dict] = {}
    for r in rows:
        p = projects.setdefault(r["project"], {
            "tin": 0, "tout": 0, "cr": 0, "sub_tin": 0, "sub_tout": 0, "msgs": 0,
            "tasks": {}, "days": defaultdict(int), "sessions": {}, "first": None, "last": None,
        })
        sub = r["sub"]
        t = p["tasks"].setdefault(r["branch"], {
            "tin": 0, "tout": 0, "cr": 0, "sub_tin": 0, "sub_tout": 0, "msgs": 0,
            "sessions": set(), "first": None, "last": None,
        })
        s = p["sessions"].setdefault(r["sid"], {"tin": 0, "tout": 0, "cr": 0, "sub_tin": 0, "sub_tout": 0,
                                                 "first": None, "last": None, "branches": set()})
        for tgt in (p, t, s):
            if sub:
                tgt["sub_tin"] += r["tin"]
                tgt["sub_tout"] += r["tout"]
            else:
                tgt["tin"] += r["tin"]
                tgt["tout"] += r["tout"]
                tgt["cr"] += r["cr"]
        p["msgs"] += r["msgs"]
        t["msgs"] += r["msgs"]
        t["sessions"].add(r["sid"])
        s["branches"].add(r["branch"])
        p["days"][r["day"]] += r["tin"] + r["tout"]
        for tgt in (p, t, s):
            if r["day"] != "unknown":
                tgt["first"] = r["day"] if tgt["first"] is None else min(tgt["first"], r["day"])
                tgt["last"] = r["day"] if tgt["last"] is None else max(tgt["last"], r["day"])
    return projects


def weekly(rows: List[dict], today: Optional[datetime.date] = None, days: int = 7) -> dict:
    """Last `days` UTC days (including today) per project, main sessions only (subagents are
    reported separately by summarize). Definitions:
      sessions      distinct main-session transcripts with usage in the window
      in_out        input + cache creation + output tokens
      cache_hit     cache_read / (cache_read + input + cache creation); None if both are 0
      median_turns  median API responses (distinct message ids) per session within the window
    """
    today = today or datetime.datetime.now(datetime.timezone.utc).date()
    window = {(today - datetime.timedelta(days=i)).isoformat() for i in range(days)}
    out: Dict[str, dict] = {}
    for p in sorted({r["project"] for r in rows}):
        sel = [r for r in rows if r["project"] == p and r["day"] in window and not r["sub"]]
        if not sel:
            continue
        per: Dict[str, int] = {}
        for r in sel:
            per[r["sid"]] = per.get(r["sid"], 0) + r["msgs"]
        tin = sum(r["tin"] for r in sel)
        tout = sum(r["tout"] for r in sel)
        cr = sum(r["cr"] for r in sel)
        out[p] = {"sessions": len(per), "in_out_tokens": tin + tout, "cache_read_tokens": cr,
                  "cache_hit_share": round(cr / (cr + tin), 4) if cr + tin else None,
                  "median_session_turns": statistics.median(per.values())}
    return out


def main(argv: List[str]) -> int:
    """session_data.py --weekly OUTPUT.json: write the last-7-days table (same transcript source as the atlas)."""
    if len(argv) == 2 and argv[0] == "--weekly":
        here = os.path.dirname(os.path.abspath(__file__))
        sys.path.insert(0, os.path.join(here, "..", "hooks"))
        sys.path.insert(0, here)
        from gate_lib import data_dir, projects_root
        from memory_lib import claude_home
        import generate_atlas
        root = projects_root()
        rows = scan(claude_home(), root, generate_atlas.list_project_names(root), os.path.join(data_dir(), "cache", "sessions.json"))
        today = datetime.datetime.now(datetime.timezone.utc).date()
        doc = {"schema": 1, "kind": os.path.splitext(os.path.basename(argv[1]))[0], "recorded": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
               "window_utc_days": [(today - datetime.timedelta(days=6)).isoformat(), today.isoformat()],
               "source": "session transcripts via session_data.scan (same as the atlas); no prompt text", "projects": weekly(rows, today)}
        with open(argv[1], "w") as f:
            json.dump(doc, f, indent=1)
            f.write("\n")
        print(argv[1])
        return 0
    print("usage: session_data.py --weekly OUTPUT.json", file=sys.stderr)
    return 2


def fmt(n: int) -> str:
    """Compact token count: 1,234 -> 1.2k, 1,234,567 -> 1.23M."""
    n = int(n)
    if n >= 1_000_000:
        return "%.2fM" % (n / 1_000_000)
    if n >= 10_000:
        return "%dk" % round(n / 1000)
    if n >= 1000:
        return "%.1fk" % (n / 1000)
    return str(n)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
