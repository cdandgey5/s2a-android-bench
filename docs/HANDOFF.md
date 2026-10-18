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
- Phase: `4` — step: `8`. Valid run `20261018-0429-dev5-plain-1`: 6/6 resolved, mean est. $0.20, audit PASS. `20261018-0456-dev5-plain-2` stopped on the **usage limit** after 3 trials (canary captured, verified.md); invalid earlier runs: D-043
- Last commit: `phase 4: wip — fixes D-041..D-043 …` on `main` (`git log -1`)
- Working tree: Gradle-health counters (transcript/metrics/report/runner circuit breaker) uncommitted until the next gate commit
- Date: `2026-10-18`

## What exists and is verified

| Item | State | Proof |
|---|---|---|
| Phase 0 | gate passed 2026-10-17 (`a4c7c8b`) | README status |
| Phase 1 | gate passed 2026-10-18 (`fe3fb66`); re-verified after D-043: AntennaPod 60/60 offline as `abb-agent` in 131 s | `C:\abb\logs\verify-after-d043.log`, `C:\abb\state\env-verify-*.json` |
| Sandbox | `abb-agent`, firewall `abb-agent-block-out`, ACLs; D-036 list grants; D-037 revoke + OWNER RIGHTS; D-043 cache grants re-applied after every warm, checked before every run | `uv run abb sandbox check` |
| Plan / usage | owner on **Pro** since 21:00 EDT 2026-10-17; five-hour window resets on the hour (01:00/06:00 UTC …), weekly Sundays 15:00 local; the building session's own usage shows up in the same five-hour counter (RUNS.md Phase 4) | `docs/RUNS.md` |
| Phase 2 | gate passed 2026-10-18: dev5 + seed validated 3×, S2 approved | `uv run abb tasks list` |
| Phase 3 | gate passed 2026-10-18: sanity matrix 14/14 | `$env:ABB_INTEGRATION=1; uv run pytest -q tests/test_grading_matrix.py` |
| Phase 4 code | `abb run` / `abb audit [--rederive]` / `abb report`; plain, plain-guided, plain-gate; `abb ws smoke --until-limit`; D-040…D-043 | `uv run pytest -q` (83 passed) |

## Open issues / blockers

- Phase 8 needs one more UAC step: `abb sandbox setup --slots 2` (D-037).
- Usage-limit canary not captured yet (phase-4 step 8): the first trial that hits a limit, or `abb ws smoke --until-limit --max-calls 200` near a window's end.
- Carry-overs: Phase 5 — Spec Kit installs skills by default; Phase 6 — s2a's driver needs its own launcher console for Ctrl+C (D-032) and the D-041/D-042 parsing rules.

## Decisions waiting on the human

- None. Overturnable autopilot decisions: D-031…D-043.

## Exact next action

After the five-hour reset (06:00 UTC): in `benchmark/`, `uv run abb run --resume 20261018-0456-dev5-plain-2`, then
`uv run abb run --arm plain-guided --tasks dev5 --trials 1 --model claude-sonnet-5-5 --label dev5-guided-1 --grade`;
`abb audit` + `abb report` on each. Do not edit `repos/*.yaml` or `config/*` while a run is live (a lazily re-read YAML
crashed `0429-dev5-plain-1` once; resumed). Then RUNS.md rows (generator: rows from run.json/grade.json), trials per
window (~1.7 pp of the Pro five-hour window per dev5 trial; this building session uses far more of the same window),
the Phase 4 gate, MVP default (RUN-ALL §3) as D-045, README, commit + push; then Phase 7 (re-warm with D-044 commands).
