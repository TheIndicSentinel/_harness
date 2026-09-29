#!/usr/bin/env python3
"""PreToolUse hook (matcher: Edit|Write|Read|Grep|Bash): guards a narrow list of
sensitive filenames. Only active when cwd is under the harness's projects
root (see gate_lib.projects_root(), overridable via
CLAUDE_HARNESS_PROJECTS_ROOT) — no-ops elsewhere.

Semantics: "ask", not hard-deny — emits the official PreToolUse JSON decision
so the user gets a permission prompt with the reason and can approve a
genuinely-intended operation, instead of being told to leave Claude Code.
- Edit/Write/Read: asks when the target file matches a sensitive pattern.
  Read is covered here (not only by settings.json's permissions.deny) because
  a plugin install doesn't get that deny list -- without this, a plugin user
  had no guard on reading .env/keys into context at all.
- Grep: asks when its `path` or `glob` targets a sensitive-looking file.
- Bash: asks when the command string mentions a sensitive-looking filename
  (covers `cat foo.pem`, `cp x credentials.json`, redirects — heuristic and
  deliberately over-broad, which is fine because a false positive costs one
  extra prompt, not a blocked workflow).
"""
import fnmatch
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gate_lib import projects_root  # noqa: E402

BLOCKLIST = [
    "*.pem",
    "*_rsa",
    "id_rsa*",
    "*.p12",
    "service-account*.json",
    "credentials.json",
    ".env",
    ".env.*",
]


def matches_blocklist(basename: str):
    for pattern in BLOCKLIST:
        if fnmatch.fnmatch(basename, pattern):
            return pattern
    return None


def ask(reason: str) -> int:
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "ask",
            "permissionDecisionReason": reason,
        }
    }))
    return 0


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0

    cwd = os.path.abspath(payload.get("cwd") or os.getcwd())
    root = projects_root()
    if cwd != root and not cwd.startswith(root + os.sep):
        return 0

    tool_name = payload.get("tool_name", "") or ""
    tool_input = payload.get("tool_input", {}) or {}

    if tool_name == "Bash":
        command = tool_input.get("command", "") or ""
        # Tokenize loosely; check the basename of each path-looking token.
        for token in re.split(r"[\s;|&<>()]+", command):
            token = token.strip("'\"`")
            if not token or token.startswith("-"):
                continue
            pattern = matches_blocklist(os.path.basename(token))
            if pattern:
                return ask(
                    f"Harness secrets guard: this command touches '{os.path.basename(token)}' "
                    f"(matches sensitive pattern '{pattern}'). Approve only if this access "
                    f"to key/credential material is intended."
                )
        return 0

    targets = [tool_input.get("file_path"), tool_input.get("path")]
    if tool_name == "Grep":
        targets.append(tool_input.get("glob"))
    for target in targets:
        if not target or not isinstance(target, str):
            continue
        basename = os.path.basename(target.rstrip("/"))
        pattern = matches_blocklist(basename)
        if pattern:
            return ask(
                f"Harness secrets guard: '{basename}' matches sensitive-file pattern "
                f"'{pattern}'. Approve only if {tool_name or 'this'} access to key/credential "
                f"material is intended (blocklist: _harness/hooks/secrets_guard.py)."
            )

    return 0


if __name__ == "__main__":
    sys.exit(main())
