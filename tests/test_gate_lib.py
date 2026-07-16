import os

import pytest

import gate_lib
from conftest import commit


class TestProjectsRoot:
    def test_default(self, monkeypatch):
        monkeypatch.delenv("CLAUDE_HARNESS_PROJECTS_ROOT", raising=False)
        assert gate_lib.projects_root() == os.path.abspath(
            os.path.expanduser("~/Documents/Projects")
        )

    def test_override(self, monkeypatch, tmp_path):
        monkeypatch.setenv("CLAUDE_HARNESS_PROJECTS_ROOT", str(tmp_path))
        assert gate_lib.projects_root() == str(tmp_path)


class TestProjectRootFor:
    def test_resolves_project_under_root(self, git_repo):
        assert gate_lib.project_root_for(str(git_repo)) == str(git_repo)

    def test_nested_cwd_resolves_to_top_project_dir(self, git_repo):
        nested = git_repo / "sub" / "dir"
        nested.mkdir(parents=True)
        assert gate_lib.project_root_for(str(nested)) == str(git_repo)

    def test_sibling_prefix_is_not_matched(self, tmp_path, monkeypatch):
        """Regression: root '.../Projects' must not match '.../Projects2'."""
        monkeypatch.setenv("CLAUDE_HARNESS_PROJECTS_ROOT", str(tmp_path / "Projects"))
        sibling = tmp_path / "Projects2" / "someproj"
        sibling.mkdir(parents=True)
        assert gate_lib.project_root_for(str(sibling)) is None

    def test_harness_itself_excluded(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CLAUDE_HARNESS_PROJECTS_ROOT", str(tmp_path))
        harness_dir = tmp_path / "_harness"
        harness_dir.mkdir()
        assert gate_lib.project_root_for(str(harness_dir)) is None

    def test_outside_root_returns_none(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CLAUDE_HARNESS_PROJECTS_ROOT", str(tmp_path / "Projects"))
        outside = tmp_path / "elsewhere"
        outside.mkdir()
        assert gate_lib.project_root_for(str(outside)) is None


class TestGateRoundtrip:
    def test_record_and_check_passing(self, git_repo):
        gate_lib.record_gate(str(git_repo), "privacy_guardrails_review", "pass", "ok")
        assert gate_lib.check_passing(str(git_repo), "privacy_guardrails_review") is True

    def test_stale_after_new_commit(self, git_repo):
        gate_lib.record_gate(str(git_repo), "privacy_guardrails_review", "pass", "ok")
        (git_repo / "file.txt").write_text("changed")
        commit(git_repo, "more work")
        assert gate_lib.check_passing(str(git_repo), "privacy_guardrails_review") is False

    def test_fail_status_not_passing(self, git_repo):
        gate_lib.record_gate(str(git_repo), "privacy_guardrails_review", "fail", "no")
        assert gate_lib.check_passing(str(git_repo), "privacy_guardrails_review") is False

    def test_never_run_not_passing(self, git_repo):
        assert gate_lib.check_passing(str(git_repo), "privacy_guardrails_review") is False

    def test_invalid_status_rejected(self, git_repo):
        with pytest.raises(ValueError):
            gate_lib.record_gate(str(git_repo), "qa_review", "maybe", "")

    def test_reserved_key_rejected(self, git_repo):
        with pytest.raises(ValueError):
            gate_lib.record_gate(str(git_repo), "required_gates", "pass", "")


class TestRequiredGates:
    def test_privacy_always_required(self, git_repo):
        assert gate_lib.required_gates(str(git_repo)) == ["privacy_guardrails_review"]

    def test_set_required_gates_adds(self, git_repo):
        result = gate_lib.set_required_gates(str(git_repo), ["qa_review", "compliance_review"])
        assert set(result) == {"privacy_guardrails_review", "qa_review", "compliance_review"}

    def test_cannot_remove_privacy_via_set_required_gates(self, git_repo):
        gate_lib.set_required_gates(str(git_repo), [])
        assert "privacy_guardrails_review" in gate_lib.required_gates(str(git_repo))

    def test_failing_required_lists_unmet(self, git_repo):
        gate_lib.set_required_gates(str(git_repo), ["qa_review"])
        gate_lib.record_gate(str(git_repo), "privacy_guardrails_review", "pass", "")
        assert gate_lib.failing_required(str(git_repo)) == ["qa_review"]

    def test_failing_required_empty_when_all_pass(self, git_repo):
        gate_lib.set_required_gates(str(git_repo), ["qa_review"])
        gate_lib.record_gate(str(git_repo), "privacy_guardrails_review", "pass", "")
        gate_lib.record_gate(str(git_repo), "qa_review", "pass", "")
        assert gate_lib.failing_required(str(git_repo)) == []
