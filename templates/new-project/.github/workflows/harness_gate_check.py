#!/usr/bin/env python3
"""CI-side check: does .harness/gates.json show every required gate passing
for the commit being built? See docs/CI_GATE_CHECK.md in the harness root
for the convention this depends on (committing the gate record) and why the
match rule below is more lenient than the local hook's strict equality.

Exits 0 (pass, prints a one-line confirmation) or 1 (fail, prints each
failing gate via a GitHub Actions ::error:: annotation).
"""
import json
import os
import subprocess
import sys

GATES_PATH = ".harness/gates.json"


def sh(repo_dir: str, *args) -> str:
    return subprocess.run(
        ["git", "-C", repo_dir, *args], capture_output=True, text=True, check=False
    ).stdout.strip()


def record_valid_for_head(entry: dict, head: str, parent: str, repo_dir: str) -> bool:
    reviewed = entry.get("reviewed_commit")
    if reviewed == head:
        return True
    if parent and reviewed == parent:
        # Could be the "record the gate pass" bookkeeping commit made right
        # after review -- valid only if it changes nothing but the gate file.
        changed = sh(repo_dir, "diff", "--name-only", parent, head).splitlines()
        return changed == [GATES_PATH]
    return False


def check(gates_path: str, head: str, parent: str, repo_dir: str = "."):
    """Returns (ok: bool, failures: list[str])."""
    if not os.path.isfile(gates_path):
        return False, [
            f"No {gates_path} committed — nothing for CI to verify. "
            "Run the harness review skill(s) and commit the gate record."
        ]

    try:
        with open(gates_path) as f:
            gates = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        # Fail closed, not a crash -- a malformed file is not evidence of a
        # pass, and a script traceback is a worse CI experience than a clear
        # one-line reason.
        return False, [f"{gates_path} is not valid JSON ({e}) — treating as no record"]

    if not isinstance(gates, dict):
        return False, [f"{gates_path} did not contain a JSON object — treating as no record"]

    required = ["privacy_guardrails_review"]
    extra = gates.get("required_gates")
    if isinstance(extra, list):
        required += [g for g in extra if g not in required]

    failures = []
    for name in required:
        entry = gates.get(name)
        if not isinstance(entry, dict):
            failures.append(f"{name}: no record")
            continue
        if entry.get("status") != "pass":
            failures.append(f"{name}: status={entry.get('status')}")
            continue
        if not record_valid_for_head(entry, head, parent, repo_dir):
            failures.append(
                f"{name}: reviewed_commit={entry.get('reviewed_commit')} doesn't cover HEAD={head}"
            )

    return (not failures), failures


def main() -> int:
    repo_dir = os.environ.get("GITHUB_WORKSPACE") or "."
    head = sh(repo_dir, "rev-parse", "HEAD")
    parent = sh(repo_dir, "rev-parse", "HEAD~1") or None

    ok, failures = check(os.path.join(repo_dir, GATES_PATH), head, parent, repo_dir)
    if not ok:
        print("::error::Harness release gate check FAILED:")
        for f in failures:
            print(f"::error::  - {f}")
        return 1

    print(f"All required gates pass for {head}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
