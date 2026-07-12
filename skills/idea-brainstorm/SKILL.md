---
name: idea-brainstorm
description: Structured brainstorming and early validation for a new app idea — problem, target user, why-now, and the privacy/guardrails angle. Use this whenever the user floats a new product idea, asks "should I build X", wants to brainstorm, or is exploring a problem space before committing to it, even if they don't say the word "brainstorm" explicitly. This is the front door of the harness lifecycle — it comes before market-research, prd-writer, or /new-project.
---

# Idea Brainstorm

You're helping a solo entrepreneur who builds privacy-first, guardrail-first applications think through a new idea before committing engineering time to it. The goal of this skill is a sharper idea, not a finished plan — don't rush to `/new-project` until the idea can survive a few pointed questions.

## Process

1. **Diverge first.** If the user's idea is vague ("something for X"), help generate 2-4 concrete variations before narrowing. Don't just accept the first framing.
2. **Ask, don't assume, on these axes** (skip any the user has clearly already answered):
   - **Problem**: what's actually broken today, for whom, and how do you know?
   - **Target user**: specific enough to picture one real person, not "everyone who..."
   - **Why now**: why hasn't this been solved already, or why is now different?
   - **Privacy/guardrails angle**: what data would this touch, and what's the minimum needed? Is there an abuse/misuse surface worth naming early? (This project's standing default is privacy-by-default — see `~/Documents/Projects/CLAUDE.md`.)
3. **Converge.** Once the axes above have real answers, summarize the idea back in 3-4 sentences and ask if it's a fair restatement.
4. **Next step.** If the idea holds up, suggest one of: `market-research` (if competitive/demand signal is the open question), `prd-writer` (if the shape is clear enough to spec), or `/new-project <name> "<one-line idea>"` (if it's ready to become a real project directory).

## Example

**Input:** "I want to build something for farmers to check crop prices."

**Output (converged restatement, after the questioning):** "A voice-first, offline app for smallholder farmers in [specific region] to check mandi prices for their specific crops without needing continuous data connectivity — the gap being that existing price apps assume steady internet and text literacy, both unreliable assumptions for this user. Privacy angle: no location tracking needed beyond a one-time district selection, no account/phone-number requirement. Does this match what you're picturing?"

## What this skill is not
Don't write a PRD here — that's `prd-writer`. Don't do web research here — that's `market-research`. Keep this conversational and fast; a brainstorm that takes longer than the idea deserves is a smell.
