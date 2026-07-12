#!/usr/bin/env python3
"""Read-only harness status report: what state has the harness left each project in.

Usage:
  python3 harness_status.py            # table across every project under Projects/
  python3 harness_status.py <name>     # detailed report for one project
"""
import os
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "hooks"))
from gate_lib import current_commit, load_gates  # noqa: E402

PROJECTS_ROOT = os.path.expanduser("~/Documents/Projects")
DOC_FILES = ["PRD.md", "MARKETING.md", "COST_LOG.md", "RELEASE_CHECKLIST.md"]


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


def gate_state(project_root):
    gates = load_gates(project_root)
    entry = gates.get("privacy_guardrails_review")
    if not entry:
        return "none", None
    head = current_commit(project_root)
    if entry.get("status") == "pass" and entry.get("reviewed_commit") == head:
        return "pass (current)", entry
    if entry.get("status") == "pass":
        return "pass (stale — new commits since review)", entry
    return f"{entry.get('status', 'unknown')}", entry


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


def summary_row(name):
    project_root = os.path.join(PROJECTS_ROOT, name)
    docs = docs_state(project_root)
    adopted = f"{sum(1 for d in docs if d)}/{len(DOC_FILES)}"
    gate, _ = gate_state(project_root)
    sessions = session_count(project_root)
    git = git_state(project_root)
    return name, adopted, gate, str(sessions), git


def print_table(names):
    rows = [summary_row(n) for n in names]
    headers = ["Project", "Docs adopted", "Gate", "Sessions logged", "Git"]
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
    print()
    print("docs:")
    for d in docs_state(project_root):
        print(f"  [{'x' if d else ' '}] {d or '(missing)'}")
    print()
    gate, entry = gate_state(project_root)
    print(f"privacy_guardrails_review gate: {gate}")
    if entry:
        print(f"  reviewed_commit: {entry.get('reviewed_commit')}")
        print(f"  current HEAD:    {current_commit(project_root)}")
        print(f"  timestamp:       {entry.get('timestamp')}")
        print(f"  notes:           {entry.get('notes')}")
    print()
    print(f"sessions logged: {session_count(project_root)}")


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
