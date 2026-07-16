# {{PROJECT_NAME}} — Operations

Runbook + incident history + support intake, in one place. The `incident-response` skill drives the incident sections; `support-triage` drives the feedback table.

## Release & rollback runbook
<!-- Fill once, keep current. The launch-checklist skill asks about this. -->
- **Release command:**
- **How to verify a release is healthy:** (what you check in the first hour, given no telemetry)
- **Rollback procedure:** (exact steps — e.g. "re-publish previous APK kept at <path>")
- **Previous-version artifact kept at:**

## Support channels
- **Where users reach you:** (e.g. in-app "Report a problem" email, GitHub Issues, store reviews)
- **Response target:** (honest, solo-realistic — e.g. "within 3 days")

## Feedback / bug triage log
Classify on intake: `bug` / `feature` / `question`. Anything accepted as work moves to [ROADMAP.md](ROADMAP.md); this table is the intake record, not the backlog.

| Date | Source | Type | Summary | Decision |
|------|--------|------|---------|----------|

## Incident log
One `###` section per incident, newest first. Postmortem format — blameless, written within a week of resolution:

### YYYY-MM-DD — <one-line title>
- **Impact:** who/what was affected, for how long
- **Timeline:** detected → mitigated → resolved
- **Root cause:**
- **Fix:**
- **Prevention:** (concrete follow-ups — add them to ROADMAP.md "Now/Next", don't leave them here to rot)
