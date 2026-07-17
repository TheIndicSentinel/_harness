#!/usr/bin/env python3
"""Generate a live, self-contained HTML dashboard of current harness state.

Deterministic, no LLM involvement -- every value is read directly from
gates.json, docs/, COST_LOG.md, budget.json, and git, via the same functions
`/harness-status` uses (this module imports harness_status.py rather than
re-deriving any of it). Always accurate as of generation time; it does NOT
reconstruct historical narrative -- gates.json only stores the current
status per gate, not a review history, and this script makes no attempt to
synthesize one from commit messages or memory files.

Usage:
  python3 generate_dashboard.py [output_path]
  # output_path defaults to ~/.claude/harness-dashboard.html
"""
import datetime
import html
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
    release_commands,
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

# Deliberately NOT importing harness_status.list_projects(): it depends on
# that module's PROJECTS_ROOT, a constant computed once at import time. In a
# long-lived or test process where CLAUDE_HARNESS_PROJECTS_ROOT can change
# after harness_status has already been imported once, that constant goes
# stale. This script always wants the *current* root, so it recomputes its
# own project listing against a freshly-called projects_root() every run.


def list_project_names(root):
    if not os.path.isdir(root):
        return []
    return sorted(
        entry for entry in os.listdir(root)
        if os.path.isdir(os.path.join(root, entry))
        and entry != "_harness"
        and not entry.startswith(".")
    )

HARNESS_ROOT = os.path.abspath(os.path.join(_SCRIPTS, ".."))
DEFAULT_OUTPUT = os.path.expanduser("~/.claude/harness-dashboard.html")


def recent_commits(repo_path, n=6):
    try:
        result = subprocess.run(
            ["git", "-C", repo_path, "log", f"-{n}", "--pretty=format:%h|%s|%ad", "--date=short"],
            capture_output=True, text=True, timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    if result.returncode != 0:
        return []
    commits = []
    for line in result.stdout.splitlines():
        parts = line.split("|", 2)
        if len(parts) == 3:
            commits.append(parts)
    return commits


def harness_capability_counts():
    def count_md(subdir, nested=False):
        d = os.path.join(HARNESS_ROOT, subdir)
        if not os.path.isdir(d):
            return 0
        if nested:
            return sum(
                1 for name in os.listdir(d)
                if os.path.isfile(os.path.join(d, name, "SKILL.md"))
            )
        return sum(1 for f in os.listdir(d) if f.endswith(".md"))

    return count_md("skills", nested=True), count_md("commands"), count_md("agents")


def e(s):
    return html.escape(str(s), quote=True)


def render_gate_rows(root):
    gates = load_gates(root)
    req = required_gates(root)
    names = req + sorted(g for g in gates if g not in req and g not in RESERVED_KEYS)
    if not names:
        return '<p class="muted">No gates recorded yet.</p>'
    rows = []
    for name in names:
        entry = gates.get(name)
        label = gate_label(root, name)
        cls = "pass" if label.startswith("pass") and "STALE" not in label else ("fail" if "fail" in label else "mid")
        advisory = "" if name in req else ' <span class="muted">(advisory)</span>'
        commit = entry.get("reviewed_commit", "")[:7] if isinstance(entry, dict) else ""
        notes = e(entry.get("notes", "")) if isinstance(entry, dict) else ""
        rows.append(
            f'<div class="grow"><div class="gr-head"><code>{e(name)}</code>{advisory} '
            f'<span class="chip {cls}">{e(label)}</span></div>'
            f'<div class="gr-meta">commit {e(commit)}</div>'
            + (f'<p class="gr-notes">{notes}</p>' if notes else "")
            + "</div>"
        )
    return "".join(rows)


def render_docs_grid(root):
    present = docs_state(root)
    tiles = []
    for name, ok in zip(DOC_FILES, present):
        cls = "ok" if ok else "missing"
        tiles.append(f'<div class="doctile {cls}">{e(name)}</div>')
    return "".join(tiles)


def render_health(root):
    checks = project_health(root)
    rows = []
    for label, value, ok in checks:
        cls = "ok" if ok else "no"
        mark = "✓" if ok else "·"
        rows.append(
            f'<div class="hrow"><span class="hmark {cls}">{mark}</span>'
            f'<span class="hlabel">{e(label)}</span><span class="hval muted">{e(value)}</span></div>'
        )
    return "".join(rows)


def render_commits(commits):
    if not commits:
        return '<p class="muted">No commits.</p>'
    return "".join(
        f'<div class="crow"><code>{e(h)}</code><span>{e(msg)}</span><span class="muted">{e(d)}</span></div>'
        for h, msg, d in commits
    )


def render_project(name, root, is_focus):
    docs = docs_state(root)
    adopted = sum(1 for d in docs if d)
    ok, total = project_health_score(root)
    budget = budget_status(root)
    budget_txt = "not set"
    if budget is not None:
        used, cap, pct = budget
        alert = alert_threshold_crossed(pct)
        budget_txt = f"{used}/{cap} tokens ({pct}%)" + (f" — crossed {alert}%" if alert else "")
    elif is_budget_skipped(root):
        budget_txt = "intentionally skipped"

    stage = project_stage(root) or "not declared"
    tier = risk_tier(root) or "not set"
    git = git_state(root)
    open_attr = " open" if is_focus else ""
    focus_badge = ' <span class="chip mid">you are here</span>' if is_focus else ""

    return f"""
<details class="project"{open_attr}>
  <summary><span class="pname">{e(name)}</span>{focus_badge}
    <span class="psum muted">{adopted}/{len(DOC_FILES)} docs · health {ok}/{total} · {e(git)}</span>
  </summary>
  <div class="pbody">
    <div class="col">
      <h4>Gates</h4>
      {render_gate_rows(root)}
      <h4>Project health {ok}/{total}</h4>
      {render_health(root)}
    </div>
    <div class="col">
      <h4>Docs {adopted}/{len(DOC_FILES)}</h4>
      <div class="docgrid">{render_docs_grid(root)}</div>
      <h4>Stats</h4>
      <div class="statline"><span>Stage</span><span class="muted">{e(stage)}</span></div>
      <div class="statline"><span>Risk tier</span><span class="muted">{e(tier)}</span></div>
      <div class="statline"><span>Sessions logged</span><span class="muted">{session_count(root)}</span></div>
      <div class="statline"><span>Token budget</span><span class="muted">{e(budget_txt)}</span></div>
      <h4>Recent commits</h4>
      <div class="commits">{render_commits(recent_commits(root))}</div>
    </div>
  </div>
</details>"""


def render_harness_meta():
    skills, commands, agents = harness_capability_counts()
    commits = recent_commits(HARNESS_ROOT, n=6)
    return f"""
<details class="project meta">
  <summary><span class="pname">_harness</span> <span class="chip mid">meta — not gated</span>
    <span class="psum muted">{skills} skills · {commands} commands · {agents} subagents</span>
  </summary>
  <div class="pbody">
    <div class="col">
      <h4>What it is</h4>
      <div class="statline"><span>Skills</span><span class="muted">{skills}</span></div>
      <div class="statline"><span>Commands</span><span class="muted">{commands}</span></div>
      <div class="statline"><span>Subagents</span><span class="muted">{agents}</span></div>
      <p class="muted" style="font-size:12px;margin-top:8px;">Excluded from gate/docs/session tracking by design (project_root_for() skips any path starting with "_harness") — this is the instrument, not a product.</p>
    </div>
    <div class="col">
      <h4>Recent commits</h4>
      <div class="commits">{render_commits(commits)}</div>
    </div>
  </div>
</details>"""


def generate(output_path=None, focus_cwd=None):
    output_path = output_path or DEFAULT_OUTPUT
    root = projects_root()
    focus_root = project_root_for(focus_cwd or os.getcwd())
    names = list_project_names(root)

    cards = []
    for name in names:
        proj_root = os.path.join(root, name)
        try:
            cards.append(render_project(name, proj_root, is_focus=(proj_root == focus_root)))
        except Exception as exc:  # noqa: BLE001 -- one broken project must not sink the whole dashboard
            cards.append(f'<div class="project errored">Could not render <code>{e(name)}</code>: {e(exc)}</div>')

    try:
        harness_card = render_harness_meta()
    except Exception as exc:  # noqa: BLE001
        harness_card = f'<div class="project errored">Could not render _harness: {e(exc)}</div>'

    generated_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    doc = TEMPLATE.format(
        generated_at=e(generated_at),
        projects_root=e(root),
        project_count=len(names),
        cards="".join(cards),
        harness_card=harness_card,
    )

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        f.write(doc)
    return output_path


TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Harness Dashboard — live</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
  :root {{
    --bg:#F3F5F4; --surface:#FFFFFF; --surface-sunken:#E9EDEC; --ink:#17222B; --ink-soft:#4A5A66; --ink-faint:#7C8B94;
    --line:#CBD4D3; --accent:#C1791F; --accent-ink:#7A4A10; --good:#0ca30c; --good-soft:#E1F3E1;
    --critical:#d03b3b; --critical-soft:#FBE4E4; --warn:#b3790f; --warn-soft:#FBF0DA;
    --font-display:"Avenir Next","Futura PT","Century Gothic",ui-sans-serif,sans-serif;
    --font-body:"Iowan Old Style",Georgia,serif; --font-mono:"SF Mono","Menlo",ui-monospace,monospace;
  }}
  @media (prefers-color-scheme: dark) {{
    :root {{ --bg:#12181D; --surface:#1A222A; --surface-sunken:#0E1317; --ink:#E7EDEE; --ink-soft:#93A5AC; --ink-faint:#647178;
      --line:#2B3941; --accent:#E0A23F; --accent-ink:#F3D9A6; --good:#2fbf4f; --good-soft:#16281B;
      --critical:#e8615f; --critical-soft:#301A19; --warn:#e0a940; --warn-soft:#33280f; }}
  }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:var(--bg); color:var(--ink); font-family:var(--font-body); padding:32px 24px 64px; }}
  .wrap {{ max-width:980px; margin:0 auto; }}
  h1 {{ font-family:var(--font-display); font-size:26px; margin:0 0 4px; }}
  .meta-line {{ font-family:var(--font-mono); font-size:12px; color:var(--ink-faint); margin-bottom:24px; }}
  h4 {{ font-family:var(--font-display); font-size:11px; letter-spacing:.06em; text-transform:uppercase; color:var(--ink-faint); margin:16px 0 8px; }}
  .muted {{ color:var(--ink-soft); }}
  code {{ font-family:var(--font-mono); font-size:.9em; }}
  .project {{ border:1px solid var(--line); background:var(--surface); border-radius:10px; margin-bottom:12px; overflow:hidden; }}
  .project summary {{ cursor:pointer; padding:14px 18px; display:flex; align-items:center; gap:10px; flex-wrap:wrap; list-style:none; font-family:var(--font-display); font-weight:700; font-size:14px; }}
  .project summary::-webkit-details-marker {{ display:none; }}
  .project summary::before {{ content:"▸"; color:var(--ink-faint); }}
  .project[open] summary::before {{ content:"▾"; }}
  .psum {{ margin-left:auto; font-family:var(--font-mono); font-size:11.5px; font-weight:400; }}
  .pbody {{ padding:0 18px 18px; display:grid; grid-template-columns:1fr 1fr; gap:20px; border-top:1px solid var(--line); }}
  @media (max-width:700px) {{ .pbody {{ grid-template-columns:1fr; }} }}
  .chip {{ font-family:var(--font-display); font-size:10px; font-weight:700; letter-spacing:.05em; text-transform:uppercase; padding:2px 8px; border-radius:999px; }}
  .chip.pass {{ background:var(--good-soft); color:var(--good); }}
  .chip.fail {{ background:var(--critical-soft); color:var(--critical); }}
  .chip.mid {{ background:var(--warn-soft); color:var(--warn); }}
  .grow {{ border-top:1px solid var(--line); padding:10px 0; font-size:13px; }}
  .grow:first-child {{ border-top:none; }}
  .gr-head {{ display:flex; align-items:center; gap:8px; }}
  .gr-meta {{ font-family:var(--font-mono); font-size:11px; color:var(--ink-faint); margin-top:2px; }}
  .gr-notes {{ font-size:12px; color:var(--ink-soft); margin:4px 0 0; }}
  .docgrid {{ display:flex; flex-wrap:wrap; gap:6px; }}
  .doctile {{ font-family:var(--font-mono); font-size:11px; padding:4px 8px; border-radius:6px; border:1px solid var(--line); }}
  .doctile.ok {{ background:var(--good-soft); border-color:var(--good); color:var(--good); }}
  .doctile.missing {{ background:var(--surface-sunken); color:var(--ink-faint); }}
  .hrow {{ display:flex; align-items:center; gap:8px; padding:4px 0; font-size:12.5px; }}
  .hmark {{ width:16px; text-align:center; font-weight:700; }}
  .hmark.ok {{ color:var(--good); }}
  .hmark.no {{ color:var(--ink-faint); }}
  .hlabel {{ flex:0 0 auto; }}
  .hval {{ margin-left:auto; font-family:var(--font-mono); font-size:11px; }}
  .statline {{ display:flex; justify-content:space-between; font-size:12.5px; padding:3px 0; }}
  .commits {{ display:flex; flex-direction:column; gap:4px; }}
  .crow {{ display:grid; grid-template-columns:56px 1fr auto; gap:8px; font-size:11.5px; align-items:baseline; }}
  .project.errored {{ padding:14px 18px; color:var(--critical); font-size:13px; }}
</style>
</head>
<body>
<div class="wrap">
  <h1>Harness Dashboard</h1>
  <div class="meta-line">generated {generated_at} · live, deterministic, no LLM involved · {project_count} project(s) under {projects_root} · regenerate anytime with the dashboard command</div>
  {cards}
  {harness_card}
</div>
</body>
</html>
"""


def main():
    output_path = sys.argv[1] if len(sys.argv) > 1 else None
    path = generate(output_path)
    print(path)


if __name__ == "__main__":
    main()
