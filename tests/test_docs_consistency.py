"""Regression test for the exact gap a prior review caught: /new-project
scaffolds its whole templates/new-project/ tree wholesale (so it's complete
by construction), but /adopt-project lists files one by one -- and that list
has gone stale before (missing harness_gate_check.py, then ARCHITECTURE.md).
This asserts every template file's name appears somewhere in adopt-project.md
so a newly-added template can't be silently left off that list again.
"""
import os

HARNESS_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE_ROOT = os.path.join(HARNESS_ROOT, "templates", "new-project")
ADOPT_PROJECT_MD = os.path.join(HARNESS_ROOT, "commands", "adopt-project.md")


def _adopt_project_text() -> str:
    with open(ADOPT_PROJECT_MD) as f:
        return f.read()


def test_every_template_doc_referenced_in_adopt_project():
    docs_dir = os.path.join(TEMPLATE_ROOT, "docs")
    text = _adopt_project_text()
    missing = [
        name
        for name in sorted(os.listdir(docs_dir))
        if name.endswith(".md") and name not in text
    ]
    assert not missing, f"templates/new-project/docs/ files missing from adopt-project.md: {missing}"


def test_every_github_template_file_referenced_in_adopt_project():
    github_dir = os.path.join(TEMPLATE_ROOT, ".github")
    text = _adopt_project_text()
    missing = []
    for root, _dirs, files in os.walk(github_dir):
        for name in files:
            if name not in text:
                missing.append(os.path.relpath(os.path.join(root, name), TEMPLATE_ROOT))
    assert not missing, f".github/ template files missing from adopt-project.md: {missing}"


def test_new_project_command_copies_dotdirs_explicitly():
    """Regression: a naive glob copy (cp source/* dest/) silently skips
    dot-directories like .github/ -- new-project.md's instructions must say
    so explicitly, or a future template dotdir addition ships broken."""
    with open(os.path.join(HARNESS_ROOT, "commands", "new-project.md")) as f:
        text = f.read()
    assert "dot-director" in text.lower() or "dotfile" in text.lower()
