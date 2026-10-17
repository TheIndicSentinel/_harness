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


def required_in(gates: dict) -> set:
    names = {"privacy_guardrails_review"}
    extra = gates.get("required_gates") if isinstance(gates, dict) else None
    if isinstance(extra, list):
        names |= {g for g in extra if isinstance(g, str)}
    return names


def gates_at(ref: str, repo_dir: str):
    """Parsed gates.json as of `ref`, or None when absent/invalid there."""
    raw = sh(repo_dir, "show", f"{ref}:{GATES_PATH}")
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def baseline_refs(head: str, parent, repo_dir: str) -> list:
    """Commits whose required-gate set the current record must not loosen.
    Comparing only against the parent is defeated by a two-commit PR (commit 1
    drops the gate, commit 2 ships), so also compare against:
      - the merge-base with the PR's target branch (GITHUB_BASE_REF), else the
        remote default branch, and
      - the most recent tag before HEAD (what was last released).
    Refs that can't be resolved (shallow clone, no tags) are skipped."""
    refs = []
    if parent:
        refs.append(parent)
    base = os.environ.get("GITHUB_BASE_REF") or ""
    for cand in ([f"origin/{base}"] if base else []) + ["origin/HEAD", "origin/main", "origin/master"]:
        mb = sh(repo_dir, "merge-base", head, cand)
        if mb and mb != head:
            refs.append(mb)
            break
    tag = sh(repo_dir, "describe", "--tags", "--abbrev=0", f"{head}~1")
    if tag:
        tag_commit = sh(repo_dir, "rev-list", "-n", "1", tag)
        if tag_commit and tag_commit != head:
            refs.append(tag_commit)
    seen, out = set(), []
    for r in refs:
        if r not in seen:
            seen.add(r)
            out.append(r)
    return out


def removed_required_gates(gates: dict, refs, repo_dir: str) -> list:
    """Gates required at any baseline ref but not required now, minus those the
    current record explicitly acknowledges in `acknowledged_gate_removals`.
    The acknowledgement is deliberate, visible friction in review, not a
    security boundary: the record is still self-attested inside the repo."""
    if isinstance(refs, str):
        refs = [refs]
    before = set()
    for ref in refs or []:
        prior = gates_at(ref, repo_dir)
        if prior is not None:
            before |= required_in(prior)
    acked = gates.get("acknowledged_gate_removals")
    acked = {g for g in acked if isinstance(g, str)} if isinstance(acked, list) else set()
    return sorted(before - required_in(gates) - acked)


def check(gates_path: str, head: str, parent: str, repo_dir: str = ".", baselines=None):
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
    refs = baselines if baselines is not None else baseline_refs(head, parent, repo_dir)
    removed = removed_required_gates(gates, refs, repo_dir)
    if removed:
        failures.append(
            "required gate(s) removed since the previous commit, last tag or target branch: "
            + ", ".join(removed)
            + " — to loosen the gate set on purpose, list them in "
            '"acknowledged_gate_removals" in a change that gets its own review '
            "(CODEOWNERS for .harness/), not alongside a release"
        )
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
