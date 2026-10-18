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
- Phase: `2` — step: `6 — hard stop S2: human review of dev5 (benchmark/tasks/TRIAGE.md); meanwhile step 7 (warm the dev5 base commits) runs`
- Last commit: `phase 1: environments + sandbox …` (`fe3fb66`) + this handoff commit, on `main` (`git log -2`)
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
| Phase 2 tooling | `abb tasks new|lint|tag|mine|validate|list`; `mine.reverted_from_pr` | `uv run pytest -q tests/test_tasks.py` (14 passed) |
| dev5 drafts | 0000 seed, 0001 legacy iTunes ns, 0002 uppercase SubscribeOnAndroid, 0003 FLAC description (feature), 0004 M4A description (reverted, new surface), 0005 comparators refactor (authored, new surface); lint 0 errors; 0005 passed V0/V1/V2 once | `benchmark/tasks/TRIAGE.md`, `uv run abb tasks lint --all` |

## Open issues / blockers

- **Stop S2:** the human reviews every task in `benchmark/tasks/TRIAGE.md` and replies `approved` (or `approved, dropped: <ids>`); validation only after that.
- Phase 8 needs one more UAC step: `abb sandbox setup --slots 2` (D-037).
- Carry-overs: Phase 4 — `AskUserQuestion` absent from `-p` tools (D-005 note); trials per window on realistic tasks; Phase 5 — Spec Kit installs skills by default; Phase 6 — s2a's driver needs its own launcher console for Ctrl+C (D-032).

## Decisions waiting on the human

- S2 approval of dev5. Overturnable autopilot decisions: D-031…D-038.

## Exact next action

Warm the dev5 base commits (`uv run abb env warm antennapod` picks them up from the tasks), compute
`setup_commit = git merge-base --octopus <dev5 bases>` into `repos/antennapod.yaml` and warm it,
then after S2 `approved`: `uv run abb tasks validate --all --runs 3 --keep-going`, fix flaky ones,
Phase 2 gate (`abb tasks lint --all`, `validate`, `list`, `pytest tests/test_tasks.py`), commit `phase 2: …`.
