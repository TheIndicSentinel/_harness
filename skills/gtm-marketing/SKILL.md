---
name: gtm-marketing
description: Builds out positioning, launch channels, and messaging in docs/MARKETING.md, optionally researched via a subagent. Use when the user asks for a "marketing plan", "launch copy", "how should I announce this", "go to market strategy", or is approaching launch and hasn't thought about GTM yet.
---

# GTM / Marketing

## Process

1. Check whether real research is needed (unfamiliar market, unsure which channels fit) or whether the user already has a clear channel/audience in mind. If research would help, launch the `growth-marketer` subagent (read-only) with a brief: the product, target user, and what's already known from `docs/PRD.md`.
2. Fill `docs/MARKETING.md` (scaffolded by `/new-project`):
   - **Positioning**: one sentence, specific — who it's for and why they'd care. Favor the privacy/guardrails angle where it's a genuine differentiator, not as decoration.
   - **Launch channels**: concrete, ranked by fit for this specific audience, not a generic list.
   - **Messaging**: 2-3 core talking points.
   - **Post-launch**: how feedback gets gathered and acted on.
3. Draft actual launch copy if asked (a Product Hunt blurb, a launch tweet/post, a landing page pitch) — short, concrete, no marketing-speak filler.
4. Don't overclaim. If the product doesn't have a real privacy/security differentiator yet (e.g. it does collect data it shouldn't), don't market it as privacy-first — flag the mismatch back to the user instead of writing copy that isn't true.
