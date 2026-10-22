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
- Phase: `9` **passed 2026-10-22** (README row 9; S4 skipped, D-057). Phase 6 step 18 tuning in progress: tuning 1 (verify checks the original request) kept — neutral on pass@1 (0.75 -> 0.75), pass^2 0.60 -> 0.70; tuning 2 (locate lists files to create separately, s2a `8a06aa2`) after-run `20261021-2234-dev-s2a-tune2` running (7/20 at 00:26 UTC, paused for the five-hour window until 04:02 UTC, resumes by itself). Plan: Max since 2026-10-21 (`abb auth set-plan`).
- Last commit: `phase 9: analysis …` (`git log -1`)
- Working tree: clean
- Date: `2026-10-22`

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

1. When `dev-s2a-tune2` ends: audit, report, compare s2a with tuning 1 (`20261021-1802-dev-s2a-tune1`) and the baseline per task; log in `s2a/CHANGELOG.md` and RUNS.md; keep or revert tuning 2 (`abb sandbox install-s2a` after a revert).
2. Freeze s2a: a "frozen" entry in `s2a/CHANGELOG.md` with the final sha; no prompt/pipeline change after it.
3. Opus dev confirmation run (Phase 10 prerequisite): `$env:ABB_TUNING=1; abb run --arm plain --arm plain-guided --arm speckit --arm s2a --arm s2a-nomap --arm s2a-noverify --tasks dev --trials 1 --parallel 2 --model claude-opus-5-5 --label dev-opus-confirm --grade` (profile `final`); RUNS.md with cost and five-hour share per arm.
4. Draft `docs/PREREG.md` (fill every known field: test n = 15, robustness n = 3 with detectable delta ~0.6, TASKSET 80b55a02…, split seed 20261101 dev 10 / test 15, arms, limits, exclusion + invalidation rules (D-056), budget from step 3) and stop at **S5**: owner reviews PREREG, decides `auth_mode`, creates a fresh `claude setup-token` token; then tag `v1.0-frozen`.
- Facts: wikipedia-0007 fixed after the split (tasks/CHANGELOG.md); D-056 ACL race fixed (`abb run invalidate` for spoiled trials); labels LLM-only (D-057).
