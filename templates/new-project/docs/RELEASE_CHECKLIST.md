# {{PROJECT_NAME}} — Release Checklist

Run `/ship` (or the `launch-checklist` skill directly) to walk this end to end. The privacy/guardrails item below is mechanically enforced — see `~/Documents/Projects/CLAUDE.md` — a real publish/deploy/release command will be blocked until it passes for the current commit.

## Before shipping
- [ ] Privacy review — data collected matches what's disclosed to the user, nothing extra
- [ ] Guardrails review — abuse/misuse paths considered for any user input surface
- [ ] Secrets check — no keys, tokens, or credentials committed
- [ ] Crash/error monitoring in place (or explicitly deferred, with a reason)
- [ ] Rollback plan if the release breaks something

## Launch
- [ ] Marketing/GTM plan reviewed — see [MARKETING.md](MARKETING.md)
- [ ] Support channel ready for user feedback/bug reports
