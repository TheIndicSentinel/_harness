import json
import os
import re
import subprocess

import pytest

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
    """The page engine lives in scripts/atlas_engine.html, not pasted into this
    script: the generated page must contain it exactly once."""
    out = tmp_path / "atlas.html"
    ga.generate(output_path=str(out), focus_cwd=str(git_repo))
    content = out.read_text()
    assert content.count("function navigateTo") == 1
    assert content.count("<script>") == 1


def test_engine_template_exists_and_has_each_placeholder_once():
    """Fails if scripts/atlas_engine.html is deleted or loses a placeholder."""
    assert os.path.isfile(ga.ENGINE_SOURCE), "scripts/atlas_engine.html is missing"
    text = open(ga.ENGINE_SOURCE, encoding="utf-8").read()
    for placeholder in ga.ENGINE_PLACEHOLDERS:
        assert text.count(placeholder) == 1, placeholder
    assert "function navigateTo" in text and "function render" in text


def test_generate_fails_loudly_when_the_engine_is_missing(git_repo, tmp_path, monkeypatch):
    monkeypatch.setattr(ga, "ENGINE_SOURCE", str(tmp_path / "no-such-engine.html"))
    out = tmp_path / "atlas.html"
    with pytest.raises(RuntimeError, match="Atlas engine template not found"):
        ga.generate(output_path=str(out), focus_cwd=str(git_repo))
    assert not out.exists()          # no half-written page that looks like an empty harness


def test_generate_fails_when_a_placeholder_is_lost(git_repo, tmp_path, monkeypatch):
    broken = tmp_path / "engine.html"
    broken.write_text(open(ga.ENGINE_SOURCE, encoding="utf-8").read().replace("@@FLEET_PILLS@@", ""), encoding="utf-8")
    monkeypatch.setattr(ga, "ENGINE_SOURCE", str(broken))
    with pytest.raises(RuntimeError, match="@@FLEET_PILLS@@"):
        ga.generate(output_path=str(tmp_path / "atlas.html"), focus_cwd=str(git_repo))


def test_engine_does_not_depend_on_the_removed_hand_written_map():
    text = open(ga.ENGINE_SOURCE, encoding="utf-8").read()
    assert "harness-map" not in text
    assert not os.path.exists(os.path.join(ga.HARNESS_ROOT, "harness-map.html"))
    assert not os.path.exists(os.path.join(ga.HARNESS_ROOT, "commands", "harness-map.md"))


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
    project's data silently overwrite the earlier one's. the first
    project showed the second's commits because both used the literal id
    "commits" and the second sorts later alphabetically."""
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


def test_weekly_table_is_in_the_fleet_overview():
    import generate_atlas as ga
    weekly = {"alpha": {"sessions": 2, "in_out_tokens": 220, "cache_read_tokens": 900, "cache_hit_share": 0.8182, "median_session_turns": 4.5},
              "beta": {"sessions": 1, "in_out_tokens": 5, "cache_read_tokens": 0, "cache_hit_share": None, "median_session_turns": 1}}
    html_ = ga._weekly_html(weekly, {})
    assert "Last 7 days per project" in html_ and "81.8%" in html_ and "n/a" in html_ and "4.5" in html_
    assert ga._weekly_html({}, {}) == ""
