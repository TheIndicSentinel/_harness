import os

import generate_dashboard as gd


def test_generate_writes_valid_looking_html(git_repo, tmp_path):
    out = tmp_path / "out" / "dashboard.html"
    path = gd.generate(output_path=str(out), focus_cwd=str(git_repo))
    assert path == str(out)
    assert out.is_file()
    content = out.read_text()
    assert "<html" in content and "</html>" in content
    assert "proj" in content  # git_repo fixture's project dir is named "proj"


def test_focus_project_is_marked(git_repo, tmp_path):
    out = tmp_path / "dashboard.html"
    gd.generate(output_path=str(out), focus_cwd=str(git_repo))
    content = out.read_text()
    assert "you are here" in content


def test_non_focus_run_has_no_focus_marker(git_repo, tmp_path):
    out = tmp_path / "dashboard.html"
    # focus_cwd outside any project -> project_root_for() returns None
    gd.generate(output_path=str(out), focus_cwd=str(tmp_path))
    content = out.read_text()
    assert "you are here" not in content


def test_output_defaults_creates_parent_dirs(git_repo, tmp_path, monkeypatch):
    nested = tmp_path / "a" / "b" / "dashboard.html"
    gd.generate(output_path=str(nested), focus_cwd=str(git_repo))
    assert nested.is_file()


def test_a_broken_project_does_not_crash_the_whole_run(git_repo, tmp_path, monkeypatch):
    # A project directory that exists but isn't a git repo and has odd
    # permissions-free content should still render *something*, not raise.
    bad = tmp_path / "broken"
    bad.mkdir()
    out = tmp_path / "dashboard.html"
    path = gd.generate(output_path=str(out), focus_cwd=str(git_repo))
    assert os.path.isfile(path)


def test_harness_meta_card_present(git_repo, tmp_path):
    out = tmp_path / "dashboard.html"
    gd.generate(output_path=str(out), focus_cwd=str(git_repo))
    content = out.read_text()
    assert "meta — not gated" in content
    assert "skills ·" in content or "skill" in content.lower()
