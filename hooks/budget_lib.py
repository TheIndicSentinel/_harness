#!/usr/bin/env python3
"""Shared helpers for <project>/.harness/budget.json — an optional, best-effort
monthly token budget check layered on top of session_log.py's COST_LOG.md data.

This is NOT authoritative accounting — COST_LOG.md itself is a best-effort,
transcript-parsed estimate (see docs/OTEL.md for the full ranking of sources
by trust; nothing this harness touches directly is authoritative billing).
It exists to turn "use subagents, keep context lean" from a purely
behavioral habit into a number that can actually be threshold-alerted on.
Absence of a budget is not an error: most projects won't set one, and
that's fine — budget_status() returns None rather than a false "0% used".
"""
import json
import os
import re
from datetime import datetime, timezone
from typing import Optional, Tuple

ALERT_THRESHOLDS = [100, 80, 50]

_ROW_RE = re.compile(
    r"^\|\s*(\d{4}-\d{2}-\d{2})\s*\|[^|]*\|[^|]*\|\s*(\d+)\s*/\s*(\d+)\s*\|"
)


def budget_path(project_root: str) -> str:
    return os.path.join(project_root, ".harness", "budget.json")


def load_budget(project_root: str) -> dict:
    path = budget_path(project_root)
    if not os.path.isfile(path):
        return {}
    try:
        with open(path) as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def _save_budget(project_root: str, data: dict) -> dict:
    path = budget_path(project_root)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")
    return data


def set_monthly_budget(project_root: str, tokens: int) -> dict:
    if tokens <= 0:
        raise ValueError("tokens must be a positive integer")
    data = load_budget(project_root)
    data["monthly_token_budget"] = tokens
    data.pop("skipped", None)  # setting a real budget supersedes "skipped"
    return _save_budget(project_root, data)


def mark_budget_skipped(project_root: str) -> dict:
    """Record an explicit 'no budget, on purpose' decision -- distinct from
    never having set one, so status reporting can tell "haven't decided yet"
    from "decided not to bother"."""
    data = load_budget(project_root)
    data["skipped"] = True
    data.pop("monthly_token_budget", None)
    return _save_budget(project_root, data)


def is_budget_skipped(project_root: str) -> bool:
    return bool(load_budget(project_root).get("skipped"))


def tokens_used_this_month(project_root: str) -> Optional[int]:
    """Sum input+output tokens from COST_LOG.md rows dated in the current
    UTC calendar month. None means "no COST_LOG.md yet", distinct from 0
    (a log that exists but has no parseable rows this month)."""
    log_path = os.path.join(project_root, "docs", "COST_LOG.md")
    if not os.path.isfile(log_path):
        return None
    this_month = datetime.now(timezone.utc).strftime("%Y-%m")
    total = 0
    with open(log_path) as f:
        for line in f:
            m = _ROW_RE.match(line.strip())
            if not m:
                continue
            date, in_tok, out_tok = m.groups()
            if date.startswith(this_month):
                total += int(in_tok) + int(out_tok)
    return total


def budget_status(project_root: str) -> Optional[Tuple[int, int, int]]:
    """(used, budget, pct), or None if no budget is set or no COST_LOG.md exists."""
    data = load_budget(project_root)
    budget = data.get("monthly_token_budget")
    if not isinstance(budget, int) or budget <= 0:
        return None
    used = tokens_used_this_month(project_root)
    if used is None:
        return None
    pct = round(100 * used / budget)
    return used, budget, pct


def alert_threshold_crossed(pct: int) -> Optional[int]:
    """Highest of [100, 80, 50] that pct has crossed, or None below 50."""
    for t in ALERT_THRESHOLDS:
        if pct >= t:
            return t
    return None


def _current_month() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


def should_alert(project_root: str, threshold: int) -> bool:
    """True if this threshold hasn't already been alerted on this calendar
    month -- a SessionStart hook fires every session, and re-printing the
    same crossing every time is noise, not signal. A new month always resets
    (last month's alert doesn't suppress this month's first crossing)."""
    data = load_budget(project_root)
    last = data.get("last_alerted")
    if not isinstance(last, dict):
        return True
    if last.get("month") != _current_month():
        return True
    return threshold > last.get("threshold", 0)


def record_alert(project_root: str, threshold: int) -> None:
    data = load_budget(project_root)
    data["last_alerted"] = {"month": _current_month(), "threshold": threshold}
    _save_budget(project_root, data)
