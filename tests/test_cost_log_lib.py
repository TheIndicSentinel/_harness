import os
import sys

HOOKS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hooks")
sys.path.insert(0, HOOKS)
import cost_log_lib as cl  # noqa: E402

LEGACY = (
    "# P - Session / Cost Log\n\nintro line\n\n"
    "| Date | Session ID | Duration | Est. tokens (in/out) | Cache read |\n"
    "|------|-----------|----------|------------------------|------------|\n"
    "| 2026-09-30 | bd6b4656 | 1m40s | 22469/1698 | 231957 |\n"
    "| 2026-10-02 | 4fc63604 | n/a | n/a | n/a |\n"
    "| 2026-10-14 | eb29e2a7 | 18854m44s | 7713731/298764 | 47139431 |\n"
    "| 2026-10-14 | eb29e2a7 | 21891m49s | 18356276/5376205 | 2601123738 |\n"
    "| 2026-10-18 | eb29e2a7 | 4681m43s | 21197922/5676940 | feat/x | 9 |\n"
    "| 2026-10-18 | 88853438 | 0m00s | n/a | - | - |\n")


def test_parse_row_handles_the_three_shapes():
    five = cl.parse_row("| 2026-09-30 | bd6b4656 | 1m40s | 22469/1698 | 231957 |")
    six = cl.parse_row("| 2026-10-18 | eb29e2a7 | 4681m43s | 21197922/5676940 | feat/x | 9 |")
    seven = cl.parse_row("| 2026-10-18 | eb29e2a7 | 4m | 1/2 | 55 | feat/x | 9 |")
    assert (five["cache_read"], five["branch"], five["legacy_duration"], five["in"], five["out"]) == ("231957", "-", True, 22469, 1698)
    assert (six["cache_read"], six["branch"], six["orient"], six["legacy_duration"]) == ("-", "feat/x", "9", False)
    assert (seven["cache_read"], seven["branch"], seven["orient"]) == ("55", "feat/x", "9")
    assert cl.parse_row("| 2026-10-02 | x | n/a | n/a | n/a |")["in"] is None
    for not_a_row in ("", "| Date | Session ID |", "|---|---|", "prose", "| 2026-1 | a | b | c |"):
        assert cl.parse_row(not_a_row) is None


def test_migration_is_lossless_consistent_and_idempotent():
    new = cl.migrate_text(LEGACY)
    assert new.count(cl.HEADER) == 1 and new.splitlines().count(cl.SEP) == 1 and "intro line" in new and cl.NOTE in new
    old_rows = [cl.parse_row(l) for l in LEGACY.splitlines() if cl.parse_row(l)]
    new_rows = [cl.parse_row(l) for l in new.splitlines() if cl.parse_row(l)]
    assert len(old_rows) == len(new_rows) == 6
    for o, n in zip(old_rows, new_rows):
        for k in ("date", "session", "tokens", "cache_read", "branch", "orient"):
            assert o[k] == n[k], (k, o, n)                   # every value survives in its own column
        assert n["active"].startswith(o["active"])           # wall-clock duration kept, only marked
    assert all(len(l.strip().strip("|").split("|")) == 7 for l in new.splitlines() if l.startswith("| 20"))
    assert "1m40s wall" in new and "| 4fc63604 | n/a |" in new            # unknown duration is not marked
    assert cl.migrate_text(new) == new                       # second pass changes nothing


def test_headerless_rows_get_a_header():
    new = cl.migrate_text("| 2026-10-01 | a | 1m | 5/5 |\n")
    assert new.startswith(cl.HEADER) and "| 2026-10-01 | a | 1m | 5/5 | - | - | - |" in new


def test_latest_row_per_session_wins_and_unknown_is_never_merged():
    rows = [cl.parse_row(l) for l in cl.migrate_text(LEGACY).splitlines() if cl.parse_row(l)]
    latest = cl.latest_per_session(rows)
    assert [r["session"] for r in latest] == ["bd6b4656", "4fc63604", "eb29e2a7", "88853438"]
    assert [r for r in latest if r["session"] == "eb29e2a7"][0]["in"] == 21197922      # not the 3-row sum
    two_unknown = [cl.parse_row("| 2026-10-01 | unknown | 1m | 1/1 |"), cl.parse_row("| 2026-10-02 | unknown | 1m | 2/2 |")]
    assert len(cl.latest_per_session(two_unknown)) == 2


def test_ensure_canonical_backs_up_once_and_leaves_canonical_files_alone(tmp_path):
    p = tmp_path / "cost" / "p.md"
    p.parent.mkdir()
    p.write_text(LEGACY)
    assert cl.ensure_canonical(str(p)) is True
    assert cl.ensure_canonical(str(p)) is False
    backups = list((p.parent / ".pre-migration").iterdir())
    assert len(backups) == 1 and backups[0].read_text() == LEGACY
    assert cl.read_rows(str(tmp_path / "missing.md")) == []
