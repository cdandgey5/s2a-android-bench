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
- Phase: `4` — step: `8 (dev5 x 1 on plain, then plain-guided; long run in the background)`; driver, arms, runner, audit, report built; shakedown `20261018-0317-shakedown` resolved + audit PASS
- Last commit: `phase 3: grading …` on `main` (`git log -1`)
- Working tree: `clean after that commit`
- Date: `2026-10-18`

## What exists and is verified

| Item | State | Proof |
|---|---|---|
| Phase 0 | gate passed 2026-10-17 (`a4c7c8b`) | README status |
| Phase 1 | gate passed 2026-10-18 (`fe3fb66`): `abb sandbox check` all OK as `abb-agent`; `abb env verify <repo> --sandbox user` AntennaPod 60/60 offline 130 s (+ seed fail→pass), Wikipedia 367/367 347 s; invariants 28 passed / 1 skipped (slot 2 → Phase 8); throughput probe recorded | `C:\abb\state\env-verify-*.json`, `C:\abb\state\sandbox-check.json`, `docs/RUNS.md` |
| Sandbox | `abb-agent` (S1 done 2026-10-17 23:03Z), firewall `abb-agent-block-out`, ACLs; D-036 list grants on ancestors; D-037 revoke finished trials + OWNER RIGHTS | `uv run abb sandbox check` |
| Caches | warm at the cache commits (fingerprints in `benchmark/env.lock.json`); `seed_transforms: false` (no net gain) | `uv run abb env fingerprint antennapod` |
| Plan / usage | owner on **Pro** since 21:00 EDT 2026-10-17 (was Max 5x); weekly reset Sundays 15:00; this building session runs on Opus 5.5 extra usage; probe: ~3 % session per trial (lower bound); D-038 stay on Pro, MVP decision at the first results table | `docs/RUNS.md` "S1b throughput estimate" |
| Phase 2 | gate passed 2026-10-18: `abb tasks lint --all` 0 errors; dev5 + seed `validated` 3× (env fingerprint `c18a14fc…`); S2 approved (post-S2 fixes to 0002/0003 listed in `tasks/TRIAGE.md`) | `uv run abb tasks list`; task.yaml `validation:` blocks |
| Phase 3 | gate passed 2026-10-18: sanity matrix 14/14 (antennapod-0000 bugfix + 0005 new-surface refactor x gold/empty/delete-test/compile-break/regression/gradlew-edit/interface-mismatch); `grade-patch 0001 gold` resolved in 38 s; `abb grade <run>` writes grade.json + metrics.json; no lint delta (D-039) | `$env:ABB_INTEGRATION=1; uv run pytest -q tests	est_grading_matrix.py` |
| Caches | antennapod warm at the 5 dev5 base commits + `setup_commit d05a58b4` (27 min); wikipedia at its cache commit | `benchmark/env.lock.json` |

## Open issues / blockers

- Phase 8 needs one more UAC step: `abb sandbox setup --slots 2` (D-037).
- Carry-overs: Phase 4 — `AskUserQuestion` absent from `-p` tools (D-005 note); trials per window on realistic tasks; Phase 5 — Spec Kit installs skills by default; Phase 6 — s2a's driver needs its own launcher console for Ctrl+C (D-032).

## Decisions waiting on the human

- None. Overturnable autopilot decisions: D-031…D-038.

## Exact next action

If the dev5 runs were interrupted: `uv run abb run --resume <run_id>` (in `benchmark/`; complete trials are skipped;
run ids are in `docs/RUNS.md` / `C:bbesults`). Then `abb audit <run_id>`, `abb report <run_id>`, record trials per
session window (from the transcripts' rate_limit_event utilisation) in `docs/RUNS.md`, the Phase 4 gate, and the
MVP default (RUN-ALL §3) as a D-0xx; then Phase 7.
