#!/usr/bin/env python3
"""Read-only harness status report: what state has the harness left each project in.

Usage:
  python3 harness_status.py            # table across every project under Projects/
  python3 harness_status.py <name>     # detailed report for one project, including
                                        # a project-health checklist (see project_health())
"""
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "hooks"))
from budget_lib import alert_threshold_crossed, budget_status, is_budget_skipped  # noqa: E402
from gate_lib import (  # noqa: E402
    RESERVED_KEYS,
    check_passing,
    current_commit,
    load_gates,
    projects_root,
    release_commands,
    required_gates,
)

PROJECTS_ROOT = projects_root()
DOC_FILES = [
    "PRD.md",
    "MARKETING.md",
    "COST_LOG.md",
    "RELEASE_CHECKLIST.md",
    "ROADMAP.md",
    "CHANGELOG.md",
    "OPERATIONS.md",
    "BUSINESS.md",
    "COMPLIANCE.md",
    "CONNECTORS.md",
]


def list_projects():
    if not os.path.isdir(PROJECTS_ROOT):
        return []
    names = []
    for entry in sorted(os.listdir(PROJECTS_ROOT)):
        path = os.path.join(PROJECTS_ROOT, entry)
        if not os.path.isdir(path) or entry == "_harness" or entry.startswith("."):
            continue
        names.append(entry)
    return names


def docs_state(project_root):
    docs_dir = os.path.join(project_root, "docs")
    present = []
    for f in DOC_FILES:
        present.append(f if os.path.isfile(os.path.join(docs_dir, f)) else None)
    return present


def gate_label(project_root, name):
    gates = load_gates(project_root)
    entry = gates.get(name)
    if not isinstance(entry, dict):
        return "never run"
    if check_passing(project_root, name):
        return "pass (current)"
    if entry.get("status") == "pass":
        return "pass (stale — new commits since review)"
    return entry.get("status", "unknown")


def gates_summary(project_root):
    """One compact cell for the table: required gates and their state."""
    gates = load_gates(project_root)
    if not gates:
        return "none"
    parts = []
    for name in required_gates(project_root):
        label = gate_label(project_root, name)
        short = {"pass (current)": "pass", "never run": "missing"}.get(label, label)
        if "stale" in label:
            short = "STALE"
        parts.append(f"{name.replace('_review', '').replace('_guardrails', '')}:{short}")
    return "  ".join(parts)


def session_count(project_root):
    log_path = os.path.join(project_root, "docs", "COST_LOG.md")
    if not os.path.isfile(log_path):
        return 0
    count = 0
    with open(log_path) as f:
        for line in f:
            line = line.strip()
            if line.startswith("|") and not line.startswith("|--") and not line.startswith("| Date"):
                count += 1
    return count


def git_state(project_root):
    if not os.path.isdir(os.path.join(project_root, ".git")):
        return "not a git repo"
    result = subprocess.run(
        ["git", "-C", project_root, "status", "--porcelain"],
        capture_output=True, text=True, timeout=5,
    )
    if result.returncode != 0:
        return "git error"
    dirty = len([l for l in result.stdout.splitlines() if l.strip()])
    return "clean" if dirty == 0 else f"{dirty} uncommitted change(s)"


def budget_cell(project_root):
    status = budget_status(project_root)
    if status is None:
        return "skipped" if is_budget_skipped(project_root) else "not set"
    used, budget, pct = status
    label = f"{pct}%"
    if alert_threshold_crossed(pct) is not None:
        label += "!"
    return label


def _read_file(path):
    try:
        with open(path) as f:
            return f.read()
    except OSError:
        return None


def _field_value(text, label):
    """Find a '- **Label:** value' line and return the trimmed value, or
    None if that field isn't present at all (as opposed to present-but-empty,
    which returns ""). [ \\t]* (not \\s*) after the label -- \\s* would cross
    the newline when the field is empty and swallow the start of the NEXT
    line as if it were this field's value (a real bug caught by a test)."""
    m = re.search(rf"^-\s*\*\*{re.escape(label)}:\*\*[ \t]*(.*)$", text, re.MULTILINE)
    return m.group(1).strip() if m else None


def release_command_status(project_root):
    """None: no OPERATIONS.md at all. '': field present but empty (unfilled).
    Otherwise: the filled-in value."""
    text = _read_file(os.path.join(project_root, "docs", "OPERATIONS.md"))
    if text is None:
        return None
    return _field_value(text, "Release command") or ""


def rollback_runbook_filled(project_root):
    """None: no OPERATIONS.md. True/False: whether Rollback procedure looks
    filled in (the template placeholder always starts with "(exact steps")."""
    text = _read_file(os.path.join(project_root, "docs", "OPERATIONS.md"))
    if text is None:
        return None
    value = _field_value(text, "Rollback procedure")
    if not value:
        return False
    return not value.startswith("(exact steps")


def connectors_reviewed(project_root):
    """None: no CONNECTORS.md. True/False: whether the approved-connectors
    table has at least one data row beyond the header/separator."""
    text = _read_file(os.path.join(project_root, "docs", "CONNECTORS.md"))
    if text is None:
        return None
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        if "Name" in stripped and "Source" in stripped:
            continue  # header row
        if set(stripped) <= set("|-: "):
            continue  # separator row
        return True
    return False


def risk_tier(project_root):
    """None: no COMPLIANCE.md or no Tier field. Otherwise the declared tier,
    or "undecided" if the template's slash-separated placeholder is untouched."""
    text = _read_file(os.path.join(project_root, "docs", "COMPLIANCE.md"))
    if text is None:
        return None
    value = _field_value(text, "Tier")
    if value is None:
        return None
    if " / " in value:
        return "undecided (template placeholder)"
    return value.split("—")[0].split("(")[0].strip() or "undecided"


def project_stage(project_root):
    """The single checked '- [x] Stage N: ...' line from the project's own
    CLAUDE.md, or None if there's no CLAUDE.md or nothing is checked yet."""
    text = _read_file(os.path.join(project_root, "CLAUDE.md"))
    if text is None:
        return None
    m = re.search(r"^-\s*\[x\]\s*(Stage \d+:.*)$", text, re.MULTILINE | re.IGNORECASE)
    return m.group(1).strip() if m else None


def release_command_in_claude_md(project_root):
    """Whether the project's own CLAUDE.md 'Key commands' block still has
    the unfilled template placeholder."""
    text = _read_file(os.path.join(project_root, "CLAUDE.md"))
    if text is None:
        return None
    return "# fill in: build, test, lint, run" not in text


def ci_gate_status(project_root):
    """'not present' / 'present but not wired into any workflow' /
    'wired into <workflow>.yml' -- whether the CI gate-check template exists
    AND is actually referenced (via `uses:`) by another workflow. Presence
    alone doesn't protect anything; it has to be called."""
    workflow_dir = os.path.join(project_root, ".github", "workflows")
    gate_file = os.path.join(workflow_dir, "harness-gate-check.yml")
    if not os.path.isfile(gate_file):
        return "not present"
    for fname in sorted(os.listdir(workflow_dir)):
        if fname == "harness-gate-check.yml":
            continue
        text = _read_file(os.path.join(workflow_dir, fname))
        if text and "harness-gate-check.yml" in text:
            return f"wired into {fname}"
    return "present but not wired into any workflow"


def project_health(project_root):
    """The full checklist: (label, status_string, is_ok) tuples. is_ok is a
    simple heuristic for the compact table score, not a strict pass/fail --
    several of these (budget, connectors, risk tier) are fine left "not set"
    for a genuine prototype, so the health score is informational, not a gate.
    """
    checks = []

    ci = ci_gate_status(project_root)
    checks.append(("CI gate wired", ci, ci.startswith("wired into")))

    rel_cmd = release_command_status(project_root)
    if rel_cmd is None:
        checks.append(("Release command documented", "no OPERATIONS.md", False))
    else:
        checks.append(("Release command documented", rel_cmd or "not filled in", bool(rel_cmd)))

    rollback = rollback_runbook_filled(project_root)
    if rollback is None:
        checks.append(("Rollback runbook filled", "no OPERATIONS.md", False))
    else:
        checks.append(("Rollback runbook filled", "yes" if rollback else "not filled in", rollback))

    req = required_gates(project_root)
    checks.append(("Required gates chosen", ", ".join(req), True))  # always "ok" -- privacy alone is a valid choice

    budget = budget_status(project_root)
    skipped = is_budget_skipped(project_root)
    if budget is not None:
        checks.append(("Budget set or skipped", f"set ({budget[2]}%)", True))
    elif skipped:
        checks.append(("Budget set or skipped", "intentionally skipped", True))
    else:
        checks.append(("Budget set or skipped", "no decision recorded", False))

    connectors = connectors_reviewed(project_root)
    if connectors is None:
        checks.append(("Connector registry reviewed", "no CONNECTORS.md", False))
    else:
        checks.append(("Connector registry reviewed", "has entries" if connectors else "empty (fine if none in use)", True))

    return checks


def project_health_score(project_root):
    checks = project_health(project_root)
    ok = sum(1 for _, _, is_ok in checks if is_ok)
    return ok, len(checks)


def summary_row(name):
    project_root = os.path.join(PROJECTS_ROOT, name)
    docs = docs_state(project_root)
    adopted = f"{sum(1 for d in docs if d)}/{len(DOC_FILES)}"
    gates = gates_summary(project_root)
    sessions = session_count(project_root)
    git = git_state(project_root)
    budget = budget_cell(project_root)
    ok, total = project_health_score(project_root)
    return name, adopted, gates, str(sessions), budget, f"{ok}/{total}", git


def print_table(names):
    rows = [summary_row(n) for n in names]
    headers = ["Project", "Docs", "Required gates", "Sessions", "Budget", "Health", "Git"]
    widths = [max(len(h), *(len(r[i]) for r in rows)) if rows else len(h) for i, h in enumerate(headers)]
    def fmt_row(r):
        return "  ".join(c.ljust(w) for c, w in zip(r, widths))
    print(fmt_row(headers))
    print("  ".join("-" * w for w in widths))
    for r in rows:
        print(fmt_row(r))


def print_detail(name):
    project_root = os.path.join(PROJECTS_ROOT, name)
    if not os.path.isdir(project_root):
        print(f"No such project: {name}", file=sys.stderr)
        sys.exit(1)

    print(f"=== {name} ===")
    print(f"path: {project_root}")
    print(f"git: {git_state(project_root)}")
    stage = project_stage(project_root)
    tier = risk_tier(project_root)
    print(f"project stage: {stage or '(not set in CLAUDE.md)'}")
    print(f"risk tier: {tier or '(not set in COMPLIANCE.md)'}")
    print()
    print("docs:")
    for d, f in zip(docs_state(project_root), DOC_FILES):
        print(f"  [{'x' if d else ' '}] {f}")
    print()
    gates = load_gates(project_root)
    req = required_gates(project_root)
    print(f"required gates: {', '.join(req)}")
    all_names = req + sorted(
        g for g in gates if g not in req and g not in RESERVED_KEYS
    )
    for gname in all_names:
        entry = gates.get(gname)
        tag = "" if gname in req else " (advisory)"
        print(f"  {gname}{tag}: {gate_label(project_root, gname)}")
        if isinstance(entry, dict):
            print(f"    reviewed_commit: {entry.get('reviewed_commit')}")
            print(f"    timestamp:       {entry.get('timestamp')}")
            print(f"    notes:           {entry.get('notes')}")
    print(f"  current HEAD: {current_commit(project_root)}")
    rel_cmds = release_commands(project_root)
    if rel_cmds:
        print(f"  declared release commands: {', '.join(rel_cmds)}")
    print()
    print(f"sessions logged: {session_count(project_root)}")
    status = budget_status(project_root)
    if status is None:
        note = "intentionally skipped" if is_budget_skipped(project_root) else "not set (python3 hooks/budget_write.py <project_root> <tokens>, or --skip)"
        print(f"monthly token budget: {note}")
    else:
        used, budget, pct = status
        crossed = alert_threshold_crossed(pct)
        flag = f"  [ALERT: crossed {crossed}%]" if crossed else ""
        print(f"monthly token budget: {used}/{budget} ({pct}%){flag} — best-effort estimate, see docs/OTEL.md for the full source ranking")

    print()
    ok, total = project_health_score(project_root)
    print(f"project health: {ok}/{total} (informational -- several of these are fine left unset for a genuine prototype)")
    for label, value, is_ok in project_health(project_root):
        print(f"  [{'x' if is_ok else ' '}] {label}: {value}")


def main():
    if len(sys.argv) > 1:
        print_detail(sys.argv[1])
    else:
        names = list_projects()
        if not names:
            print("No projects found under ~/Documents/Projects/ (besides _harness).")
            return
        print_table(names)


if __name__ == "__main__":
    main()
