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
- Phase: `7` (MVP cut, D-045) — step: `1 skipped (no repos 3/4); start at step 2 (mining sweep)`. Phase 4 gate passed 2026-10-18
- Last commit: `phase 4: plain arm + first results …` on `main` (`git log -1`)
- Working tree: `clean after that commit`
- Date: `2026-10-18`

## What exists and is verified

| Item | State | Proof |
|---|---|---|
| Phases 0–3 | gates passed 2026-10-17/18 | README status |
| Phase 4 | gate passed 2026-10-18: valid runs `20261018-0429-dev5-plain-1` (6/6), `20261018-0456-dev5-plain-2` (6/6, one usage-limited attempt kept), `20261018-1010-dev5-guided-1` (6/6); audit PASS; est. $0.20 per plain trial; usage-limit canary in verified.md. Runs `0317`, `0322`, `0340` invalid (D-043) | `uv run abb report <run_id>`, `docs/RUNS.md` |
| Sandbox | `abb-agent`, firewall, ACLs (D-036, D-037); cache grants re-applied by every warm and checked before every run (D-043) | `uv run abb sandbox check` |
| Caches | antennapod warm at cache commit + 5 dev5 base commits + setup_commit; wikipedia at its cache commit. **The next warm adds D-044's all-variant command** (fingerprint changes → re-validate every task, Phase 7 steps 7–8) | `benchmark/env.lock.json` |
| Plan / usage | owner on **Pro**; five-hour window ~55–75 dev5 trials if trials are the only use; this building session uses the same window heavily; weekly resets Sundays 15:00 local | `docs/RUNS.md` "Phase 4 throughput" |
| Tasks | 6 validated (antennapod-0000…0005: 3 mined, 1 reverted, 2 authored); Phase 7 MVP target 24–30 validated, 2 repos ≤ 50 % each, 6 authored | `uv run abb tasks list` |

## Open issues / blockers

- Phase 8 needs one more UAC step: `abb sandbox setup --slots 2` (D-037).
- Wikipedia `abb env verify` was stopped mid-run after D-043 (AntennaPod passed); re-run it after Phase 7's re-warm (part of the Phase 7 gate).
- Never edit `repos/*.yaml` or `config/*` while an `abb run` is live (they are re-read per trial).
- Carry-overs: Phase 5 — Spec Kit installs skills by default; Phase 6 — s2a's driver needs its own launcher console for Ctrl+C (D-032) and the D-041/D-042 parsing rules; Phase 8 — D-028(c): stop launching trials on `allowed_warning`.

## Decisions waiting on the human

- None now. Next hard stop: **S2** — review of the drafted Phase 7 tasks (`tasks/TRIAGE.md`). Overturnable autopilot decisions: D-031…D-045.

## Exact next action

Phase 7 step 2 (`phases/phase-7-scale-tasks.md`): in `benchmark/`, `uv run abb tasks mine antennapod --since 2026-07-01 --limit 80`
and the same for `wikipedia` (plus a pre-cutoff sweep), triage into `tasks/TRIAGE.md`; then reverted (step 3) and 4 more
authored tasks (step 4, `drafted_by: agent`); lint/tag/coverage (step 5) toward 24–30 tasks with ≤ 50 % per repo;
then stop at S2 for the owner's review.
