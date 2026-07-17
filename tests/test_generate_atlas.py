import json
import os
import re
import subprocess

import generate_atlas as ga
from generate_dashboard import list_project_names


def _extract(content, name, end_marker):
    m = re.search(r"var %s = (\{.*?\});\s*\n\s*%s" % (re.escape(name), re.escape(end_marker)), content, re.S)
    return json.loads(m.group(1))


def test_generate_writes_valid_html_with_live_data(git_repo, tmp_path):
    out = tmp_path / "atlas.html"
    path = ga.generate(output_path=str(out), focus_cwd=str(git_repo))
    assert path == str(out)
    content = out.read_text()
    assert "<html" in content and "</html>" in content
    assert "LIVE — generated" in content
    assert "proj" in content  # git_repo fixture's project dir name


def test_focus_project_marked_in_state(git_repo, tmp_path):
    out = tmp_path / "atlas.html"
    ga.generate(output_path=str(out), focus_cwd=str(git_repo))
    content = out.read_text()
    script = content[content.index("<script>"):content.index("</script>")]
    assert "project: \"proj\"" in script


def test_cats_leaves_detail_are_structurally_consistent(git_repo, tmp_path):
    out = tmp_path / "atlas.html"
    ga.generate(output_path=str(out), focus_cwd=str(git_repo))
    content = out.read_text()
    script = content[content.index("<script>"):content.index("</script>")]

    cats = _extract(script, "CATS_BY_PROJECT", "var LEAVES")
    leaves = _extract(script, "LEAVES", "var KIND_META")
    detail = _extract(script, "DETAIL", "var state")

    for proj, catlist in cats.items():
        for c in catlist:
            assert c["id"] in detail, "category %s missing DETAIL" % c["id"]
            if c["hasLeaves"]:
                assert c["id"] in leaves, "category %s claims leaves but none generated" % c["id"]

    for group, leaf_list in leaves.items():
        for leaf in leaf_list:
            assert leaf["id"] in detail, "leaf %s missing DETAIL" % leaf["id"]


def test_harness_meta_always_present(git_repo, tmp_path):
    out = tmp_path / "atlas.html"
    ga.generate(output_path=str(out), focus_cwd=str(git_repo))
    content = out.read_text()
    script = content[content.index("<script>"):content.index("</script>")]
    # PROJECTS is emitted as a raw JS object literal (unquoted keys), not JSON
    assert "id: \"harness\"" in script
    assert "kind: \"meta\"" in script


def test_engine_is_extracted_not_duplicated(git_repo, tmp_path):
    """The shell/engine must come from harness-map.html at runtime, not be
    hand-copied into this script -- this test would fail if someone pastes a
    static copy of the engine into generate_atlas.py instead of extracting it."""
    out = tmp_path / "atlas.html"
    ga.generate(output_path=str(out), focus_cwd=str(git_repo))
    content = out.read_text()
    assert content.count("function navigateTo") == 1
    assert content.count("<script>") == 1


def _make_repo(path, commit_message):
    path.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "test"], cwd=path, check=True)
    (path / "file.txt").write_text("x")
    subprocess.run(["git", "add", "."], cwd=path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", commit_message], cwd=path, check=True)


def test_two_projects_do_not_leak_commits_into_each_other(tmp_path, monkeypatch):
    """Regression test for a real bug: every project used the same bare
    category id ("commits", "memory", etc.), so LEAVES/DETAIL -- which are
    flat objects shared across all projects once merged -- had the later
    project's data silently overwrite the earlier one's. kavach showed
    saarthi's commits because both used the literal id "commits" and
    saarthi sorts after kavach alphabetically."""
    monkeypatch.setenv("CLAUDE_HARNESS_PROJECTS_ROOT", str(tmp_path))
    _make_repo(tmp_path / "alpha", "UNIQUE_ALPHA_COMMIT_MARKER")
    _make_repo(tmp_path / "zeta", "UNIQUE_ZETA_COMMIT_MARKER")

    assert set(list_project_names(str(tmp_path))) == {"alpha", "zeta"}

    out = tmp_path / "atlas.html"
    ga.generate(output_path=str(out), focus_cwd=str(tmp_path / "alpha"))
    content = out.read_text()
    script = content[content.index("<script>"):content.index("</script>")]

    cats = _extract(script, "CATS_BY_PROJECT", "var LEAVES")
    leaves = _extract(script, "LEAVES", "var KIND_META")
    detail = _extract(script, "DETAIL", "var state")

    alpha_commit_cat = next(c["id"] for c in cats["alpha"] if c["label"] == "Recent Commits")
    zeta_commit_cat = next(c["id"] for c in cats["zeta"] if c["label"] == "Recent Commits")
    assert alpha_commit_cat != zeta_commit_cat, "category ids collided across projects"

    alpha_leaf_ids = {l["id"] for l in leaves[alpha_commit_cat]}
    zeta_leaf_ids = {l["id"] for l in leaves[zeta_commit_cat]}
    assert alpha_leaf_ids.isdisjoint(zeta_leaf_ids)

    alpha_messages = " ".join(detail[i]["fields"][0][1] for i in alpha_leaf_ids)
    zeta_messages = " ".join(detail[i]["fields"][0][1] for i in zeta_leaf_ids)
    assert "UNIQUE_ALPHA_COMMIT_MARKER" in alpha_messages
    assert "UNIQUE_ZETA_COMMIT_MARKER" not in alpha_messages
    assert "UNIQUE_ZETA_COMMIT_MARKER" in zeta_messages
    assert "UNIQUE_ALPHA_COMMIT_MARKER" not in zeta_messages


def test_no_gate_round_history_or_savings_narrative_claimed(git_repo, tmp_path):
    """This generator must not claim things it can't produce -- no invented
    'Features Worked On' savings narrative, no fabricated gate-round history.
    The CSS (reused verbatim for the shared engine) still defines a
    .savings-block *class* even though nothing here populates it -- that's
    fine; what matters is no DETAIL entry actually uses it."""
    out = tmp_path / "atlas.html"
    ga.generate(output_path=str(out), focus_cwd=str(git_repo))
    content = out.read_text()
    script = content[content.index("<script>"):content.index("</script>")]
    detail = _extract(script, "DETAIL", "var state")
    for entry in detail.values():
        assert "savings-block" not in entry.get("html", "")
    assert "Features Worked On" not in script
