import json
import os
import subprocess
import sys

HOOK_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hooks", "secrets_guard.py"
)


def run_hook(payload, env):
    result = subprocess.run(
        [sys.executable, HOOK_PATH],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=env,
    )
    return result.returncode, result.stdout


def env_with_root(root):
    return {**os.environ, "CLAUDE_HARNESS_PROJECTS_ROOT": str(root)}


class TestSecretsGuard:
    def test_asks_on_write_to_pem(self, tmp_path):
        proj = tmp_path / "proj"
        proj.mkdir()
        code, out = run_hook(
            {"cwd": str(proj), "tool_name": "Write", "tool_input": {"file_path": "key.pem"}},
            env_with_root(tmp_path),
        )
        assert code == 0
        data = json.loads(out)
        assert data["hookSpecificOutput"]["permissionDecision"] == "ask"

    def test_asks_on_bash_touching_credentials(self, tmp_path):
        proj = tmp_path / "proj"
        proj.mkdir()
        code, out = run_hook(
            {
                "cwd": str(proj),
                "tool_name": "Bash",
                "tool_input": {"command": "cat credentials.json"},
            },
            env_with_root(tmp_path),
        )
        data = json.loads(out)
        assert data["hookSpecificOutput"]["permissionDecision"] == "ask"

    def test_asks_on_env_file(self, tmp_path):
        proj = tmp_path / "proj"
        proj.mkdir()
        code, out = run_hook(
            {"cwd": str(proj), "tool_name": "Bash", "tool_input": {"command": "echo X >> .env"}},
            env_with_root(tmp_path),
        )
        data = json.loads(out)
        assert data["hookSpecificOutput"]["permissionDecision"] == "ask"

    def test_silent_on_benign_edit(self, tmp_path):
        proj = tmp_path / "proj"
        proj.mkdir()
        code, out = run_hook(
            {"cwd": str(proj), "tool_name": "Edit", "tool_input": {"file_path": "Main.kt"}},
            env_with_root(tmp_path),
        )
        assert code == 0
        assert out.strip() == ""

    def test_silent_on_benign_bash(self, tmp_path):
        proj = tmp_path / "proj"
        proj.mkdir()
        code, out = run_hook(
            {
                "cwd": str(proj),
                "tool_name": "Bash",
                "tool_input": {"command": "./gradlew assembleDebug"},
            },
            env_with_root(tmp_path),
        )
        assert out.strip() == ""

    def test_sibling_prefix_not_matched(self, tmp_path):
        """Regression: root '.../Projects' must not match '.../Projects2'."""
        root = tmp_path / "Projects"
        sibling_proj = tmp_path / "Projects2" / "proj"
        sibling_proj.mkdir(parents=True)
        code, out = run_hook(
            {
                "cwd": str(sibling_proj),
                "tool_name": "Write",
                "tool_input": {"file_path": "key.pem"},
            },
            env_with_root(root),
        )
        assert out.strip() == ""

    def test_no_op_outside_root(self, tmp_path):
        code, out = run_hook(
            {"cwd": "/tmp", "tool_name": "Write", "tool_input": {"file_path": "key.pem"}},
            env_with_root(tmp_path / "Projects"),
        )
        assert out.strip() == ""
