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
- Phase: `6 step 18 (tuning) + 9 (analysis)`. Phase 9 code done and committed: `stats.py` (known-answer tests), full deterministic `report.py` (`abb report <run> [--out]`, `abb report-diff`), `charts.py`, blind LLM labeller (`labeller.py`, `abb labels init|show|set|llm|agreement`; tried on 2 failures, $0.035). 159 tests pass. **Waiting on the owner's quota decision** before the dev-set baseline run: the seven-day window was at 59 % on 2026-10-20 05:50 UTC (resets Sun 2026-10-25 19:00 UTC) and the dev baseline (plain + speckit + s2a, 10 dev tasks x 2) is est. $42 ≈ 90 % of a week on Pro. Options given: A wait for the reset (default), B a small run now, C move to Max.
- Last commit: `phase 9: wip — stats …` + this handoff
- Working tree: clean
- Date: `2026-10-20`

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

1. Owner's quota answer (A/B/C). Then the dev-set baseline under `$env:ABB_TUNING=1`: `abb run --arm plain --arm speckit --arm s2a --tasks dev --trials 2 --parallel 2 --label dev-baseline-1 --grade` (first Wikipedia trials for Spec Kit and s2a: their one-time setups run first); controls `--arm plain-guided --arm plain-gate --trials 1` after it if the quota allows.
2. Phase 9 on that run: `abb report`, `abb labels init`, then **S4**: 20–30 blind bundles for the owner (`abb labels show`), or `skip` (labeller stays uncalibrated); `abb labels llm --calibrate`; `abb labels agreement`; determinism check (`--out r1/r2`, `report-diff`); commit `phase 9: analysis`.
3. Tuning (Phase 6 step 18) on `split: dev` only with `ABB_TUNING=1`: verifier calibration (6 dev diffs), then one change at a time, >= 2 trials, before/after in `s2a/CHANGELOG.md`. First candidate: locate/plan naming files to create without `(new)`.
4. Then Phase 10 (S5, S6). Budget it before S5: the held-out run is pinned to Opus.
- D-055 (open): one parallel trial lost its Gradle distribution's readability mid-trial; watch for it.
