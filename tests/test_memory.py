import os
import time

import pytest

import memory_lib
import memory_lint

DAY = 86400


@pytest.fixture
def proj(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "claude"))
    root = tmp_path / "Projects" / "demo_app"
    root.mkdir(parents=True)
    return root


def write(root, name, body, age_days=0):
    d = memory_lib.memory_dir(str(root))
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, name)
    with open(p, "w") as f:
        f.write(body)
    t = time.time() - age_days * DAY
    os.utime(p, (t, t))
    return p


def good(verified="2026-10-14"):
    return f"---\nname: gotcha\ndescription: x\nmetadata:\n  type: project\n  verified: {verified}\n---\nbody\n"


def test_memory_dir_encoding_matches_claude_code(proj):
    assert memory_lib.memory_dir(str(proj)).endswith(
        "-Projects-demo-app/memory"
    ) and "demo_app" not in memory_lib.memory_dir(str(proj))


def test_clean_memory_has_no_findings(proj):
    write(proj, "gotcha.md", good(time.strftime("%Y-%m-%d")))
    assert memory_lint.lint(str(proj)) == []


def test_flags_oversize_status_log_and_missing_verified(proj):
    body = "---\nname: cli-track-status\ndescription: x\n---\n" + "\n".join(
        f"- Merged: thing (#{100 + i})" for i in range(200)
    )
    write(proj, "cli-track-status.md", body)
    msgs = " | ".join(m for _, m in memory_lint.lint(str(proj)))
    assert "bytes (>" in msgs and "status log" in msgs and "no `verified:`" in msgs


def test_unverified_collapsed_and_user_feedback_exempt(proj):
    for i in range(6):
        write(proj, f"p{i}.md", "---\nname: p%d\ndescription: x\nmetadata:\n  type: project\n---\nb\n" % i)
    write(proj, "me.md", "---\nname: me\ndescription: x\nmetadata:\n  type: user\n---\nb\n")
    unv = [m for _, m in memory_lint.lint(str(proj)) if "no `verified:`" in m]
    assert len(unv) == 1 and "6 file" not in unv[0] and "+2 more" in unv[0]


def test_flags_stale_verified_and_dead_paths(proj):
    body = good("2020-01-01") + "see `src/gone/module.py` for details\n"
    write(proj, "old.md", body)
    msgs = " | ".join(m for _, m in memory_lint.lint(str(proj)))
    assert "re-verify" in msgs and "src/gone/module.py" in msgs


def test_existing_path_not_flagged(proj):
    (proj / "src").mkdir()
    (proj / "src" / "a.py").write_text("")
    write(proj, "ok.md", good(time.strftime("%Y-%m-%d")) + "see `src/a.py`\n")
    assert memory_lint.lint(str(proj)) == []


def test_handoff_stale_and_oversize(proj):
    write(proj, "handoff.md", "x" * 3000, age_days=20)
    msgs = " | ".join(m for _, m in memory_lint.lint(str(proj)))
    assert "bytes (> 2048)" in msgs and "older than 14 days" in msgs


def test_index_line_length_flagged(proj):
    write(proj, "MEMORY.md", "- [t](t.md) — " + "x" * 300 + "\n")
    assert any("chars" in m for _, m in memory_lint.lint(str(proj)))


def test_nudge_silent_without_git_activity(proj):
    assert memory_lib.memory_nudge(str(proj)) is None


def test_nudge_reports_handoff(proj):
    write(proj, "handoff.md", "# task\n", age_days=2)
    assert "handoff.md present (2d old)" in memory_lib.memory_nudge(str(proj))


def test_nudge_flags_memory_behind_commits(proj, monkeypatch):
    write(proj, "a.md", good(), age_days=10)
    monkeypatch.setattr(memory_lib, "last_commit_time", lambda _r: time.time() - 1 * DAY)
    line = memory_lib.memory_nudge(str(proj))
    assert "behind the last commit" in line and "9d behind" in line
    write(proj, "b.md", good(), age_days=0)  # fresh capture silences it
    assert memory_lib.memory_nudge(str(proj)) is None
