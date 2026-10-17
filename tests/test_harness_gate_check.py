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

    def test_malformed_json_fails_closed_not_crash(self, git_repo):
        gates_path = git_repo / ".harness" / "gates.json"
        os.makedirs(gates_path.parent, exist_ok=True)
        gates_path.write_text("{not valid json!!")
        ok, failures = gc.check(str(gates_path), head(git_repo), None)
        assert ok is False
        assert "not valid JSON" in failures[0]

    def test_non_object_json_fails_closed(self, git_repo):
        gates_path = git_repo / ".harness" / "gates.json"
        os.makedirs(gates_path.parent, exist_ok=True)
        gates_path.write_text(json.dumps(["not", "an", "object"]))
        ok, failures = gc.check(str(gates_path), head(git_repo), None)
        assert ok is False
        assert "did not contain a JSON object" in failures[0]


class TestGateRemoval:
    def _commit_record(self, repo, gates, msg):
        write_gates(repo, gates)
        subprocess.run(["git", "add", "."], cwd=repo, check=True)
        commit(repo, msg)

    def test_removing_a_required_gate_fails_even_with_valid_pass(self, git_repo):
        code = head(git_repo)
        full = {
            "privacy_guardrails_review": {"status": "pass", "reviewed_commit": code},
            "qa_review": {"status": "pass", "reviewed_commit": code},
            "required_gates": ["qa_review"],
        }
        self._commit_record(git_repo, full, "record gates")
        parent = head(git_repo)
        relaxed = {k: v for k, v in full.items() if k != "required_gates"}
        relaxed["privacy_guardrails_review"] = {"status": "pass", "reviewed_commit": parent}
        self._commit_record(git_repo, relaxed, "quietly drop qa gate")
        ok, failures = gc.check(
            str(git_repo / ".harness" / "gates.json"), head(git_repo), parent, repo_dir=str(git_repo)
        )
        assert ok is False
        assert any("removed since the previous commit, last tag or target branch: qa_review" in f for f in failures)

    def test_adding_a_gate_is_fine(self, git_repo):
        code = head(git_repo)
        self._commit_record(
            git_repo, {"privacy_guardrails_review": {"status": "pass", "reviewed_commit": code}}, "r1"
        )
        parent = head(git_repo)
        self._commit_record(
            git_repo,
            {
                "privacy_guardrails_review": {"status": "pass", "reviewed_commit": parent},
                "qa_review": {"status": "pass", "reviewed_commit": parent},
                "required_gates": ["qa_review"],
            },
            "r2",
        )
        ok, failures = gc.check(
            str(git_repo / ".harness" / "gates.json"), head(git_repo), parent, repo_dir=str(git_repo)
        )
        assert ok is True, failures


class TestRemovalBaselines:
    """The reviewer-found bypass: commit 1 drops the gate, commit 2 is the
    release, so a parent-only comparison sees nothing removed."""

    def _record(self, repo, gates, msg):
        write_gates(repo, gates)
        subprocess.run(["git", "add", "."], cwd=repo, check=True)
        commit(repo, msg)

    def test_two_commit_pr_bypass_is_caught_via_merge_base(self, git_repo):
        subprocess.run(["git", "branch", "-M", "main"], cwd=git_repo, check=True)
        c0 = head(git_repo)
        self._record(git_repo, {
            "privacy_guardrails_review": {"status": "pass", "reviewed_commit": c0},
            "qa_review": {"status": "pass", "reviewed_commit": c0},
            "required_gates": ["qa_review"],
        }, "main: gates recorded")
        main_sha = head(git_repo)
        subprocess.run(["git", "checkout", "-q", "-b", "feature"], cwd=git_repo, check=True)
        # commit 1 of the PR: quietly drop the qa gate
        self._record(git_repo, {
            "privacy_guardrails_review": {"status": "pass", "reviewed_commit": main_sha},
        }, "feature: tidy gates")
        c1 = head(git_repo)
        # commit 2: the "release", bookkeeping record only
        self._record(git_repo, {
            "privacy_guardrails_review": {"status": "pass", "reviewed_commit": c1},
        }, "feature: record pass")
        gates_path = str(git_repo / ".harness" / "gates.json")
        # parent-only view: nothing removed -> the old check passes
        ok_old, _ = gc.check(gates_path, head(git_repo), c1, repo_dir=str(git_repo), baselines=[c1])
        assert ok_old is True
        # with the target branch as a baseline it fails
        ok, failures = gc.check(gates_path, head(git_repo), c1, repo_dir=str(git_repo), baselines=[c1, main_sha])
        assert ok is False and any("qa_review" in f for f in failures)

    def test_baseline_refs_finds_merge_base_and_last_tag(self, git_repo, monkeypatch):
        subprocess.run(["git", "branch", "-M", "main"], cwd=git_repo, check=True)
        subprocess.run(["git", "tag", "v1"], cwd=git_repo, check=True)
        tag_sha = head(git_repo)
        commit(git_repo, "second", allow_empty=True)
        commit(git_repo, "third", allow_empty=True)
        refs = gc.baseline_refs(head(git_repo), subprocess.run(
            ["git", "rev-parse", "HEAD~1"], cwd=git_repo, capture_output=True, text=True).stdout.strip(), str(git_repo))
        assert tag_sha in refs and len(refs) >= 2

    def test_acknowledged_removal_passes(self, git_repo):
        c0 = head(git_repo)
        self._record(git_repo, {
            "privacy_guardrails_review": {"status": "pass", "reviewed_commit": c0},
            "qa_review": {"status": "pass", "reviewed_commit": c0},
            "required_gates": ["qa_review"],
        }, "r1")
        before = head(git_repo)
        self._record(git_repo, {
            "privacy_guardrails_review": {"status": "pass", "reviewed_commit": before},
            "acknowledged_gate_removals": ["qa_review"],
        }, "r2: deliberate, reviewed loosening")
        ok, failures = gc.check(
            str(git_repo / ".harness" / "gates.json"), head(git_repo), before,
            repo_dir=str(git_repo), baselines=[before],
        )
        assert ok is True, failures
