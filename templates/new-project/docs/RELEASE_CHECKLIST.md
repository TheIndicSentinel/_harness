# {{PROJECT_NAME}} — Release Checklist

Run `/ship` (or the `launch-checklist` skill directly) to walk this end to end. Gated items are mechanically enforced — see `~/Documents/Projects/CLAUDE.md` — a real publish/deploy/release command will be blocked until every gate in `.harness/gates.json`'s `required_gates` passes for the current commit (`privacy_guardrails_review` always; add `qa_review` / `compliance_review` there to hard-gate them too).

## Before shipping
- [ ] Privacy review — data collected matches what's disclosed to the user, nothing extra (GATED)
- [ ] Guardrails review — abuse/misuse paths considered for any user input surface (GATED, same review)
- [ ] QA review — tests pass, changed surfaces exercised, dependency vulnerabilities checked (`qa-review` skill)
- [ ] Compliance current — privacy policy matches code, store/regulatory items reviewed (`compliance-review` skill / [COMPLIANCE.md](COMPLIANCE.md))
- [ ] Secrets check — no keys, tokens, or credentials committed
- [ ] Version bumped + [CHANGELOG.md](CHANGELOG.md) updated (`release-notes` skill)
- [ ] Crash/error monitoring in place (or explicitly deferred, with a reason)
- [ ] Rollback plan current in [OPERATIONS.md](OPERATIONS.md) runbook

## Launch
- [ ] Marketing/GTM plan reviewed — see [MARKETING.md](MARKETING.md)
- [ ] Support channel ready — see [OPERATIONS.md](OPERATIONS.md)

## Post-launch (scheduled, not fire-and-forget)
- [ ] Success-criteria check scheduled — [ROADMAP.md](ROADMAP.md) table, first review at +2 weeks
