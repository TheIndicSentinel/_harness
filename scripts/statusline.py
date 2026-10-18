#!/usr/bin/env python3
"""Claude Code status line: one short line from the JSON Claude Code sends on stdin.

  ctx 23% · cache 97% · $0.42 · Sonnet 5.5

Field names are the ones in the status line docs (https://code.claude.com/docs/en/statusline):
  context_window.used_percentage   0-100, null early in a session
  prompt_cache.hit_ratio           0-1, needs Claude Code >= 2.1.251, null while nothing is cached
  cost.total_cost_usd              estimate for this session
  model.display_name (else model.id)
A missing or null field is left out, never guessed. On any error nothing is printed (a status
line must not break a session). Local only: no network, no files read or written, stdlib only,
and the transcript path in the payload is never opened.
"""
import json
import sys


def _num(x):
    return x if isinstance(x, (int, float)) and not isinstance(x, bool) else None


def _obj(d, key):
    v = d.get(key)
    return v if isinstance(v, dict) else {}


def render(data):
    if not isinstance(data, dict):
        return ""
    parts = []
    used = _num(_obj(data, "context_window").get("used_percentage"))
    if used is not None:
        parts.append("ctx %d%%" % round(used))
    ratio = _num(_obj(data, "prompt_cache").get("hit_ratio"))
    if ratio is not None:
        parts.append("cache %d%%" % round(ratio * 100))
    cost = _num(_obj(data, "cost").get("total_cost_usd"))
    if cost is not None:
        parts.append("$%.2f" % cost)
    model = _obj(data, "model")
    name = model.get("display_name") or model.get("id")
    if isinstance(name, str) and name.strip():
        parts.append(name.strip()[:24])
    return " · ".join(parts)


def main():
    try:
        line = render(json.load(sys.stdin))
        if line:
            sys.stdout.write(line + "\n")
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
