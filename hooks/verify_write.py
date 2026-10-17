#!/usr/bin/env python3
"""Configure (or clear) the opt-in Stop verification command for a project.

  verify_write.py <project_root> "<command>" [--timeout SECONDS]
  verify_write.py <project_root> --clear
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gate_lib import project_root_for  # noqa: E402
from verify_lib import DEFAULT_TIMEOUT, MAX_TIMEOUT, SLOW_SECONDS, clear_config, config_path, load_config, load_state, save_config  # noqa: E402


def main(argv) -> int:
    args = argv[1:]
    if not args:
        print(__doc__)
        return 64
    root = os.path.abspath(args[0])
    if project_root_for(root) != root:
        print(f"{root} is not a project directly under the harness projects root.", file=sys.stderr)
        return 1
    if "--clear" in args:
        clear_config(root)
        print(f"Cleared verify command for {os.path.basename(root)}.")
        return 0
    timeout = DEFAULT_TIMEOUT
    if "--timeout" in args:
        i = args.index("--timeout")
        try:
            timeout = int(args[i + 1])
        except (IndexError, ValueError):
            print("--timeout needs an integer number of seconds", file=sys.stderr)
            return 64
        del args[i : i + 2]
    command = " ".join(a for a in args[1:] if not a.startswith("--")).strip()
    if not command:
        cfg = load_config(root)
        print(f"{os.path.basename(root)}: " + (f"verify = {cfg['command']!r} ({cfg['timeout_seconds']}s)" if cfg else "no verify command set"))
        took = load_state(root).get("last_seconds")
        if cfg and isinstance(took, (int, float)):
            print(f"last run: {took}s" + (f"  <-- over {SLOW_SECONDS}s: this runs after every turn that changes files; narrow it or use /goal" if took > SLOW_SECONDS else ""))
        return 0
    if timeout > SLOW_SECONDS:
        print(f"note: a {timeout}s ceiling is high. The check runs after every turn that changes files, "
              f"so keep it under ~{SLOW_SECONDS}s (affected tests + lint) and leave long suites to CI or /goal.")
    cfg = save_config(root, command, timeout)
    print(f"Saved ({config_path(root)}): {cfg['command']!r}, timeout {cfg['timeout_seconds']}s (max {MAX_TIMEOUT}).")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
