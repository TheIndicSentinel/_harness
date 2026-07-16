#!/usr/bin/env python3
"""CLI used by review skills to record a gate result reliably (no hand-written JSON).

Usage:
  python3 gate_write.py <project_root> <check_name> <pass|fail> "<notes>"
  python3 gate_write.py <project_root> --require qa_review,compliance_review
  python3 gate_write.py <project_root> --require ""        # back to privacy-only

--require sets the opt-in hard-gate list (privacy_guardrails_review is always
required and never needs listing). It can ADD gates freely; a skill must never
use it to drop a gate just to unblock a ship.
"""
import sys

from gate_lib import record_gate, set_required_gates


def main() -> int:
    if len(sys.argv) >= 4 and sys.argv[2] == "--require":
        names = [n.strip() for n in sys.argv[3].split(",") if n.strip()]
        result = set_required_gates(sys.argv[1], names)
        print(f"Required gates for {sys.argv[1]}: {', '.join(result)}")
        return 0

    if len(sys.argv) < 4:
        print(
            "usage: gate_write.py <project_root> <check_name> <pass|fail> [notes]\n"
            "       gate_write.py <project_root> --require <gate1,gate2,...>",
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
