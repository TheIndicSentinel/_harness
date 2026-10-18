#!/usr/bin/env python3
"""Read, migrate and total the per-project cost log (~/.claude/harness/cost/<project>.md).

One column set for header and rows:

  | Date | Session ID | Active time | Est. tokens (in/out) | Cache read | Branch | Orient |

Older rows were written in two other shapes under the same file header, so a log could
hold three row shapes at once. They are recognised by cell count:
  5 cells  Date, Session ID, Duration, tokens, Cache read          (original format)
  6 cells  Date, Session ID, Active time, tokens, Branch, Orient   (until this change)
  7 cells  the current format
Migration rewrites every row in the 7-cell form and loses nothing: the original format's
wall-clock duration stays in "Active time" marked `wall` (it is not comparable with the
idle-gap-free active time), its cache-read value keeps its column, and fields an older
format never had are `-`. A copy of the file as it was is kept under cost/.pre-migration/.

A session that ends more than once (resumed, or logged per turn by the old Stop-wired
hook) leaves several rows, each cumulative for the whole transcript. Anything that totals the
log must therefore use only the latest row per session ID: latest_per_session(). The
session ID is an 8-character prefix; rows with the ID "unknown" are never merged.
"""
import os
import re
import tempfile
from datetime import datetime, timezone
from typing import Dict, List, Optional

COLUMNS = ("Date", "Session ID", "Active time", "Est. tokens (in/out)", "Cache read", "Branch", "Orient")
HEADER = "| " + " | ".join(COLUMNS) + " |"
SEP = "|" + "|".join("-" * (len(c) + 2) for c in COLUMNS) + "|"
NOTE = ("Migrated to the 7-column format: rows from the original format show wall-clock duration "
        "marked `wall` in Active time; `-` means that format did not record the field.")

_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_TOKENS = re.compile(r"^(\d+)\s*/\s*(\d+)$")


def _cells(line: str) -> List[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def parse_row(line: str) -> Optional[dict]:
    """A dict for a table row, None for anything else (header, separator, prose, blank)."""
    line = line.strip()
    if not line.startswith("| 20"):
        return None
    c = _cells(line)
    if len(c) < 4 or not _DATE.match(c[0]):
        return None
    row = {"date": c[0], "session": c[1], "active": c[2], "tokens": c[3],
           "cache_read": "-", "branch": "-", "orient": "-", "legacy_duration": False, "in": None, "out": None}
    if len(c) == 5:
        row["cache_read"] = c[4]
        row["legacy_duration"] = True
    elif len(c) == 6:
        row["branch"], row["orient"] = c[4], c[5]
    elif len(c) >= 7:
        row["cache_read"], row["branch"], row["orient"] = c[4], c[5], c[6]
    m = _TOKENS.match(c[3])
    if m:
        row["in"], row["out"] = int(m.group(1)), int(m.group(2))
    return row


def format_row(r: dict) -> str:
    active = r["active"]
    if r["legacy_duration"] and active not in ("n/a", "-") and not active.endswith(" wall"):
        active += " wall"
    return "| %s | %s | %s | %s | %s | %s | %s |" % (r["date"], r["session"], active, r["tokens"],
                                                   r["cache_read"], r["branch"], r["orient"])


def read_rows(path: str) -> List[dict]:
    try:
        with open(path, errors="replace") as f:
            return [r for r in (parse_row(l) for l in f) if r]
    except OSError:
        return []


def latest_per_session(rows: List[dict]) -> List[dict]:
    """The last row for each session ID, in file order of those last rows."""
    last: Dict[str, int] = {}
    for i, r in enumerate(rows):
        if r["session"] != "unknown":
            last[r["session"]] = i
    keep = {i for i in last.values()} | {i for i, r in enumerate(rows) if r["session"] == "unknown"}
    return [r for i, r in enumerate(rows) if i in keep]


def migrate_text(text: str) -> str:
    """The same log in the 7-column form; text already in that form comes back unchanged."""
    out: List[str] = []
    header_done = False
    changed = False
    for line in text.splitlines():
        s = line.strip()
        is_header = s.startswith("| Date") or re.match(r"^\|[-\s|]+$", s) is not None
        row = parse_row(line)
        if is_header or row:
            if not header_done:
                if NOTE not in text and any(
                        (parse_row(l) or {}).get("legacy_duration") for l in text.splitlines()):
                    out.append(NOTE + "\n")
                out += [HEADER, SEP]
                header_done = True
            if is_header:
                continue
            new = format_row(row)
            out.append(new)
            continue
        out.append(line)
    result = "\n".join(out) + ("\n" if text.endswith("\n") or out else "")
    return result if result != text else text


def ensure_canonical(path: str) -> bool:
    """Migrate the file in place if it is not in the 7-column form. True if it was rewritten."""
    try:
        with open(path, errors="replace") as f:
            text = f.read()
    except OSError:
        return False
    new = migrate_text(text)
    if new == text:
        return False
    backup_dir = os.path.join(os.path.dirname(path), ".pre-migration")
    os.makedirs(backup_dir, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    with open(os.path.join(backup_dir, "%s.%s" % (os.path.basename(path), stamp)), "w") as f:
        f.write(text)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), prefix=".cost-", suffix=".tmp")
    with os.fdopen(fd, "w") as f:
        f.write(new)
    os.replace(tmp, path)
    return True
