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
        gate_lib.record_gate(str(git_repo), "privacy_guardrails_review", "pass", "no findings, reviewed")
        assert gate_lib.check_passing(str(git_repo), "privacy_guardrails_review") is True

    def test_stale_after_new_commit(self, git_repo):
        gate_lib.record_gate(str(git_repo), "privacy_guardrails_review", "pass", "no findings, reviewed")
        (git_repo / "file.txt").write_text("changed")
        commit(git_repo, "more work")
        assert gate_lib.check_passing(str(git_repo), "privacy_guardrails_review") is False

    def test_fail_status_not_passing(self, git_repo):
        gate_lib.record_gate(str(git_repo), "privacy_guardrails_review", "fail", "found a real issue")
        assert gate_lib.check_passing(str(git_repo), "privacy_guardrails_review") is False

    def test_never_run_not_passing(self, git_repo):
        assert gate_lib.check_passing(str(git_repo), "privacy_guardrails_review") is False

    def test_invalid_status_rejected(self, git_repo):
        with pytest.raises(ValueError):
            gate_lib.record_gate(str(git_repo), "qa_review", "maybe", "a perfectly fine long note")

    def test_reserved_key_rejected(self, git_repo):
        with pytest.raises(ValueError):
            gate_lib.record_gate(str(git_repo), "required_gates", "pass", "a perfectly fine long note")

    def test_trivial_notes_rejected(self, git_repo):
        with pytest.raises(ValueError):
            gate_lib.record_gate(str(git_repo), "privacy_guardrails_review", "pass", "ok")

    def test_empty_notes_rejected(self, git_repo):
        with pytest.raises(ValueError):
            gate_lib.record_gate(str(git_repo), "privacy_guardrails_review", "pass", "")

    def test_whitespace_only_notes_rejected(self, git_repo):
        with pytest.raises(ValueError):
            gate_lib.record_gate(str(git_repo), "privacy_guardrails_review", "pass", "   \n  ")


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
        gate_lib.record_gate(str(git_repo), "privacy_guardrails_review", "pass", "no findings, reviewed")
        assert gate_lib.failing_required(str(git_repo)) == ["qa_review"]

    def test_failing_required_empty_when_all_pass(self, git_repo):
        gate_lib.set_required_gates(str(git_repo), ["qa_review"])
        gate_lib.record_gate(str(git_repo), "privacy_guardrails_review", "pass", "no findings, reviewed")
        gate_lib.record_gate(str(git_repo), "qa_review", "pass", "tests green, lint clean")
        assert gate_lib.failing_required(str(git_repo)) == []


class TestReleaseCommands:
    def test_empty_by_default(self, git_repo):
        assert gate_lib.release_commands(str(git_repo)) == []

    def test_set_and_get(self, git_repo):
        result = gate_lib.set_release_commands(str(git_repo), ["make release", "./deploy.sh"])
        assert set(result) == {"make release", "./deploy.sh"}
        assert set(gate_lib.release_commands(str(git_repo))) == {"make release", "./deploy.sh"}

    def test_blank_entries_dropped(self, git_repo):
        result = gate_lib.set_release_commands(str(git_repo), ["make release", "  ", ""])
        assert result == ["make release"]

    def test_release_commands_key_reserved_for_record_gate(self, git_repo):
        with pytest.raises(ValueError):
            gate_lib.record_gate(str(git_repo), "release_commands", "pass", "a perfectly fine long note")


class TestWorkingTreeDirty:
    def test_clean_tree_not_dirty(self, git_repo):
        assert gate_lib.is_working_tree_dirty(str(git_repo)) is False

    def test_uncommitted_tracked_change_is_dirty(self, git_repo):
        (git_repo / "file.txt").write_text("changed, not committed")
        assert gate_lib.is_working_tree_dirty(str(git_repo)) is True

    def test_untracked_file_is_dirty(self, git_repo):
        (git_repo / "new_untracked.txt").write_text("new")
        assert gate_lib.is_working_tree_dirty(str(git_repo)) is True

    def test_harness_dir_alone_is_not_dirty(self, git_repo):
        """Regression: recording a gate creates an untracked .harness/ dir by
        design (see docs/CI_GATE_CHECK.md) -- its mere presence must not
        itself trip the dirty-worktree check, or every project would
        permanently fail release right after its first passing review."""
        gate_lib.record_gate(str(git_repo), "privacy_guardrails_review", "pass", "no findings, reviewed")
        assert gate_lib.is_working_tree_dirty(str(git_repo)) is False

    def test_harness_dir_plus_real_change_is_still_dirty(self, git_repo):
        gate_lib.record_gate(str(git_repo), "privacy_guardrails_review", "pass", "no findings, reviewed")
        (git_repo / "file.txt").write_text("sneaked in alongside the gate record")
        assert gate_lib.is_working_tree_dirty(str(git_repo)) is True

    def test_not_a_git_repo_counts_as_dirty(self, tmp_path):
        not_a_repo = tmp_path / "not_a_repo"
        not_a_repo.mkdir()
        assert gate_lib.is_working_tree_dirty(str(not_a_repo)) is True
