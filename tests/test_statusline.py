import json
import os
import statistics
import subprocess
import sys
import time

SCRIPT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts", "statusline.py")
sys.path.insert(0, os.path.dirname(SCRIPT))
import statusline  # noqa: E402

FULL = {"model": {"id": "claude-x", "display_name": "Sonnet 5.5"}, "cost": {"total_cost_usd": 0.4213},
        "context_window": {"used_percentage": 23.4}, "prompt_cache": {"hit_ratio": 0.974}}


def run(payload, raw=None):
    return subprocess.run([sys.executable, SCRIPT], input=raw if raw is not None else json.dumps(payload),
                          capture_output=True, text=True, timeout=10)


def test_full_payload():
    assert statusline.render(FULL) == "ctx 23% · cache 97% · $0.42 · Sonnet 5.5"


def test_missing_and_null_fields_are_omitted_not_guessed():
    d = json.loads(json.dumps(FULL))
    d["prompt_cache"] = None                                  # before the first response / older Claude Code
    d["context_window"]["used_percentage"] = None             # early in a session
    assert statusline.render(d) == "$0.42 · Sonnet 5.5"
    assert statusline.render({"model": {"id": "claude-x"}}) == "claude-x"
    assert statusline.render({}) == ""


def test_zero_values_are_shown_and_booleans_are_not_numbers():
    d = {"context_window": {"used_percentage": 0}, "cost": {"total_cost_usd": 0}, "prompt_cache": {"hit_ratio": True}}
    assert statusline.render(d) == "ctx 0% · $0.00"


def test_wrong_shapes_print_nothing():
    assert statusline.render([1, 2]) == ""
    assert statusline.render({"model": "Sonnet", "cost": 3, "context_window": "x"}) == ""


def test_any_error_prints_nothing_and_exits_zero():
    for raw in ("", "not json", "[]", "null", "\xff"):
        r = run(None, raw=raw)
        assert r.returncode == 0 and r.stdout == "" and r.stderr == ""


def test_cli_end_to_end_and_fast():
    r = run(FULL)
    assert r.stdout == "ctx 23% · cache 97% · $0.42 · Sonnet 5.5\n" and r.returncode == 0
    times = []
    for _ in range(5):
        t = time.perf_counter()
        run(FULL)
        times.append(time.perf_counter() - t)
    assert statistics.median(times) < 0.5       # loose bound for slow CI; the real figure is reported in the docs


def test_script_does_not_touch_files_or_network():
    src = open(SCRIPT).read()
    code = src.split('"""', 2)[2]               # everything after the docstring
    for banned in ("open(", "socket", "urllib", "requests", "subprocess", "transcript_path"):
        assert banned not in code, banned
