# CI-side release gate check (GitHub Actions)

`hooks/release_gate.py` is a fast, local, Claude-Code-side nudge — it only sees Bash commands and MCP tool calls made *through* Claude Code. Running `./gradlew assembleRelease` in a plain terminal, or any release step triggered from CI directly, never touches it. `templates/new-project/.github/workflows/harness-gate-check.yml` closes that specific gap for projects that build/release via **GitHub Actions** — the one CI system actually in use by harness projects today. (Other CI/deploy targets — Vercel, AWS, GCP, Kubernetes, Terraform, etc. — aren't covered; add an equivalent adapter if and when a project actually deploys through one of those, rather than building unused ones now.)

## The convention this depends on: commit the gate record
`.harness/gates.json` is not gitignored, but it's also not committed by default — it's a local sidecar file the local hook reads live off disk. CI has no "live disk state"; it only sees whatever's in the git history for the commit it checked out. So for CI to verify anything, **you have to commit `.harness/gates.json`** after a review.

This creates an ordering wrinkle worth understanding rather than working around: `gate_write.py` stamps `reviewed_commit` as `git rev-parse HEAD` *at review time* — i.e., the code commit, before the gate file itself is committed. A commit's SHA is a hash of its own content, so `gates.json` can never validly declare `reviewed_commit` equal to the very commit it's part of — that SHA doesn't exist yet when the file is written (an `--amend` doesn't get around this either: amending changes the tree, which changes the commit's SHA, which no longer matches whatever was written into the file — tested and confirmed while building this). The commit that actually contains the up-to-date `gates.json` is necessarily one commit *later* than the code it's vouching for.

So the CI check (`harness_gate_check.py`) accepts exactly one shape as valid: `reviewed_commit` is the current commit's **parent**, and the diff between them touches **only** `.harness/gates.json` — i.e., the current commit is purely "record the pass," with no code change since the review. Anything else — the record is older, points at a non-parent, or code changed after the review — fails the check. This is intentionally a *different, more lenient* rule than the local hook's strict "reviewed_commit == HEAD" (which works fine locally, since there's no commit-ordering problem when checking live, uncommitted disk state) — don't try to unify them; they're solving different problems.

## Recommended workflow
1. Make code changes, commit.
2. Run the review skill(s) (`privacy-guardrails-review`, and `qa-review`/`compliance-review` if required).
3. Commit `.harness/gates.json` by itself: `git add .harness/gates.json && git commit -m "Record gate pass for <sha>"`.
4. Tag/release from **this** commit, not the code commit before it.

## Wiring it into an existing release workflow
Add a `needs:` dependency so the release job won't run until the gate check passes:

```yaml
jobs:
  gate-check:
    uses: ./.github/workflows/harness-gate-check.yml

  release:
    needs: gate-check
    runs-on: ubuntu-latest
    steps:
      # ... your existing release steps ...
```

This is opt-in — `harness-gate-check.yml` does nothing on its own (`workflow_call` only triggers when another workflow references it). Nothing breaks if you never wire it in; it just sits there as an available building block, per the harness's own rule against unused infrastructure.

## The honest limit of this check: it's self-attested
Be clear about what `harness_gate_check.py` actually verifies: that a gate record exists, says `pass`, and covers the current commit per the rule above. It does **not** verify that an independent review actually happened — nothing stops anyone (or an AI agent acting unsupervised) from hand-writing `{"status": "pass", ...}` into `gates.json` and committing it. That's not a flaw specific to this script; it's the ceiling of any self-attested record. Two things raise that ceiling, both GitHub repo settings rather than harness code:

1. **Required status checks** (Settings → Branches → branch protection rule → "Require status checks to pass" → select the `gate-check` job). Once set, merging to the protected branch through GitHub's UI/API cannot skip the check — a real improvement over "the check exists but nothing forces anyone to run it," even for a single-maintainer repo, since bypassing a required check is a distinct, visible, deliberate admin action rather than an ordinary commit.
2. **CODEOWNERS + required review** (`templates/new-project/.github/CODEOWNERS`, copied in inert/commented-out by default). This only becomes real protection once a second person with push access exists — for a genuine solo repo, "require review" either has no one to review or degrades to self-approval, neither of which adds trust. Uncomment it for `.harness/`, `.github/workflows/`, and `docs/COMPLIANCE.md` the day a co-founder or contractor gets write access, so a change to what counts as "reviewed" itself gets reviewed.

What this harness deliberately does **not** do: have CI itself re-run the actual privacy/QA/compliance review. That would require an LLM call from inside the CI job (an Anthropic API key sitting in CI secrets, real per-run cost, and API usage this harness otherwise has no involvement with — see the README's scope section). If that trade-off is ever worth it for a specific project, it's a deliberate addition to that project's workflow, not something this harness builds in by default.
