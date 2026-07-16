import os

import harness_status as hs


def write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(content)


class TestReleaseCommandStatus:
    def test_no_operations_md_returns_none(self, git_repo):
        assert hs.release_command_status(str(git_repo)) is None

    def test_unfilled_field_returns_empty_string(self, git_repo):
        write(
            os.path.join(git_repo, "docs", "OPERATIONS.md"),
            "## Release & rollback runbook\n- **Release command:**\n- **Rollback procedure:** (exact steps)\n",
        )
        assert hs.release_command_status(str(git_repo)) == ""

    def test_filled_field_returns_value(self, git_repo):
        write(
            os.path.join(git_repo, "docs", "OPERATIONS.md"),
            "## Release & rollback runbook\n- **Release command:** `npm publish`\n",
        )
        assert hs.release_command_status(str(git_repo)) == "`npm publish`"


class TestRollbackRunbookFilled:
    def test_no_operations_md_returns_none(self, git_repo):
        assert hs.rollback_runbook_filled(str(git_repo)) is None

    def test_template_placeholder_is_not_filled(self, git_repo):
        write(
            os.path.join(git_repo, "docs", "OPERATIONS.md"),
            '- **Rollback procedure:** (exact steps — e.g. "re-publish previous APK kept at <path>")\n',
        )
        assert hs.rollback_runbook_filled(str(git_repo)) is False

    def test_real_content_is_filled(self, git_repo):
        write(
            os.path.join(git_repo, "docs", "OPERATIONS.md"),
            "- **Rollback procedure:** re-publish previous version from npm dist-tags\n",
        )
        assert hs.rollback_runbook_filled(str(git_repo)) is True

    def test_missing_field_is_not_filled(self, git_repo):
        write(os.path.join(git_repo, "docs", "OPERATIONS.md"), "## Release & rollback runbook\n")
        assert hs.rollback_runbook_filled(str(git_repo)) is False


class TestConnectorsReviewed:
    def test_no_connectors_md_returns_none(self, git_repo):
        assert hs.connectors_reviewed(str(git_repo)) is None

    def test_empty_table_is_not_reviewed(self, git_repo):
        write(
            os.path.join(git_repo, "docs", "CONNECTORS.md"),
            "## Approved connectors\n"
            "| Name | Source | Version/commit | Scope | Risk tier | Reviewed | Next review |\n"
            "|------|--------|-----------------|-------|-----------|----------|--------------|\n",
        )
        assert hs.connectors_reviewed(str(git_repo)) is False

    def test_table_with_data_row_is_reviewed(self, git_repo):
        write(
            os.path.join(git_repo, "docs", "CONNECTORS.md"),
            "## Approved connectors\n"
            "| Name | Source | Version/commit | Scope | Risk tier | Reviewed | Next review |\n"
            "|------|--------|-----------------|-------|-----------|----------|--------------|\n"
            "| GitHub MCP | github.com/x | v1.2.0 | read-only | low | 2026-07-01 | 2026-10-01 |\n",
        )
        assert hs.connectors_reviewed(str(git_repo)) is True


class TestRiskTier:
    def test_no_compliance_md_returns_none(self, git_repo):
        assert hs.risk_tier(str(git_repo)) is None

    def test_template_placeholder_is_undecided(self, git_repo):
        write(
            os.path.join(git_repo, "docs", "COMPLIANCE.md"),
            "## Risk tier\n- **Tier:** consumer / startup / regulated — default **consumer**\n",
        )
        assert "undecided" in hs.risk_tier(str(git_repo))

    def test_decided_tier_is_returned(self, git_repo):
        write(os.path.join(git_repo, "docs", "COMPLIANCE.md"), "## Risk tier\n- **Tier:** startup\n")
        assert hs.risk_tier(str(git_repo)) == "startup"


class TestProjectStage:
    def test_no_claude_md_returns_none(self, git_repo):
        assert hs.project_stage(str(git_repo)) is None

    def test_no_checked_stage_returns_none(self, git_repo):
        write(
            os.path.join(git_repo, "CLAUDE.md"),
            "## Project status\n- [ ] Stage 0: Idea\n- [ ] Stage 1: Research\n",
        )
        assert hs.project_stage(str(git_repo)) is None

    def test_checked_stage_is_returned(self, git_repo):
        write(
            os.path.join(git_repo, "CLAUDE.md"),
            "## Project status\n- [ ] Stage 0: Idea\n- [x] Stage 2: Building the MVP\n",
        )
        assert "Stage 2" in hs.project_stage(str(git_repo))


class TestReleaseCommandInClaudeMd:
    def test_no_claude_md_returns_none(self, git_repo):
        assert hs.release_command_in_claude_md(str(git_repo)) is None

    def test_template_placeholder_is_not_documented(self, git_repo):
        write(
            os.path.join(git_repo, "CLAUDE.md"),
            "## Key commands\n```bash\n# fill in: build, test, lint, run\n```\n",
        )
        assert hs.release_command_in_claude_md(str(git_repo)) is False

    def test_filled_in_commands_are_documented(self, git_repo):
        write(
            os.path.join(git_repo, "CLAUDE.md"),
            "## Key commands\n```bash\nnpm run build && npm test\n```\n",
        )
        assert hs.release_command_in_claude_md(str(git_repo)) is True


class TestCiGateStatus:
    def test_not_present(self, git_repo):
        assert hs.ci_gate_status(str(git_repo)) == "not present"

    def test_present_but_not_wired(self, git_repo):
        write(
            os.path.join(git_repo, ".github", "workflows", "harness-gate-check.yml"),
            "on:\n  workflow_call:\n",
        )
        write(
            os.path.join(git_repo, ".github", "workflows", "unrelated.yml"),
            "on: push\njobs:\n  build:\n    runs-on: ubuntu-latest\n",
        )
        assert hs.ci_gate_status(str(git_repo)) == "present but not wired into any workflow"

    def test_wired_into_a_workflow(self, git_repo):
        write(
            os.path.join(git_repo, ".github", "workflows", "harness-gate-check.yml"),
            "on:\n  workflow_call:\n",
        )
        write(
            os.path.join(git_repo, ".github", "workflows", "release.yml"),
            "jobs:\n  gate-check:\n    uses: ./.github/workflows/harness-gate-check.yml\n",
        )
        assert hs.ci_gate_status(str(git_repo)) == "wired into release.yml"


class TestProjectHealth:
    def test_all_checks_present_for_bare_project(self, git_repo):
        checks = hs.project_health(str(git_repo))
        labels = [label for label, _, _ in checks]
        assert "CI gate wired" in labels
        assert "Release command documented" in labels
        assert "Rollback runbook filled" in labels
        assert "Required gates chosen" in labels
        assert "Budget set or skipped" in labels
        assert "Connector registry reviewed" in labels

    def test_required_gates_always_counted_ok(self, git_repo):
        """Privacy-only is a valid, deliberate choice -- not a red flag."""
        checks = dict((label, is_ok) for label, _, is_ok in hs.project_health(str(git_repo)))
        assert checks["Required gates chosen"] is True

    def test_score_improves_as_things_get_filled_in(self, git_repo):
        import budget_lib

        before_ok, before_total = hs.project_health_score(str(git_repo))
        budget_lib.mark_budget_skipped(str(git_repo))
        after_ok, after_total = hs.project_health_score(str(git_repo))
        assert after_ok == before_ok + 1
        assert after_total == before_total
