#!/usr/bin/env python3
"""CLI to set a project's monthly token budget (best-effort, advisory —
see budget_lib.py's module docstring for what this is and isn't).

Usage: python3 budget_write.py <project_root> <monthly_token_budget>
"""
import sys

from budget_lib import set_monthly_budget


def main() -> int:
    if len(sys.argv) != 3:
        print(
            "usage: budget_write.py <project_root> <monthly_token_budget>",
            file=sys.stderr,
        )
        return 1

    try:
        tokens = int(sys.argv[2])
    except ValueError:
        print("error: monthly_token_budget must be an integer", file=sys.stderr)
        return 1

    try:
        set_monthly_budget(sys.argv[1], tokens)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    print(f"Set monthly token budget for {sys.argv[1]}: {tokens}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
