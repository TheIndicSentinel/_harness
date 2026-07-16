# {{PROJECT_NAME}} — Legal & Compliance

Filled/reviewed by the `compliance-review` skill. This is the disclosure-and-obligation record; the code-level privacy check is `privacy-guardrails-review` (separate, mechanically gated). Mark items N/A with a one-line reason rather than deleting them.

## Risk tier
One line, picked once and revisited if the product changes shape — not a formal profile system, just enough to calibrate how much rigor the rest of this document needs.
- **Tier:** consumer / startup / regulated — default **consumer** for an indie app with no PII beyond what's disclosed above, no B2B/enterprise customers, and no regulated-industry data (health, finance, children's data under 13/16). Bump to **regulated** and treat every section above with real rigor if any of those apply.

## Privacy policy
- **File / URL:** (e.g. docs/PRIVACY_POLICY.md — required before any store listing)
- **Last verified against actual code behavior:** (date + commit)

## Terms of service
- **File / URL, or "N/A because":**

## Platform / store policies
- **Target store(s):** (Play, App Store, web, ...)
- **Known policy obligations:** (e.g. Play Data Safety form answers, account-deletion requirement)

## Regulatory
Which apply depends on users and data. For India-market apps: DPDP Act 2023. EU users: GDPR. Under-18 users: parental-consent rules.
- **Applicable:**
- **Position:** (e.g. "no personal data leaves device → minimal obligations; DPDP notice still required in policy")

## Third-party licenses
- **Dependency licenses checked:** (date; flag copyleft in shipped code)
- **Attribution/notice file:** (if any license requires it)

## Accessibility
- **Quick pass done:** (date — contrast, touch targets, screen-reader labels on the main flows; note gaps in ROADMAP.md)
