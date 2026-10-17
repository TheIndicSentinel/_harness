#!/usr/bin/env python3
"""Lint a project's native Claude Code memory for the failure modes that make
memory a liability: status logs masquerading as memory, oversized files,
missing/old verification dates, and references to files that no longer exist.

Usage: memory_lint.py [project_root]   (default: cwd)   [--strict]

Findings are advice (exit 0) unless --strict, which exits 1 if any exist so it
can run in CI. Rules and thresholds are the harness's own judgment, not an
Anthropic requirement (Anthropic's documented limit is MEMORY.md's first 200
lines / 25 KB loading each session).
"""
import os
import re
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hooks"))
from memory_lib import (  # noqa: E402
    age_days,
    memory_dir,
    memory_files,
    parse_frontmatter,
)

MAX_FILE_BYTES = 4096
MAX_INDEX_LINES = 60
MAX_INDEX_LINE_CHARS = 200
STALE_DAYS = 90
HANDOFF_STALE_DAYS = 14
HANDOFF_MAX_BYTES = 2048

STATUS_NAME = re.compile(r"(status|progress|roadmap|todo|changelog)", re.I)
PR_REF = re.compile(r"(?<![\w&])#\d{2,5}\b")
STATUS_LINE = re.compile(r"^\s*[-*]?\s*(merged|done|completed|shipped)\b", re.I)
PATHISH = re.compile(r"`([\w./-]+/[\w.-]+\.\w{1,6})`")


def lint(project_root, now=None):
    now = now or time.time()
    findings = []
    unverified = []
    mdir = memory_dir(project_root)

    index = os.path.join(mdir, "MEMORY.md")
    if os.path.isfile(index):
        lines = open(index, errors="ignore").read().splitlines()
        if len(lines) > MAX_INDEX_LINES:
            findings.append(("MEMORY.md", f"{len(lines)} lines (> {MAX_INDEX_LINES}); prune or merge"))
        for n, line in enumerate(lines, 1):
            if len(line) > MAX_INDEX_LINE_CHARS:
                findings.append(("MEMORY.md", f"line {n} is {len(line)} chars (> {MAX_INDEX_LINE_CHARS}); an index entry is one short hook"))

    for path in memory_files(project_root):
        name = os.path.basename(path)
        text = open(path, errors="ignore").read()
        size = len(text.encode())
        fm = parse_frontmatter(text)

        if name == "handoff.md":
            if size > HANDOFF_MAX_BYTES:
                findings.append((name, f"{size} bytes (> {HANDOFF_MAX_BYTES}); a handoff is the current task only, overwritten"))
            if age_days(os.path.getmtime(path), now) > HANDOFF_STALE_DAYS:
                findings.append((name, f"older than {HANDOFF_STALE_DAYS} days; refresh or delete"))
            continue

        if size > MAX_FILE_BYTES:
            findings.append((name, f"{size} bytes (> {MAX_FILE_BYTES}); split, or move to docs/ if it's a log"))
        prs = len(PR_REF.findall(text))
        status_lines = sum(1 for l in text.splitlines() if STATUS_LINE.match(l))
        if prs >= 5 or status_lines >= 3 or STATUS_NAME.search(fm.get("name", name)):
            findings.append((name, f"looks like a status log ({prs} PR refs, {status_lines} done-lines); git and ROADMAP already answer this — keep the why/gotchas only"))

        stamp = fm.get("verified")
        # Who the user is / how they like to work doesn't rot like a fact about code.
        if not stamp and fm.get("type") in ("user", "feedback"):
            pass
        elif not stamp:
            unverified.append(name)
        else:
            try:
                t = time.mktime(time.strptime(stamp[:10], "%Y-%m-%d"))
                if age_days(t, now) > STALE_DAYS:
                    findings.append((name, f"verified {stamp[:10]} (> {STALE_DAYS} days ago); re-verify or delete"))
            except ValueError:
                findings.append((name, f"unparseable `verified:` value {stamp!r}"))

        dead = sorted({p for p in PATHISH.findall(text)
                       if not os.path.exists(os.path.join(project_root, p))})
        if dead:
            findings.append((name, "references paths that don't exist: " + ", ".join(dead[:5])))
    if unverified:
        shown = ", ".join(unverified[:4]) + (f", +{len(unverified) - 4} more" if len(unverified) > 4 else "")
        findings.append((f"{len(unverified)} file(s)", f"no `verified:` date in metadata, so staleness can't be judged: {shown}"))
    return findings


def main(argv):
    args = [a for a in argv[1:] if not a.startswith("--")]
    root = os.path.abspath(args[0] if args else os.getcwd())
    if not os.path.isdir(memory_dir(root)):
        print(f"No memory directory for {root} ({memory_dir(root)}); nothing to lint.")
        return 0
    findings = lint(root)
    if not findings:
        print("Memory lint: clean.")
        return 0
    print(f"Memory lint: {len(findings)} finding(s) for {os.path.basename(root)}")
    for name, msg in findings:
        print(f"  - {name}: {msg}")
    return 1 if "--strict" in argv else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
