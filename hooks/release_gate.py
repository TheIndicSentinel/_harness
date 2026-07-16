#!/usr/bin/env python3
"""PreToolUse hook (matcher: Bash|mcp__.*): hard-blocks release/publish/deploy
actions until every required gate (privacy_guardrails_review always; plus any
project opt-ins in gates.json "required_gates") has passed for the CURRENT commit.

Only active when cwd is under the harness's projects root (see
gate_lib.projects_root(), overridable via CLAUDE_HARNESS_PROJECTS_ROOT) —
no-ops elsewhere.

Coverage and known boundaries (documented deliberately):
- Bash: matches commands that are recognizably "ship it to users". Plain
  `git push` is deliberately NOT matched (would block ordinary branch pushes).
  `./gradlew *Release*` IS matched even for local builds — stricter than pure
  "publish", kept on purpose: a signed release artifact tends to get
  distributed, so it should clear the gates before it exists.
- MCP tools: any mcp__* tool whose name says deploy/publish/release/submit is
  gated the same way.
- This is policy for the cooperative path, not a security boundary: a command
  run outside the project cwd (git -C, absolute paths), an obfuscated command
  string, or a manual terminal outside Claude Code bypasses it. The honest
  reviews it points to are the real control; this hook makes skipping them a
  deliberate act instead of an accident.
- Fail-mode: infrastructure errors (unreadable payload) fail OPEN so a hook bug
  can't brick every Bash call; the gate check itself fails CLOSED (missing or
  stale record blocks).
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gate_lib import failing_required, project_root_for  # noqa: E402

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
MCP_SHIP_TOOL = re.compile(r"^mcp__.*(deploy|publish|release|submit)", re.IGNORECASE)


def is_ship_action(payload: dict) -> str:
    """Return a short label of what matched, or '' if not a ship action."""
    tool_name = payload.get("tool_name", "") or ""
    if tool_name.startswith("mcp__"):
        if MCP_SHIP_TOOL.search(tool_name):
            return f"MCP tool '{tool_name}'"
        return ""
    command = (payload.get("tool_input", {}) or {}).get("command", "")
    if command and any(p.search(command) for p in COMPILED):
        return f"command '{command.strip()[:80]}'"
    return ""


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0

    cwd = payload.get("cwd") or os.getcwd()
    project_root = project_root_for(cwd)
    if not project_root or not os.path.isdir(project_root):
        return 0

    matched = is_ship_action(payload)
    if not matched:
        return 0

    failing = failing_required(project_root)
    if not failing:
        return 0

    skill_hint = {
        "privacy_guardrails_review": "privacy-guardrails-review",
        "qa_review": "qa-review",
        "compliance_review": "compliance-review",
    }
    hints = ", ".join(skill_hint.get(g, g) for g in failing)
    print(
        f"Blocked by harness release gate: this looks like a release/publish/deploy "
        f"action ({matched}), but these required gate(s) for "
        f"{os.path.basename(project_root)} haven't passed for the current commit: "
        f"{', '.join(failing)}. Run the matching skill(s) first ({hints}), or /ship.",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
