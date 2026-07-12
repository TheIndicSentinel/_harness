#!/usr/bin/env python3
"""PreToolUse hook (matcher: Bash): hard-blocks release/publish/deploy commands
until the privacy_guardrails_review gate has passed for the CURRENT commit.

Only active when cwd is under ~/Documents/Projects/ — no-ops elsewhere.
Deliberately does not match plain `git push` (would block ordinary branch
pushes); only matches commands that are recognizably "ship it to users."
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gate_lib import check_passing  # noqa: E402

PROJECTS_ROOT = os.path.expanduser("~/Documents/Projects")

RELEASE_PATTERNS = [
    r"\bgh\s+release\s+create\b",
    r"\bnpm\s+publish\b",
    r"\beas\s+submit\b",
    r"\beas\s+build\b.*--auto-submit",
    r"\bfastlane\b.*\b(release|deploy|publish)\w*\b",
    r"\./gradlew\b.*\b\w*Release\w*\b",
    r"\bvercel\b.*--prod\b",
    r"\bnetlify\s+deploy\b.*--prod\b",
    r"\bdocker\s+push\b",
    r"\bfirebase\s+deploy\b",
    r"\bgit\s+push\b.*(--tags\b|refs/tags/)",
]

COMPILED = [re.compile(p) for p in RELEASE_PATTERNS]


def project_root_for(cwd: str):
    cwd = os.path.abspath(cwd)
    if not cwd.startswith(PROJECTS_ROOT + os.sep):
        return None
    rest = cwd[len(PROJECTS_ROOT) + 1 :]
    if not rest or rest.startswith("_harness"):
        return None
    top = rest.split(os.sep)[0]
    return os.path.join(PROJECTS_ROOT, top)


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0

    cwd = payload.get("cwd") or os.getcwd()
    project_root = project_root_for(cwd)
    if not project_root or not os.path.isdir(project_root):
        return 0

    command = (payload.get("tool_input", {}) or {}).get("command", "")
    if not command or not any(p.search(command) for p in COMPILED):
        return 0

    if check_passing(project_root, "privacy_guardrails_review"):
        return 0

    print(
        "Blocked by harness release gate: this looks like a release/publish/deploy "
        f"command ('{command.strip()[:80]}'), but the privacy_guardrails_review gate "
        f"for {os.path.basename(project_root)} hasn't passed for the current commit. "
        "Run the privacy-guardrails-review skill (or /ship) first.",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
