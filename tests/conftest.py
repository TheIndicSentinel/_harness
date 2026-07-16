import os
import subprocess
import sys

import pytest

HARNESS_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HARNESS_ROOT, "hooks"))
sys.path.insert(
    0, os.path.join(HARNESS_ROOT, "templates", "new-project", ".github", "workflows")
)


@pytest.fixture
def git_repo(tmp_path, monkeypatch):
    """A fresh git repo at <tmp_path>/proj, with CLAUDE_HARNESS_PROJECTS_ROOT
    pointed at tmp_path so gate_lib.project_root_for() resolves it correctly."""
    monkeypatch.setenv("CLAUDE_HARNESS_PROJECTS_ROOT", str(tmp_path))
    repo = tmp_path / "proj"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "test"], cwd=repo, check=True)
    (repo / "file.txt").write_text("initial")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=repo, check=True)
    return repo


def commit(repo, msg="commit", allow_empty=False):
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    args = ["git", "commit", "-q", "-m", msg]
    if allow_empty:
        args.append("--allow-empty")
    subprocess.run(args, cwd=repo, check=True)


def head(repo):
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True
    ).stdout.strip()
