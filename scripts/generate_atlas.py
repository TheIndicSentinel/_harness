#!/usr/bin/env python3
"""Generate the LIVE mind tree ("Atlas") from current harness data.

The page is a fixed engine plus generated data. The engine (CSS, layout, the
render()/navigateTo()/kind-badge JavaScript) lives in its own file,
scripts/atlas_engine.html, with three placeholders this script fills in:
@@ATLAS_DATA@@ (projects, categories, leaves, detail cards), @@PROVENANCE@@
(the "generated at" banner) and @@FLEET_PILLS@@ (the project selector).

What is live here: gate status, docs adopted, project health, recent commits,
memory files, wired hooks and capabilities, and tokens per project and per task
(read from Claude Code session transcripts, see session_data.py).
What it cannot show: gate-round-by-round HISTORY (gates.json only keeps the
current record) and any "why this mattered" narrative -- both need judgment,
not just data.

Usage: python3 generate_atlas.py [output_path] [--open] [--no-refresh]
  --open        open the generated page in the default browser (or run /harness-atlas, or `harness-ui`)
  --no-refresh  do not re-measure the session-start context with `claude -p /context` (it costs no
                tokens and is only redone when the stored snapshot is over 6 hours old)
"""
import datetime
import glob
import html
import json
import os
import re
import subprocess
import sys
import webbrowser

_HOOKS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "hooks")
_SCRIPTS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HOOKS)
sys.path.insert(0, _SCRIPTS)

from budget_lib import alert_threshold_crossed, budget_status, is_budget_skipped  # noqa: E402
from gate_lib import (  # noqa: E402
    RESERVED_KEYS,
    current_commit,
    data_dir,
    existing_cost_log,
    load_gates,
    project_root_for,
    projects_root,
    required_gates,
)
from harness_status import (  # noqa: E402
    DOC_FILES,
    docs_state,
    gate_label,
    git_state,
    project_health,
    project_health_score,
    project_stage,
    risk_tier,
    session_count,
)
from generate_dashboard import list_project_names, recent_commits, harness_capability_counts  # noqa: E402
from memory_lib import claude_home, memory_dir  # noqa: E402
import context_snapshot  # noqa: E402
import cost_benefit  # noqa: E402
import session_data  # noqa: E402

HARNESS_ROOT = os.path.abspath(os.path.join(_SCRIPTS, ".."))
ENGINE_SOURCE = os.path.join(_SCRIPTS, "atlas_engine.html")
ENGINE_PLACEHOLDERS = ("@@ATLAS_DATA@@", "@@PROVENANCE@@", "@@FLEET_PILLS@@")
DEFAULT_OUTPUT = os.path.expanduser("~/.claude/harness-atlas.html")



def e(s):
    return html.escape(str(s), quote=True)


def js_str(s):
    return json.dumps(str(s))


def memory_dir_for(project_root):
    return memory_dir(project_root)


def memory_files(project_root):
    d = memory_dir_for(project_root)
    if not os.path.isdir(d):
        return []
    return sorted(
        f for f in os.listdir(d) if f.endswith(".md") and f != "MEMORY.md"
    )


def read_snippet(path, max_chars=1600):
    try:
        with open(path) as f:
            text = f.read()
    except OSError:
        return ""
    return text[:max_chars] + ("…" if len(text) > max_chars else "")


def token_chart(project_root):
    log_path = existing_cost_log(project_root)
    if not log_path:
        return None
    rows = []
    with open(log_path) as f:
        for line in f:
            line = line.strip()
            if line.startswith("|") and not line.startswith("|--") and not line.startswith("| Date"):
                parts = [p.strip() for p in line.strip("|").split("|")]
                if len(parts) >= 4:  # legacy rows carry a 5th (cache) column
                    rows.append(parts[:4])
    if not rows:
        return None
    by_date = {}
    for date, sid, dur, tok in rows:
        by_date[date] = tok
    dates = sorted(by_date)
    outs = []
    for d in dates:
        try:
            outs.append(int(by_date[d].split("/")[1]))
        except (ValueError, IndexError):
            outs.append(0)
    sessions = len(set(r[1] for r in rows))
    return {"dates": dates, "outs": outs, "rows": len(rows), "sessions": sessions}


# ---------------------------------------------------------------------------
# Work & tokens (from Claude Code's own session transcripts; see session_data.py)
# ---------------------------------------------------------------------------

_BASELINE_FILE = re.compile(r"^zz-baseline-(?P<proj>[A-Za-z0-9_.]+?)-(?:(?P<var>[a-z]+)-)?T(?P<n>\d+)\.md$")
TABLE_WRAP = '<div style="max-height:340px;overflow:auto;">%s</div>'


def tok(n):
    return session_data.fmt(n)


def _table(headers, rows, num_cols=()):
    head = "".join("<th%s>%s</th>" % (' style="text-align:right"' if i in num_cols else "", e(h)) for i, h in enumerate(headers))
    body = "".join(
        "<tr>%s</tr>" % "".join(
            "<td%s>%s</td>" % (' style="text-align:right;font-variant-numeric:tabular-nums"' if i in num_cols else "", c)
            for i, c in enumerate(r)
        )
        for r in rows
    )
    return '<table class="gate-table"><thead><tr>%s</tr></thead><tbody>%s</tbody></table>' % (head, body)


def _spark_svg(days):
    """days: sorted list of (day, value). Inline SVG area chart in the page's style."""
    if len(days) < 2:
        return ""
    vals = [v for _, v in days]
    maxv = max(vals) or 1
    n = len(days)
    xs = [30 + i * (290.0 / max(n - 1, 1)) for i in range(n)]
    ys = [120 - (v / float(maxv)) * 110 for v in vals]
    pts = " ".join("%.1f,%.1f" % (x, y) for x, y in zip(xs, ys))
    return (
        '<svg viewBox="0 0 340 150" style="width:100%%;height:auto;">'
        '<g stroke="var(--line)" stroke-width="1"><line x1="30" y1="120" x2="320" y2="120"/></g>'
        '<polygon points="30,120 %s %.1f,120" fill="var(--accent)" opacity="0.15"/>'
        '<polyline points="%s" fill="none" stroke="var(--accent)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
        '<g font-family="var(--font-mono)" font-size="8" fill="var(--ink-faint)"><text x="30" y="134">%s</text>'
        '<text x="320" y="134" text-anchor="end">%s</text><text x="30" y="8">peak %s/day</text></g></svg>'
    ) % (pts, xs[-1], pts, e(days[0][0]), e(days[-1][0]), tok(maxv))


TOKEN_NOTE = (
    '<p style="font-size:11.5px;color:var(--ink-faint);margin-top:10px;">A task is a git branch (a proxy for one PR, not a measurement of intent). '
    '<b>in</b> = input + cache writes, <b>out</b> = output; <b>cache read</b> is shown apart because it re-counts the whole context every turn and says little about cost. '
    'Subagent tokens are listed separately and are not in the in/out columns. Days are UTC. '
    'Read from Claude Code session transcripts (undocumented format, best-effort). No prompt or message text is read.</p>'
)


def work_category(name, pdata, cid):
    """Category, leaves and details for one project's tokens by task. None if no data."""
    if not pdata or not (pdata["tin"] or pdata["tout"] or pdata["sub_tin"]):
        return None
    tasks = sorted(pdata["tasks"].items(), key=lambda kv: -(kv[1]["tin"] + kv[1]["tout"]))
    top = tasks[:25]
    rest = tasks[25:]
    trows = [
        [e(b), str(len(t["sessions"])), tok(t["tin"]), tok(t["tout"]), tok(t["cr"]), e("%s – %s" % (t["first"], t["last"]))]
        for b, t in top
    ]
    if rest:
        trows.append([e("+ %d more tasks" % len(rest)), "", tok(sum(t["tin"] for _, t in rest)), tok(sum(t["tout"] for _, t in rest)),
                      tok(sum(t["cr"] for _, t in rest)), ""])
    sess = sorted(pdata["sessions"].items(), key=lambda kv: kv[1]["first"] or "")
    srows = [
        [e(sid[:8]), e("%s – %s" % (v["first"], v["last"])), str(len(v["branches"])), tok(v["tin"]), tok(v["tout"]), tok(v["cr"]),
         tok(v["sub_tin"] + v["sub_tout"])]
        for sid, v in sess
    ]
    days = sorted(pdata["days"].items())
    summary = (
        '<div class="fields">'
        '<div class="field"><span class="fl">Totals</span><p>%s in · %s out · %s cache read · %d task(s) · %d session(s) · %s – %s</p></div>'
        '<div class="field"><span class="fl">Subagents</span><p>%s in · %s out (separate transcripts, not counted above)</p></div>'
        '</div>'
    ) % (tok(pdata["tin"]), tok(pdata["tout"]), tok(pdata["cr"]), len(pdata["tasks"]), len(pdata["sessions"]),
         e(pdata["first"]), e(pdata["last"]), tok(pdata["sub_tin"]), tok(pdata["sub_tout"]))
    html_ = (
        summary +
        '<h4 style="margin:12px 0 4px">Tokens by task (top %d)</h4>' % len(top) +
        TABLE_WRAP % _table(["Task (branch)", "Sessions", "in", "out", "cache read", "Dates"], trows, num_cols=(1, 2, 3, 4)) +
        '<h4 style="margin:12px 0 4px">By session</h4>' +
        TABLE_WRAP % _table(["Session", "Dates", "Tasks", "in", "out", "cache read", "Subagents"], srows, num_cols=(2, 3, 4, 5, 6)) +
        ('<h4 style="margin:12px 0 4px">in + out per day</h4><div class="mini-chart">%s</div>' % _spark_svg(days) if len(days) > 1 else "") +
        TOKEN_NOTE
    )
    cat = {"id": cid("work"), "label": "Work & Tokens", "badge": "neutral", "badgeTxt": tok(pdata["tin"] + pdata["tout"]),
           "hasLeaves": True, "kind": "record"}
    detail = {cid("work"): {
        "title": "Work & Tokens", "sub": "%s tokens (in+out) across %d task(s)" % (tok(pdata["tin"] + pdata["tout"]), len(pdata["tasks"])),
        "html": html_, "source": {"file": "~/.claude/projects/*/*.jsonl (Claude Code transcripts)", "trust": "local record", "generated": NOW}}}
    leaves, items = [], top[:10]
    for i, (b, t) in enumerate(items):
        lid = "t-%s-%d" % (name, i)
        label = "%s · %s" % (b if len(b) <= 30 else b[:29] + "…", tok(t["tin"] + t["tout"]))
        leaves.append({"id": lid, "label": label, "status": "neutral", "kind": "record"})
        detail[lid] = {
            "title": b, "sub": "%s – %s" % (t["first"], t["last"]), "chip": "neutral",
            "fields": [
                ["Tokens", "%s in · %s out · %s cache read" % (tok(t["tin"]), tok(t["tout"]), tok(t["cr"]))],
                ["Sessions", "%d (a long session can cover many branches)" % len(t["sessions"])],
                ["Assistant messages", str(t["msgs"])],
                ["Subagents", "%s in · %s out" % (tok(t["sub_tin"]), tok(t["sub_tout"]))],
            ],
            "source": {"file": "Claude Code transcripts, grouped by gitBranch", "trust": "local record", "generated": NOW},
        }
    return cat, {cid("work"): leaves}, detail


def baseline_rows(project):
    """Rows of the measurement pilot written by the cost-log hook, keyed (task, variant)."""
    out = {}
    for path in glob.glob(os.path.join(data_dir(), "baseline", "zz-baseline-*.md")):
        m = _BASELINE_FILE.match(os.path.basename(path))
        if not m or m.group("proj") != project:
            continue
        rows = [l for l in open(path).read().splitlines() if l.startswith("| 20")]
        if not rows:
            continue
        cells = [c.strip() for c in rows[-1].strip("|").split("|")]
        if len(cells) < 4:
            continue
        try:
            tin, tout = (int(x) for x in cells[3].split("/"))
        except ValueError:
            continue
        out[(int(m.group("n")), m.group("var") or "before")] = {
            "active": cells[2], "in": tin, "out": tout, "orient": cells[5] if len(cells) > 5 else "-"}
    return out


def baseline_category(name, cid):
    data = baseline_rows(name)
    if not data:
        return None
    variants = [v for v in ("before", "control", "after") if any(k[1] == v for k in data)]
    tasks = sorted({k[0] for k in data})
    headers = ["Task"] + ["%s: in+out · active · orient" % v for v in variants]
    rows = []
    for t in tasks:
        r = ["T%d" % t]
        for v in variants:
            x = data.get((t, v))
            r.append("%s · %s · %s" % (tok(x["in"] + x["out"]), e(x["active"]), e(x["orient"])) if x else "–")
        rows.append(r)
    html_ = (
        '<p style="font-size:12.8px;color:var(--ink-soft);">The same five prompts run in disposable worktrees at a pinned commit. '
        '<b>before</b>: no CLAUDE.md. <b>control</b>: later memory, no CLAUDE.md. <b>after</b>: CLAUDE.md copied in. One run per cell, so differences under about 20% are noise.</p>' +
        _table(headers, rows) +
        '<p style="font-size:11.5px;color:var(--ink-faint);margin-top:10px;"><b>Orient is not comparable across columns:</b> the before runs were logged with the original '
        'definition (Read/Grep/Glob only); control and after include shell reads. The side-by-side recomputation is in ~/.claude/harness/baseline/%s.md.</p>' % e(name)
    )
    cat = {"id": cid("baseline"), "label": "Baseline Pilot", "badge": "neutral", "badgeTxt": "%dx%d" % (len(tasks), len(variants)),
           "hasLeaves": False, "kind": "record"}
    detail = {cid("baseline"): {"title": "Baseline Pilot", "sub": "%d tasks x %d variants, tokens per task" % (len(tasks), len(variants)),
                                 "html": html_, "source": {"file": "~/.claude/harness/baseline/zz-baseline-%s-*.md" % name, "trust": "local record", "generated": NOW}}}
    return cat, detail


def tokens_line(pdata):
    if not pdata:
        return "No transcript data for this project."
    return "%s in · %s out across %d task(s) in %d session(s), %s – %s. Open the Work &amp; Tokens branch for the per-task table." % (
        tok(pdata["tin"]), tok(pdata["tout"]), len(pdata["tasks"]), len(pdata["sessions"]), e(pdata["first"]), e(pdata["last"]))


def gate_kind(project_root):
    req = required_gates(project_root)
    if not req:
        return "none"
    worst = "pass"
    for name in req:
        label = gate_label(project_root, name)
        if label.startswith("fail"):
            return "fail"
        if "STALE" in label or label == "never run":
            worst = "mid"
    return worst


def build_project(name, root, work=None):
    # Every category id below is namespaced with the project name (cid()).
    # LEAVES and DETAIL are FLAT objects shared across every project once
    # merged in generate() -- an unnamespaced id like "commits" would be
    # silently overwritten by the next project using the same bare id
    # (this was a real bug: one project's commits were replaced by another's
    # because both used the literal id "commits").
    def cid(base):
        return "%s-%s" % (base, name)

    is_repo = os.path.isdir(os.path.join(root, ".git"))
    commits = recent_commits(root, n=8) if is_repo else []
    kind = "product" if (is_repo and commits) else "empty"

    cats = []
    leaves = {}
    detail = {}

    gk = gate_kind(root)
    gates = load_gates(root)
    req = required_gates(root)
    gate_rows = "".join(
        "<tr><td>%s</td><td>%s</td><td>%s</td></tr>" % (
            e(g), "Yes" if g in req else "No", e(gate_label(root, g))
        )
        for g in (req + sorted(x for x in gates if x not in req and x not in RESERVED_KEYS))
    ) or "<tr><td colspan=3>No gates recorded</td></tr>"
    cats.append({"id": cid("gate-status"), "label": "Gate Status", "badge": {"pass": "good", "mid": "mixed", "fail": "fail", "none": "neutral"}[gk], "badgeTxt": "", "hasLeaves": False, "kind": "record"})
    detail[cid("gate-status")] = {
        "title": "Gate Status", "sub": "Current only — gates.json doesn't retain history",
        "html": '<table class="gate-table"><thead><tr><th>Gate</th><th>Required</th><th>Status</th></tr></thead><tbody>%s</tbody></table>' % gate_rows,
        "source": {"file": "%s/.harness/gates.json" % name, "trust": "local record", "generated": NOW},
    }

    docs = docs_state(root)
    tiles = "".join(
        '<div class="doc-tile %s"><b>%s</b><span>%s</span></div>' % (
            "" if present else "missing", e(f), "Present" if present else "Missing"
        )
        for f, present in zip(DOC_FILES, docs)
    )
    adopted = sum(1 for d in docs if d)
    cats.append({"id": cid("docs"), "label": "Docs Adopted", "badge": "good" if adopted == len(DOC_FILES) else "mixed", "badgeTxt": "%d/%d" % (adopted, len(DOC_FILES)), "hasLeaves": False, "kind": "record"})
    detail[cid("docs")] = {"title": "Docs Adopted", "sub": "%d of %d standard docs" % (adopted, len(DOC_FILES)),
                       "html": '<div class="docs-mini">%s</div>' % tiles,
                       "source": {"file": "%s/docs/" % name, "trust": "local record", "generated": NOW}}

    ok, total = project_health_score(root)
    hrows = "".join(
        '<div class="d"><span class="v" style="color:var(--%s)">%s</span><p><b>%s</b> — %s</p></div>' % (
            "good" if isok else "critical", "Done" if isok else "Not set", e(label), e(val)
        )
        for label, val, isok in project_health(root)
    )
    cats.append({"id": cid("health"), "label": "Project Health", "badge": "good" if ok == total else "mixed", "badgeTxt": "%d/%d" % (ok, total), "hasLeaves": False, "kind": "record"})
    detail[cid("health")] = {"title": "Project Health", "sub": "%d/%d · informational, not a gate" % (ok, total),
                         "html": '<div class="decision-mini">%s</div>' % hrows,
                         "source": {"file": "/harness-status %s" % name, "trust": "local record", "generated": NOW}}

    wc = work_category(name, (work or {}).get(name), cid)
    if wc:
        wcat, wleaves, wdetail = wc
        cats.append(wcat)
        leaves.update(wleaves)
        detail.update(wdetail)
    bc = baseline_category(name, cid)
    if bc:
        cats.append(bc[0])
        detail.update(bc[1])

    chart = token_chart(root) if not wc else None  # the transcript view supersedes the legacy log
    if chart:
        n = len(chart["outs"])
        maxv = max(chart["outs"]) or 1
        xs = [30 + i * (290.0 / max(n - 1, 1)) for i in range(n)]
        ys = [120 - (v / float(maxv)) * 110 for v in chart["outs"]]
        pts = " ".join("%.1f,%.1f" % (x, y) for x, y in zip(xs, ys))
        poly = "30,120 " + pts + " %.1f,120" % xs[-1]
        chart_svg = (
            '<svg viewBox="0 0 340 150" style="width:100%%;height:auto;">'
            '<g stroke="var(--line)" stroke-width="1"><line x1="30" y1="120" x2="320" y2="120"/></g>'
            '<polygon points="%s" fill="var(--accent)" opacity="0.15"/>'
            '<polyline points="%s" fill="none" stroke="var(--accent)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
            '<g font-family="var(--font-mono)" font-size="8" fill="var(--ink-faint)"><text x="30" y="134">%s</text><text x="290" y="134" text-anchor="end">%s</text></g>'
            '</svg>'
        ) % (poly, pts, e(chart["dates"][0]), e(chart["dates"][-1]))
        cats.append({"id": cid("tokens"), "label": "Token Usage", "badge": "neutral", "badgeTxt": "", "hasLeaves": False, "kind": "record"})
        detail[cid("tokens")] = {"title": "Token Usage", "sub": "%d log rows · %d real session(s)" % (chart["rows"], chart["sessions"]),
                             "html": '<div class="mini-chart">%s</div>' % chart_svg,
                             "source": {"file": "%s/docs/COST_LOG.md" % name, "trust": "local record", "generated": NOW}}

    if commits:
        leaves[cid("commits")] = [{"id": "c-%s-%d" % (name, i), "label": h, "status": "neutral", "kind": "record"} for i, (h, m, d) in enumerate(commits)]
        for i, (h, msg, cdate) in enumerate(commits):
            detail["c-%s-%d" % (name, i)] = {
                "title": h, "sub": cdate, "chip": "neutral",
                "fields": [["Message", e(msg)]],
                "source": {"file": "%s git log" % name, "commit": h, "trust": "local record"},
            }
        cats.append({"id": cid("commits"), "label": "Recent Commits", "badge": "neutral", "badgeTxt": str(len(commits)), "hasLeaves": True, "kind": "record"})
        detail[cid("commits")] = {"title": "Recent Commits", "sub": "Last %d, verbatim from git log — no interpretation" % len(commits),
                              "html": "<p style=\"font-size:12.8px;color:var(--ink-soft);\">Click a commit for its raw message. No skill/prompt/savings narrative is attached — that requires reading and judgment this script doesn't do.</p>",
                              "source": {"file": "%s git log" % name, "trust": "local record", "generated": NOW}}

    mfiles = memory_files(root)
    if mfiles:
        leaves[cid("memory")] = [{"id": "m-%s-%d" % (name, i), "label": f.replace(".md", ""), "status": "neutral", "kind": "record"} for i, f in enumerate(mfiles)]
        for i, f in enumerate(mfiles):
            snippet = read_snippet(os.path.join(memory_dir_for(root), f))
            detail["m-%s-%d" % (name, i)] = {
                "title": f, "sub": "Raw file content (truncated)", "chip": "neutral",
                "html": '<pre style="white-space:pre-wrap;font-family:var(--font-mono);font-size:11px;line-height:1.6;color:var(--ink-soft);">%s</pre>' % e(snippet),
                "source": {"file": "~/.claude/projects/.../memory/%s" % f, "trust": "local record"},
            }
        cats.append({"id": cid("memory"), "label": "Project Memory", "badge": "neutral", "badgeTxt": str(len(mfiles)), "hasLeaves": True, "kind": "record"})
        detail[cid("memory")] = {"title": "Project Memory", "sub": "%d file(s) — raw content, not summarized" % len(mfiles),
                             "html": "<p style=\"font-size:12.8px;color:var(--ink-soft);\">Native Claude Code memory. Shown verbatim (truncated) — this script reads, it doesn't synthesize.</p>",
                             "source": {"file": memory_dir_for(root), "trust": "local record"}}

    stage = project_stage(root) or "not declared"
    tier = risk_tier(root) or "not set"
    git = git_state(root)
    detail[name] = {
        "title": name, "sub": "Live snapshot, generated %s" % NOW,
        "html": '<div class="fields">'
                '<div class="field"><span class="fl">Lifecycle position</span><p>%s. Risk tier: %s.</p></div>'
                '<div class="field"><span class="fl">Git</span><p>%s</p></div>'
                '<div class="field"><span class="fl">Docs / Health</span><p>%d/%d docs adopted, health %d/%d.</p></div>'
                '<div class="field"><span class="fl">Work &amp; tokens</span><p>%s</p></div>'
                '</div>' % (e(stage), e(tier), e(git), adopted, len(DOC_FILES), ok, total, tokens_line((work or {}).get(name))),
        "source": {"file": "/harness-status %s" % name, "trust": "local record", "generated": NOW},
    }

    return {"id": name, "label": name, "kind": kind}, cats, leaves, detail


def harness_inventory():
    """Names of the harness's own skills, commands and agents, read from disk."""
    skills = sorted(os.path.basename(os.path.dirname(p)) for p in glob.glob(os.path.join(HARNESS_ROOT, "skills", "*", "SKILL.md"))
                    if os.sep + "synced" + os.sep not in p)
    commands = sorted(os.path.splitext(os.path.basename(p))[0] for p in glob.glob(os.path.join(HARNESS_ROOT, "commands", "*.md")))
    agents = sorted(os.path.splitext(os.path.basename(p))[0] for p in glob.glob(os.path.join(HARNESS_ROOT, "agents", "*.md")))
    return skills, commands, agents


def harness_hooks():
    """Wired hooks from hooks/hooks.json: (event, matcher, script, timeout, onFailure)."""
    try:
        with open(os.path.join(HARNESS_ROOT, "hooks", "hooks.json")) as f:
            data = json.load(f).get("hooks", {})
    except (OSError, json.JSONDecodeError):
        return []
    rows = []
    for event, entries in data.items():
        for entry in entries:
            for h in entry.get("hooks", []):
                m = re.search(r"(\w+\.py)", h.get("command", ""))
                rows.append((event, entry.get("matcher", "") or "-", m.group(1) if m else h.get("command", "?"),
                             str(h.get("timeout", "-")), h.get("onFailure", "-")))
    return rows


def build_harness_meta(work=None, panel=None):
    skills, commands, agents = harness_inventory()
    commits = recent_commits(HARNESS_ROOT, n=8)
    cid = lambda base: "hm-%s" % base
    cats, leaves, detail = [], {}, {}

    if panel:
        cats.append(panel[0])
        detail.update(panel[1])

    wc = work_category("harness", (work or {}).get("harness"), cid)
    if wc:
        cats.append(wc[0]); leaves.update(wc[1]); detail.update(wc[2])

    hooks = harness_hooks()
    if hooks:
        cats.append({"id": cid("hooks"), "label": "Hooks & Gates", "badge": "good", "badgeTxt": str(len(hooks)), "hasLeaves": False, "kind": "enforced"})
        detail[cid("hooks")] = {
            "title": "Hooks & Gates", "sub": "%d hook(s) wired in hooks/hooks.json" % len(hooks),
            "html": _table(["Event", "Matcher", "Script", "Timeout s", "onFailure"], [[e(x) for x in r] for r in hooks]) +
                    '<p style="font-size:11.5px;color:var(--ink-faint);margin-top:10px;">Read from hooks.json. onFailure "block" makes a crash or timeout block the tool call (needs Claude Code 2.1.295+). '
                    'It is set on the release gate only; the Stop verification hook is inert until a verify command is configured for a project.</p>',
            "source": {"file": "hooks/hooks.json", "trust": "local record", "generated": NOW}}

    cats.append({"id": cid("capabilities"), "label": "Capabilities", "badge": "neutral",
                 "badgeTxt": str(len(skills) + len(commands) + len(agents)), "hasLeaves": False, "kind": "advisory"})
    detail[cid("capabilities")] = {
        "title": "Capabilities", "sub": "%d skills · %d commands · %d subagents (counted from disk)" % (len(skills), len(commands), len(agents)),
        "html": '<div class="fields">'
                '<div class="field"><span class="fl">Skills</span><p>%s</p></div>'
                '<div class="field"><span class="fl">Commands</span><p>%s</p></div>'
                '<div class="field"><span class="fl">Subagents</span><p>%s</p></div></div>' % (
                    e(", ".join(skills)), e(", ".join("/" + c for c in commands)), e(", ".join(agents))),
        "source": {"file": "skills/, commands/, agents/", "trust": "local record", "generated": NOW}}

    cats.append({"id": "hm-commits", "label": "Own History", "badge": "good", "badgeTxt": str(len(commits)), "hasLeaves": True, "kind": "record"})
    leaves["hm-commits"] = [{"id": "hc-%d" % i, "label": h, "status": "neutral", "kind": "record"} for i, (h, m, d) in enumerate(commits)]
    detail["hm-commits"] = {"title": "Own History", "sub": "Live git log — %d commits shown" % len(commits),
                            "html": "<p style=\"font-size:12.8px;color:var(--ink-soft);\">Click a commit for its raw message.</p>",
                            "source": {"file": "_harness git log", "trust": "local record", "generated": NOW}}
    for i, (h, msg, cdate) in enumerate(commits):
        detail["hc-%d" % i] = {"title": h, "sub": cdate, "chip": "neutral", "fields": [["Message", e(msg)]],
                                "source": {"file": "_harness git log", "commit": h, "trust": "local record"}}

    mfiles = memory_files(HARNESS_ROOT)
    if mfiles:
        leaves[cid("memory")] = [{"id": "hmem-%d" % i, "label": f.replace(".md", ""), "status": "neutral", "kind": "record"} for i, f in enumerate(mfiles)]
        for i, f in enumerate(mfiles):
            detail["hmem-%d" % i] = {
                "title": f, "sub": "Raw file content (truncated)", "chip": "neutral",
                "html": '<pre style="white-space:pre-wrap;font-family:var(--font-mono);font-size:11px;line-height:1.6;color:var(--ink-soft);">%s</pre>' % e(read_snippet(os.path.join(memory_dir_for(HARNESS_ROOT), f))),
                "source": {"file": "~/.claude/projects/.../memory/%s" % f, "trust": "local record"}}
        cats.append({"id": cid("memory"), "label": "Project Memory", "badge": "neutral", "badgeTxt": str(len(mfiles)), "hasLeaves": True, "kind": "record"})
        detail[cid("memory")] = {"title": "Project Memory", "sub": "%d file(s) — raw content" % len(mfiles),
                                 "html": "<p style=\"font-size:12.8px;color:var(--ink-soft);\">The harness's own memory: decisions and constraints that are not derivable from the code.</p>",
                                 "source": {"file": memory_dir_for(HARNESS_ROOT), "trust": "local record"}}

    try:
        with open(os.path.join(HARNESS_ROOT, ".claude-plugin", "plugin.json")) as f:
            version = json.load(f).get("version", "?")
    except (OSError, json.JSONDecodeError):
        version = "?"
    tests = len(glob.glob(os.path.join(HARNESS_ROOT, "tests", "test_*.py")))
    detail["harness"] = {
        "title": "_harness", "sub": "Live: %s" % NOW,
        "html": '<div class="fields">'
                '<div class="field"><span class="fl">Version</span><p>solo-founder-harness %s · %d test files</p></div>'
                '<div class="field"><span class="fl">Capabilities</span><p>%d skills, %d commands, %d subagents, %d wired hooks — counted live from disk.</p></div>'
                '<div class="field"><span class="fl">Work &amp; tokens</span><p>%s</p></div></div>' % (
                    e(version), tests, len(skills), len(commands), len(agents), len(hooks), tokens_line((work or {}).get("harness"))),
        "source": {"file": ".claude-plugin/plugin.json, skills/, commands/, agents/, hooks/hooks.json", "trust": "local record", "generated": NOW},
    }
    return {"id": "harness", "label": "_harness", "kind": "meta"}, cats, leaves, detail


# ---------------------------------------------------------------------------
# Panel: "Harness cost vs measured benefit"
# ---------------------------------------------------------------------------

COST_BENEFIT_TITLE = "Harness cost vs measured benefit"
COST_BENEFIT_ID = "hm-costbenefit"
SNAPSHOT_MAX_AGE_HOURS = 6


def _metric_fmt(key, v):
    if v is None:
        return "–"
    if key == "cost_usd":
        return "$%.2f" % v
    if key in ("in_out", "cache_read"):
        return tok(v)
    return "%d" % round(v)


def _pct(x):
    return "–" if x is None else "%+.0f%%" % (x * 100)


def get_context_snapshot(refresh):
    """Latest /context snapshot, refreshed (no tokens spent) when it is old and `refresh` is set."""
    snap = context_snapshot.load_latest()
    age = context_snapshot.age_hours(snap) if snap else None
    if refresh and (snap is None or age is None or age > SNAPSHOT_MAX_AGE_HOURS):
        skills, commands, _agents = harness_inventory()
        fresh = context_snapshot.capture(skills + commands, HARNESS_ROOT)
        if fresh:
            context_snapshot.save(fresh)
            snap = fresh
    return snap


def cost_benefit_panel(root, project_names, work, snapshot):
    """The one panel: what the harness costs per session, and what has been measured in return."""
    inj = cost_benefit.injected_context(root, project_names, HARNESS_ROOT)
    compare = cost_benefit.find_compare()
    prov = cost_benefit.provenance(compare) if compare else None
    rows = cost_benefit.delta_table(compare) if compare else []
    orient_real = cost_benefit.real_orient_rows()
    n_tasks = len(compare["cells"]["before"]) if compare else 0
    runs = compare.get("runs_per_cell", 1) if compare else 0

    # ---- 1. cost
    snap_h = snapshot["harness"] if snapshot else None
    cost_rows = [
        ["Umbrella CLAUDE.md", tok(inj["umbrella_est"]), tok(snap_h["umbrella_claude_md"]) if snap_h else "–"],
        ["Harness skills and commands listed", tok(inj["listing_est"]), tok(snap_h["skills_and_commands"]) if snap_h else "–"],
        ["Harness subagents listed", "–", tok(snap_h["agents"]) if snap_h else "–"],
        ["<b>Harness total</b>", "<b>%s</b>" % tok(inj["umbrella_est"] + inj["listing_est"]),
         "<b>%s</b>" % (tok(snap_h["harness_total"]) if snap_h else "–")],
    ]
    cost_html = _table(["Injected into every session", "file estimate", "measured /context"], cost_rows, num_cols=(1, 2))
    if snapshot:
        age = context_snapshot.age_hours(snapshot)
        cats = snapshot["categories"]
        mcp = cats.get("MCP tools", 0) + cats.get("MCP server instructions", 0)
        other_skills = max(cats.get("Skills", 0) - snap_h["skills_and_commands"], 0)
        cost_html += (
            '<p style="font-size:12px;color:var(--ink-soft);margin-top:8px;">Measured %s (UTC) with Claude Code %s%s: the whole session starts at <b>%s</b> tokens, '
            'of which the harness is <b>%s%%</b>. For scale, the rest: system prompt %s, system tools %s, MCP %s, other skills %s (Claude Code\'s own rounded estimates).</p>'
            % (e(snapshot["captured_at"][:16].replace("T", " ")), e(snapshot.get("claude_version", "?").replace(" (Claude Code)", "")),
               (" (<b>%d h old</b>)" % round(age)) if age and age > 24 else "",
               format(snapshot["total_tokens"], ","), snap_h["harness_share_pct"],
               format(cats.get("System prompt", 0), ","), format(cats.get("System tools", 0), ","), format(mcp, ","), format(other_skills, ",")))
    else:
        cost_html += '<p style="font-size:12px;color:var(--ink-soft);">No /context snapshot yet. Run <code>python3 scripts/context_snapshot.py</code> (costs no tokens).</p>'
    proj_rows = []
    for p in inj["projects"]:
        sub_total = p["claude_md"] + p["imports"] + p["memory_index"] + p["session_start"]
        proj_rows.append([e(p["name"]), tok(p["claude_md"] + p["imports"]), tok(p["memory_index"]),
                          "%s (%d line%s)" % (tok(p["session_start"]), p["session_start_lines"], "" if p["session_start_lines"] == 1 else "s"), tok(sub_total)])
    cost_html += (
        '<h5 style="margin:12px 0 4px">Per project, on top of the above (file estimates)</h5>' +
        _table(["Project", "CLAUDE.md + imports", "MEMORY.md index", "SessionStart hook", "Total"], proj_rows, num_cols=(1, 2, 3, 4)) +
        '<p style="font-size:11.5px;color:var(--ink-faint);">Estimates are bytes / 4 and undercount by roughly 40% against /context. The hook text is what it prints now, computed without recording any alert.</p>')

    # ---- 2. orient trend
    if orient_real:
        recent = orient_real[-8:]
        orient_html = ('<p>%d real-session row(s). Latest: %s</p>' % (
            len(orient_real), e(", ".join("%s %s=%d" % (r["date"], r["project"], r["orient"]) for r in recent))))
    else:
        orient_html = ('<p><b>No real-session rows yet.</b> The cost log under ~/.claude/harness/cost/ fills as sessions end under the current hook; '
                       'the older in-repo logs carry no Orient. Until then the only Orient data is the baseline pilot below.</p>')
    if compare:
        orient_rows = [r for r in rows if r["key"] in ("orient_old", "orient_new")]
        if orient_rows:
            orient_html += _table(["Orient (edit tasks only)", "n", "before", "control", "after"],
                                  [[e(r["metric"]), str(r["n_tasks"])] + [str(r["totals"][v]) for v in ("before", "control", "after")] for r in orient_rows],
                                  num_cols=(1, 2, 3, 4))
    # ---- 3. per-task tokens
    heavy = cost_benefit.top_tasks(work, 8)
    heavy_html = _table(["Heaviest tasks (fleet-wide)", "Project", "Sessions", "in + out"],
                        [[e(t["task"]), e(t["project"]), str(t["sessions"]), tok(t["tokens"])] for t in heavy], num_cols=(2, 3)) if heavy else ""
    base_html = ""
    if compare:
        base_html = _table(["Baseline task", "before", "control", "after"],
                           [[e(t["task"])] + [tok(t[v]) for v in ("before", "control", "after")] for t in cost_benefit.task_tokens(compare)],
                           num_cols=(1, 2, 3)) + (
            '<p style="font-size:11.5px;color:var(--ink-faint);">Baseline figures are hand-entered from the pilot; in + out is cross-checked against the hook-written cost rows where the file says so.</p>'
            if cost_benefit.provenance(compare)["hand_entered"] else "")
    # ---- 4. baseline deltas
    if compare:
        drows = []
        for r in rows:
            verdict = "<b>beyond noise</b>" if r["verdict"] == "beyond noise" else e(r["verdict"])
            if r["verdict"] == "beyond noise" and r["concentrated"]:
                verdict += " <i>(one task drives it)</i>"
            t = r["totals"]
            evidence = "cross-checked" if r["key"] in prov["cross_checked"] else ("hand-entered only" if prov["hand_entered"] else "generated")
            drows.append([e(r["metric"]), str(r["n_tasks"]), _metric_fmt(r["key"], t["before"]), _metric_fmt(r["key"], t["control"]),
                          _metric_fmt(r["key"], t["after"]), _pct(r["rel_after"]), _pct(r["rel_control"]), verdict, evidence])
        if prov["hand_entered"]:
            source_html = ('<p style="border-left:3px solid var(--accent);padding-left:8px;font-size:12px;color:var(--ink-soft);"><b>Source: hand-entered from the pilot.</b> %s</p>'
                           % e(prov["text"]))
        else:
            source_html = ('<p style="border-left:3px solid var(--accent);padding-left:8px;font-size:12px;color:var(--ink-soft);"><b>Source: generated by %s.</b> %s</p>'
                           % (e(prov["generated_by"]), e(prov["text"])))
        delta_html = (
            source_html +
            '<p style="font-size:12px;color:var(--ink-soft);">%s pilot at commit %s: <b>n = %d tasks, %d run per cell</b>, no repeats. '
            '<b>after</b> is the change under test; <b>control</b> is the same conditions without it, so its drift from <b>before</b> is the noise proxy.</p>'
            % (e(compare["project"]), e(compare["commit"]), n_tasks, runs) +
            TABLE_WRAP % _table(["Metric", "n", "before", "control", "after", "Δ after", "Δ control", "verdict", "evidence"], drows, num_cols=(1, 2, 3, 4, 5, 6)) +
            '<p style="font-size:11.5px;color:var(--ink-faint);margin-top:8px;"><b>Noise rule:</b> "within noise" when |Δ after| is no larger than the control\'s drift or 10%, whichever is bigger. '
            '"One task drives it" means a single task accounts for at least 60% of the summed change. Orient is summed over the tasks that edit; tasks that make no edit are left out. '
            'Lower is not claimed to be better for any metric; Orient in particular can fall because a session read less, or because it edited blind.</p>' +
            '<ul style="font-size:11.5px;color:var(--ink-faint);padding-left:18px;margin:6px 0 0;">%s</ul>' % "".join("<li>%s</li>" % e(n) for n in compare.get("notes", [])))
    else:
        delta_html = '<p>No baseline comparison recorded (~/.claude/harness/baseline/&lt;project&gt;-compare.json).</p>'

    reading_lines = cost_benefit.reading(rows, snapshot, len(orient_real), runs, n_tasks, hand_entered=bool(prov and prov["hand_entered"]))
    html_ = (
        '<div class="fields"><div class="field"><span class="fl">What the data says</span>%s</div></div>' % "".join("<p>%s</p>" % e(l) for l in reading_lines) +
        '<h4 style="margin:14px 0 4px">1 · Cost: injected-context tokens</h4>' + cost_html +
        '<h4 style="margin:14px 0 4px">2 · Orient trend</h4>' + orient_html +
        '<h4 style="margin:14px 0 4px">3 · Tokens per task</h4>' + TABLE_WRAP % heavy_html + base_html +
        '<h4 style="margin:14px 0 4px">4 · Baseline deltas</h4>' + delta_html)
    badge = tok(snap_h["harness_total"]) if snap_h else "est"
    cat = {"id": COST_BENEFIT_ID, "label": COST_BENEFIT_TITLE, "badge": "neutral", "badgeTxt": badge, "hasLeaves": False, "kind": "record"}
    detail = {COST_BENEFIT_ID: {
        "title": COST_BENEFIT_TITLE,
        "sub": "what the harness injects into every session, against what has been measured so far",
        "html": html_,
        "source": {"file": "/context snapshot, hooks and CLAUDE.md files, transcripts, ~/.claude/harness/baseline/&lt;project&gt;-compare.json", "trust": "local record", "generated": NOW}}}
    return cat, detail



def fleet_overview_html(root, work, project_names, weekly=None):
    """Root-node view: tokens per project, one table."""
    order = list(project_names) + ["harness", "baseline", "other"]
    labels = {"harness": "_harness (the tool itself)", "baseline": "baseline pilot worktrees", "other": "other / removed projects"}
    rows, tot = [], [0, 0, 0, 0, 0, 0, 0]
    for p in order:
        v = (work or {}).get(p)
        if not v:
            continue
        rows.append([e(labels.get(p, p)), str(len(v["tasks"])), str(len(v["sessions"])), tok(v["tin"]), tok(v["tout"]), tok(v["cr"]),
                     tok(v["sub_tin"] + v["sub_tout"]), e("%s – %s" % (v["first"], v["last"]))])
        for i, k in enumerate(("tasks", "sessions", "tin", "tout", "cr")):
            tot[i] += len(v[k]) if k in ("tasks", "sessions") else v[k]
        tot[5] += v["sub_tin"] + v["sub_tout"]
    if not rows:
        return "<p>No session transcripts found under ~/.claude/projects.</p>"
    rows.append(["<b>Total</b>", str(tot[0]), str(tot[1]), tok(tot[2]), tok(tot[3]), tok(tot[4]), tok(tot[5]), ""])
    return (
        '<div class="fields"><div class="field"><span class="fl">Projects</span><p>%d project(s) under %s, plus _harness itself.</p></div></div>' % (len(project_names), e(root)) +
        '<h4 style="margin:12px 0 4px">Tokens by project</h4>' +
        _table(["Project", "Tasks", "Sessions", "in", "out", "cache read", "Subagents", "Dates"], rows, num_cols=(1, 2, 3, 4, 5, 6)) +
        TOKEN_NOTE + _weekly_html(weekly, labels)
    )


def _weekly_html(weekly, labels):
    """Last 7 UTC days per project, main sessions (see session_data.weekly for the definitions)."""
    if not weekly:
        return ""
    rows = []
    for p, v in weekly.items():
        share = "n/a" if v["cache_hit_share"] is None else "%.1f%%" % (100 * v["cache_hit_share"])
        rows.append([e(labels.get(p, p)), str(v["sessions"]), tok(v["in_out_tokens"]), tok(v["cache_read_tokens"]), share,
                     "%g" % v["median_session_turns"]])
    return ('<h4 style="margin:14px 0 4px">Last 7 days per project</h4>' +
            _table(["Project", "Sessions", "in + out", "cache read", "cache-hit share", "median turns"], rows, num_cols=(1, 2, 3, 4, 5)) +
            '<p style="font-size:11.5px;color:var(--ink-faint);">Main sessions only, UTC days, from the session transcripts. '
            'cache-hit share = cache read / (cache read + input + cache creation). Small samples: a week with one or two sessions per project says little.</p>')


def load_engine():
    """The page template. Fails loudly if the file is missing or has lost a placeholder,
    because a silently empty page would look like a harness with no data."""
    try:
        with open(ENGINE_SOURCE, encoding="utf-8") as f:
            text = f.read()
    except OSError as exc:
        raise RuntimeError(
            "Atlas engine template not found or unreadable: %s (%s). "
            "Restore scripts/atlas_engine.html from git." % (ENGINE_SOURCE, exc)
        ) from exc
    bad = [p for p in ENGINE_PLACEHOLDERS if text.count(p) != 1]
    if bad:
        raise RuntimeError("Atlas engine template %s must contain each of %s exactly once; problem with: %s"
                           % (ENGINE_SOURCE, ", ".join(ENGINE_PLACEHOLDERS), ", ".join(bad)))
    return text


def generate(output_path=None, focus_cwd=None, refresh_context=False):
    global NOW
    NOW = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    output_path = output_path or DEFAULT_OUTPUT
    root = projects_root()
    focus_root = project_root_for(focus_cwd or os.getcwd())

    project_names = list_project_names(root)
    rows_all = session_data.scan(claude_home(), root, project_names, os.path.join(data_dir(), "cache", "sessions.json"))
    work = session_data.summarize(rows_all)
    weekly = session_data.weekly(rows_all)

    projects, all_cats, all_leaves, all_detail = [], {}, {}, {}
    for name in project_names:
        proj, cats, leaves, detail = build_project(name, os.path.join(root, name), work)
        projects.append(proj)
        all_cats[name] = cats
        all_leaves.update(leaves)
        all_detail.update(detail)

    snapshot = get_context_snapshot(refresh_context)
    panel = cost_benefit_panel(root, project_names, work, snapshot)
    hproj, hcats, hleaves, hdetail = build_harness_meta(work, panel)
    projects.append(hproj)
    all_cats["harness"] = hcats
    all_leaves.update(hleaves)
    all_detail.update(hdetail)

    all_detail["root"] = {
        "title": "THE HARNESS", "sub": "Live fleet overview — generated %s" % NOW,
        "html": fleet_overview_html(root, work, project_names, weekly),
        "related": [{"id": COST_BENEFIT_ID, "label": COST_BENEFIT_TITLE}],
        "source": {"file": "projects_root()", "trust": "local record", "generated": NOW},
    }

    kind_meta_js = (
        "var KIND_META = { enforced:{glyph:'⛔',word:'Enforced control'}, advisory:{glyph:'◐',word:'Advisory workflow'}, "
        "record:{glyph:'▤',word:'Record'}, external:{glyph:'↗',word:'External / manual'}, scope:{glyph:'∅',word:'Out of scope'} };"
    )

    focus_id = None
    if focus_root:
        base = os.path.basename(focus_root)
        if any(p["id"] == base for p in projects):
            focus_id = base

    data_js = (
        "  var PROJECTS = [\n" +
        ",\n".join("    { id: %s, label: %s, kind: %s }" % (js_str(p["id"]), js_str(p["label"]), js_str(p["kind"])) for p in projects) +
        "\n  ];\n\n" +
        "  var CATS_BY_PROJECT = " + json.dumps(all_cats, indent=2) + ";\n\n" +
        "  var LEAVES = " + json.dumps(all_leaves, indent=2) + ";\n\n" +
        "  " + kind_meta_js + "\n\n" +
        "  var DETAIL = " + json.dumps(all_detail, indent=2) + ";\n\n" +
        "  var state = { project: %s, expandedCat: null, selectedLeaf: null, rootSelected: %s, focusId: %s };\n" % (
            js_str(focus_id or (projects[0]["id"] if projects else "harness")),
            "false" if focus_id else "true",
            js_str(focus_id) if focus_id else "null",
        )
    )

    provenance = (
        '<details class="provenance" open>\n'
        '<summary>LIVE — generated %s, no LLM involved</summary>\n'
        '<p>Every value here is read fresh from gates.json, docs/, project memory, git, and the session transcripts Claude Code keeps (the Work &amp; Tokens branches: tokens per project and per task, where a task is a git branch) — no prompt text is read. '
        'What\'s intentionally missing: gate-round-by-round <em>history</em> (gates.json only keeps the current record) '
        'and any "why this mattered" narrative synthesis — both require judgment, not just data. Everything else is real and current as of the timestamp above.</p>\n'
        '</details>'
    ) % NOW

    fleet_html = "\n    ".join(
        '<button class="fleet-pill" data-project="%s"><span class="fp-dot %s"></span><span class="fp-body"><b>%s</b></span></button>' % (
            e(p["id"]), "meta" if p["kind"] == "meta" else ("neutral" if p["kind"] == "empty" else "good"), e(p["label"])
        )
        for p in projects
    )

    doc = (load_engine()
           .replace("@@PROVENANCE@@", provenance)
           .replace("@@FLEET_PILLS@@", fleet_html)
           .replace("@@ATLAS_DATA@@", data_js))

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        f.write(doc)
    return output_path


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    path = generate(args[0] if args else None, refresh_context="--no-refresh" not in sys.argv[1:])
    print(path)
    if "--open" in sys.argv[1:]:
        webbrowser.open("file://" + os.path.abspath(path))


if __name__ == "__main__":
    main()
