---
name: incident-response
description: Structured handling of a live problem in a shipped build — triage, mitigate/rollback per the project's runbook, then a blameless postmortem in docs/OPERATIONS.md with prevention items pushed to the roadmap. Use when the user reports "the release is broken", "users are crashing", "something's wrong in production", or after any bad release, even if the immediate fire is already out.
---

# Incident Response

Order matters: stabilize first, understand second, document third. Don't start root-causing while users are broken.

## Process

1. **Triage.** Establish impact in one or two questions: what's broken, since which version/commit, how many users (or "unknown — no telemetry, going by reports"). Severity: users blocked vs. degraded vs. cosmetic.
2. **Mitigate.** Open `docs/OPERATIONS.md` → "Release & rollback runbook" and follow it. Rolling back a known-good artifact beats debugging forward under pressure — recommend rollback whenever the runbook makes it cheap. Any republish/redeploy action still gets explicit user confirmation (standing rule; the release gate also still applies to the rollback publish itself).
3. **Root-cause** only after stable. Normal debugging; keep notes as you go — they become the timeline.
4. **Postmortem.** Append an incident section to `docs/OPERATIONS.md` (format is in the file: impact, timeline, root cause, fix, prevention). Blameless and specific — "the default was unsafe" not "we were careless". Write it within the session if possible; a week later it won't happen.
5. **Prevention items become roadmap items.** Each prevention follow-up goes into `ROADMAP.md` "Now/Next" — a postmortem whose actions live only in the postmortem is decoration. If the incident revealed a gate gap (something the privacy/QA review should have caught), also update the relevant review's memory entry so the next review looks for it.

## Example

**Input:** "v1.0.31 is crashing on launch for Samsung users."

**Output (after mitigation):** "Rolled back: re-published v1.0.30 APK from the kept artifact (you confirmed the publish). Root cause: OneUI-specific NPE in the new notification path. Postmortem written to OPERATIONS.md; prevention items added to ROADMAP Now: (1) add Samsung device to pre-release manual checklist, (2) guard the notification call. Fix branch ready to review."
