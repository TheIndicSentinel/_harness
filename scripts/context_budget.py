#!/usr/bin/env python3
"""Report the harness's always-loaded context cost, so token efficiency is a
measured number and not a feeling.

What loads into EVERY session: the umbrella CLAUDE.md, plus the `description`
of every skill, agent and command (bodies load only when invoked). Commands
marked `disable-model-invocation: true` are not listed to the model at all, so
they're excluded from the total. Tokens are estimated as chars/4 -- a rough
figure for comparison over time, not a billing number.

Scope and accuracy (measured with `/context` on 2026-10-15): this counts only
what THIS repo contributes. Plugin and built-in skills, MCP tools and the
system prompt are not counted. chars/4 also undercounts: the real
harness-owned load was ~3.1k tokens against this script's ~2.2k estimate.
Use the number as a regression guard on the harness's own files; use
`/context` for what a session actually carries.

Do not read the "Skills" row as something plugins can shrink. The skill listing
has a fixed budget (1% of the context window; descriptions of the least-used
skills are shortened when it overflows). Disabling four plugins (31 skills)
changed Skills from 9.9k to 9.2k and left the total at 23.9k, because other
skills' descriptions grew to fill the freed budget. The levers are
`skillListingBudgetFraction` and `skillOverrides`, not plugin count.

Usage: context_budget.py [--json]
"""
import glob
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHARS_PER_TOKEN = 4


def frontmatter(path):
    with open(path, errors="ignore") as f:
        m = re.match(r"---\n(.*?)\n---", f.read(), re.S)
    return m.group(1) if m else ""


def description_len(fm):
    m = re.search(r"^description:\s*(.*)$", fm, re.M)
    return len(m.group(1).strip()) if m else 0


def measure(root=ROOT):
    items = []
    for kind, pattern in (
        ("skill", "skills/*/SKILL.md"),
        ("agent", "agents/*.md"),
        ("command", "commands/*.md"),
    ):
        for path in sorted(glob.glob(os.path.join(root, pattern))):
            fm = frontmatter(path)
            hidden = bool(re.search(r"^disable-model-invocation:\s*true", fm, re.M))
            items.append({
                "kind": kind,
                "name": os.path.relpath(path, root),
                "description_chars": description_len(fm),
                "listed": not hidden,
            })
    claude_md = os.path.join(root, "CLAUDE.md")
    claude_md_bytes = os.path.getsize(claude_md) if os.path.isfile(claude_md) else 0
    listed_chars = sum(i["description_chars"] for i in items if i["listed"])
    return {
        "claude_md_bytes": claude_md_bytes,
        "listed_description_chars": listed_chars,
        "items": items,
        "est_tokens_always_loaded": (claude_md_bytes + listed_chars) // CHARS_PER_TOKEN,
    }


def main():
    report = measure()
    if "--json" in sys.argv:
        print(json.dumps(report, indent=2))
        return 0
    print(f"{'kind':8} {'desc chars':>10}  listed  name")
    for i in report["items"]:
        print(f"{i['kind']:8} {i['description_chars']:>10}  {'yes' if i['listed'] else 'no ':6}  {i['name']}")
    print(f"\numbrella CLAUDE.md: {report['claude_md_bytes']} bytes")
    print(f"listed descriptions: {report['listed_description_chars']} chars")
    print(f"~{report['est_tokens_always_loaded']} tokens (chars/4 estimate, harness-owned files only; "
          f"/context shows the real total, ~40% higher in the 2026-10-15 measurement)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
