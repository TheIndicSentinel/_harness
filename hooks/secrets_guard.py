#!/usr/bin/env python3
"""PreToolUse hook: block Edit/Write to a narrow list of sensitive filenames.
Only active when cwd is under ~/Documents/Projects/ (the harness scope) — no-ops elsewhere.
"""
import fnmatch
import json
import os
import sys

PROJECTS_ROOT = os.path.expanduser("~/Documents/Projects")

BLOCKLIST = [
    "*.pem",
    "*_rsa",
    "id_rsa*",
    "*.p12",
    "service-account*.json",
    "credentials.json",
]


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0

    cwd = payload.get("cwd") or os.getcwd()
    if not os.path.abspath(cwd).startswith(PROJECTS_ROOT):
        return 0

    tool_input = payload.get("tool_input", {}) or {}
    file_path = tool_input.get("file_path") or tool_input.get("path")
    if not file_path:
        return 0

    basename = os.path.basename(file_path)
    for pattern in BLOCKLIST:
        if fnmatch.fnmatch(basename, pattern):
            print(
                f"Blocked by harness secrets guard: '{basename}' matches sensitive-file "
                f"pattern '{pattern}'. If this is genuinely safe to edit, do it manually "
                f"outside Claude Code, or adjust the blocklist in "
                f"~/Documents/Projects/_harness/hooks/secrets_guard.py.",
                file=sys.stderr,
            )
            return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
