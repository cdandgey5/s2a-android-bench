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
- Phase: `10` prerequisites. s2a **frozen** at `8f8fc50` (s2a/CHANGELOG.md "Frozen"; D-058). Phases 0-9 passed. Running: the Opus dev-set confirmation `dev-opus-confirm` (plain, plain-guided, speckit, s2a, s2a-nomap, s2a-noverify; dev x 1; `claude-opus-5-5`, profile `final`, parallel 2; started 2026-10-22 03:5x UTC; log `C:\abb\logs\dev-opus-confirm.log`). `docs/PREREG.md` drafted for S5.
- Last commit: `PREREG: draft for S5 …` + this handoff
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

1. When `dev-opus-confirm` ends: audit, report, RUNS.md with est. USD and five-hour share per arm (trials per window on Max); fill PREREG's **[confirm]** fields (expected windows; `--max-usd` = 1.3 x the dry-run estimate of `--arm plain --arm plain-guided --arm speckit --arm s2a --arm s2a-nomap --arm s2a-noverify --tasks test --trials 3 --model claude-opus-5-5`, after adding the Opus per-trial costs to `config/cost_estimates.yaml` under a model key); decide the optional arms.
2. **S5 (hard stop):** show the owner PREREG; they choose `auth_mode` (subscription batches / ask Anthropic first / API key) and create a fresh token (`claude setup-token` -> `ABB_OAUTH_TOKEN`). Then Phase 10 step 1: `abb tasks lint --all`, `abb tasks lint --setup-leak`, `abb env verify` per repo, TASKSET check; commit PREREG; tag `v1.0-frozen`; D-010 entry.
3. **S6:** held-out run (`abb run … --tasks test --trials 3 --parallel 2 --model claude-opus-5-5 --label heldout-final --grade --max-usd <PREREG>`) in batches; never under `ABB_TUNING=1`; never tuned on.
4. Report, labels (LLM-only, D-057), README, reproducibility package (`abb repro` still to build), write-up, publish (Phase 10 steps 5-9).
