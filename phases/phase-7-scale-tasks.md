# Phase 7 — Scale to 40 tasks and freeze the split

**Goal.** 40 validated tasks across 3–5 repos with the target mix, metadata and license notes;
caches warmed for every base commit; dev/test split frozen with a seed.

**Prerequisites.** Phase 2 step 3 (mining tooling yields candidates); the rest of Phase 2's
tooling (lint, validate) lands while this phase is under way. In the per-phase-session variant
it starts mid-Phase 2 in its own session and branch and runs alongside Phases 3–6; **in autopilot
(`RUN-ALL.md`) it runs right after Phase 4, before any `s2a/` code exists, on `main`, in the
same checkout, with the human reviewing every drafted task at stop point S2 and author
isolation by ordering only.** Repo #3 (and #4) environments are built **in this phase**
(Phase 0 step 6 + Phase 1 for each; ~1 week hidden here; skipped under the MVP cut).
**Author isolation (D-019), per-phase variant:** this session's checkout must not contain `s2a/`: the PowerShell block in `START-HERE.md` §3 clones
`<remote>` with `--no-checkout` into `%USERPROFILE%\abb-tasks`, runs `git sparse-checkout init
--no-cone` and `git sparse-checkout set "/*" "!/s2a/"` (non-cone mode is required to exclude a
directory), and creates branch `phase-7` from `main`; every session of this phase is opened
there. **Autopilot variant:** same checkout, `main`; isolation is ordering-only (`RUN-ALL.md` §1)
and is recorded in PREREG. `tasks/TRIAGE.md`
entries are timestamped. Shared-machine rules: this is the only session that re-warms
`caches\gradle\<repo>`; it never runs `abb env prune` while another session has a run active.

**Effort.** ~2–3 weeks part-time. This is the biggest manual effort in the project.

## Targets

| Dimension | Target (N = 40) | Tolerance |
|---|---|---|
| Repos | 3–5; no repo > 40 % of tasks | ±1 task |
| Category | bugfix 16 · feature 12 · refactor 8 · cross_module 4 | ±2 each |
| Source | mined 20 · reverted 6 · authored 14 | ±3 each |
| Post-cutoff share | ≥ 50 % of mined/reverted tasks have **both** `issue_created` and `fix_date` after the pinned model's cutoff (the robustness-check denominator; aim for ≥ 13 such tasks in the test split) | — |
| files_bucket | roughly 1: 30 % · 2–5: 50 % · 6+: 20 % | — |
| lang | both java and kotlin present; mixed allowed | — |
| ui | ≥ 8 tasks with `ui != none` (xml and compose both present) | — |
| test_kind | ≥ 10 robolectric; ≥ 2 compose or screenshot | — |

Record the pinned model's training cutoff date (from the model docs) in `docs/DECISIONS.md`.

## Deliverables

```
benchmark/tasks/<repo>-NNNN/ … (40 validated)
benchmark/tasks/split.yaml                # seed, dev_frac, lists, sha256 of task ids
benchmark/tasks/COVERAGE.md               # generated table vs targets (abb tasks coverage)
benchmark/tasks/<id>/LICENSE-NOTE.md      # per task
benchmark/env.lock.json                # rebuilt with all base commits warmed
CLI: abb tasks coverage      abb tasks lint --setup-leak      abb split --seed N --dev-frac 0.3 [--pin-dev ids]      abb env warm <repo> --warm-commits-from-tasks
```

## Steps

1. **Environments for repo #3/#4** (Phase 1 procedure; **skipped under the MVP cut**). Thunderbird (JDK 21, Compose) is the
   preferred modern-Kotlin repo; NewPipe or Wikipedia fills the "in between" slot depending on
   Phase 0 results.
2. **Mining sweep** per repo: `abb tasks mine <repo> --since <cutoff> --limit 80` plus a
   pre-cutoff sweep for variety. Triage in a spreadsheet (`tasks/TRIAGE.md`): keep candidates
   with a clear issue, tests in the PR, ≤ 8 non-test files.
3. **Reverted tasks**: pick feature commits with tests; write tickets in the project's own
   issue style (look at 5 real feature requests first).
4. **Authored tasks** (14; 6 under the MVP cut): drafted by the agent in autopilot (`drafted_by:
   agent`, `drafted_with_model`), reviewed and edited by the human at S2 — or written by the
   human in the per-phase variant. Aim for things real maintainers would ask — a setting that doesn't
   persist, a sort order, a parser edge case, a refactor to an existing pattern (e.g. move a
   class to the repo's DI style), a cross-module change (model + storage + ui). Each needs a
   reference fix and hidden tests you wrote. Keep to the repo's test frameworks.
5. **Tagging and lint**: `abb tasks tag` on all; `abb tasks lint --all`; `abb tasks coverage`
   writes `COVERAGE.md`, prints deltas vs targets, and sets `repos.<repo>.build.setup_commit`
   to `git merge-base --octopus <all base commits of the repo>` (computed in the upstream
   mirror); `--warm-commits-from-tasks` (step 7) includes it so the
   setup calls can run Gradle offline there. Iterate until within tolerance. Then
   `abb tasks lint --setup-leak` (autopilot: passes trivially here because no constitution or
   map exists yet — do not create one to satisfy it; the binding run is Phase 10 step 1): fails
   if any cached one-time setup artifact (constitution,
   map under `results/_setup_cache/`) mentions a path or class name added by any task's
   `gold.patch`; regenerate the setup at the new `setup_commit` if it does.
6. **License notes**: `LICENSE-NOTE.md` template → GPL-3.0 for AntennaPod/NewPipe-derived
   patches, Apache-2.0 for Wikipedia/Thunderbird; authored tasks carry the harness license but
   still note the base repo.
7. **Warm caches** with all base commits: `abb env warm <repo> --warm-commits-from-tasks`
   → re-verify offline; update `env.lock.json`.
8. **Validate everything 3×** (`abb tasks validate --all --runs 3 --keep-going`), overnight on the laptop (or a Windows VM) if the daytime laptop is too slow (~40 × 3 × 2 Gradle runs). Fix or drop flaky tasks; keep
   the drop list in `tasks/DROPPED.md` with reasons (this is reportable data: "we dropped X %
   as flaky").
9. **Freeze the split**: `abb split --seed 20261101 --dev-frac 0.30` (stratified on
   repo × category). `--pin-dev` defaults to every task id that already has a trial under
   `results/` (dev5 and anything used while building Phases 4–6); those are forced into `dev`
   and listed in `split.yaml: pinned_dev`, because prompts were tuned on them. Commit
   `split.yaml`. From this commit on, test-set tickets are not to be read by whoever tunes
   S2A. Add the split sha256 to the manifest logic (`run.py`).
10. **Task-set hash.** `abb tasks hash` writes `tasks/TASKSET.sha256` (sha256 over every task's
    `task.yaml`, `problem.md`, `test.patch`, `gold.patch`); commit it. S2A tuning (Phase 6
    step 18) may not begin before this commit exists. No candidate may be dropped after a trial
    ran on it (`DROPPED.md` carries the date; `events.jsonl` proves order).
11. Commit `phase 7: 40 tasks, split frozen`.

## Acceptance gate

```
uv run abb tasks lint --all                      # 0 errors
uv run abb tasks validate --all --runs 3         # 40 validated (or N>=35 with DROPPED.md explaining)
uv run abb tasks coverage                        # within tolerance on every dimension, or a note why not
Get-Content benchmark\tasks\split.yaml            # seed, pinned_dev (contains dev5), counts per repo x category in dev and test
uv run abb tasks lint --setup-leak               # 0 leaks
Get-Content benchmark\tasks\TASKSET.sha256        # committed before any S2A tuning
uv run abb env verify <each repo>             # offline OK after re-warm
```

Passes when ≥ 35 tasks are validated (**MVP cut: ≥ 24**, two repos, "no repo > 50 %", authored
≥ 6 — `RUN-ALL.md` §3), coverage is within tolerance (or documented), every task has a license
note, and the split is committed.

## Pitfalls

- Mining yields mostly bug fixes; features and refactors come from reverted/authored work —
  budget your time accordingly.
- Validation at scale is slow: run per repo in parallel on separate workspaces (2 at a time); use
  `--keep-going` and a summary table.
- Do not "improve" a task after seeing an arm fail on it unless it is a genuine task bug; log
  every post-split task edit in `tasks/CHANGELOG.md` (this is a credibility artifact).

## Next (autopilot, `RUN-ALL.md`)

Gate passed → paste the gate output, rewrite `docs/HANDOFF.md`, update the README status table,
commit, push — then start Phase 5: `phase-5-arm-speckit.md`. Hard stop points ahead in it: none.
