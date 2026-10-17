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
- Phase: `1` — step: `6 — hard stop S1: waiting for the human to run "uv run abb sandbox setup" (in benchmark/) and accept the UAC prompt`
- Last commit: `phase 1: wip — warm caches, workspace, proxy, sandbox code (before S1)` on `main` (`git log -1`)
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
| As-user launch (`CreateProcessWithLogonW`, no profile) + `check_paths` probe | written, **untested** (no sandbox user yet) | after S1 |
| `abb sandbox setup` | non-elevated part ran (`--prepare-only`): password in Credential Manager (service `abb`), params `C:\abb\state\sandbox-setup-params.json`; elevated script `benchmark/scripts/sandbox-setup.ps1` parses cleanly | — |
| `abb sandbox check`, `tests/test_workspace.py` | written, run after S1 | — |

## Open issues / blockers

- **Blocker S1:** the elevated step needs the human at the keyboard (UAC).
- Carry-overs: Phase 4 — `AskUserQuestion` absent from the `-p` tool list (D-005 note); Phase 5 — Spec Kit installs skills by default; Phase 6 — s2a's driver needs its own launcher console for Ctrl+C (D-032).

## Decisions waiting on the human

- None blocking. Overturnable autopilot decisions: D-031…D-035 (`docs/DECISIONS.md`).

## Exact next action

After the human replies `done`: `uv run abb sandbox check` (in `benchmark/`), fix what fails, then
`uv run abb env verify antennapod --sandbox user` and `wikipedia`, `$env:ABB_INTEGRATION=1; uv run
pytest -q tests\test_workspace.py tests\test_junit.py tests\test_proxy.py tests\platform`, then
step 10b (S1b throughput probe: ask for the usage-meter readings before and after).
