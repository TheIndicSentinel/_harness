import json
import os
import subprocess
import sys

import pytest

import gate_lib
import release_gate

HOOK_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hooks", "release_gate.py"
)


def run_hook(payload, env):
    result = subprocess.run(
        [sys.executable, HOOK_PATH],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=env,
    )
    return result.returncode, result.stderr


class TestIsShipAction:
    @pytest.mark.parametrize(
        "command",
        [
            "gh release create v1.0 app.apk",
            "npm publish",
            "eas submit",
            "./gradlew assembleRelease --stacktrace",
            "git push origin --tags",
            "docker push myimage:latest",
            "firebase deploy",
        ],
    )
    def test_matches_ship_commands(self, command):
        payload = {"tool_name": "Bash", "tool_input": {"command": command}}
        assert release_gate.is_ship_action(payload) != ""

    @pytest.mark.parametrize(
        "command",
        [
            "git status",
            "git push origin main",
            "./gradlew assembleDebug",
            "ls -la",
            "git log --oneline",
        ],
    )
    def test_does_not_match_benign_commands(self, command):
        payload = {"tool_name": "Bash", "tool_input": {"command": command}}
        assert release_gate.is_ship_action(payload) == ""

    def test_matches_mcp_deploy_tool(self):
        assert release_gate.is_ship_action({"tool_name": "mcp__vercel__deploy_project"}) != ""

    def test_does_not_match_benign_mcp_tool(self):
        assert release_gate.is_ship_action({"tool_name": "mcp__github__list_issues"}) == ""

    def test_declared_command_matched_when_no_builtin_pattern_fits(self):
        payload = {"tool_name": "Bash", "tool_input": {"command": "make release --prod"}}
        assert release_gate.is_ship_action(payload) == ""  # not matched without declaration
        assert release_gate.is_ship_action(payload, declared_commands=["make release"]) != ""

    def test_declared_command_is_case_insensitive_substring(self):
        payload = {"tool_name": "Bash", "tool_input": {"command": "MAKE RELEASE --prod"}}
        assert release_gate.is_ship_action(payload, declared_commands=["make release"]) != ""

    def test_unrelated_declared_command_does_not_false_positive(self):
        payload = {"tool_name": "Bash", "tool_input": {"command": "echo hello"}}
        assert release_gate.is_ship_action(payload, declared_commands=["make release"]) == ""


class TestReleaseGateHookEndToEnd:
    def test_blocks_when_no_gate_recorded(self, git_repo):
        env = {**os.environ, "CLAUDE_HARNESS_PROJECTS_ROOT": os.path.dirname(str(git_repo))}
        code, stderr = run_hook(
            {"cwd": str(git_repo), "tool_name": "Bash", "tool_input": {"command": "npm publish"}},
            env,
        )
        assert code == 2
        assert "privacy_guardrails_review" in stderr

    def test_passes_when_gate_recorded_and_current(self, git_repo):
        gate_lib.record_gate(str(git_repo), "privacy_guardrails_review", "pass", "no findings, reviewed")
        env = {**os.environ, "CLAUDE_HARNESS_PROJECTS_ROOT": os.path.dirname(str(git_repo))}
        code, _ = run_hook(
            {"cwd": str(git_repo), "tool_name": "Bash", "tool_input": {"command": "npm publish"}},
            env,
        )
        assert code == 0

    def test_no_op_for_benign_command(self, git_repo):
        env = {**os.environ, "CLAUDE_HARNESS_PROJECTS_ROOT": os.path.dirname(str(git_repo))}
        code, _ = run_hook(
            {"cwd": str(git_repo), "tool_name": "Bash", "tool_input": {"command": "git status"}},
            env,
        )
        assert code == 0

    def test_no_op_outside_projects_root(self, tmp_path):
        env = {**os.environ, "CLAUDE_HARNESS_PROJECTS_ROOT": str(tmp_path / "Projects")}
        code, _ = run_hook(
            {"cwd": str(tmp_path), "tool_name": "Bash", "tool_input": {"command": "npm publish"}},
            env,
        )
        assert code == 0

    def test_fails_open_on_garbage_stdin(self):
        result = subprocess.run(
            [sys.executable, HOOK_PATH], input="not json", capture_output=True, text=True
        )
        assert result.returncode == 0

    def test_blocks_on_dirty_worktree_even_with_passing_gate(self, git_repo):
        """The core dirty-worktree regression: a passing gate for the
        reviewed commit must not authorize a release built from a working
        tree with uncommitted edits on top of it."""
        gate_lib.record_gate(str(git_repo), "privacy_guardrails_review", "pass", "no findings, reviewed")
        (git_repo / "file.txt").write_text("edited after the review, never committed")
        env = {**os.environ, "CLAUDE_HARNESS_PROJECTS_ROOT": os.path.dirname(str(git_repo))}
        code, stderr = run_hook(
            {"cwd": str(git_repo), "tool_name": "Bash", "tool_input": {"command": "npm publish"}},
            env,
        )
        assert code == 2
        assert "uncommitted changes" in stderr

    def test_declared_release_command_end_to_end(self, git_repo):
        gate_lib.set_release_commands(str(git_repo), ["make release"])
        env = {**os.environ, "CLAUDE_HARNESS_PROJECTS_ROOT": os.path.dirname(str(git_repo))}
        code, stderr = run_hook(
            {"cwd": str(git_repo), "tool_name": "Bash", "tool_input": {"command": "make release"}},
            env,
        )
        assert code == 2  # blocked: declared command recognized, but no gate recorded yet
        assert "privacy_guardrails_review" in stderr

        gate_lib.record_gate(str(git_repo), "privacy_guardrails_review", "pass", "no findings, reviewed")
        code, _ = run_hook(
            {"cwd": str(git_repo), "tool_name": "Bash", "tool_input": {"command": "make release"}},
            env,
        )
        assert code == 0  # now passes once the gate is recorded
