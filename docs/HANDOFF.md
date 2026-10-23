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
- Phase: `10`, **S6** (held-out run) — **running: `20261022-2104-heldout-final`** (started 2026-10-22 21:04 UTC, one batch per the owner's S6 approval of all batches, D-064; log `C:\abb\logs\heldout-final.log`; manifest has `prereg_sha256` 7253364d…, `freeze_commit` 207ebfe). **Frozen at tag `v1.0-frozen` on 2026-10-22** (S5 passed: owner chose `auth_mode: subscription`, Max 5x, optional arms kept, freeze approved; fresh token stored as user env `ABB_OAUTH_TOKEN`). Phase 10 step 1 pre-flight: `tasks lint --all` 25/0; `tasks lint --setup-leak` 0 leaks (D-062); `env verify` AntennaPod 60/60 x2 + 13 seed OK, Wikipedia 367/367 x2 + 12 seed OK (logs `C:\abb\logs\verify-phase10-<repo>.log`); TASKSET 80b55a02… matches; s2a `5ca7283`. The runner enforces the freeze for `split: test` runs (D-063).
- Last commit: `phase 10 step 1: freeze …` (tagged `v1.0-frozen`) + this handoff
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

1. **Running:** `20261022-2104-heldout-final` (log `C:\abb\logs\heldout-final.log`; one pause so far, one usage-limited cut re-run). **Chained after it** (owner, 2026-10-23: "finish everything soon"): the session's background script `chain_optional.py` waits for the main run's clean finish, smoke-tests `plain-gate`, `s2a-norepro`, `speckit-sdd` on antennapod-0000 (label `smoke-optional-arms`, log `C:\abb\logs\smoke-optional-arms.log`), and, if no harness error, starts `heldout-optional` (`--arm plain-gate --arm s2a-norepro --arm speckit-sdd --tasks test --trials 1 --parallel 2 --model claude-opus-5-5 --profile final --grade --max-usd 149.66 --max-pause-h 150`, log `C:\abb\logs\heldout-optional.log`). If the session died, start these by hand with the new token in the child environment (from HKCU\Environment `ABB_OAUTH_TOKEN`), never under `ABB_TUNING`. If a run stopped: `abb run --resume <run_id> --max-pause-h 150`.
2. When the main run ends: `abb audit`, `abb report`, RUNS.md rows (`scripts/runs_rows.py`), `abb labels init/llm` for its failures (LLM-only, D-057); then fill the [after the run] sections of `benchmark/README.md` and `docs/WRITEUP.md` from `report/summary.md` only (three transcript excerpts per major finding).
3. After both runs: `abb repro <run_id>` (refuses while a run is live), publish (`benchmark/published/<run_id>/`: manifest, audit, report, labels; tarball of the results dir for the release — ask the owner before pushing a release), retire the S5 token, README status table to done.

Drafted while the run goes (2026-10-23, committed): `abb repro` (+ test), public `benchmark/README.md`, `docs/architecture.svg`, `docs/DEMO.md` (dev task antennapod-0000, Opus confirmation run), `docs/WRITEUP.md` (question, design, dev lessons, limits).
