---
name: market-research
description: Competitive and market-demand research for a product idea, delegated to a read-only research subagent so raw search results don't bloat the main conversation. Use whenever the user wants to know who competitors are, whether there's demand for an idea, how an existing market works, or says things like "research this", "who else does this", "is there a market for X". Typically follows idea-brainstorm and precedes prd-writer.
---

# Market Research

Delegate the actual searching to the `market-researcher` subagent (read-only: WebSearch/WebFetch/Read, no writes) rather than doing broad web research inline — this keeps raw search results out of the main thread's context, which matters for token efficiency across a long project session.

## Process

1. Identify the idea being researched. If it's ambiguous, ask one clarifying question rather than guessing.
2. Launch the `market-researcher` subagent with a specific brief: the idea, the target user (if known from a prior brainstorm), and what you want back (competitors, demand signals, privacy-angle opening).
3. Wait for the synthesis, don't have it stream raw results into the main conversation.
4. Write the findings into the project's docs:
   - If `docs/PRD.md` exists and has a market/competition section, fill it there.
   - Otherwise create `docs/RESEARCH.md` with the synthesis (competitor table, demand signals, sourced links, and the recommended opening/positioning).
5. Summarize back to the user in a few sentences — don't just say "done, see the file." Call out the single most important finding (e.g. "all three competitors are cloud-only, which is your opening if you go offline-first").

## Example

**Input:** "Research the market for an offline mandi price checker."

**Output (synthesis handed back to the user, not the raw subagent dump):** "3 direct competitors, all requiring continuous internet and a phone-number account (AgriApp, Kisan Suvidha, DeHaat's price module) — every one of them has App Store reviews complaining about connectivity failures in low-signal areas. That's the opening: none of them work offline. No competitor found handling this without an account. Full table and sources in docs/RESEARCH.md."

## When there's no project yet
If this idea hasn't been scaffolded with `/new-project` yet, still run the research, but hold the findings in the conversation and suggest `/new-project` once research supports building — don't create files with nowhere to live.
