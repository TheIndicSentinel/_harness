---
name: prd-writer
description: Turns a validated idea (from brainstorming and/or market research) into a filled-out docs/PRD.md for the current project. Use when the user asks to "write a PRD", "spec this out", "turn this into a spec/doc", or when an idea has been sufficiently discussed and is ready to be committed to a document. Comes after idea-brainstorm/market-research, before real build work starts.
---

# PRD Writer

Every project scaffolded by `/new-project` already has a `docs/PRD.md` skeleton (Problem, Idea, Target user, Success criteria, Privacy & guardrails considerations, Out of scope, Open questions). Your job is to fill it in well, not to invent a new structure.

## Process

1. Confirm you're in a project directory with `docs/PRD.md`. If the file doesn't exist, either the project hasn't been scaffolded (suggest `/new-project` first) or this is an older project — in that case create `docs/PRD.md` using the same section headers as the template at `~/Documents/Projects/_harness/templates/new-project/docs/PRD.md`.
2. Pull from conversation context: prior brainstorming, any `docs/RESEARCH.md` or research notes already in the project, and anything the user states directly now.
3. Fill every section with specifics, not placeholders. "Success criteria" must be something checkable (a number, an event, a threshold) — push back gently if the user gives you something unfalsifiable like "people like it."
4. The "Privacy & guardrails considerations" section is not optional filler — this is a standing requirement of every project in this harness (see `~/Documents/Projects/CLAUDE.md`). Name the actual data touched and the minimum needed, even if the answer is "none."
5. Leave genuinely open questions in "Open questions" rather than inventing answers to sound complete.
6. Show the filled PRD back to the user for a quick sanity check before considering it done — this document will get referenced by `market-research`, `launch-checklist`, and `privacy-guardrails-review` later, so it's worth getting right once.
