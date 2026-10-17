import json
import os
import subprocess
import sys

import pytest

import verify_lib
from conftest import commit

HOOK = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hooks", "verify_before_stop.py")
WRITE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hooks", "verify_write.py")


def run_stop(repo, tmp_path):
    env = {**os.environ, "CLAUDE_HARNESS_PROJECTS_ROOT": str(repo.parent)}
    return subprocess.run(
        [sys.executable, HOOK], input=json.dumps({"cwd": str(repo)}),
        capture_output=True, text=True, env=env,
    )


@pytest.fixture
def repo(git_repo):
    return git_repo


def configure(repo, command, timeout=30):
    verify_lib.save_config(str(repo), command, timeout)


def test_noop_without_config(repo, tmp_path):
    (repo / "file.txt").write_text("changed")
    r = run_stop(repo, tmp_path)
    assert r.returncode == 0 and r.stderr == ""


def test_clean_tree_seeds_baseline_and_never_runs(repo, tmp_path):
    marker = tmp_path / "ran"
    configure(repo, f"touch {marker}")
    assert run_stop(repo, tmp_path).returncode == 0
    assert not marker.exists()
    assert verify_lib.load_state(str(repo))["result"] == "baseline"


def test_failure_blocks_with_output_then_pass_clears(repo, tmp_path):
    configure(repo, "echo BOOM-from-test; exit 1")
    (repo / "file.txt").write_text("edited")
    r = run_stop(repo, tmp_path)
    assert r.returncode == 2 and "BOOM-from-test" in r.stderr and "attempt 1/3" in r.stderr
    configure(repo, "true")
    r = run_stop(repo, tmp_path)
    assert r.returncode == 0
    assert verify_lib.load_state(str(repo))["result"] == "pass"


def test_unchanged_tree_after_pass_is_not_rerun(repo, tmp_path):
    marker = tmp_path / "count"
    configure(repo, f"echo x >> {marker}")
    (repo / "file.txt").write_text("edited")
    assert run_stop(repo, tmp_path).returncode == 0
    assert run_stop(repo, tmp_path).returncode == 0
    assert marker.read_text().count("x") == 1


def test_gives_up_after_max_blocks(repo, tmp_path):
    configure(repo, "exit 1")
    (repo / "file.txt").write_text("edited")
    codes = [run_stop(repo, tmp_path).returncode for _ in range(verify_lib.MAX_CONSECUTIVE_BLOCKS + 1)]
    assert codes == [2, 2, 2, 0]
    # and does not immediately re-block on the same tree
    assert run_stop(repo, tmp_path).returncode == 0


def test_timeout_counts_as_failure(repo, tmp_path):
    configure(repo, "sleep 5", timeout=1)
    (repo / "file.txt").write_text("edited")
    r = run_stop(repo, tmp_path)
    assert r.returncode == 2 and "timed out" in r.stderr


def test_new_commit_triggers_new_verification(repo, tmp_path):
    marker = tmp_path / "count"
    configure(repo, f"echo x >> {marker}")
    (repo / "file.txt").write_text("a")
    run_stop(repo, tmp_path)
    commit(repo, "c2")
    run_stop(repo, tmp_path)
    assert marker.read_text().count("x") == 2


def test_outside_projects_root_is_noop(tmp_path):
    env = {**os.environ, "CLAUDE_HARNESS_PROJECTS_ROOT": str(tmp_path / "Projects")}
    r = subprocess.run([sys.executable, HOOK], input=json.dumps({"cwd": str(tmp_path)}),
                       capture_output=True, text=True, env=env)
    assert r.returncode == 0


def test_garbage_stdin_fails_open():
    r = subprocess.run([sys.executable, HOOK], input="nope", capture_output=True, text=True)
    assert r.returncode == 0


def test_verify_write_roundtrip_and_validation(repo, tmp_path):
    env = {**os.environ, "CLAUDE_HARNESS_PROJECTS_ROOT": str(repo.parent)}
    ok = subprocess.run([sys.executable, WRITE, str(repo), "pytest -q", "--timeout", "90"],
                        capture_output=True, text=True, env=env)
    assert ok.returncode == 0
    assert verify_lib.load_config(str(repo)) == {"command": "pytest -q", "timeout_seconds": 90}
    bad = subprocess.run([sys.executable, WRITE, str(tmp_path), "x"], capture_output=True, text=True, env=env)
    assert bad.returncode == 1
    subprocess.run([sys.executable, WRITE, str(repo), "--clear"], capture_output=True, text=True, env=env)
    assert verify_lib.load_config(str(repo)) == {}


def test_config_lives_outside_the_repo(repo):
    configure(repo, "true")
    assert not os.path.exists(repo / ".harness" / "verify.json")
    assert str(repo) not in verify_lib.config_path(str(repo))

def test_records_last_seconds_and_show_warns_when_slow(repo, tmp_path):
    configure(repo, "true")
    (repo / "file.txt").write_text("edited")
    assert run_stop(repo, tmp_path).returncode == 0
    assert "last_seconds" in verify_lib.load_state(str(repo))
    st = verify_lib.load_state(str(repo))
    st["last_seconds"] = 120.0
    verify_lib.save_state(str(repo), st)
    env = {**os.environ, "CLAUDE_HARNESS_PROJECTS_ROOT": str(repo.parent)}
    r = subprocess.run([sys.executable, WRITE, str(repo)], capture_output=True, text=True, env=env)
    assert "last run: 120.0s" in r.stdout and "over 60s" in r.stdout
