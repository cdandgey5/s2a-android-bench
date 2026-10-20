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
- Phase: `8` (runner), **waiting for the owner's UAC step**: `abb sandbox setup --slots 2` (creates `abb-agent2`, its grants and firewall rule; D-037). Built and committed: scheduler, cost meter, manifest, runner on top (slot users per worker, setup lock, pause/probe, audit in the loop), `abb run --parallel/--max-usd/--dry-run`, `abb run status|abort`, report withholds totals on a failed audit; 151 tests pass. Verified on real trials: `20261019-2337-p8-smoke` (1 trial, slot 1, audit in the loop OK) and the budget gate `20261019-2341-p8-budget-test` (stopped after the trial that crossed $0.50: aborted_reason budget).
- Last commit: `phase 8: wip — run CLI …` + this handoff
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

1. Owner (hard stop, UAC): in PowerShell, `cd $env:USERPROFILE\abb-src\benchmark; .\.venv\Scripts\abb.exe sandbox setup --slots 2`, accept the UAC prompt. The agent never runs it (system/security settings).
2. Then `abb sandbox check --no-smoke` (every slot row OK), and the resume gate: `abb run --arm plain --arm s2a --tasks dev5 --trials 2 --parallel 2 --model claude-sonnet-5-5 --label p8-resume-test --grade`, interrupted (Ctrl+C) after ~3 trials complete, then `abb run --resume <run_id>`: completed trials skipped, the rest finished; no memory-limit kills (`abb run status` peak memory). Mind the five-hour window (~$16 est. for the 24 trials).
3. RUNS.md (smoke, budget, resume runs; parallel memory numbers), README, commit `phase 8: runner`.
4. Then Phase 6 step 18 (tuning, `ABB_TUNING=1`) + Phase 9.
