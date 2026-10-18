#!/usr/bin/env python3
"""SessionEnd hook: append one best-effort session summary row to the
harness-owned per-project cost log (gate_lib.cost_log_path(), by default
~/.claude/harness/cost/<project>.md).

The log lives OUTSIDE the project repo on purpose: it used to be
<project>/docs/COST_LOG.md and was once published by accident. A legacy
in-repo log is copied over on first write and left in place (never deleted
by the hook) -- /harness-status flags it so you can untrack it yourself.

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
- cache reads (cache_read_input_tokens) are written to their own "Cache read"
  column but never added into the token total: they re-count the whole context every
  turn, so the figure (billions after a long session) says little about cost.
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
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from typing import Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gate_lib import cost_log_path, legacy_cost_log_path, project_root_for  # noqa: E402
from cost_log_lib import HEADER as TABLE_HEADER, SEP as TABLE_SEP, ensure_canonical  # noqa: E402

# Gaps longer than this between transcript entries are treated as idle (a
# resumed session can span days; wall-clock first->last made "18854m44s").
IDLE_GAP_SECONDS = 600


def current_branch(project_root: str) -> str:
    """Branch at session end, as a rough "task" label for cost-per-task
    reporting. '-' when unknown (not a git repo, detached HEAD, error)."""
    try:
        r = subprocess.run(
            ["git", "-C", project_root, "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, timeout=5,
        )
        name = r.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return "-"
    if r.returncode != 0 or not name or name == "HEAD":
        return "-"
    return re.sub(r"[\s|]+", "_", name)[:80]


ORIENT_TOOLS = ("Read", "Grep", "Glob")
EDIT_TOOLS = ("Edit", "Write", "MultiEdit", "NotebookEdit")

# Models explore mostly through Bash, so counting only Read/Grep/Glob undercounted
# orientation (a session with 8 shell reads reported 0). A Bash call counts as one
# orientation call when any command segment starts with one of these verbs.
SHELL_READ_VERBS = ("cat", "sed", "head", "rg", "grep", "ls", "find")
_SEGMENT_SPLIT = re.compile(r"&&|\|\||;|\||\n")


def is_shell_read(command: str) -> bool:
    """True if the shell command reads files/directories (cat, sed, head, rg,
    grep, ls, find). Write-shaped uses are not reads: `sed -i`, and any segment
    with an output redirection (`cat > f <<EOF`)."""
    for segment in _SEGMENT_SPLIT.split(command or ""):
        tokens = segment.strip().split()
        while tokens and re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", tokens[0]):
            tokens.pop(0)  # leading VAR=value assignments
        if not tokens or tokens[0] not in SHELL_READ_VERBS:
            continue
        if ">" in segment:
            continue
        if tokens[0] == "sed" and any(t == "-i" or t.startswith("-i") or t == "--in-place" for t in tokens[1:]):
            continue
        return True
    return False


def orientation_calls(transcript_path: str, include_shell_reads: bool = True) -> str:
    """How many Read/Grep/Glob calls, plus shell reads (cat, sed, head, rg, grep,
    ls, find through Bash), happened before the first edit: a rough "how much
    re-exploration did this session need" signal -- the cost that CLAUDE.md,
    memory and a handoff exist to reduce. A TREND signal, not a score: only
    comparable between sessions of the same task type in the same project (a
    refactor legitimately reads more than a one-line fix). "-" when the session
    made no edit (nothing to measure against) or the transcript is unreadable.

    include_shell_reads=False gives the original (pre-fix) definition, so older
    rows and "before" measurements stay comparable. Transcript format is
    undocumented, so this is best-effort like the rest."""
    if not transcript_path or not os.path.isfile(transcript_path):
        return "-"
    seen = {}
    count = 0
    try:
        with open(transcript_path, "r") as f:
            for line in f:
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                message = entry.get("message") if isinstance(entry.get("message"), dict) else {}
                content = message.get("content")
                if not isinstance(content, list):
                    continue
                for block in content:
                    if not isinstance(block, dict) or block.get("type") != "tool_use":
                        continue
                    if block.get("id") in seen:
                        continue
                    seen[block.get("id")] = True
                    name = block.get("name")
                    if name in EDIT_TOOLS:
                        return str(count)
                    if name in ORIENT_TOOLS:
                        count += 1
                    elif include_shell_reads and name == "Bash":
                        tool_input = block.get("input") if isinstance(block.get("input"), dict) else {}
                        if is_shell_read(str(tool_input.get("command", ""))):
                            count += 1
    except OSError:
        return "-"
    return "-"


def summarize_transcript(transcript_path: str) -> Tuple[str, str, str]:
    """(duration, "in/out", cache_read) as display strings, "n/a" when unknown."""
    if not transcript_path or not os.path.isfile(transcript_path):
        return "n/a", "n/a", "n/a"

    timestamps = []
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
                    timestamps.append(ts)

                message = entry.get("message") if isinstance(entry.get("message"), dict) else {}
                usage = message.get("usage") or entry.get("usage")
                if not isinstance(usage, dict):
                    continue
                usage_by_msg[message.get("id") or f"line:{lineno}"] = usage
    except OSError:
        return "n/a", "n/a", "n/a"

    duration = "n/a"
    if timestamps:
        parsed = []
        for ts in timestamps:
            try:
                parsed.append(datetime.fromisoformat(ts.replace("Z", "+00:00")))
            except ValueError:
                continue
        if parsed:
            seconds = 0
            for a, b in zip(parsed, parsed[1:]):
                gap = (b - a).total_seconds()
                if 0 < gap <= IDLE_GAP_SECONDS:
                    seconds += int(gap)
            duration = f"{seconds // 60}m{seconds % 60:02d}s"

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

    log_path = cost_log_path(project_root)
    os.makedirs(os.path.dirname(log_path), exist_ok=True)

    if not os.path.isfile(log_path):
        legacy = legacy_cost_log_path(project_root)
        if os.path.isfile(legacy):
            shutil.copyfile(legacy, log_path)  # keep history; the repo copy is left alone
        else:
            with open(log_path, "w") as f:
                f.write(
                    f"# {os.path.basename(project_root)} — Session / Cost Log\n\n"
                    "Auto-appended by the harness's SessionEnd hook, one row per session. "
                    "Stored outside the repo on purpose. Active time excludes gaps over "
                    f"{IDLE_GAP_SECONDS // 60} minutes. Token counts are a best-effort estimate, "
                    "not an authoritative dollar figure — cross-check `/cost`. \"in\" includes "
                    "cache writes; cache reads have their own column and are not part of the "
                    "total (they re-count the whole context every turn). A session that ends "
                    "more than once has several rows, each cumulative: use the latest per "
                    "session ID.\n\n"
                    f"{TABLE_HEADER}\n{TABLE_SEP}\n"
                )

    ensure_canonical(log_path)  # an older header or row shape is migrated, losslessly, before appending
    with open(log_path, "a") as f:
        f.write(
            f"| {date} | {session_id} | {duration} | {tokens} | {cache_read} | "
            f"{current_branch(project_root)} | {orientation_calls(payload.get('transcript_path', ''))} |\n"
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
