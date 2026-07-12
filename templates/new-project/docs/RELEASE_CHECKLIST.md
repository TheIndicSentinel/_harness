# {{PROJECT_NAME}} — Release Checklist

Honor-system for now (see `~/Documents/Projects/CLAUDE.md` — hard-block gate enforcement is Phase 2 of the harness, not yet wired up).

## Before shipping
- [ ] Privacy review — data collected matches what's disclosed to the user, nothing extra
- [ ] Guardrails review — abuse/misuse paths considered for any user input surface
- [ ] Secrets check — no keys, tokens, or credentials committed
- [ ] Crash/error monitoring in place (or explicitly deferred, with a reason)
- [ ] Rollback plan if the release breaks something

## Launch
- [ ] Marketing/GTM plan reviewed — see [MARKETING.md](MARKETING.md)
- [ ] Support channel ready for user feedback/bug reports
