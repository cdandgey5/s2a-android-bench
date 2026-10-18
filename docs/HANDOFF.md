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
- Phase: `7` gate pending (S2 approved, S3 passed: all 25 tasks validated 3x, 16:52-20:11 UTC); `abb env verify antennapod` + `wikipedia` (`--transforms off`) running in the background since 20:13 UTC, logs `C:bb\logserify-phase7-<repo>.log`. Phases 5 and 6 built in the overlap window (RUN-ALL): Phase 5 code done (gate run pending), Phase 6 code done through step 16 (end-to-end and runs pending).
- Last commit: `phase 6: wip — s2a orchestrator package …` (`fa49cca`) + this handoff
- Working tree: clean after the handoff commit
- Date: `2026-10-18`

## What exists and is verified

| Item | State | Proof |
|---|---|---|
| Phases 0-4 | gates passed 2026-10-17/18 | README status, `docs/RUNS.md` |
| Phase 7 | 25 tasks (13 AntennaPod / 12 Wikipedia, 10 authored; D-045-D-047); S2 approved (TRIAGE.md); S3: 3x validation of all 25 passed (commit `0f75f40`) | `uv run abb tasks list` |
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

1. When verify ends: check both logs (main run OK + every seed task `v2_f2p` passing). Then in `benchmark/`: `abb split --seed 20261101 --dev-frac 0.30`, `abb tasks hash`, `abb tasks lint --setup-leak`, `abb tasks coverage`; paste the Phase 7 gate; HANDOFF, README, commit `phase 7: …` + push.
2. Phase 5 gate: `abb run --arm speckit --tasks dev5 --trials 1 --model claude-sonnet-5-5 --label dev5-speckit-1 --grade`, `abb audit`, `abb report`, RUNS.md, commit.
3. Phase 6 step 13: one dev task end-to-end with `s2a run` as the sandbox user (inspect `.s2a/runs/<id>/`), kill during implement + `s2a resume`; then step 17: `abb run --arm s2a --arm s2a-nomap --arm s2a-noverify --tasks dev5 --trials 1 --model claude-sonnet-5-5 --label dev5-s2a-1 --grade`; gate, commit.
