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
- Phase: `5` gate. First run `20261018-2151-dev5-speckit-1` (6/6 resolved, audit PASS) is **invalid (D-050)**: trigger (b) nudged `speckit-specify` and the agent implemented there on the sdd path. Fixed (artifact calls `structured`; slash-command names stripped). Re-run `dev5-speckit-2` queued in the background to start 01:12 UTC (after the five-hour reset at 01:10; the window was at 0.90 at 22:53 UTC).
- Last commit: `env.lock: s2a reinstalled (D-050 heuristic)` (`ba8bbb3`) + this handoff
- Working tree: clean
- Date: `2026-10-18`

## What exists and is verified

| Item | State | Proof |
|---|---|---|
| Phases 0-4 | gates passed 2026-10-17/18 | README status, `docs/RUNS.md` |
| Phase 7 | **gate passed**: 25 tasks validated 3x, lint 0 errors, setup-leak 0, env verify OK (AntennaPod 60/60 + 13 seed tasks, Wikipedia 367/367 + 12); split frozen seed 20261101 (dev 10 incl. pinned dev5, test 15); `tasks/TASKSET.sha256` = `split.yaml: taskset_sha256` = 2eeddcff...; coverage short on UI and Compose (COVERAGE-NOTES.md) | `uv run abb tasks list`, `tasks/split.yaml` |
| Phase 5 | Spec Kit arm (`abb/arms/speckit`, D-048), one-time setup cache (`abb/harness/setup.py`), 15 unit tests; no dev5 run yet | `uv run pytest -q tests/test_speckit_arm.py` |
| Phase 6 | `s2a/` package: 45 tests (fake Claude + Gradle), `s2a --help`; Arm C wrapper `abb/arms/s2a` (+ nomap/noverify/norepro, D-049), 19 tests; `abb sandbox install-s2a` done (sha `fa49cca`), `abb sandbox check --no-smoke` all OK incl. `s2a.exe` as the sandbox user | `cd s2a; uv run pytest -q`; `cd benchmark; uv run pytest -q` (136 pass) |
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

1. Phase 5 gate: when `dev5-speckit-2` ends (log `C:\abb\logs\dev5-speckit-2.log`): check that no artifact call was nudged and the sdd path edits code only in `speckit-implement*`; `abb audit <run_id>`, `abb report <run_id>`, artifacts listing, `scripts/runs_rows.py <run_id>` into RUNS.md, README, HANDOFF, commit `phase 5: …`. If the run stops `usage_limit`, `abb run --resume <run_id>` after the reset.
2. Phase 6 step 13 + gate: `.venv\Scripts\python.exe scripts\s2a_e2e.py --task antennapod-0001 --grade`; then `abb run --arm s2a --arm s2a-nomap --arm s2a-noverify --tasks dev5 --trials 1 --model claude-sonnet-5-5 --label dev5-s2a-1 --grade`; audit, report, RUNS.md, commit `phase 6: …`. Mind the five-hour window: Spec Kit sdd trials used ~7 % each.
3. Then Phase 8 (`phases/phase-8-runner.md`; needs `abb sandbox setup --slots 2`, one UAC).
- From now on: test-split tickets and results are not read by whoever tunes S2A; tuning (Phase 6 step 18) runs with `ABB_TUNING=1`.
