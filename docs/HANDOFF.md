# Handoff (rewritten by the agent at every phase gate and whenever it is told to stop)

Any new chat can continue the project from this file plus `git log`. Keep it short and exact;
no narrative. `docs/RUNS.md` holds run history, `reference/verified.md` holds verified facts,
`docs/DECISIONS.md` holds decisions — do not duplicate them here, link to them.

**One handoff per branch.** This file belongs to `main`. A parallel-phase chat (Phases 5, 6, 7)
works on branch `phase-<N>` and keeps **`docs/HANDOFF-phase-<N>.md`** instead (same template);
it never edits this file. The merge commit (order 7 → 5 → 6) deletes the branch's handoff file
and folds its open items into this one.

## Where we are

- Mode: `autopilot (RUN-ALL.md)`
- Phase: `6` **passed 2026-10-19** (bring-up; README row 6). Next in RUN-ALL order: **Phase 8** (runner), then Phase 6 step 18 (tuning, `ABB_TUNING=1`) + Phase 9, then Phase 10.
- Last commit: `phase 6: s2a orchestrator + arm …` (`git log -1`)
- Working tree: clean
- Date: `2026-10-19`

## What exists and is verified

| Item | State | Proof |
|---|---|---|
| Phases 0-4 | gates passed 2026-10-17/18 | README status, `docs/RUNS.md` |
| Phase 7 | **gate passed**: 25 tasks validated 3x, lint 0 errors, setup-leak 0, env verify OK (AntennaPod 60/60 + 13 seed tasks, Wikipedia 367/367 + 12); split frozen seed 20261101 (dev 10 incl. pinned dev5, test 15); `tasks/TASKSET.sha256` = `split.yaml: taskset_sha256` = 2eeddcff...; coverage short on UI and Compose (COVERAGE-NOTES.md) | `uv run abb tasks list`, `tasks/split.yaml` |
| Phase 5 | **gate passed**: speckit 6/6 on dev5 (`20261019-0112-dev5-speckit-2`), audit PASS; arm D-048 + D-050; 17 unit tests | `uv run abb report 20261019-0112-dev5-speckit-2` |
| Phase 6 | **gate passed** (bring-up): e2e `20261019-0310-s2a-e2e` (every stage, interrupt + resume, ACCEPT, resolved); dev5 × 1 `20261019-1112-dev5-s2a-2`: s2a 6/6, nomap 5/6, noverify 4/6, audit PASS; s2a 54 tests, arm 19; D-049–D-053 | `cd s2a; uv run pytest -q`; `uv run abb report 20261019-1112-dev5-s2a-2` |
| Sandbox / caches | as before (D-036, D-037, D-043, D-044); fingerprints changed at the Phase 7 re-warm | `uv run abb sandbox check`, `benchmark/env.lock.json` |
| Plan / usage | owner on **Pro**; weekly reset Sundays 15:00 local (reset today); this session shares the five-hour window | `docs/RUNS.md` |

## Open issues / blockers

- No agent trial may run while `env verify` or validation runs as the same sandbox user (their workspaces hold test and gold patches).
- Never edit `repos/*.yaml`, `config/*` or `tasks/*` while an `abb` run or verify is live.
- Phase 8 needs one more UAC step: `abb sandbox setup --slots 2` (D-037).
- Phase 8 carry-over: D-028(c), stop launching trials on `allowed_warning`.

## Decisions waiting on the human

- None now. Next hard stop: **S4** (manual labels, Phase 9). Overturnable autopilot decisions: D-031-D-049.

## Exact next action

Phase 8 is in progress (usage limit reached mid-build, 2026-10-19). Done and committed as WIP:
`abb/harness/scheduler.py` (worker pool, job order, budget/abort/pause/probe), `costmeter.py`, `manifest.py`,
`run.py` rewritten on top of them (slot users per worker, setup lock, Outcome per trial, scheduler probe,
audit at the end, `status()`, `abort()`, `dry_run()`), sandbox slots (`abb sandbox setup --slots N`, the
elevated script loops over slot users, `sandbox check` covers every slot), `Workspace(run_as=...)` + peak memory,
platform `ac_standby_timeout_s`. Existing tests pass (138); none of the new code has run against a real trial yet.

Still to do, in order:
1. CLI: `abb run` options `--parallel`, `--max-usd`, `--dry-run`, `--allow-no-canary`, `--max-pause-h` (pass to Runner;
   on `--resume` keep the manifest's values unless given); `abb run status <id>` -> `run.status()`, `abb run abort <id>` -> `run.abort()`.
2. `config/cost_estimates.yaml` (`per_trial_usd`: plain 0.21, plain-guided 0.22, speckit 0.72, s2a 1.18, s2a-nomap 0.85, s2a-noverify 0.81).
3. `tests/test_scheduler.py` (fake run_job/clock/sleep/probe): order, resume rule (`complete`), retry-once on harness_error,
   budget stop, abort file, usage-limit pause -> probe -> resume, pause_at.
4. `abb report` refuses headline numbers when `manifest.audit_ok` is false.
5. Ask the owner for the UAC step: `abb sandbox setup --slots 2`, then `abb sandbox check`.
6. Gate runs (phases/phase-8-runner.md), RUNS.md, README, commit `phase 8: runner`.
