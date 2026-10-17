"""Portability guarantees: the harness must work from a clean checkout on any
machine -- no author-specific absolute paths, every wired hook command resolves
to a script that exists, and the hooks actually run from a copied install
rooted somewhere other than ~/Documents/Projects/_harness.
"""
import json
import os
import shutil
import subprocess
import sys

import pytest

HARNESS_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKIP_DIRS = {".git", "skills/synced", "__pycache__", ".pytest_cache", "tests"}
TEXT_EXT = (".py", ".md", ".json", ".yml", ".yaml", ".sh", ".html")


def _tracked_files():
    """Files git tracks (what a plugin/clone user receives); falls back to a walk."""
    try:
        out = subprocess.run(
            ["git", "ls-files"], cwd=HARNESS_ROOT, capture_output=True, text=True, check=True
        ).stdout.split("\n")
        files = [f for f in out if f]
    except (OSError, subprocess.CalledProcessError):
        files = []
        for root, dirs, names in os.walk(HARNESS_ROOT):
            dirs[:] = [d for d in dirs if d not in (".git", "__pycache__", ".pytest_cache")]
            files += [os.path.relpath(os.path.join(root, n), HARNESS_ROOT) for n in names]
    return [
        f for f in files
        if f.endswith(TEXT_EXT)
        and not any(f == d or f.startswith(d + "/") for d in SKIP_DIRS)
        and os.path.isfile(os.path.join(HARNESS_ROOT, f))
    ]


def test_no_author_specific_absolute_paths():
    offenders = []
    for rel in _tracked_files():
        with open(os.path.join(HARNESS_ROOT, rel), errors="ignore") as f:
            for n, line in enumerate(f, 1):
                if "/Users/" in line or "/home/" in line:
                    offenders.append(f"{rel}:{n}")
    assert not offenders, f"machine-specific absolute paths found: {offenders}"


def test_manifests_are_well_formed():
    with open(os.path.join(HARNESS_ROOT, ".claude-plugin", "plugin.json")) as f:
        plugin = json.load(f)
    with open(os.path.join(HARNESS_ROOT, ".claude-plugin", "marketplace.json")) as f:
        market = json.load(f)
    for key in ("name", "description", "version", "hooks"):
        assert plugin.get(key), f"plugin.json missing {key}"
    assert market.get("description"), "marketplace.json should describe the marketplace"
    assert os.path.isfile(os.path.join(HARNESS_ROOT, plugin["hooks"]))


def _hook_commands(path):
    with open(path) as f:
        data = json.load(f)
    for entries in data.get("hooks", {}).values():
        for entry in entries:
            for hook in entry.get("hooks", []):
                if hook.get("type") == "command":
                    yield hook["command"]


@pytest.mark.parametrize("rel", ["hooks/hooks.json", "settings.json"])
def test_every_wired_hook_script_exists(rel):
    for command in _hook_commands(os.path.join(HARNESS_ROOT, rel)):
        scripts = [t for t in command.replace('"', " ").split() if t.endswith(".py")]
        assert scripts, f"no script in hook command: {command}"
        for token in scripts:
            resolved = (
                token.replace("${CLAUDE_PLUGIN_ROOT:-$HOME/Documents/Projects/_harness}", HARNESS_ROOT)
                .replace("${CLAUDE_PLUGIN_ROOT}", HARNESS_ROOT)
            )
            assert os.path.isfile(resolved), f"{rel}: {token} does not resolve to a file"


def test_hooks_run_from_a_relocated_clean_install(tmp_path):
    """Copy only what a plugin install ships to an arbitrary directory and run
    the real hooks from a different cwd: a ship command blocks, a benign one
    doesn't, garbage input doesn't crash."""
    install = tmp_path / "somewhere" / "else" / "harness"
    shutil.copytree(
        os.path.join(HARNESS_ROOT, "hooks"), install / "hooks",
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    projects = tmp_path / "Projects"
    proj = projects / "demo"
    proj.mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=proj, check=True)
    subprocess.run(["git", "-c", "user.email=t@e.x", "-c", "user.name=t",
                    "commit", "-q", "--allow-empty", "-m", "i"], cwd=proj, check=True)
    env = {k: v for k, v in os.environ.items() if k != "CLAUDE_PLUGIN_ROOT"}
    env.update(CLAUDE_HARNESS_PROJECTS_ROOT=str(projects), CLAUDE_PLUGIN_ROOT=str(install))

    def run(script, payload):
        return subprocess.run(
            [sys.executable, str(install / "hooks" / script)],
            input=payload if isinstance(payload, str) else json.dumps(payload),
            capture_output=True, text=True, env=env, cwd=str(tmp_path),
        )

    ship = {"cwd": str(proj), "tool_name": "Bash", "tool_input": {"command": "npm publish"}}
    benign = {"cwd": str(proj), "tool_name": "Bash", "tool_input": {"command": "ls"}}
    assert run("release_gate.py", ship).returncode == 2
    assert run("release_gate.py", benign).returncode == 0
    assert run("release_gate.py", "not json").returncode == 0
    secret = {"cwd": str(proj), "tool_name": "Read", "tool_input": {"file_path": str(proj / ".env")}}
    assert '"ask"' in run("secrets_guard.py", secret).stdout
    assert run("session_start.py", {"cwd": str(proj)}).returncode == 0


def test_plugin_root_placeholder_is_always_quoted():
    """An unquoted ${CLAUDE_PLUGIN_ROOT} splits on a space in the install path and
    silently breaks the hook; hooks fail open, so nothing would say so."""
    import re
    for rel in ("hooks/hooks.json", "settings.json"):
        for command in _hook_commands(os.path.join(HARNESS_ROOT, rel)):
            for m in re.finditer(r"\$\{CLAUDE_PLUGIN_ROOT[^}]*\}", command):
                before = command[: m.start()]
                assert before.count('"') % 2 == 1, f"{rel}: unquoted placeholder in {command!r}"
