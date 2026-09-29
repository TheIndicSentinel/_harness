import json
import os
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
        log = (proj / "docs" / "COST_LOG.md").read_text()
        rows = [l for l in log.splitlines() if l.startswith("| 20")]
        assert len(rows) == 1
        assert "| abcdef12 |" in rows[0] and "| 100/100 | 9999 |" in rows[0]
        # Cache reads stay out of the budget total.
        assert budget_lib.tokens_used_this_month(str(proj)) == 200
