# Security

## What this is
A set of Claude Code hooks, skills and scripts that run locally with your user's permissions. Nothing here is a hosted service, and the harness sends no telemetry.

## Reporting a vulnerability
Please report privately, using GitHub's "Report a vulnerability" on this repository's Security tab if it is available. If it is not, open an issue that says only that you have a security report, with no exploit details, and I will arrange a private channel. I read reports as a solo maintainer and will reply when I can; there is no response-time commitment.

## What counts
- A way to make `release_gate.py` or `secrets_guard.py` allow what they are meant to block.
- A hook or script that writes, logs or transmits more than its documentation says (see `docs/DATA_RETENTION.md`).
- A committed secret, token or personal path.

## Known limits (not vulnerabilities)
- The release gate sees only commands and MCP calls made through Claude Code. It is a local nudge, and gate records are self-attested; the CI check in `docs/CI_GATE_CHECK.md` is the stronger control.
- Token and cost figures are estimates, not billing.
