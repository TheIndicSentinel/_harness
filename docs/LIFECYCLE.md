# Lifecycle map — which skill/command owns what

Moved out of the umbrella `CLAUDE.md` (which loads in every session of every project) so it costs nothing until you need it. Read this when asked "what skill does X" or when adopting an existing project.

- **Setup (plugin installs only):** `/harness-init`
- **Ideation → spec:** `idea-brainstorm` → `market-research` → `prd-writer`
- **Build quality:** `qa-review`
- **Ship:** `release-notes` → `launch-checklist` / `/ship` (release gates enforced by `hooks/release_gate.py`)
- **Legal:** `compliance-review`
- **Post-launch:** `incident-response` (fires), `support-triage` (feedback), `weekly-review` / `/weekly-review` (roadmaps, success criteria, risks, docs freshness)
- **Business:** `pricing-strategy`, `gtm-marketing`, `/cost-report`
- **Every working session:** `/wrap-up`
- **End-of-life:** `/sunset-project`

## Gates in detail
`release_gate.py` (a `PreToolUse` hook) checks `<project>/.harness/gates.json` before any ship-shaped Bash command or deploy/publish/release MCP tool. Every required gate needs a pass tied to the *current* git commit (a stale pass doesn't count) and the working tree must be clean. `privacy_guardrails_review` is always required; a project opts into more via `gate_write.py --require` (e.g. `qa_review`, `compliance_review`). Never remove a gate from `required_gates` to unblock a ship. The hook is cooperative-path policy, not a security boundary — CI (`harness_gate_check.py`) is the independent check.

## Existing projects (not scaffolded by `/new-project`)
Umbrella rules and hooks apply automatically. Run `/adopt-project` once to add the missing standard docs (PRD, MARKETING, COST_LOG, RELEASE_CHECKLIST, ROADMAP, CHANGELOG, OPERATIONS, BUSINESS, COMPLIANCE, CONNECTORS, plus the CI gate-check workflow, CODEOWNERS and secrets-deny settings). It only creates files that don't exist and never touches the project's own `CLAUDE.md`.

## Editing the harness itself
See `.claude/rules/harness-development.md` (loads only inside `_harness/`).
