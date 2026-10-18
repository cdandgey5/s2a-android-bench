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
- Phase: `7` (MVP cut, D-045) — steps 2–7 done: 25 tasks (13 AntennaPod / 12 Wikipedia, 10 authored; D-046, D-047), both repos re-warmed at every base commit, coverage written, **all 19 new tasks pass a single validation run**; **waiting at S2** (owner review of `benchmark/tasks/TRIAGE.md`, Phase 7 section)
- Last commit: `phase 7: wip — 25 drafted tasks …` on `main` (`git log -1`)
- Working tree: clean after the S2-ready commit
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

- None now. Next hard stop: **S2** — review of the drafted Phase 7 tasks (`tasks/TRIAGE.md`). Overturnable autopilot decisions: D-031…D-047.

## Exact next action

**S2 (hard stop):** the owner reviews the 19 new tasks in `benchmark/tasks/TRIAGE.md` (Phase 7 section) and replies
`approved` / `approved, dropped: <ids>` / change requests. After approval: in `benchmark/`,
`abb tasks validate --all --runs 3 --keep-going` (**S3**, long: all 25 incl. dev5 — the environment fingerprint
changed; run per repo in two streams with `.venv\Scripts\abb.exe`, not two parallel `uv run`), `abb env verify wikipedia`
and `abb env verify antennapod`, then `abb split --seed 20261101 --dev-frac 0.30`, `abb tasks hash`,
`abb tasks lint --setup-leak`, the Phase 7 gate, commit + push; then Phase 5 (`phases/phase-5-arm-speckit.md`).
