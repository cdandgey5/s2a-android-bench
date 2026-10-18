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
- Phase: `1` — step: `10b — hard stop S1b: throughput probe; waiting for the owner's usage-meter reading #1 (session %, weekly %)`
- Last commit: `phase 1: wip — sandbox user works; verify, check and invariants green (before S1b)` on `main` (`git log -1`)
- Working tree: `clean after that commit`
- Date: `2026-10-17`

## What exists and is verified

| Item | State | Proof |
|---|---|---|
| Phase 0 | gate passed (`a4c7c8b`) | `docs/HANDOFF.md` history, README status |
| `abb env warm` (env.py) | done for both repos: AntennaPod 9.8 min, Wikipedia 11.7 min; gradle-ro / robolectric / gradle-pristine split; fingerprints | `benchmark/env.lock.json`; `uv run abb env fingerprint antennapod` |
| Workspace (workspace.py) | snapshot (git archive → strip automation → 1 commit tagged `base`), per-trial gradle-home seeded with `wrapper/dists`, symlinks checked out as files like Git for Windows | `abb env verify <repo> --sandbox none` |
| `abb env verify --sandbox none` (dev mode, harness user, proxy stopped) | AntennaPod 60/60 tests offline in 109 s + seed fail→pass; Wikipedia 367/367 in 308 s | `C:\abb\state\env-verify-*.json` |
| gradle.py, junit.py, proxy.py | done; proxy tested incl. a real TLS request to api.anthropic.com | `uv run pytest -q` → 46 passed, 10 skipped (integration/sandbox) |
| Sandbox (S1 done 2026-10-17 23:03Z) | `abb-agent` (SID ...-1006), firewall rule, ACLs; D-036 list grants on ancestors, D-037 revoke + OWNER RIGHTS | `uv run abb sandbox check` all OK (fs denies, github blocked, API via proxy 401, tools without profile, Claude smoke as abb-agent via proxy) |
| `abb env verify <repo> --sandbox user` | AntennaPod 60/60 offline 126 s (113 s + 29 s copy with transforms), seed fail→pass; Wikipedia 367/367 327 s (312 s + 34 s); `seed_transforms` stays false | `C:bb\state\env-verify-*.json` |
| Integration tests | 27 passed, 2 skipped (slot-2 concurrency → Phase 8; no gold class yet) | `$env:ABB_INTEGRATION=1; uv run pytest -q tests	est_workspace.py tests	est_junit.py tests	est_proxy.py tests\platform` |

## Open issues / blockers

- **Stop S1b:** the throughput probe needs the owner's usage-meter readings before and after.
- Phase 8 needs one more UAC step: `abb sandbox setup --slots 2` creates `abb-agent2` for parallel trials (D-037).
- Carry-overs: Phase 4 — `AskUserQuestion` absent from the `-p` tool list (D-005 note); Phase 5 — Spec Kit installs skills by default; Phase 6 — s2a's driver needs its own launcher console for Ctrl+C (D-032).

## Decisions waiting on the human

- None blocking. Overturnable autopilot decisions: D-031…D-035 (`docs/DECISIONS.md`).

## Exact next action

S1b (Phase 1 step 10b): owner reads claude.ai → Settings → Usage (session %, weekly %) and stops
chatting; then run (in `benchmark/`) `uv run abb ws smoke --sandbox user --proxy --repo antennapod
--prompt-file tasks/antennapod-0000/problem.md --max-turns 200 --max-usd 5 --deadline 2700 --model
claude-sonnet-5-5`; owner reads the meter again; record in `docs/RUNS.md` + `reference/verified.md`
with the weeks estimate; then the Phase 1 gate commands, handoff, commit `phase 1: …`.
