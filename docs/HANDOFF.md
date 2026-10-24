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
- Phase: `10`, **S6 — held-out run PAUSED by the owner** ("pause it … I plan to resume this task after Sunday", 2026-10-24). `20261022-2104-heldout-final` stopped cleanly at 2026-10-24T11:01Z with `abb run abort` (STOP file; the running trials finished and were graded): **140 of 270 trials done, 130 pending**, est. $287.73, 2 scheduler pauses, 2 usage-limited cuts (kept under `usage_limited/`, re-run, not scored), `aborted_reason: abort` (resumable), **`abb audit` ok** on the 140. The chained optional run was cancelled before it started. Weekly usage was 0.71 at the stop; it resets Sundays 19:00 UTC.
- Frozen at `v1.0-frozen` (`207ebfe`, 2026-10-22); s2a `5ca7283`; PREREG sha256 `7253364d…` in the run's manifest.
- Last commit: `handoff: held-out run paused by the owner …`
- Working tree: clean
- Date: `2026-10-24`

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

When the owner says to resume (after Sunday 2026-10-25):

1. **Token.** The run needs the S5 token in `ABB_OAUTH_TOKEN`. A Claude app or shell started after 2026-10-22 18:00Z inherits it from the user environment; an older shell holds the previous token. Check without printing it: compare the sha256 of `os.environ["ABB_OAUTH_TOKEN"]` with that of `HKCU\Environment\ABB_OAUTH_TOKEN` (`winreg`); if they differ, pass the HKCU value into the child's environment only (never argv). Never set `ABB_TUNING`.
2. **Resume the main run** in the background (log `C:\abb\logs\heldout-final.log`, append):
   `abb run --resume 20261022-2104-heldout-final --max-pause-h 150` — keeps its arms/tasks/trials/`--max-usd 757.52`/parallel 2 from the manifest, removes the STOP file, records the resume (with its code shas) in `manifest.resumes`; the freeze gate re-checks PREREG and the tasks. ~130 trials ≈ 29 h at ~4.5/h.
3. **Then the optional arms** (only after the main run ends cleanly): smoke on a dev task — `abb run --arm plain-gate --arm s2a-norepro --arm speckit-sdd --tasks antennapod-0000 --trials 1 --parallel 2 --model claude-opus-5-5 --profile final --grade --label smoke-optional-arms` — and if no `harness_error`, `abb run --arm plain-gate --arm s2a-norepro --arm speckit-sdd --tasks test --trials 1 --parallel 2 --model claude-opus-5-5 --profile final --grade --label heldout-optional --max-usd 149.66 --max-pause-h 150` (~10 h).
4. When the main run ends: `abb audit`, `abb report`, RUNS.md rows (`scripts/runs_rows.py`), `abb labels init/llm` for its failures (LLM-only, D-057); fill the [after the run] sections of `benchmark/README.md` and `docs/WRITEUP.md` from `report/summary.md` only (three transcript excerpts per major finding); then the same for the optional run.
5. After both runs: `abb repro <run_id>` (refuses while a run is live); publish (`benchmark/published/<run_id>/`: manifest, audit, report, labels; tarball of the results dir for the release — ask the owner before pushing a release); retire the S5 token; README status table to done.

Drafted already (2026-10-23, committed): `abb repro` (+ test), public `benchmark/README.md`, `docs/architecture.svg`, `docs/DEMO.md`, `docs/WRITEUP.md` (question, design, dev lessons, limits).
