#!/usr/bin/env python3
"""Stop hook: append a best-effort session summary row to <project>/docs/COST_LOG.md.
Only active when cwd is under ~/Documents/Projects/ (the harness scope) — no-ops elsewhere.
Token counts are parsed from the transcript JSONL when present; this is an estimate,
not an authoritative dollar figure (use the native /cost command for that).
Never blocks Stop — any parse failure is swallowed and the hook exits 0.
"""
import json
import os
import sys
from datetime import datetime, timezone
from typing import Optional, Tuple

PROJECTS_ROOT = os.path.expanduser("~/Documents/Projects")
TABLE_HEADER = "| Date | Session ID | Duration | Est. tokens (in/out) |"
TABLE_SEP = "|------|-----------|----------|------------------------|"


def project_root_for(cwd: str) -> Optional[str]:
    cwd = os.path.abspath(cwd)
    if not cwd.startswith(PROJECTS_ROOT + os.sep):
        return None
    rest = cwd[len(PROJECTS_ROOT) + 1 :]
    if not rest or rest.startswith("_harness"):
        return None
    top = rest.split(os.sep)[0]
    return os.path.join(PROJECTS_ROOT, top)


def summarize_transcript(transcript_path: str) -> Tuple[str, str]:
    if not transcript_path or not os.path.isfile(transcript_path):
        return "n/a", "n/a"

    first_ts = last_ts = None
    in_tokens = out_tokens = 0
    have_tokens = False

    try:
        with open(transcript_path, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue

                ts = entry.get("timestamp")
                if ts:
                    if first_ts is None:
                        first_ts = ts
                    last_ts = ts

                usage = (
                    entry.get("message", {}).get("usage")
                    if isinstance(entry.get("message"), dict)
                    else None
                ) or entry.get("usage")
                if isinstance(usage, dict):
                    have_tokens = True
                    in_tokens += usage.get("input_tokens", 0) or 0
                    out_tokens += usage.get("output_tokens", 0) or 0
    except OSError:
        return "n/a", "n/a"

    duration = "n/a"
    if first_ts and last_ts:
        try:
            t0 = datetime.fromisoformat(first_ts.replace("Z", "+00:00"))
            t1 = datetime.fromisoformat(last_ts.replace("Z", "+00:00"))
            seconds = max(0, int((t1 - t0).total_seconds()))
            duration = f"{seconds // 60}m{seconds % 60:02d}s"
        except ValueError:
            pass

    tokens = f"{in_tokens}/{out_tokens}" if have_tokens else "n/a"
    return duration, tokens


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0

    cwd = payload.get("cwd") or os.getcwd()
    project_root = project_root_for(cwd)
    if not project_root or not os.path.isdir(project_root):
        return 0

    session_id = payload.get("session_id", "unknown")[:8]
    duration, tokens = summarize_transcript(payload.get("transcript_path", ""))
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    docs_dir = os.path.join(project_root, "docs")
    os.makedirs(docs_dir, exist_ok=True)
    log_path = os.path.join(docs_dir, "COST_LOG.md")

    if not os.path.isfile(log_path):
        with open(log_path, "w") as f:
            f.write(
                f"# {os.path.basename(project_root)} — Session / Cost Log\n\n"
                "Auto-appended by the harness's Stop hook. Token counts are a best-effort "
                "estimate, not an authoritative dollar figure — cross-check `/cost`.\n\n"
                f"{TABLE_HEADER}\n{TABLE_SEP}\n"
            )

    with open(log_path, "a") as f:
        f.write(f"| {date} | {session_id} | {duration} | {tokens} |\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
