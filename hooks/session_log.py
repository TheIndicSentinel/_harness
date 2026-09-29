#!/usr/bin/env python3
"""SessionEnd hook: append one best-effort session summary row to
<project>/docs/COST_LOG.md.

Wired to SessionEnd, not Stop: Stop fires after every assistant turn, and
since each row sums the whole transcript, a Stop-wired logger wrote one
cumulative row per turn -- a 20-turn session got counted ~210x-turns worth
of tokens, which then inflated budget_lib's monthly total.

Token accounting (from the transcript's per-message `usage` blocks):
- "in" = input_tokens + cache_creation_input_tokens -- new input processed.
  With prompt caching (which Claude Code does automatically), input_tokens
  alone is only the small uncached tail, so ignoring cache writes badly
  undercounts.
- "out" = output_tokens.
- "cache read" = cache_read_input_tokens, shown in its own column and NOT
  added to "in": cache reads bill at a small fraction of the input rate and
  re-read the whole context every turn, so folding them into "in" would
  swamp the budget with the cheapest tokens.
- Usage is counted once per API message id: the transcript can write one
  line per content block of the same assistant message, each repeating that
  message's usage.

Only active when cwd is under the harness's projects root (see
gate_lib.projects_root(), overridable via CLAUDE_HARNESS_PROJECTS_ROOT) —
no-ops elsewhere. This is an estimate, not an authoritative dollar figure —
use `/cost`, or OpenTelemetry (see docs/OTEL.md). Subagent transcripts are
stored separately and aren't included. Never blocks — any parse failure is
swallowed and the hook exits 0.
"""
import json
import os
import sys
from datetime import datetime, timezone
from typing import Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gate_lib import project_root_for  # noqa: E402

TABLE_HEADER = "| Date | Session ID | Duration | Est. tokens (in/out) | Cache read |"
TABLE_SEP = "|------|-----------|----------|------------------------|------------|"


def summarize_transcript(transcript_path: str) -> Tuple[str, str, str]:
    """(duration, "in/out", cache_read) as display strings, "n/a" when unknown."""
    if not transcript_path or not os.path.isfile(transcript_path):
        return "n/a", "n/a", "n/a"

    first_ts = last_ts = None
    # msg id (or line number when absent) -> that message's usage; a later
    # line for the same id overwrites, so the final usage wins.
    usage_by_msg = {}

    try:
        with open(transcript_path, "r") as f:
            for lineno, line in enumerate(f):
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

                message = entry.get("message") if isinstance(entry.get("message"), dict) else {}
                usage = message.get("usage") or entry.get("usage")
                if not isinstance(usage, dict):
                    continue
                usage_by_msg[message.get("id") or f"line:{lineno}"] = usage
    except OSError:
        return "n/a", "n/a", "n/a"

    duration = "n/a"
    if first_ts and last_ts:
        try:
            t0 = datetime.fromisoformat(first_ts.replace("Z", "+00:00"))
            t1 = datetime.fromisoformat(last_ts.replace("Z", "+00:00"))
            seconds = max(0, int((t1 - t0).total_seconds()))
            duration = f"{seconds // 60}m{seconds % 60:02d}s"
        except ValueError:
            pass

    if not usage_by_msg:
        return duration, "n/a", "n/a"
    in_tokens = out_tokens = cache_read = 0
    for usage in usage_by_msg.values():
        in_tokens += (usage.get("input_tokens", 0) or 0) + (
            usage.get("cache_creation_input_tokens", 0) or 0
        )
        out_tokens += usage.get("output_tokens", 0) or 0
        cache_read += usage.get("cache_read_input_tokens", 0) or 0
    return duration, f"{in_tokens}/{out_tokens}", str(cache_read)


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
    duration, tokens, cache_read = summarize_transcript(payload.get("transcript_path", ""))
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    docs_dir = os.path.join(project_root, "docs")
    os.makedirs(docs_dir, exist_ok=True)
    log_path = os.path.join(docs_dir, "COST_LOG.md")

    if not os.path.isfile(log_path):
        with open(log_path, "w") as f:
            f.write(
                f"# {os.path.basename(project_root)} — Session / Cost Log\n\n"
                "Auto-appended by the harness's SessionEnd hook, one row per session. Token "
                "counts are a best-effort estimate, not an authoritative dollar figure — "
                "cross-check `/cost`. \"in\" includes cache writes; cache reads are listed "
                "separately and excluded from the monthly budget.\n\n"
                f"{TABLE_HEADER}\n{TABLE_SEP}\n"
            )

    with open(log_path, "a") as f:
        f.write(f"| {date} | {session_id} | {duration} | {tokens} | {cache_read} |\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
