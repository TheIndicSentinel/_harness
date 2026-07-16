---
name: pricing-strategy
description: Pricing and monetization work for the current project — model choice, price points, unit economics — researched via the growth-marketer subagent and recorded in docs/BUSINESS.md. Use when the user asks "what should this cost", "how do I monetize", "pricing strategy", "should this be a subscription", or is adding a paywall/purchase flow.
---

# Pricing Strategy

Fills the "Pricing & monetization" and "Unit economics" sections of `docs/BUSINESS.md` (create from the harness template if missing). The standing privacy rule shapes this: monetization that requires tracking or new data collection (ad SDKs, behavioral analytics) is off the table unless the user explicitly overrides — surface that trade-off, don't bury it.

## Process

1. Establish the inputs: target user's price sensitivity (from PRD), real per-user costs (on-device = near zero marginal; API-backed = compute it), and what the product's willingness-to-pay driver actually is.
2. If comparable-product pricing is unknown, launch the `growth-marketer` subagent with a specific brief: category, target market/geography, and "what do comparable products charge, in what model" — keep raw research out of the main thread.
3. Recommend one model with reasoning (and name the runner-up): free / one-time / subscription / freemium split. For freemium, define the split by *value*, not by crippling the core promise.
4. Do the unit economics honestly in BUSINESS.md: cost per user, break-even users at the recommended price, and the fixed-cost table. A number that embarrasses the idea is exactly the number to write down.
5. If a paywall/purchase flow gets built later: store billing policies belong to `compliance-review`, and the purchase flow is a user-input surface — it goes through `privacy-guardrails-review` like any other before ship.
6. Record the chosen model + why in BUSINESS.md; if it's a durable non-obvious decision (e.g. "no ads ever, because X"), save it to project memory.

## Example

**Output:** "Recommend one-time ₹299 unlock (runner-up: free + ₹99/pack). Reasoning: target user distrusts subscriptions, marginal cost is zero (on-device), and comparable offline-first tools in India price ₹199–₹499 one-time (research in BUSINESS.md). Break-even on fixed costs: 34 sales/year. No ad model — it would require the tracking the whole product is positioned against."
