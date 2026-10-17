import json
import os
import pathlib
import subprocess
import sys

import session_log

HOOK_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hooks", "session_log.py"
)


def write_transcript(path, entries):
    with open(path, "w") as f:
        for e in entries:
            f.write(json.dumps(e) + "\n")


def assistant(msg_id, ts, inp, out, cache_write=0, cache_read=0):
    return {
        "timestamp": ts,
        "message": {
            "id": msg_id,
            "usage": {
                "input_tokens": inp,
                "output_tokens": out,
                "cache_creation_input_tokens": cache_write,
                "cache_read_input_tokens": cache_read,
            },
        },
    }


class TestSummarizeTranscript:
    def test_counts_cache_writes_in_input_and_cache_reads_separately(self, tmp_path):
        t = tmp_path / "t.jsonl"
        write_transcript(t, [assistant("m1", "2026-09-29T10:00:00Z", 5, 100, cache_write=2000, cache_read=30000)])
        assert session_log.summarize_transcript(str(t)) == ("0m00s", "2005/100", "30000")

    def test_repeated_message_id_counted_once_with_final_usage(self, tmp_path):
        """The transcript writes one line per content block of the same
        message, each carrying that message's usage -- summing every line
        multiplied the count."""
        t = tmp_path / "t.jsonl"
        write_transcript(t, [
            assistant("m1", "2026-09-29T10:00:00Z", 10, 1, cache_read=500),
            assistant("m1", "2026-09-29T10:00:05Z", 10, 40, cache_read=500),
            assistant("m2", "2026-09-29T10:02:05Z", 3, 7, cache_read=900),
        ])
        assert session_log.summarize_transcript(str(t)) == ("2m05s", "13/47", "1400")

    def test_no_usage_is_na(self, tmp_path):
        t = tmp_path / "t.jsonl"
        write_transcript(t, [{"timestamp": "2026-09-29T10:00:00Z", "type": "user"}])
        assert session_log.summarize_transcript(str(t)) == ("0m00s", "n/a", "n/a")


class TestHook:
    def test_appends_one_row_parseable_by_budget(self, tmp_path):
        import budget_lib

        proj = tmp_path / "proj"
        proj.mkdir()
        t = tmp_path / "t.jsonl"
        write_transcript(t, [assistant("m1", "2026-09-29T10:00:00Z", 5, 100, cache_write=95, cache_read=9999)])
        env = {**os.environ, "CLAUDE_HARNESS_PROJECTS_ROOT": str(tmp_path)}
        payload = {"cwd": str(proj), "session_id": "abcdef123456", "transcript_path": str(t)}
        result = subprocess.run(
            [sys.executable, HOOK_PATH], input=json.dumps(payload), capture_output=True, text=True, env=env
        )
        assert result.returncode == 0
        log = (tmp_path / "_harness_data" / "cost" / "proj.md").read_text()
        assert not (proj / "docs" / "COST_LOG.md").exists()  # nothing written into the repo
        rows = [l for l in log.splitlines() if l.startswith("| 20")]
        assert len(rows) == 1
        assert "| abcdef12 |" in rows[0] and "| 100/100 |" in rows[0] and "9999" not in rows[0]
        # Cache reads stay out of the budget total.
        assert budget_lib.tokens_used_this_month(str(proj)) == 200


class TestRelocatedLog:
    def _run(self, tmp_path, proj, transcript):
        env = {**os.environ, "CLAUDE_HARNESS_PROJECTS_ROOT": str(tmp_path)}
        payload = {"cwd": str(proj), "session_id": "abcdef123456", "transcript_path": str(transcript)}
        return subprocess.run(
            [sys.executable, HOOK_PATH], input=json.dumps(payload), capture_output=True, text=True, env=env
        )

    def test_active_time_ignores_idle_gaps(self, tmp_path):
        t = tmp_path / "t.jsonl"
        write_transcript(t, [
            assistant("m1", "2026-09-29T10:00:00Z", 1, 1),
            assistant("m2", "2026-09-29T10:05:00Z", 1, 1),   # 5 min active
            assistant("m3", "2026-10-12T10:00:00Z", 1, 1),   # 13 days idle: excluded
            assistant("m4", "2026-10-12T10:02:00Z", 1, 1),   # 2 min active
        ])
        duration, _, _ = session_log.summarize_transcript(str(t))
        assert duration == "7m00s"

    def test_legacy_in_repo_log_is_migrated_and_left_in_place(self, tmp_path):
        proj = tmp_path / "proj"
        (proj / "docs").mkdir(parents=True)
        legacy = proj / "docs" / "COST_LOG.md"
        legacy.write_text("| Date | Session ID | Duration | Est. tokens (in/out) | Cache read |\n"
                          "|--|--|--|--|--|\n| 2026-09-01 | old00000 | 1m00s | 10/10 | 5 |\n")
        t = tmp_path / "t.jsonl"
        write_transcript(t, [assistant("m1", "2026-09-29T10:00:00Z", 5, 100)])
        assert self._run(tmp_path, proj, t).returncode == 0
        new = (tmp_path / "_harness_data" / "cost" / "proj.md").read_text()
        assert "old00000" in new and "abcdef12" in new          # history kept + new row
        assert "abcdef12" not in legacy.read_text()              # repo copy untouched

    def test_budget_prefers_new_location_over_legacy(self, tmp_path):
        import budget_lib, gate_lib
        proj = tmp_path / "proj"
        (proj / "docs").mkdir(parents=True)
        today = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).strftime("%Y-%m-%d")
        (proj / "docs" / "COST_LOG.md").write_text(f"| {today} | a | 1m | 1000/1000 |\n")
        new = pathlib.Path(gate_lib.cost_log_path(str(proj)))
        new.parent.mkdir(parents=True)
        new.write_text(f"| {today} | b | 1m | 5/5 |\n")
        assert budget_lib.tokens_used_this_month(str(proj)) == 10


class TestBranchColumn:
    def test_row_carries_branch_and_stays_budget_parseable(self, tmp_path):
        import budget_lib
        proj = tmp_path / "proj"
        proj.mkdir()
        subprocess.run(["git", "init", "-q", "-b", "feat/my-task"], cwd=proj, check=True)
        subprocess.run(["git", "-c", "user.email=t@e.x", "-c", "user.name=t", "commit", "-q",
                        "--allow-empty", "-m", "i"], cwd=proj, check=True)
        t = tmp_path / "t.jsonl"
        write_transcript(t, [assistant("m1", "2026-09-29T10:00:00Z", 5, 100)])
        env = {**os.environ, "CLAUDE_HARNESS_PROJECTS_ROOT": str(tmp_path)}
        payload = {"cwd": str(proj), "session_id": "abcdef123456", "transcript_path": str(t)}
        r = subprocess.run([sys.executable, HOOK_PATH], input=json.dumps(payload),
                           capture_output=True, text=True, env=env)
        assert r.returncode == 0
        log = (tmp_path / "_harness_data" / "cost" / "proj.md").read_text()
        row = [l for l in log.splitlines() if l.startswith("| 20")][0]
        assert "| feat/my-task |" in row
        assert "| Branch |" in log
        assert budget_lib.tokens_used_this_month(str(proj)) == 105


class TestOrientation:
    def _t(self, tmp_path, blocks):
        t = tmp_path / "t.jsonl"
        with open(t, "w") as f:
            for i, (name) in enumerate(blocks):
                f.write(json.dumps({"message": {"id": f"m{i}", "content": [
                    {"type": "tool_use", "id": f"tu{i}", "name": name}]}}) + "\n")
        return str(t)

    def test_counts_reads_before_first_edit(self, tmp_path):
        t = self._t(tmp_path, ["Read", "Grep", "Bash", "Glob", "Edit", "Read", "Read"])
        assert session_log.orientation_calls(t) == "3"

    def test_no_edit_means_no_measurement(self, tmp_path):
        assert session_log.orientation_calls(self._t(tmp_path, ["Read", "Read"])) == "-"

    def test_missing_transcript(self):
        assert session_log.orientation_calls("/nonexistent") == "-"


class TestShellReadOrientation:
    """Regression for the undercount: models explore through Bash, so a session
    with 8 shell reads before its first edit used to report Orient 0."""

    def _t(self, tmp_path, calls):
        t = tmp_path / "t.jsonl"
        with open(t, "w") as f:
            for i, (name, command) in enumerate(calls):
                block = {"type": "tool_use", "id": f"tu{i}", "name": name}
                if command is not None:
                    block["input"] = {"command": command}
                f.write(json.dumps({"message": {"id": f"m{i}", "content": [block]}}) + "\n")
        return str(t)

    def test_shell_reads_count_old_definition_does_not(self, tmp_path):
        t = self._t(tmp_path, [
            ("Bash", "cat src/a.py"),
            ("Bash", "grep -rn authorize src | head -20"),
            ("Bash", "cd src && rg -n 'def ' pipeline.py"),
            ("Bash", "ls -la tests"),
            ("Bash", "find . -name '*.py'"),
            ("Bash", "sed -n 1,40p src/a.py"),
            ("Bash", "head -5 README.md"),
            ("Edit", None),
        ])
        assert session_log.orientation_calls(t) == "7"
        assert session_log.orientation_calls(t, include_shell_reads=False) == "0"

    def test_writes_and_non_reads_are_not_orientation(self, tmp_path):
        t = self._t(tmp_path, [
            ("Bash", "sed -i 's/a/b/' src/a.py"),
            ("Bash", "cat > notes.txt <<'EOF'\nhello\nEOF"),
            ("Bash", "python3 -m unittest discover -s tests"),
            ("Bash", "git status --short"),
            ("Bash", "echo cat"),
            ("Edit", None),
        ])
        assert session_log.orientation_calls(t) == "0"

    def test_mixed_tools_and_compound_commands(self, tmp_path):
        t = self._t(tmp_path, [
            ("Read", None),
            ("Bash", "FOO=1 grep -n x file"),     # leading assignment is skipped
            ("Bash", "make build && cat out.txt"),  # one read segment -> one call
            ("Grep", None),
            ("Write", None),
            ("Bash", "cat after_edit.txt"),         # after the first edit: ignored
        ])
        assert session_log.orientation_calls(t) == "4"

    def test_is_shell_read_unit(self):
        assert session_log.is_shell_read("ls")
        assert session_log.is_shell_read("cd x; head -3 y")
        assert not session_log.is_shell_read("sed --in-place s/a/b/ f")
        assert not session_log.is_shell_read("grep x f > out.txt")
        assert not session_log.is_shell_read("")
