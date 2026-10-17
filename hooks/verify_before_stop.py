#!/usr/bin/env python3
"""Stop hook (OPT-IN): before Claude ends its turn, run the project's verify
command and, if it fails, block the stop (exit 2) with the output so Claude
keeps working until the check passes -- Anthropic's "deterministic gate"
recipe for unattended or long tasks.

Does nothing unless you configured a command for the project:
    python3 hooks/verify_write.py <project_root> "<test command>" [--timeout N]

Design points:
- Runs only when something changed since the last pass (HEAD or the dirty
  tree), so read-only questions and re-stops cost nothing.
- A clean tree with no recorded state just seeds a baseline; it never runs.
- At most MAX_CONSECUTIVE_BLOCKS blocks in a row, then it lets the stop
  through and says so -- a broken or flaky command can't trap a session.
- Hook infrastructure errors fail OPEN (exit 0): this is a quality nudge for
  the cooperative path, not a security boundary.
- Only active under the harness's projects root.
"""
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gate_lib import project_root_for  # noqa: E402
from verify_lib import (  # noqa: E402
    MAX_CONSECUTIVE_BLOCKS,
    fingerprint,
    load_config,
    load_state,
    save_state,
)

MAX_OUTPUT_CHARS = 4000


def tail(text: str) -> str:
    text = text.strip()
    if len(text) <= MAX_OUTPUT_CHARS:
        return text
    return "…(truncated)…\n" + text[-MAX_OUTPUT_CHARS:]


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        root = project_root_for(payload.get("cwd") or os.getcwd())
        if not root or not os.path.isdir(root):
            return 0
        cfg = load_config(root)
        if not cfg:
            return 0
        fp = fingerprint(root)
        if fp is None:
            return 0

        state = load_state(root)
        if not state:
            if not fp["dirty"]:
                save_state(root, {"fingerprint": fp["hash"], "result": "baseline", "blocks": 0})
                return 0
        elif state.get("fingerprint") == fp["hash"] and state.get("result") in ("pass", "baseline", "gave_up"):
            return 0

        started = time.monotonic()
        try:
            proc = subprocess.run(
                cfg["command"], shell=True, cwd=root, capture_output=True, text=True,
                timeout=cfg["timeout_seconds"],
            )
            passed = proc.returncode == 0
            output = (proc.stdout or "") + (proc.stderr or "")
            reason = f"exit code {proc.returncode}"
        except subprocess.TimeoutExpired as exc:
            passed = False
            output = (exc.stdout or b"").decode(errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
            reason = f"timed out after {cfg['timeout_seconds']}s (narrow the command or raise --timeout)"

        took = round(time.monotonic() - started, 1)
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        if passed:
            save_state(root, {"fingerprint": fp["hash"], "result": "pass", "blocks": 0, "at": now, "last_seconds": took})
            return 0

        blocks = int(state.get("blocks", 0)) + 1
        if blocks > MAX_CONSECUTIVE_BLOCKS:
            save_state(root, {"fingerprint": fp["hash"], "result": "gave_up", "blocks": 0, "at": now, "last_seconds": took})
            print(
                f"[harness] verify command still failing after {MAX_CONSECUTIVE_BLOCKS} attempts "
                f"({reason}); letting the stop through. Tell the user it is NOT verified.",
                file=sys.stderr,
            )
            return 0
        save_state(root, {"fingerprint": fp["hash"], "result": "fail", "blocks": blocks, "at": now, "last_seconds": took})
        print(
            f"[harness] verification failed ({reason}) -- attempt {blocks}/{MAX_CONSECUTIVE_BLOCKS}. "
            f"Fix the cause (not the test, unless the test is wrong) and let the check run again.\n"
            f"$ {cfg['command']}\n{tail(output)}",
            file=sys.stderr,
        )
        return 2
    except Exception:
        return 0


if __name__ == "__main__":
    sys.exit(main())
