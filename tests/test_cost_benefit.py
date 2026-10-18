import json
import os
from datetime import datetime, timedelta, timezone

import context_snapshot as cs
import cost_benefit as cb
import generate_atlas as ga
import session_start
from gate_lib import data_dir

CONTEXT_SAMPLE = """## Context Usage

**Model:** claude-sonnet-5-5
**Tokens:** 24.7k / 1m (2%)

### Estimated usage by category

| Category | Tokens | Percentage |
|----------|--------|------------|
| System prompt | 2.8k | 0.3% |
| System tools | 10.2k | 1.0% |
| MCP tools | 635 | 0.1% |
| MCP server instructions | 717 | 0.1% |
| Custom agents | 295 | 0.0% |
| Memory files | 865 | 0.1% |
| Skills | 9.2k | 0.9% |
| Free space | 942.3k | 94.2% |

### Custom Agents

| Agent type | Source | Tokens |
|------------|--------|--------|
| helper-one | User | 93 |
| helper-two | User | 202 |

### Memory Files

| Type | Path | Tokens |
|------|------|--------|
| Project | {umbrella} | 865 |

### Skills

| Skill | Source | Tokens |
|-------|--------|--------|
| my-skill | User | ~150 |
| my-command | User | ~50 |
| other:plugin-skill | Plugin (other) | ~100 |
"""


def compare(cells_by_variant, runs=1):
    return {"schema": 1, "project": "demo", "commit": "abc1234", "runs_per_cell": runs, "notes": ["a confound"], "cells": cells_by_variant}


def cell(in_out, orient=None, wall=10, cache=100, cost=0.1, turns=5):
    return {"wall_s": wall, "first_edit_s": 5, "in_out": in_out, "cache_read": cache, "cost_usd": cost, "turns": turns,
            "orient_old": orient, "orient_new": orient, "ran_tests": True}


class TestNoiseRule:
    def test_within_noise_when_change_is_smaller_than_control_drift_or_ten_percent(self):
        assert cb.label_delta(100, 130, 120)["verdict"] == "within noise"      # control drifted 30%
        assert cb.label_delta(100, 100, 108)["verdict"] == "within noise"      # under the 10% floor
        assert cb.label_delta(100, 100, 92)["verdict"] == "within noise"

    def test_beyond_noise_when_change_exceeds_both(self):
        r = cb.label_delta(100, 105, 140)
        assert r["verdict"] == "beyond noise" and round(r["rel_after"], 2) == 0.40

    def test_zero_baseline_is_not_applicable(self):
        assert cb.label_delta(0, 5, 5)["verdict"] == "n/a"


class TestDeltaTable:
    def _cells(self, deltas, base=100):
        tasks = ["T1", "T2", "T3", "T4", "T5"]
        before = {t: cell(base) for t in tasks}
        control = {t: cell(base) for t in tasks}
        after = {t: cell(base + d) for t, d in zip(tasks, deltas)}
        return {"before": before, "control": control, "after": after}

    def test_one_task_driving_the_total_is_flagged(self):
        rows = {r["key"]: r for r in cb.delta_table(compare(self._cells([60, 0, 0, 0, 0])))}
        r = rows["in_out"]
        assert r["verdict"] == "beyond noise" and r["concentrated"] is True and r["n_tasks"] == 5

    def test_a_spread_out_change_is_not_flagged_as_one_task(self):
        rows = {r["key"]: r for r in cb.delta_table(compare(self._cells([20, 20, 20, 20, 20])))}
        assert rows["in_out"]["verdict"] == "beyond noise" and rows["in_out"]["concentrated"] is False

    def test_orient_only_counts_tasks_that_edit(self):
        cells = {v: {"T1": cell(10, orient=2), "T2": cell(10, orient=None), "T3": cell(10, orient=4)} for v in ("before", "control", "after")}
        rows = {r["key"]: r for r in cb.delta_table(compare(cells))}
        assert rows["orient_new"]["n_tasks"] == 2 and rows["orient_new"]["totals"]["before"] == 6

    def test_reading_says_benefit_not_demonstrated_when_everything_is_noise(self):
        rows = cb.delta_table(compare(self._cells([1, 0, 0, 0, 0])))
        text = " ".join(cb.reading(rows, None, 0, 1, 5))
        assert "not demonstrated" in text and "no real-session rows yet" in text

    def test_reading_never_claims_a_result_from_one_run_per_cell(self):
        rows = cb.delta_table(compare(self._cells([20, 20, 20, 20, 20])))
        text = " ".join(cb.reading(rows, None, 0, 1, 5))
        assert "lead to test, not a result" in text and "not demonstrated" not in text


class TestOrientRows:
    def test_reads_new_rows_and_ignores_legacy_rows_and_measurement_logs(self):
        d = os.path.join(data_dir(), "cost"); os.makedirs(d, exist_ok=True)
        open(os.path.join(d, "alpha.md"), "w").write(
            "| Date | Session ID | Duration | Est. tokens (in/out) | Cache read |\n|--|--|--|--|--|\n"
            "| 2026-09-01 | old00000 | 1m | 10/10 | 99999 |\n"                       # legacy: 5 cells, last is cache read
            "| 2026-10-10 | aaaa1111 | 2m | 10/10 | feat/x | 7 |\n"
            "| 2026-10-12 | bbbb2222 | 3m | 10/10 | main | - |\n")                    # no edit: '-' is skipped
        open(os.path.join(d, "zz-baseline-alpha-T1.md"), "w").write("| 2026-10-15 | cccc3333 | 1m | 1/1 | - | 3 |\n")
        rows = cb.real_orient_rows()
        assert [(r["project"], r["orient"]) for r in rows] == [("alpha", 7)]


class TestInjectedContext:
    def test_estimates_include_imports_and_memory_index(self, tmp_path):
        root = tmp_path / "Projects"; proj = root / "demo"; proj.mkdir(parents=True)
        (proj / "CLAUDE.md").write_bytes(b"@AGENTS.md\n" + b"x" * 389)        # 400 bytes -> 100 tokens
        (proj / "AGENTS.md").write_bytes(b"y" * 4000)                          # imported -> 1000 tokens
        out = cb.injected_context(str(root), ["demo"], ga.HARNESS_ROOT)
        p = out["projects"][0]
        assert p["claude_md"] == 100 and p["imports"] == 1000 and p["memory_index"] == 0
        assert out["umbrella_est"] > 0 and out["listing_est"] > 0

    def test_measuring_the_hook_does_not_consume_the_budget_alert(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CLAUDE_HARNESS_PROJECTS_ROOT", str(tmp_path))
        proj = tmp_path / "demo"; (proj / "docs").mkdir(parents=True); (proj / ".harness").mkdir()
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        (proj / "docs" / "COST_LOG.md").write_text("| %s | s1 | 1m | 500/500 |\n" % today)
        (proj / ".harness" / "budget.json").write_text(json.dumps({"monthly_token_budget": 100}))
        lines = session_start.collect_lines(str(proj), record_alerts=False)
        assert any("token budget ALERT" in l for l in lines)
        assert "last_alerted" not in json.loads((proj / ".harness" / "budget.json").read_text())
        cb.injected_context(str(tmp_path), ["demo"], ga.HARNESS_ROOT)           # the panel's own measurement
        assert "last_alerted" not in json.loads((proj / ".harness" / "budget.json").read_text())
        session_start.collect_lines(str(proj))                                   # the real hook records it
        assert "last_alerted" in json.loads((proj / ".harness" / "budget.json").read_text())


class TestContextSnapshot:
    def test_number_parsing(self):
        assert [cs._num(x) for x in ("23.9k", "865", "~150", "< 20", "1m", "1,200")] == [23900, 865, 150, 20, 1000000, 1200]

    def test_parse_and_harness_share(self):
        parsed = cs.parse_context(CONTEXT_SAMPLE.replace("{umbrella}", "/p/Projects/CLAUDE.md"))
        assert parsed["total_tokens"] == 24700 and parsed["categories"]["Skills"] == 9200
        share = cs.harness_share(parsed, ["my-skill", "my-command"], "/p/Projects/CLAUDE.md")
        assert share["umbrella_claude_md"] == 865 and share["skills_and_commands"] == 200 and share["agents"] == 295
        assert share["harness_total"] == 1360 and share["harness_share_pct"] == 5.5

    def test_capture_returns_none_without_claude(self, monkeypatch):
        monkeypatch.setattr(cs.shutil, "which", lambda _b: None)
        assert cs.capture(["x"], ga.HARNESS_ROOT) is None

    def _probe_env(self, tmp_path, monkeypatch):
        """A projects root, a fixed 'mkdtemp' result, a fake claude, and the decoys a too-broad cleanup would hit."""
        root = tmp_path / "Projects"; root.mkdir()
        monkeypatch.setenv("CLAUDE_HARNESS_PROJECTS_ROOT", str(root))
        monkeypatch.setattr(cs.shutil, "which", lambda _b: "/usr/bin/claude")
        probe = root / (cs.PROBE_PREFIX + "FIXED"); probe.mkdir()
        monkeypatch.setattr(cs.tempfile, "mkdtemp", lambda prefix, dir: str(probe))
        projects = os.path.join(cs.claude_home(), "projects")
        enc = cs._enc(str(probe))
        return root, probe, projects, enc

    def _fake_claude(self, monkeypatch, probe, projects, enc, session="abcd1234-1111-2222"):
        class R:
            def __init__(self, out): self.stdout = out

        def fake_run(cmd, **kw):
            if "--version" in cmd:
                return R("2.1.300 (Claude Code)\n")
            assert kw["cwd"] == str(probe)
            os.makedirs(os.path.join(projects, enc, "memory"), exist_ok=True)           # what Claude Code leaves
            open(os.path.join(projects, enc, session + ".jsonl"), "w").write("{}")
            cost = os.path.join(data_dir(), "cost", os.path.basename(str(probe)) + ".md")  # what the SessionEnd hook leaves
            os.makedirs(os.path.dirname(cost), exist_ok=True)
            with open(cost, "a") as f:
                f.write("| 2026-10-16 | %s | 0m01s | 0/0 | - | - |\n" % session[:8])
            return R(CONTEXT_SAMPLE.replace("{umbrella}", str(probe.parent / "CLAUDE.md")))
        monkeypatch.setattr(cs.subprocess, "run", fake_run)

    def test_capture_leaves_no_trace_behind(self, tmp_path, monkeypatch):
        root, probe, projects, enc = self._probe_env(tmp_path, monkeypatch)
        self._fake_claude(monkeypatch, probe, projects, enc)
        snap = cs.capture(["my-skill"], ga.HARNESS_ROOT)
        assert snap["harness"]["umbrella_claude_md"] == 865 and snap["claude_version"].startswith("2.1.300")
        assert not probe.exists()
        assert not os.path.exists(os.path.join(projects, enc))                           # folder removed once empty
        assert not os.path.exists(os.path.join(data_dir(), "cost", probe.name + ".md"))  # file removed once no rows remain

    def test_other_sessions_and_projects_survive_a_capture(self, tmp_path, monkeypatch):
        root, probe, projects, enc = self._probe_env(tmp_path, monkeypatch)
        # 1. a user directory that has the OLD fixed probe name: must never be touched
        old_named = root / "zz-context-probe"; old_named.mkdir(); (old_named / "mine.txt").write_text("keep")
        # 2. another project's transcripts
        other = os.path.join(projects, "-some-other-project"); os.makedirs(other)
        other_session = os.path.join(other, "9999aaaa-bbbb.jsonl"); open(other_session, "w").write("{}")
        # 3. a FOREIGN session already sitting in the probe's own transcript folder
        os.makedirs(os.path.join(projects, enc))
        foreign = os.path.join(projects, enc, "ffff0000-cccc.jsonl"); open(foreign, "w").write("{}")
        # 4. another project's cost log, and a foreign row inside the probe's cost log
        cost_dir = os.path.join(data_dir(), "cost"); os.makedirs(cost_dir)
        other_cost = os.path.join(cost_dir, "alpha.md"); open(other_cost, "w").write("| 2026-10-01 | 12345678 | 1m | 5/5 | main | 2 |\n")
        probe_cost = os.path.join(cost_dir, probe.name + ".md")
        open(probe_cost, "w").write("| 2026-10-02 | ffff0000 | 1m | 7/7 | main | 4 |\n")

        self._fake_claude(monkeypatch, probe, projects, enc)
        assert cs.capture(["my-skill"], ga.HARNESS_ROOT) is not None

        assert not probe.exists()                                                         # the probe's own directory is gone
        assert (old_named / "mine.txt").read_text() == "keep"                             # 1
        assert os.path.isfile(other_session)                                              # 2
        assert os.path.isfile(foreign) and os.path.isdir(os.path.join(projects, enc))     # 3: kept, so the folder is kept too
        assert not os.path.exists(os.path.join(projects, enc, "abcd1234-1111-2222.jsonl"))   # the probe's own session is gone
        assert not os.path.exists(os.path.join(projects, enc, "memory"))
        assert os.path.isfile(other_cost)                                                 # 4
        left = open(probe_cost).read()
        assert "ffff0000" in left and "abcd1234" not in left                              # only the probe's row was removed

    def test_cleanup_refuses_paths_outside_where_the_probe_lives(self, tmp_path, monkeypatch):
        root = tmp_path / "Projects"; root.mkdir()
        monkeypatch.setenv("CLAUDE_HARNESS_PROJECTS_ROOT", str(root))
        outside = tmp_path / (cs.PROBE_PREFIX + "outside"); outside.mkdir(); (outside / "f").write_text("x")
        not_prefixed = root / "my-real-project"; not_prefixed.mkdir()
        projects = os.path.join(cs.claude_home(), "projects"); os.makedirs(os.path.join(projects, "-real"))
        cs._cleanup_probe(str(outside), os.path.join(projects, "-real"), set())          # outside the projects root
        cs._cleanup_probe(str(not_prefixed), os.path.join(projects, "-real"), set())     # wrong name
        assert (outside / "f").exists() and not_prefixed.exists()
        assert os.path.isdir(os.path.join(projects, "-real"))                             # folder name does not match the probe's

    def test_save_and_age(self):
        snap = {"schema": 1, "captured_at": (datetime.now(timezone.utc) - timedelta(hours=7)).isoformat(timespec="seconds"),
                "harness": {}, "categories": {}, "total_tokens": 1}
        cs.save(snap)
        got = cs.load_latest()
        assert got["captured_at"] == snap["captured_at"] and 6.9 < cs.age_hours(got) < 7.2
        assert os.path.isfile(os.path.join(os.path.dirname(cs.snapshot_path()), "context-history.jsonl"))


class TestPanelInThePage:
    def _write_compare(self, deltas, **extra):
        tasks = ["T1", "T2", "T3", "T4", "T5"]
        cells = {"before": {t: cell(100, orient=2) for t in tasks}, "control": {t: cell(100, orient=2) for t in tasks},
                 "after": {t: cell(100 + d, orient=2) for t, d in zip(tasks, deltas)}}
        d = os.path.join(data_dir(), "baseline"); os.makedirs(d, exist_ok=True)
        json.dump({**compare(cells), **extra}, open(os.path.join(d, "example-compare.json"), "w"))

    def _page(self, git_repo, tmp_path, **kw):
        out = tmp_path / "atlas.html"
        return open(ga.generate(output_path=str(out), focus_cwd=str(git_repo), **kw)).read()

    def test_panel_present_with_title_link_n_and_noise_labels(self, git_repo, tmp_path):
        self._write_compare([60, 0, 0, 0, 0])
        cs.save({"schema": 1, "captured_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "claude_version": "2.1.300 (Claude Code)",
                 "total_tokens": 24700, "categories": {"Skills": 9200, "System prompt": 2800, "System tools": 10200, "MCP tools": 635, "MCP server instructions": 717},
                 "harness": {"umbrella_claude_md": 865, "skills_and_commands": 1940, "agents": 295, "harness_total": 3100,
                             "session_total": 24700, "harness_share_pct": 12.6}})
        page = self._page(git_repo, tmp_path)
        assert "Harness cost vs measured benefit" in page and "hm-costbenefit" in page
        assert "n = 5 tasks, 1 run per cell" in page
        assert "beyond noise" in page and "one task drives it" in page and "within noise" in page
        assert "12.6%" in page and "24,700" in page
        assert "No real-session rows yet" in page

    def test_baseline_figures_are_labelled_hand_entered_unless_a_script_generated_them(self, git_repo, tmp_path):
        self._write_compare([60, 0, 0, 0, 0], provenance="Entered by hand.", cross_checked=["in_out"])
        page = self._page(git_repo, tmp_path)
        assert "Source: hand-entered from the pilot." in page and "Entered by hand." in page
        assert "the figures are hand-entered from the pilot" in page            # the computed summary says it too
        assert "cross-checked" in page and "hand-entered only" in page          # per metric: only in_out was cross-checked
        self._write_compare([60, 0, 0, 0, 0], generated_by="build_baseline.py", provenance="Built from the cost rows.")
        page = self._page(git_repo, tmp_path)
        assert "Source: generated by build_baseline.py." in page and "Source: hand-entered" not in page
        assert "hand-entered only" not in page and "the figures are hand-entered" not in page

    def test_provenance_defaults_to_hand_entered(self):
        assert cb.provenance(compare({"before": {}}))["hand_entered"] is True
        assert cb.provenance({**compare({}), "generated_by": "x.py"})["hand_entered"] is False
        tasks = ["T1", "T2", "T3"]
        cells = {v: {t: cell(100) for t in tasks} for v in ("before", "control", "after")}
        rows = cb.delta_table(compare(cells))
        assert "hand-entered" in " ".join(cb.reading(rows, None, 0, 1, 3, hand_entered=True))
        assert "hand-entered" not in " ".join(cb.reading(rows, None, 0, 1, 3, hand_entered=False))

    def test_panel_says_so_when_there_is_no_baseline_or_snapshot(self, git_repo, tmp_path):
        page = self._page(git_repo, tmp_path)
        assert "Harness cost vs measured benefit" in page
        assert "No baseline comparison recorded" in page and "No /context snapshot yet" in page

    def test_default_generation_never_calls_claude(self, git_repo, tmp_path, monkeypatch):
        def boom(*a, **k):
            raise AssertionError("generate() must not call claude unless refresh_context is set")
        monkeypatch.setattr(ga.context_snapshot, "capture", boom)
        self._page(git_repo, tmp_path)                                           # default: no refresh

    def test_refresh_captures_when_the_snapshot_is_missing_or_old(self, git_repo, tmp_path, monkeypatch):
        fresh = {"schema": 1, "captured_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "claude_version": "x", "total_tokens": 1000,
                 "categories": {}, "harness": {"umbrella_claude_md": 1, "skills_and_commands": 1, "agents": 1, "harness_total": 3,
                                                "session_total": 1000, "harness_share_pct": 0.3}}
        calls = []
        monkeypatch.setattr(ga.context_snapshot, "capture", lambda *a, **k: calls.append(1) or fresh)
        self._page(git_repo, tmp_path, refresh_context=True)
        assert calls == [1] and cs.load_latest()["total_tokens"] == 1000
        self._page(git_repo, tmp_path, refresh_context=True)                     # now fresh: no second capture
        assert calls == [1]


def test_orient_trend_uses_the_latest_row_per_session():
    d = os.path.join(data_dir(), "cost"); os.makedirs(d, exist_ok=True)
    open(os.path.join(d, "gamma.md"), "w").write(
        "| Date | Session ID | Active time | Est. tokens (in/out) | Cache read | Branch | Orient |\n|--|--|--|--|--|--|--|\n"
        "| 2026-10-10 | aaaa1111 | 2m | 10/10 | - | feat/x | 3 |\n"
        "| 2026-10-11 | aaaa1111 | 4m | 20/20 | - | feat/x | 3 |\n"     # same session again: one data point, not two
        "| 2026-10-12 | bbbb2222 | 3m | 10/10 | - | main | 5 |\n")
    rows = [r for r in cb.real_orient_rows() if r["project"] == "gamma"]
    assert [(r["date"], r["orient"]) for r in rows] == [("2026-10-11", 3), ("2026-10-12", 5)]
