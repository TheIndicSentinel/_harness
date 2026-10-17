import json
import os

import compat_check

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Event names from the official hooks reference, checked 2026-10-15.
KNOWN_HOOK_EVENTS = {
    "SessionStart", "Setup", "SessionEnd", "UserPromptSubmit", "UserPromptExpansion", "Stop",
    "StopFailure", "PreToolUse", "PermissionRequest", "PermissionDenied", "PostToolUse",
    "PostToolUseFailure", "PostToolBatch", "SubagentStart", "SubagentStop", "TaskCreated",
    "TaskCompleted", "TeammateIdle", "InstructionsLoaded", "ConfigChange", "CwdChanged",
    "DirectoryAdded", "FileChanged", "PreCompact", "PostCompact", "PreModelSwitch",
    "PostModelSwitch", "Notification", "MessageDisplay", "Elicitation", "ElicitationResult",
    "WorktreeCreate", "WorktreeRemove",
}


def test_wired_hook_events_are_documented_events():
    for rel in ("hooks/hooks.json", "settings.json"):
        with open(os.path.join(ROOT, rel)) as f:
            events = set(json.load(f).get("hooks", {}))
        assert events <= KNOWN_HOOK_EVENTS, (rel, events - KNOWN_HOOK_EVENTS)


def test_hook_timeouts_cover_the_verify_command_cap():
    import verify_lib

    with open(os.path.join(ROOT, "hooks/hooks.json")) as f:
        stop = json.load(f)["hooks"]["Stop"][0]["hooks"][0]
    assert stop["timeout"] > verify_lib.MAX_TIMEOUT


def test_parse_version_and_feature_report():
    assert compat_check.parse_version("2.1.285 (Claude Code)") == (2, 1, 285)
    assert compat_check.parse_version("garbage") is None
    old = "\n".join(compat_check.report((2, 1, 285)))
    new = "\n".join(compat_check.report((2, 1, 300)))
    newer = "\n".join(compat_check.report((2, 1, 301)))
    assert "[ ] hook onFailure" in old and "[x] hook onFailure" in new
    assert "older than the audited" in old and "newer than the audited" in newer


def _hook(cmd, on_failure=None):
    h = {"type": "command", "command": cmd, "timeout": 10}
    if on_failure:
        h["onFailure"] = on_failure
    return {"matcher": "Bash", "hooks": [h]}


def test_settings_drift_detects_missing_hook_and_deny_rule(tmp_path):
    import settings_lib

    template = {"hooks": {"PreToolUse": [_hook('python3 "$H/hooks/release_gate.py"', "block")]},
                "permissions": {"deny": ["Read(**/.env)", "Edit(**/.env)"]}}
    live_ok = {"model": "sonnet", **template}
    live_old = {"hooks": {"PreToolUse": [_hook('python3 "$H/hooks/release_gate.py"')]},
                "permissions": {"deny": ["Read(**/.env)"]}}
    t, a, b = tmp_path / "t.json", tmp_path / "a.json", tmp_path / "b.json"
    t.write_text(json.dumps(template)); a.write_text(json.dumps(live_ok)); b.write_text(json.dumps(live_old))
    assert settings_lib.settings_drift(str(t), str(a)) == []          # extra personal keys are fine
    problems = settings_lib.settings_drift(str(t), str(b))
    assert any("release_gate.py" in p for p in problems) and any("deny" in p for p in problems)


def test_settings_drift_not_applicable_without_harness_hooks(tmp_path):
    import settings_lib

    t, live = tmp_path / "t.json", tmp_path / "l.json"
    t.write_text(json.dumps({"hooks": {"PreToolUse": [_hook('python3 "$H/hooks/release_gate.py"')]}}))
    live.write_text(json.dumps({"hooks": {}}))   # plugin install: hooks come from hooks.json
    assert settings_lib.settings_drift(str(t), str(live)) is None


def test_fail_closed_policy_is_on_release_gate_only():
    """onFailure=block belongs on the release gate. It must NOT be on the secrets guard
    (a crash there would lock out Read/Edit, the recovery path) and has no effect on Stop."""
    for rel in ("hooks/hooks.json", "settings.json"):
        with open(os.path.join(ROOT, rel)) as f:
            hooks = json.load(f)["hooks"]
        import re
        seen = {}
        for entries in hooks.values():
            for e in entries:
                for h in e["hooks"]:
                    seen[re.search(r"(\w+\.py)", h["command"]).group(1)] = h.get("onFailure")
        assert seen["release_gate.py"] == "block", rel
        assert seen["secrets_guard.py"] is None, rel
        assert seen["verify_before_stop.py"] is None, rel
