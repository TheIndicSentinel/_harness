#!/usr/bin/env python3
"""Report which optional harness features the installed Claude Code supports.

Only features whose minimum version Anthropic's docs state are listed; this
is not a guess table. Re-audit against the docs when you update Claude Code
(see docs/COMPATIBILITY.md).

Usage: compat_check.py [--version X.Y.Z]   (default: read `claude --version`)
"""
import re
import subprocess
import sys

# feature -> (minimum version, what it gives the harness, source)
OPTIONAL_FEATURES = {
    "hook onFailure: \"block\"": (
        (2, 1, 295),
        "a timed-out or crashed hook blocks the action instead of falling through (enabled on release_gate.py; ignored by older versions)",
        "docs: code.claude.com/docs/en/hooks, security recommendations (checked 2026-10-15)",
    ),
}

# Last Claude Code version the harness's behaviour was audited against.
AUDITED_AGAINST = (2, 1, 300)


def parse_version(text: str):
    m = re.search(r"(\d+)\.(\d+)\.(\d+)", text or "")
    return tuple(int(x) for x in m.groups()) if m else None


def installed_version():
    try:
        out = subprocess.run(["claude", "--version"], capture_output=True, text=True, timeout=10).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    return parse_version(out)


def report(version):
    lines = []
    if version is None:
        return ["Could not determine the installed Claude Code version."]
    fmt = lambda v: ".".join(map(str, v))
    lines.append(f"Installed Claude Code: {fmt(version)} (harness last audited against {fmt(AUDITED_AGAINST)})")
    if version < AUDITED_AGAINST:
        lines.append("  ! older than the audited version: some documented behaviour may be missing")
    elif version > AUDITED_AGAINST:
        lines.append("  ~ newer than the audited version: re-check docs/COMPATIBILITY.md and run the tests")
    for name, (minimum, gives, _src) in OPTIONAL_FEATURES.items():
        ok = version >= minimum
        lines.append(f"  [{'x' if ok else ' '}] {name} (needs >= {fmt(minimum)}): {gives}")
    return lines


def main(argv):
    version = parse_version(argv[argv.index("--version") + 1]) if "--version" in argv else installed_version()
    print("\n".join(report(version)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
