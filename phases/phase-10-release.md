# Phase 10 — Final held-out run and release

**Goal.** One final run on the test set with the pinned model, a published report, and a
reproducibility package.

**Prerequisites.** Phases 7, 8, 9 gates; S2A tuning finished and `s2a/CHANGELOG.md`
closed with a "frozen" entry; `docs/RUNS.md` lists the last dev-set confirmation run on the
pinned model (`claude-opus-5-5`, or `claude-sonnet-5-5` if D-001 fell back) with cost per arm.

**Effort.** ~60 h of compute spread over the subscription's usage windows (days to weeks of
batches; the MVP cut shortens it); ~1 week of writing.

## Steps

1. **Pre-register, then freeze.** Complete `docs/PREREG.md` (primary comparison, arms in the
   matrix, exclusion rules, harness-bug criteria, rerun rule, **`auth_mode` and the usage-window
   schedule** — `specs/auth-and-usage.md` §5) and commit it; its sha256 goes
   into the manifest. Tag the harness `v1.0-frozen`. Complete D-010 in `docs/DECISIONS.md`
   ("test set run once on <date>; no task or prompt changes after the tag"). Re-run `abb tasks
   lint --all`, `abb tasks lint --setup-leak` (S2A's one-time setup now exists) and `abb env
   verify` for every repo; confirm `tasks/TASKSET.sha256` matches.
2. **Usage check.** `abb run --dry-run --arm plain --arm speckit --arm s2a --arm s2a-nomap
   --arm s2a-noverify --tasks test --trials 3 --model claude-opus-5-5` → estimated tokens, est.
   USD and **usage windows**, computed per arm from the **Opus dev-set confirmation run** in
   the prerequisites (its trials-per-window per arm in `docs/RUNS.md`; Phase 4's Sonnet figure
   is for dev scheduling only). Set
   `--max-usd` to 1.3× the estimate and write the window schedule and `auth_mode` into PREREG
   (`specs/auth-and-usage.md` §5 — decide this before the freeze, not after).
3. **Run machine.** The laptop (batches at `--parallel 2` across usage windows) or a Windows VM prepared by
   `scripts/vm-setup.ps1` (`abb tools install`, `abb env warm` for every repo, `abb sandbox
   setup`; fingerprints must equal `env.lock.json`). Create a **fresh** `setup-token` token for
   this run and store it as `ABB_OAUTH_TOKEN` (`docs/DAY-0.md` §3; D-026). Smoke trial (one dev
   task, plain arm) to confirm `abb auth check`, versions and fingerprints match the manifest you
   expect.
4. **Run.** `abb run … --parallel 6 --label heldout-final --grade` → run id
   `<YYYYMMDD>-<HHMM>-heldout-final`. Monitor with `abb run status` (usage-limit pauses show
   as `paused until …` and resume by themselves). If the run aborts (budget/host), `--resume` it; the manifest records every resume. If a **harness
   bug** meeting the PREREG criteria is found, stop, fix, tag `v1.0.1`, re-run the whole test
   set, and publish both run ids; the first run stays primary unless PREREG's asymmetry rule
   applies.
5. **Report.** `abb audit <run_id>` must pass; then `abb report <run_id>`. Hand-label 20–30
   test-set failures blind (stratified); `abb labels llm` for the rest; `abb labels agreement`
   must still be ≥ 80 % (S4 skipped: reported as not measured, labeller flagged uncalibrated).
6. **Benchmark README** (`benchmark/README.md`, public) must state: purpose; repos (URL +
   commit, licenses); task counts by repo/category/source and the dropped-task rate; the
   pinned model id and Claude Code/Spec Kit/s2a versions; limits (timeout, USD, turns, nudge
   caps) and the statement that wall-clock and USD are the binding limits; gate runs per arm;
   the control arms; the definition of "intervention"; the pre-registration and its sha256;
   the author-isolation measures and task-set hash, stated as hygiene rather than a boundary
   (the same person wrote tasks and S2A); the skipped Spec Kit commands; mined-task selection
   bias; the detectable effect size for the headline denominator; the dev/test split seed and sizes and that the test set
   was run once on <date>; the number of trials; headline table with CIs; detectable effect
   size; one-time setup costs; contamination statement (post-cutoff share, no history, no web,
   historical vs authored rows); failure breakdown; known limitations (JVM-only tests, Claude
   Code only, 40 tasks); how to reproduce (`abb tools install`, `abb env warm`, `abb sandbox setup`, `abb run`, `abb report`).
7. **Reproducibility package.** `<results root>/<run_id>/` (transcripts included, nothing
   redacted: the token is kept out of subprocess environments by the scrub, and `abb audit` has
   just proven that no file under the run contains it — D-026), `env.lock.json`, `split.yaml`,
   `tasks/TASKSET.sha256`, `docs/PREREG.md`, the git tag, and `abb repro <run_id>` which
   re-grades 3 random trials from stored diffs, re-runs `abb audit`, and re-generates the report,
   asserting identical numbers.
8. **Write-up** (`docs/WRITEUP.md`): question → design → results → failure analysis with
   3 concrete transcript excerpts per major finding → what S2A v1 should change → limits.
   Architecture diagram (`docs/architecture.svg`) and a 3-minute demo script
   (`docs/DEMO.md`: one task, three arms, side-by-side artifacts).
9. **Publish.** Copy `manifest.json`, `audit.json`, `report/` and all `labels.json` of the
   held-out run to `benchmark/published/<run_id>/` and commit; attach a tarball of the full results
   directory (transcripts, diffs, JUnit) to the release. Push the repo (harness + tasks +
   published report); open-source license files in place; task license notes present. Update
   `S2AFramework/README.md` status table to done. Retire the held-out run's token: revoke it if
   Phase 0 found a documented way, otherwise remove it from `ABB_OAUTH_TOKEN`/`.env` and let it
   expire.

## Acceptance gate

```
git tag | Select-String v1.0-frozen
uv run abb audit <run_id> && uv run abb report <run_id>   # summary.md with the primary comparison + CIs + failure breakdown
uv run abb repro <run_id>                        # "report reproduced: identical"
Get-FileHash docs\PREREG.md -Algorithm SHA256      # matches manifest.prereg_sha256
Select-String -Path benchmark\README.md -Pattern "run once" | Measure-Object   # Count >= 1
```

Passes when the held-out run exists with 3 trials × all arms, the README contains every
required statement, and `abb repro` reproduces the published numbers.

## After v1 (not part of this plan)

Emulator-based UI tasks; a second coding agent as a 4th arm (adapter = one afternoon); more
repos; S2A v1 informed by the failure breakdown; non-Android targets.

## Next (autopilot, `RUN-ALL.md`)

This is the last phase. After step 9: rewrite `docs/HANDOFF.md` ("v1.0 released"), commit, push, and
stop — the plan is complete. The write-up and the published run are the deliverables.
