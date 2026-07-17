import json
import os
import re

import generate_atlas as ga


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
