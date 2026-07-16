# {{PROJECT_NAME}} — Connectors & MCP Registry

A record of every MCP server or external connector this project's Claude Code sessions have access to — not an automated enforcement system, just the accepted-risk record so "why does this have write access" has an answer six months from now. Treat any third-party MCP server as unreviewed until an entry exists here — a marketplace/directory listing is not a security review.

## Approved connectors

| Name | Source | Version/commit | Scope (read-only / write / financial / customer-data / deploy) | Risk tier | Reviewed | Next review |
|------|--------|-----------------|------------------------------------------------------------------|-----------|----------|--------------|

## Guidelines
- **Default deny for anything with write, financial, customer-data, or deployment scope** — add it here deliberately, with a reason, before relying on it in a real session.
- Read-only connectors (search, fetch, read-only issue trackers) are lower risk but still worth listing if used regularly — makes an audit of "what could this session have touched" a lookup instead of an investigation.
- Irreversible or external actions (sending messages, publishing, spending money) through a connector still get the same explicit per-action confirmation as any other external action — being "approved" here means the connector is trusted enough to consider using, not that its actions are pre-authorized.
- Re-review on a cadence that matches risk: read-only tools, occasionally; anything with write/financial/deploy scope, whenever it updates or at least every few months — note the date in "Next review" and actually revisit it.
