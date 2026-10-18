import json
import os

import generate_atlas as ga
import session_data as sd
from gate_lib import data_dir


def msg(mid, tin, tout, cr, ts="2026-10-10T10:00:00Z", cwd="/p/Projects/alpha", branch="feat/a", cc=0):
    return {"timestamp": ts, "cwd": cwd, "gitBranch": branch,
            "message": {"id": mid, "role": "assistant",
                        "usage": {"input_tokens": tin, "output_tokens": tout,
                                  "cache_creation_input_tokens": cc, "cache_read_input_tokens": cr}}}


def write_session(home, enc, sid, entries, sub=False):
    d = os.path.join(home, "projects", enc) if not sub else os.path.join(home, "projects", enc, sid, "subagents")
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, (sid if not sub else "agent-1") + ".jsonl")
    with open(path, "w") as f:
        for e in entries:
            f.write(json.dumps(e) + "\n")
    return path


ROOT = "/p/Projects"
NAMES = ["alpha", "beta"]


class TestProjectFor:
    def test_mapping(self):
        pf = lambda c: sd.project_for(c, ROOT, NAMES)
        assert pf("/p/Projects/alpha") == "alpha"
        assert pf("/p/Projects/alpha/src/deep") == "alpha"
        assert pf("/p/Projects/_harness") == "harness"
        assert pf("/p/Projects/zz-baseline-alpha-T1") == "baseline"
        assert pf("/p/Projects/gone-project") == "other"
        assert pf("/old/place/beta") == "beta"          # a project's former location
        assert pf("/tmp/scratch") == "other"
        assert pf(None) == "other"


class TestScan:
    def test_tasks_split_by_branch_and_dedupe_message_ids(self, tmp_path):
        home = str(tmp_path / "home")
        write_session(home, "-p-Projects-alpha", "s1", [
            msg("m1", 100, 10, 1000, branch="feat/a", cc=50),
            msg("m1", 100, 20, 1000, branch="feat/a", cc=50),   # same id again: last record wins
            msg("m2", 200, 30, 2000, branch="feat/b", ts="2026-10-11T09:00:00Z"),
        ])
        rows = sd.scan(home, ROOT, NAMES)
        S = sd.summarize(rows)["alpha"]
        assert S["tasks"]["feat/a"]["tin"] == 150 and S["tasks"]["feat/a"]["tout"] == 20     # not 300/30
        assert S["tasks"]["feat/b"]["tin"] == 200 and S["tasks"]["feat/b"]["cr"] == 2000
        assert S["tin"] == 350 and S["tout"] == 50 and len(S["sessions"]) == 1
        assert S["first"] == "2026-10-10" and S["last"] == "2026-10-11"

    def test_subagent_tokens_are_kept_apart(self, tmp_path):
        home = str(tmp_path / "home")
        write_session(home, "-p-Projects-alpha", "s1", [msg("m1", 100, 10, 0)])
        write_session(home, "-p-Projects-alpha", "s1", [msg("a1", 7, 3, 0)], sub=True)
        S = sd.summarize(sd.scan(home, ROOT, NAMES))["alpha"]
        assert (S["tin"], S["tout"]) == (100, 10)
        assert (S["sub_tin"], S["sub_tout"]) == (7, 3)

    def test_unknown_cwd_goes_to_other_and_detached_head_is_labelled(self, tmp_path):
        home = str(tmp_path / "home")
        write_session(home, "-x", "s1", [msg("m1", 5, 1, 0, cwd="/tmp/scratch", branch="HEAD")])
        S = sd.summarize(sd.scan(home, ROOT, NAMES))
        assert "other" in S and "(detached)" in S["other"]["tasks"]

    def test_cache_is_used_and_invalidated_when_the_file_changes(self, tmp_path):
        home = str(tmp_path / "home"); cache = str(tmp_path / "cache" / "s.json")
        path = write_session(home, "-p-Projects-alpha", "s1", [msg("m1", 100, 10, 0)])
        first = sd.scan(home, ROOT, NAMES, cache)
        assert os.path.isfile(cache)
        assert sd.scan(home, ROOT, NAMES, cache) == first
        with open(path, "a") as f:
            f.write(json.dumps(msg("m2", 50, 5, 0)) + "\n")
        S = sd.summarize(sd.scan(home, ROOT, NAMES, cache))["alpha"]
        assert (S["tin"], S["tout"]) == (150, 15)

    def test_no_message_text_is_read_into_the_result(self, tmp_path):
        home = str(tmp_path / "home")
        secret = "SECRET-PROMPT-TEXT-9d3f"
        entries = [{"type": "user", "cwd": "/p/Projects/alpha", "message": {"role": "user", "content": secret}},
                   msg("m1", 1, 1, 0)]
        write_session(home, "-p-Projects-alpha", "s1", entries)
        rows = sd.scan(home, ROOT, NAMES)
        assert secret not in json.dumps(rows)


class TestFormat:
    def test_fmt(self):
        assert [sd.fmt(n) for n in (7, 1234, 45678, 1234567)] == ["7", "1.2k", "46k", "1.23M"]


class TestAtlasPage:
    def _home_with_work(self, git_repo):
        home = os.environ["CLAUDE_CONFIG_DIR"]
        write_session(home, "-enc-proj", "sess1", [
            msg("m1", 4000, 500, 90000, cwd=str(git_repo), branch="feat/my-task", ts="2026-10-12T08:00:00Z"),
            msg("m2", 2000, 300, 50000, cwd=str(git_repo), branch="main", ts="2026-10-13T08:00:00Z"),
        ])

    def test_page_has_work_and_tokens_with_per_task_numbers(self, git_repo, tmp_path):
        self._home_with_work(git_repo)
        out = tmp_path / "atlas.html"
        content = open(ga.generate(output_path=str(out), focus_cwd=str(git_repo))).read()
        assert "Work &amp; Tokens" in content or "Work & Tokens" in content
        assert "feat/my-task" in content
        assert "4.0k" in content            # the task's "in"
        assert "SECRET" not in content
        assert "generated %s" not in content          # the banner timestamp was once left as a literal %s
        assert "LIVE — generated 20" in content

    def test_fleet_overview_lists_projects_and_totals(self, git_repo, tmp_path):
        self._home_with_work(git_repo)
        html = ga.fleet_overview_html(str(git_repo.parent), sd.summarize(sd.scan(
            os.environ["CLAUDE_CONFIG_DIR"], str(git_repo.parent), ["proj"])), ["proj"])
        assert "proj" in html and "Total" in html and "Tokens by project" in html

    def test_baseline_pilot_category_from_cost_rows(self, git_repo):
        d = os.path.join(data_dir(), "baseline"); os.makedirs(d, exist_ok=True)
        hdr = "| Date | Session ID | Active time | Est. tokens (in/out) | Branch | Orient |\n|--|--|--|--|--|--|\n"
        open(os.path.join(d, "zz-baseline-proj-T1.md"), "w").write(hdr + "| 2026-10-15 | aaaa1111 | 0m11s | 26659/1238 | - | 2 |\n")
        open(os.path.join(d, "zz-baseline-proj-after-T1.md"), "w").write(hdr + "| 2026-10-16 | bbbb2222 | 0m41s | 40000/2000 | - | 3 |\n")
        ga.NOW = "test"
        cat, detail = ga.baseline_category("proj", lambda b: "%s-proj" % b)
        assert cat["label"] == "Baseline Pilot" and cat["badgeTxt"] == "1x2"
        text = detail["baseline-proj"]["html"]
        assert "28k" in text and "42k" in text and "not comparable" in text

    def test_open_flag_opens_the_page(self, git_repo, tmp_path, monkeypatch):
        opened = []
        monkeypatch.setattr(ga.webbrowser, "open", lambda url: opened.append(url))
        out = tmp_path / "a.html"
        monkeypatch.setattr(ga.sys, "argv", ["generate_atlas.py", str(out), "--open"])
        ga.main()
        assert opened == ["file://" + str(out)]
        monkeypatch.setattr(ga.sys, "argv", ["generate_atlas.py", str(out)])
        ga.main()
        assert len(opened) == 1             # without --open nothing is opened


def _row(project, sid, day, tin, tout, cr, msgs, sub=False):
    return {"project": project, "branch": "b", "day": day, "sid": sid, "sub": sub, "tin": tin, "tout": tout, "cr": cr, "msgs": msgs}


def test_weekly_window_definitions_and_subagents_excluded():
    import datetime
    today = datetime.date(2026, 10, 18)
    rows = [
        _row("alpha", "s1", "2026-10-18", 100, 10, 900, 5),
        _row("alpha", "s1", "2026-10-12", 100, 10, 0, 3),         # day 7 back: inside (today + 6 earlier days)
        _row("alpha", "s1", "2026-10-11", 999, 999, 999, 99),     # outside the window
        _row("alpha", "s2", "2026-10-17", 0, 0, 0, 1),
        _row("alpha", "s3", "2026-10-17", 5000, 5000, 5000, 50, sub=True),   # subagent: not counted here
        _row("beta", "s4", "2026-10-01", 1, 1, 1, 1),            # nothing in the window: project absent
    ]
    w = sd.weekly(rows, today)
    assert set(w) == {"alpha"}
    a = w["alpha"]
    assert a["sessions"] == 2 and a["in_out_tokens"] == 220 and a["cache_read_tokens"] == 900
    assert a["cache_hit_share"] == round(900 / (900 + 200), 4)
    assert a["median_session_turns"] == 4.5                      # sessions of 8 and 1 turns
    assert sd.weekly([_row("g", "s", "2026-10-18", 0, 0, 0, 1)], today)["g"]["cache_hit_share"] is None


def test_weekly_counts_long_sessions_and_their_token_share():
    import datetime
    today = datetime.date(2026, 10, 18)
    rows = [_row("alpha", "long1", "2026-10-18", 600, 0, 0, 301),      # 301 turns: long
            _row("alpha", "edge", "2026-10-18", 100, 0, 0, 300),       # exactly 300: not long
            _row("alpha", "short", "2026-10-17", 300, 0, 0, 5),
            _row("beta", "b1", "2026-10-17", 50, 0, 0, 10)]
    w = sd.weekly(rows, today)
    assert w["alpha"]["long_sessions"] == 1 and w["alpha"]["long_session_token_share"] == round(600 / 1000, 4)
    assert w["beta"]["long_sessions"] == 0 and w["beta"]["long_session_token_share"] == 0.0
    long_session = [_row("alpha", "l", "2026-10-18", 100, 0, 0, 301)]
    assert sd.weekly(long_session, today)["alpha"]["long_session_token_share"] == 1.0


def test_weekly_table_shows_long_sessions():
    import generate_atlas as ga2
    weekly = {"alpha": {"sessions": 4, "in_out_tokens": 1000, "cache_read_tokens": 0, "cache_hit_share": 0.5,
                        "median_session_turns": 10, "long_sessions": 1, "long_session_token_share": 0.6},
              "beta": {"sessions": 1, "in_out_tokens": 1000, "cache_read_tokens": 0, "cache_hit_share": None,
                       "median_session_turns": 3, "long_sessions": 0, "long_session_token_share": 0.0}}
    html_ = ga2._weekly_html(weekly, {})
    assert "&gt; 300 turns" in html_ or "> 300 turns" in html_
    assert "1 (60% of tokens)" in html_
    assert "Sessions longer than 300 turns:</b> 1 of 5, 30% of in + out tokens" in html_


def test_weekly_parallel_session_proxy_and_fleet():
    import datetime
    today = datetime.date(2026, 10, 18)
    rows = [_row("alpha", "a1", "2026-10-18", 10, 0, 0, 5), _row("alpha", "a2", "2026-10-18", 10, 0, 0, 5),
            _row("alpha", "a3", "2026-10-17", 10, 0, 0, 5), _row("beta", "b1", "2026-10-18", 10, 0, 0, 400)]
    w = sd.weekly(rows, today)
    assert w["alpha"]["max_sessions_per_day"] == 2 and w["alpha"]["active_days"] == 2
    f = sd.weekly_fleet(rows, today)
    assert f["sessions"] == 4 and f["max_sessions_per_day"] == 3 and f["long_sessions"] == 1
    assert f["long_session_token_share"] == round(10 / 40, 4)
