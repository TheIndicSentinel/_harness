import json
import os
import subprocess

import harness_gate_check as gc
from conftest import commit, head


def write_gates(repo, gates_dict, path=".harness/gates.json"):
    full = repo / path
    os.makedirs(full.parent, exist_ok=True)
    full.write_text(json.dumps(gates_dict))
    return full


class TestHarnessGateCheck:
    def test_fails_when_no_gates_file(self, git_repo):
        ok, failures = gc.check(str(git_repo / ".harness" / "gates.json"), head(git_repo), None)
        assert ok is False
        assert "No" in failures[0]

    def test_passes_for_parent_bookkeeping_commit(self, git_repo):
        code_sha = head(git_repo)
        gates_path = write_gates(
            git_repo,
            {"privacy_guardrails_review": {"status": "pass", "reviewed_commit": code_sha}},
        )
        subprocess.run(["git", "add", "."], cwd=git_repo, check=True)
        commit(git_repo, "record gate")
        ok, failures = gc.check(str(gates_path), head(git_repo), code_sha, repo_dir=str(git_repo))
        assert ok is True, failures

    def test_fails_when_code_changed_after_review(self, git_repo):
        code_sha = head(git_repo)
        gates_path = write_gates(
            git_repo,
            {"privacy_guardrails_review": {"status": "pass", "reviewed_commit": code_sha}},
        )
        (git_repo / "file.txt").write_text("more code, sneaked in with the gate record")
        subprocess.run(["git", "add", "."], cwd=git_repo, check=True)
        commit(git_repo, "code and gate together")
        ok, failures = gc.check(str(gates_path), head(git_repo), code_sha, repo_dir=str(git_repo))
        assert ok is False
        assert any("doesn't cover HEAD" in f for f in failures)

    def test_fails_on_status_fail(self, git_repo):
        code_sha = head(git_repo)
        gates_path = write_gates(
            git_repo,
            {"privacy_guardrails_review": {"status": "fail", "reviewed_commit": code_sha}},
        )
        ok, failures = gc.check(str(gates_path), code_sha, None)
        assert ok is False
        assert "status=fail" in failures[0]

    def test_fails_when_reviewed_commit_is_unrelated(self, git_repo):
        gates_path = write_gates(
            git_repo,
            {
                "privacy_guardrails_review": {
                    "status": "pass",
                    "reviewed_commit": "0" * 40,
                }
            },
        )
        ok, failures = gc.check(str(gates_path), head(git_repo), None)
        assert ok is False

    def test_required_gates_extension_enforced(self, git_repo):
        code_sha = head(git_repo)
        gates_path = write_gates(
            git_repo,
            {
                "privacy_guardrails_review": {"status": "pass", "reviewed_commit": code_sha},
                "required_gates": ["qa_review"],
            },
        )
        ok, failures = gc.check(str(gates_path), code_sha, None)
        assert ok is False
        assert any("qa_review" in f for f in failures)

    def test_passes_when_all_required_gates_pass(self, git_repo):
        code_sha = head(git_repo)
        gates_path = write_gates(
            git_repo,
            {
                "privacy_guardrails_review": {"status": "pass", "reviewed_commit": code_sha},
                "qa_review": {"status": "pass", "reviewed_commit": code_sha},
                "required_gates": ["qa_review"],
            },
        )
        ok, failures = gc.check(str(gates_path), code_sha, None)
        assert ok is True, failures
