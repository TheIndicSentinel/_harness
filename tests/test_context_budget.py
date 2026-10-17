"""Regression ceilings on always-loaded context. If one of these fails, the
change added standing per-session cost: shorten it, move it into a skill or a
path-scoped rule, or (deliberately) raise the ceiling in the same commit."""
import os
import sys

HARNESS_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HARNESS_ROOT, "scripts"))
import context_budget  # noqa: E402

REPORT = context_budget.measure(HARNESS_ROOT)


def test_umbrella_claude_md_stays_small():
    assert REPORT["claude_md_bytes"] <= 3000, REPORT["claude_md_bytes"]


def test_each_description_under_docs_cap():
    # Claude Code truncates description+when_to_use at 1,536 chars; stay well under.
    too_long = [i["name"] for i in REPORT["items"] if i["description_chars"] > 600]
    assert not too_long, too_long


def test_total_always_loaded_ceiling():
    assert REPORT["est_tokens_always_loaded"] <= 2400, REPORT["est_tokens_always_loaded"]


def test_user_only_commands_are_not_model_listed():
    hidden = {
        i["name"] for i in REPORT["items"] if i["kind"] == "command" and not i["listed"]
    }
    for name in ("new-project", "adopt-project", "sunset-project"):
        assert f"commands/{name}.md" in hidden
