#!/usr/bin/env python3
"""Generate a LIVE version of the mind-tree Atlas.

Reuses the exact visual/interaction engine from harness-map.html (CSS +
render()/navigateTo()/kind-badge JS) by extracting it at runtime from that
file -- NOT a duplicated copy living in this script. If the engine in
harness-map.html changes, this generator picks it up automatically next run.

What's live here vs. what harness-map.html has that this can't reproduce:
  LIVE (this script):    current gate status, docs adopted, project health,
                          token usage, recent commits, memory file listing.
  NOT reproduced here:    gate-round-by-round HISTORY (gates.json only keeps
                          the current record, not past ones), and any
                          "why this mattered / what was saved" narrative --
                          both require reading and judgment, not just data,
                          so they stay hand-authored in harness-map.html.

Usage: python3 generate_atlas.py [output_path]
"""
import datetime
import html
import json
import os
import subprocess
import sys

_HOOKS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "hooks")
_SCRIPTS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HOOKS)
sys.path.insert(0, _SCRIPTS)

from budget_lib import alert_threshold_crossed, budget_status, is_budget_skipped  # noqa: E402
from gate_lib import (  # noqa: E402
    RESERVED_KEYS,
    current_commit,
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

HARNESS_ROOT = os.path.abspath(os.path.join(_SCRIPTS, ".."))
SHELL_SOURCE = os.path.join(HARNESS_ROOT, "harness-map.html")
DEFAULT_OUTPUT = os.path.expanduser("~/.claude/harness-atlas.html")

MARKER_START = "  var PROJECTS = ["
MARKER_END = "  var state = {"


def e(s):
    return html.escape(str(s), quote=True)


def js_str(s):
    return json.dumps(str(s))


def memory_dir_for(project_root):
    slug = project_root.replace(os.sep, "-")
    return os.path.expanduser(os.path.join("~/.claude/projects", slug, "memory"))


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
    log_path = os.path.join(project_root, "docs", "COST_LOG.md")
    if not os.path.isfile(log_path):
        return None
    rows = []
    with open(log_path) as f:
        for line in f:
            line = line.strip()
            if line.startswith("|") and not line.startswith("|--") and not line.startswith("| Date"):
                parts = [p.strip() for p in line.strip("|").split("|")]
                if len(parts) == 4:
                    rows.append(parts)
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


def build_project(name, root):
    # Every category id below is namespaced with the project name (cid()).
    # LEAVES and DETAIL are FLAT objects shared across every project once
    # merged in generate() -- an unnamespaced id like "commits" would be
    # silently overwritten by the next project using the same bare id
    # (this was a real bug: kavach's commits were replaced by saarthi's,
    # since saarthi sorts after kavach and both used the literal id "commits").
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

    chart = token_chart(root)
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
                '</div>' % (e(stage), e(tier), e(git), adopted, len(DOC_FILES), ok, total),
        "source": {"file": "/harness-status %s" % name, "trust": "local record", "generated": NOW},
    }

    return {"id": name, "label": name, "kind": kind}, cats, leaves, detail


def build_harness_meta():
    skills, commands, agents = harness_capability_counts()
    commits = recent_commits(HARNESS_ROOT, n=8)
    cats = [{"id": "hm-commits", "label": "Own History", "badge": "good", "badgeTxt": str(len(commits)), "hasLeaves": True, "kind": "record"}]
    leaves = {"hm-commits": [{"id": "hc-%d" % i, "label": h, "status": "neutral", "kind": "record"} for i, (h, m, d) in enumerate(commits)]}
    detail = {"hm-commits": {"title": "Own History", "sub": "Live git log — %d commits shown" % len(commits),
                              "html": "<p style=\"font-size:12.8px;color:var(--ink-soft);\">Click a commit for its raw message.</p>",
                              "source": {"file": "_harness git log", "trust": "local record", "generated": NOW}}}
    for i, (h, msg, cdate) in enumerate(commits):
        detail["hc-%d" % i] = {"title": h, "sub": cdate, "chip": "neutral", "fields": [["Message", e(msg)]],
                                "source": {"file": "_harness git log", "commit": h, "trust": "local record"}}
    detail["harness"] = {
        "title": "_harness", "sub": "Live: %s" % NOW,
        "html": '<div class="fields"><div class="field"><span class="fl">Capabilities</span>'
                '<p>%d skills, %d commands, %d subagents — counted live from skills/, commands/, agents/.</p></div></div>' % (skills, commands, agents),
        "source": {"file": "skills/, commands/, agents/", "trust": "local record", "generated": NOW},
    }
    return {"id": "harness", "label": "_harness", "kind": "meta"}, cats, leaves, detail


def load_shell():
    content = open(SHELL_SOURCE).read()
    i = content.index(MARKER_START)
    j = content.index(MARKER_END)
    before = content[:i]
    after = content[j:]
    stmt_end = after.index(";\n") + 2
    after = after[stmt_end:]
    before = before.replace(
        "<title>The Harness — Mind Tree</title>",
        "<title>The Harness — Live Atlas</title>",
    )
    return before, after


def generate(output_path=None, focus_cwd=None):
    global NOW
    NOW = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    output_path = output_path or DEFAULT_OUTPUT
    root = projects_root()
    focus_root = project_root_for(focus_cwd or os.getcwd())

    projects, all_cats, all_leaves, all_detail = [], {}, {}, {}
    for name in list_project_names(root):
        proj, cats, leaves, detail = build_project(name, os.path.join(root, name))
        projects.append(proj)
        all_cats[name] = cats
        all_leaves.update(leaves)
        all_detail.update(detail)

    hproj, hcats, hleaves, hdetail = build_harness_meta()
    projects.append(hproj)
    all_cats["harness"] = hcats
    all_leaves.update(hleaves)
    all_detail.update(hdetail)

    all_detail["root"] = {
        "title": "THE HARNESS", "sub": "Live fleet overview — generated %s" % NOW,
        "html": '<div class="fields"><div class="field"><span class="fl">Projects</span><p>%d project(s) under %s, plus _harness itself.</p></div></div>' % (len(projects) - 1, e(root)),
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
        MARKER_START + "\n" +
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

    before, after = load_shell()
    provenance = (
        '<details class="provenance" open>\n'
        '<summary>LIVE — generated %s, no LLM involved</summary>\n'
        '<p>Every value here is read fresh from gates.json, docs/, COST_LOG.md, project memory, and git — the same sources /harness-status uses. '
        'What\'s intentionally missing vs. the hand-authored harness-map.html: gate-round-by-round <em>history</em> (gates.json only keeps the current record) '
        'and any "why this mattered" narrative synthesis — both require judgment, not just data. Everything else is real and current as of the timestamp above.</p>\n'
        '</details>'
    )
    before = before.replace(
        '<details class="provenance">\n      <summary>Generated 2026-07-17 · commit <code>a9d807a</code> — hand-assembled snapshot, not live data</summary>\n      <p>This page is a manually captured snapshot of the harness and the projects it governs, not generated by a script. Numbers drift as commits land. To refresh it: re-run <code>/harness-status</code> for each project, re-read <code>.harness/gates.json</code> and the privacy-guardrails-review memory file for gate history, and re-derive commit/feature entries from <code>git log</code>. No automated regeneration pipeline is wired up yet — treat every figure here as "true as of the commit above," not as a live dashboard.</p>\n    </details>',
        provenance,
    )
    before = before.replace('<p>Root → environment → what the harness did → the actual record. Click any branch; nothing here is a placeholder.</p>',
                             '<p>Root → environment → what the harness did → the actual record. Live data, regenerated fresh every run.</p>')

    fleet_html = "\n    ".join(
        '<button class="fleet-pill" data-project="%s"><span class="fp-dot %s"></span><span class="fp-body"><b>%s</b></span></button>' % (
            e(p["id"]), "meta" if p["kind"] == "meta" else ("neutral" if p["kind"] == "empty" else "good"), e(p["label"])
        )
        for p in projects
    )
    import re as _re
    before = _re.sub(r'<div class="fleet-row" id="fleet-row">.*?</div>\n\n  <div class="legend"', '<div class="fleet-row" id="fleet-row">\n    ' + fleet_html + '\n  </div>\n\n  <div class="legend"', before, flags=_re.S)

    doc = before + data_js + "\n\n  " + after

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        f.write(doc)
    return output_path


def main():
    output_path = sys.argv[1] if len(sys.argv) > 1 else None
    print(generate(output_path))


if __name__ == "__main__":
    main()
