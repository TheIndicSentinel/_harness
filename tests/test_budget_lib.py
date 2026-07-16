import os
from datetime import datetime, timezone

import pytest

import budget_lib


def write_cost_log(repo, rows):
    """rows: list of (date_str, tokens_str) e.g. ('2026-07-16', '4000/1000') or ('2026-07-16', 'n/a')"""
    os.makedirs(os.path.join(repo, "docs"), exist_ok=True)
    lines = [
        "# t — Session / Cost Log",
        "",
        "| Date | Session ID | Duration | Est. tokens (in/out) |",
        "|------|-----------|----------|------------------------|",
    ]
    for date, tokens in rows:
        lines.append(f"| {date} | aaaa1111 | 1m00s | {tokens} |")
    with open(os.path.join(repo, "docs", "COST_LOG.md"), "w") as f:
        f.write("\n".join(lines) + "\n")


def today_str():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


class TestBudgetLib:
    def test_no_budget_set_returns_none(self, git_repo):
        assert budget_lib.budget_status(str(git_repo)) is None

    def test_no_cost_log_returns_none_even_with_budget_set(self, git_repo):
        budget_lib.set_monthly_budget(str(git_repo), 10000)
        assert budget_lib.budget_status(str(git_repo)) is None

    def test_set_and_status(self, git_repo):
        write_cost_log(git_repo, [(today_str(), "4000/1000")])
        budget_lib.set_monthly_budget(str(git_repo), 10000)
        used, budget, pct = budget_lib.budget_status(str(git_repo))
        assert used == 5000
        assert budget == 10000
        assert pct == 50

    def test_rejects_non_positive_budget(self, git_repo):
        with pytest.raises(ValueError):
            budget_lib.set_monthly_budget(str(git_repo), 0)
        with pytest.raises(ValueError):
            budget_lib.set_monthly_budget(str(git_repo), -100)

    def test_ignores_na_rows(self, git_repo):
        write_cost_log(git_repo, [(today_str(), "n/a")])
        budget_lib.set_monthly_budget(str(git_repo), 1000)
        used, _, _ = budget_lib.budget_status(str(git_repo))
        assert used == 0

    def test_ignores_rows_from_other_months(self, git_repo):
        write_cost_log(git_repo, [("2020-01-01", "9999/9999"), (today_str(), "1000/1000")])
        budget_lib.set_monthly_budget(str(git_repo), 10000)
        used, _, _ = budget_lib.budget_status(str(git_repo))
        assert used == 2000

    @pytest.mark.parametrize(
        "pct,expected",
        [(30, None), (49, None), (50, 50), (79, 50), (80, 80), (99, 80), (100, 100), (150, 100)],
    )
    def test_alert_threshold_crossed(self, pct, expected):
        assert budget_lib.alert_threshold_crossed(pct) == expected

    def test_malformed_budget_json_treated_as_no_budget(self, git_repo):
        os.makedirs(os.path.join(git_repo, ".harness"), exist_ok=True)
        with open(os.path.join(git_repo, ".harness", "budget.json"), "w") as f:
            f.write("{not valid json")
        assert budget_lib.load_budget(str(git_repo)) == {}
        assert budget_lib.budget_status(str(git_repo)) is None


class TestBudgetSkip:
    def test_not_skipped_by_default(self, git_repo):
        assert budget_lib.is_budget_skipped(str(git_repo)) is False

    def test_mark_skipped(self, git_repo):
        budget_lib.mark_budget_skipped(str(git_repo))
        assert budget_lib.is_budget_skipped(str(git_repo)) is True

    def test_setting_real_budget_clears_skipped(self, git_repo):
        budget_lib.mark_budget_skipped(str(git_repo))
        budget_lib.set_monthly_budget(str(git_repo), 10000)
        assert budget_lib.is_budget_skipped(str(git_repo)) is False

    def test_marking_skipped_clears_real_budget(self, git_repo):
        budget_lib.set_monthly_budget(str(git_repo), 10000)
        budget_lib.mark_budget_skipped(str(git_repo))
        assert budget_lib.load_budget(str(git_repo)).get("monthly_token_budget") is None


class TestAlertDeduplication:
    def test_first_crossing_should_alert(self, git_repo):
        assert budget_lib.should_alert(str(git_repo), 80) is True

    def test_same_threshold_same_month_suppressed(self, git_repo):
        budget_lib.record_alert(str(git_repo), 80)
        assert budget_lib.should_alert(str(git_repo), 80) is False

    def test_lower_threshold_still_suppressed_after_higher_recorded(self, git_repo):
        """If 100% already alerted, a re-check landing on 80% (can't really
        happen since usage doesn't decrease, but the rule should still hold)
        must not re-fire below what's already been surfaced."""
        budget_lib.record_alert(str(git_repo), 100)
        assert budget_lib.should_alert(str(git_repo), 80) is False

    def test_higher_threshold_after_lower_still_fires(self, git_repo):
        budget_lib.record_alert(str(git_repo), 80)
        assert budget_lib.should_alert(str(git_repo), 100) is True

    def test_new_month_resets(self, git_repo):
        data = budget_lib.load_budget(str(git_repo))
        data["last_alerted"] = {"month": "2020-01", "threshold": 100}
        path = budget_lib.budget_path(str(git_repo))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        import json as _json
        with open(path, "w") as f:
            _json.dump(data, f)
        assert budget_lib.should_alert(str(git_repo), 50) is True
