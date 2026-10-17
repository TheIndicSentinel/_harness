# Changelog

Keep-a-Changelog style. Versions follow `.claude-plugin/plugin.json`.

## [Unreleased]
### Removed
- **The hand-written narrative map** (`harness-map.html`, 109 KB) **and `/harness-map`**, at the owner's explicit request. Its page engine (the part that renders any tree) was first extracted into `scripts/atlas_engine.html` (the atlas title and subtitle baked in, the three generated regions turned into placeholders, nothing else changed); the roughly 67 KB of hand-authored narrative cards (July snapshot, refreshed in 0.5.4) is gone from the tree and recoverable from git history at commit `908927c`. The generated page is byte-identical apart from timestamps, live counts and one provenance sentence that named the deleted map.
### Changed
- `generate_atlas.py` fills `scripts/atlas_engine.html` (placeholders `@@ATLAS_DATA@@`, `@@PROVENANCE@@`, `@@FLEET_PILLS@@`) instead of cutting the engine out of the map at run time and regex-patching it. A missing or damaged engine file now raises a clear error and writes no page; tests pin this. `harness-ui` and `/harness-atlas` are unchanged.
### Added
- **Live mind tree shows work and tokens.** `generate_atlas.py` gains a *Work & Tokens* branch per project and for `_harness`: tokens per task (git branch) and per session, subagents kept separate, a per-day chart and a fleet table on the root node; plus a baseline pilot per task (when one is recorded) and a live `_harness` branch (wired hooks, capabilities, memory). Source: Claude Code session transcripts via the new `scripts/session_data.py` (per-file cache under the harness data dir; no prompt text read). `--open` opens the page; `harness-ui` is a terminal wrapper.
- **Atlas panel "Harness cost vs measured benefit"** (first node under `_harness`, linked from the root node): injected-context tokens (live file estimate next to a real `/context` snapshot), the Orient trend (real-session rows; none exist yet), tokens per task (fleet-wide heaviest and the baseline tasks), and the baseline deltas with n, a noise rule and a "one task drives it" flag. Computed sentences state what was and was not shown; when the recorded pilot shows no movement beyond noise it says benefit is not demonstrated. New: `scripts/cost_benefit.py`, `scripts/context_snapshot.py` (`claude -p /context` makes no model call, so refreshing costs no tokens; probe leaves no trace), `hooks/session_start.py: collect_lines(record_alerts=False)` so reports can measure the hook text without consuming a budget alert. `--no-refresh` skips the re-measurement.

### Fixed
- The atlas located project memory with a path that mishandled names containing `_` or `.`; it now uses the same encoding as Claude Code (`memory_lib`).
- Tests no longer read the real `~/.claude` (transcripts, memory): `CLAUDE_CONFIG_DIR` is isolated per test.
### Corrected
- **Baseline figures are labelled hand-entered.** A `<project>-compare.json` written by hand from a pilot was presented like a measurement. The panel now shows "Source: hand-entered from the pilot", says so in its computed summary, and marks each metric `cross-checked` (in + out and Orient match the hook-written cost rows) or `hand-entered only`. A file is only called generated if it names the script in `generated_by`.
- **The `/context` probe's cleanup was broader than the probe.** It used a fixed directory name (so an existing directory by that name would have been created over and then deleted) and removed the whole transcript folder and cost file. It now uses a fresh `mkdtemp` directory, removes only transcript entries that appeared during the run (and the folder only if empty), only the cost rows carrying the probe's session id, and refuses paths outside where the probe lives. Tests place decoys exactly where a too-broad delete would hit them; four mutations of the cleanup are each caught.
- **Plugin token saving.** An earlier report projected a saving of about 3k tokens per session from disabling four plugins. Measured with `/context` after disabling `data`, `legal`, `design` and `pdf-viewer` (31 skills): Skills 9.9k to 9.2k, total unchanged at 23.9k. The skill listing has a fixed budget (1% of the context window), so the freed space went to longer descriptions of the remaining skills. Disabling plugins improves what the model sees; it does not reduce the cost. `context_budget.py` no longer implies otherwise.
### Fixed (measurement)
- **Orient undercount.** The cost-log `Orient` column counted only Read/Grep/Glob, but models explore through Bash: a session with 8 shell reads reported 0. It now also counts Bash calls that read (`cat`, `sed`, `head`, `rg`, `grep`, `ls`, `find`; not `sed -i` or output redirection). `orientation_calls(path, include_shell_reads=False)` returns the old definition so earlier rows and "before" measurements stay comparable. Rows written before this change use the old definition.

## [0.5.5] — corrections from verification
### Corrected
- `context_budget.py` described itself as the "always loaded" cost. Measured with `/context`: the harness-owned load is about 3.1k tokens (the script estimates 2.2k, chars/4 undercounts) and plugin/built-in skills add listing text that it never sees (see Unreleased: disabling plugins did not shrink it). The output and docstring now say so; the ceilings remain a regression guard on the harness's own files.
### Verified (no code change)
- Cost log under a real `claude -p` session: row written to `~/.claude/harness/cost/` with Branch and Orient.
- The secrets guard's `ask` becomes a block under `-p` in both default and auto permission modes.
- `disable-model-invocation: true` hides legacy `commands/*.md` entries from the model's skill list.

## [0.5.4] — mind tree brought up to date
### Changed
- `harness-map.html` (hand-authored narrative) refreshed from its July 17 snapshot: the _harness branch now covers Phases 1-4 and the review fixes (9 new history entries, the verification hook card, a new "Learning & Verification" category, updated hook, rigor, capabilities, distribution, monitoring and scope cards). Counts (13 skills, 12 commands, 3 agents, 5 wired hooks, 204 tests) were taken from the tree, not remembered.
### Fixed
- `generate_atlas.py` replaced the map's provenance line by exact-string match, which broke the first time that line was edited; it now matches the block by shape and fails loudly if it's gone.

## [0.5.3] — restoration
### Restored
- `/dashboard`, `/harness-atlas`, `/harness-map`, their generators, tests and `harness-map.html` (the mind-tree UI), removed in 0.5.1 by mistake. They are the owner's way of inspecting the harness; the review that suggested deleting them measured "does it change Claude's behaviour", which was the wrong test for a visibility tool. Removing a user-built feature needs an explicit instruction, not an inference from a review.

## [0.5.2] — Claude Code 2.1.300 audit
Audited against Claude Code 2.1.300 (docs checked 2026-10-15).
### Changed
- **`onFailure: "block"` enabled on the release gate** (hooks.json and settings.json). Not on the secrets guard (lockout of the recovery path) and not meaningful on Stop. See `docs/COMPATIBILITY.md` for the accepted trade-off.
### Fixed
- `${CLAUDE_PLUGIN_ROOT}` was unquoted in `hooks/hooks.json`: a plugin path containing a space would have silently broken every hook (hooks fail open). Now quoted, with a regression test.
- CI `plugin-validate` only checked the marketplace manifest; it now also validates `.claude-plugin/plugin.json`, which is what inspects hooks.
### Added
- Settings drift check (`hooks/settings_lib.py`): `/harness-status` lists differences between the live `~/.claude/settings.json` and the repo template; SessionStart prints one line only when drift exists.
- `docs/MEASUREMENT.md`: the baseline protocol (5 tasks per project, same before/after). Orient is documented and reported as a trend signal, not a score.
- README install line.
- CI gate-check workflow takes an `enforce` input (default true) so a pull-request dry run in a release workflow doesn't fail on a missing record; `gate_write.py` warns when the committed summary is long (the record may land in a public repo) and the privacy skill says what must not go in it.

## [0.5.1] — review-driven fixes
### Fixed
- **CI gate check bypass:** the removal check compared only against the parent, so a two-commit PR (drop the gate, then release) passed. Baselines are now the parent, the merge-base with the target branch and the last tag; deliberate loosening is listed in `acknowledged_gate_removals`. The check remains self-attested inside the repo: CODEOWNERS and branch protection are what make it binding.
- `/harness-status` "gate record committable" now applies only to projects that have the CI gate workflow (a project may keep its records local on purpose).
### Added
- Cost-log `Orient` column: Read/Grep/Glob calls before the first edit in a session, a rough re-exploration signal (the cost CLAUDE.md, memory and handoff exist to reduce).
- Stop hook records its last run time; `verify_write.py <project>` shows it and warns above 60 s. Policy documented: off by default, per project, fast suites only.
- `requirements-dev.txt`; CI installs from it.
### Changed
- `docs/COMPATIBILITY.md` states plainly that `test_compat` is a typo guard, not a drift detector.
### Removed
- `/dashboard`, `/harness-atlas`, `/harness-map` and their generators, tests and `harness-map.html` (~2,200 lines): hand-authored or duplicate views of data `/harness-status` already reports; none changed Claude's behaviour. Restorable from git history (commit before this one).

## [0.5.0] — Phase 4: CI authority, verification, compatibility, task-level cost
Audited against Claude Code 2.1.285 (docs checked 2026-10-15).
### Added
- **CI gate check** fails when a required gate was removed since the parent commit; `/harness-status` flags a git-ignored `.harness/` (CI can't see the record).
- **Opt-in Stop verification hook** (`hooks/verify_before_stop.py`, `verify_write.py`): runs your check before Claude may stop; blocks with the output; gives up after 3 consecutive blocks; command stored outside the repo. `docs/VERIFICATION.md` covers all four rungs (prompt, `/goal`, hook, fresh review).
- **Compatibility**: `docs/COMPATIBILITY.md`, `scripts/compat_check.py`, `tests/test_compat.py` (wired events must be documented events), informational CI job running `claude plugin validate` on a pinned release.
- **Task-level cost**: cost-log rows carry the git branch; `/cost-report` groups by branch with commits as a rough outcome. A branch is a proxy for a task, not a measurement.
### Not done
- `onFailure: "block"` on `release_gate.py` needs Claude Code >= 2.1.295 (installed: 2.1.285); documented in COMPATIBILITY.md as the one pending hardening.

## [0.4.1]
### Added
- `/harness-status` health check "AGENTS.md read by Claude Code": the umbrella CLAUDE.md above every project makes Claude Code skip `AGENTS.md` unless a project `CLAUDE.md` imports it (`@AGENTS.md`). `/adopt-project` now creates that import file when a project has `AGENTS.md` but no `CLAUDE.md`.

## [0.4.0] — Phase 3a/3b: safety fixes and the learning loop
### Security / privacy
- **Cost log moved out of repos** to `~/.claude/harness/cost/<project>.md` (`CLAUDE_HARNESS_DATA_DIR` overrides). It used to be `docs/COST_LOG.md` and was once published by accident. Legacy logs are read as a fallback, copied on first write, never deleted; `/harness-status` flags a git-tracked one.
- Template `docs/COST_LOG.md` removed.
### Fixed
- Cost-log durations were first-to-last wall clock (`18854m44s` for a resumed session); now active time (gaps over 10 min excluded). Cache-read column dropped. Atlas chart ignored every legacy 5-column row.
### Added
- `scripts/memory_lint.py`, `hooks/memory_lib.py`: flags status-log memories, oversized files, stale/unverified entries, dead path references, long index lines, stale or oversized handoff.
- SessionStart memory line (handoff present/age; memory behind last commit), from file times only.
- `/wrap-up` rewritten: admission test, `verified`/`source` metadata, single overwritten `handoff.md` in the memory dir, no status logs, promotion with confirmation.
- `/weekly-review` runs the memory lint.
### Note
- Existing projects keep their old `docs/COST_LOG.md`; untrack it (`git rm --cached`) where `/harness-status` reports it tracked.

## [0.3.0] — Phase 2: token efficiency
Always-loaded context (umbrella CLAUDE.md + listed descriptions), est. chars/4: **~3,500 -> ~2,190 tokens**.
### Added
- `scripts/context_budget.py` (measurement) and `tests/test_context_budget.py` (ceilings: CLAUDE.md <= 3 KB, descriptions <= 600 chars, total <= 2,400 tokens).
- `docs/LIFECYCLE.md`: lifecycle map, gate detail and adopt-project notes, read on demand.
- Compaction guidance in the umbrella CLAUDE.md (what to preserve).
### Changed
- Umbrella `CLAUDE.md` 6,593 -> 2,303 bytes; dropped generic Claude Code advice Claude already follows.
- `disable-model-invocation: true` on user-only commands with side effects (new-project, adopt-project, sunset-project, harness-init, dashboard, harness-atlas, harness-map, cost-report).
### Not done, on purpose
- No `disable-model-invocation` on skills: launch-checklist/qa/compliance/privacy/release-notes/market-research are invoked by other skills or commands, which that flag would break.
- No `allowed-tools`: it grants permissions without prompting, the opposite of least privilege.

## [0.2.0] — Phase 1: correctness and safety
### Added
- `tests/test_portability.py`: no author-specific absolute paths in tracked files, manifests well-formed, every wired hook script resolves, hooks run from a relocated clean install.
- Fail-closed tests for `release_gate.py` (internal error, corrupt `gates.json`).
- Project template `.claude/settings.json` (secrets deny for Read/Edit), copied by `/new-project` and `/adopt-project`.
- CI matrix: ubuntu + macOS.
### Changed
- `release_gate.py` fails closed on any unexpected error once a command is recognized as a ship action (a traceback exits 1, which is non-blocking).
- `settings.json`: hook commands use `${CLAUDE_PLUGIN_ROOT:-$HOME/...}`; allow rules are path-independent; Edit deny rules added alongside Read.
- `marketplace.json` gets a description (silences a `claude plugin validate` warning).
- `test_docs_consistency` ignores `__pycache__` (was failing after any local test run).
### Deferred
- Hook `onFailure: "block"` (needs Claude Code >= 2.1.295); sandbox is documented opt-in, not forced.
- License choice (`UNLICENSED` placeholder remains — owner decision).
