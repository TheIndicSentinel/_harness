#!/usr/bin/env python3
"""CLI used by review skills to record a gate result reliably (no hand-written JSON).

Usage: python3 gate_write.py <project_root> <check_name> <pass|fail> "<notes>"
"""
import sys

from gate_lib import record_gate


def main() -> int:
    if len(sys.argv) < 4:
        print(
            "usage: gate_write.py <project_root> <check_name> <pass|fail> [notes]",
            file=sys.stderr,
        )
        return 1

    project_root, check, status = sys.argv[1], sys.argv[2], sys.argv[3]
    notes = sys.argv[4] if len(sys.argv) > 4 else ""

    try:
        record_gate(project_root, check, status, notes)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    print(f"Recorded {check}={status} for {project_root}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
