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
- Phase: `1` — step: `1 (mirror + warm, abb/harness/env.py)`; Phase 0 gate passed 2026-10-17
- Last commit: `phase 0: foundations …` on branch `main` (the commit that contains this file; `git log -1`)
- Working tree: `clean after that commit`
- Date: `2026-10-17`

## What exists and is verified

| Item | State | Proof |
|---|---|---|
| `abb` CLI skeleton | done: every command group; stubs name their phase | `uv run abb --help` (run in `benchmark/`) |
| Platform layer (Windows, harness-user path) | done: launcher + Job Object + STOP→Ctrl+C/Ctrl+Break + robust delete; sandbox-user launch is Phase 1 | `uv run pytest -q` → 40 passed, 1 skipped (`tests/platform/test_windows.py`) |
| Toolchain (`abb tools check`) | done: JDK 17.0.20.1+1 / 21.0.12.1+1, SDK (6 pkgs), CPython 3.12.15, pwsh 7.6.7, claude.exe 2.1.302 copy, specify 1.2.1, git config | `benchmark/config/toolchain.lock.yaml`; `uv run abb tools check` all OK |
| Auth (`abb auth check` → `oauth_token`) | done (`subscriptionType` not reported under token auth, D-035) | `uv run abb auth check`; `C:\abb\state\auth.json` |
| Smoke fixtures (`tests/fixtures/transcripts/*.jsonl`) | done: smoke-success, smoke-success-opus, smoke-maxturns1, smoke-interrupt (Ctrl+Break), smoke-interrupt-ctrlc (+ `.meta.json`) | `tests/test_smoke_fixtures.py` |
| Repo experiments (`reference/build-experiments.md`) | done: AntennaPod (#1, JDK 21) + Wikipedia (#2, JDK 17); mirrors in `C:\abb\caches\repos\*.git` (`--mirror`) | `uv run abb repos check antennapod` / `wikipedia` exit 0 |
| Seed task `antennapod-0000` | drafted (`status: draft`, `drafted_by: agent`); manual V1 fail / V2 pass on the experiment checkout | `benchmark/tasks/antennapod-0000/NOTES.md` |
| Experiment checkouts | `C:\abb\work\experiments\{antennapod,wikipedia}` (scratch; Phase 1 may delete them) | — |

## Open issues / blockers

- No blocker. Carry-overs for later phases (details in `reference/verified.md` / `docs/DECISIONS.md`):
  - Phase 1: the sandbox-user launch must also clear "ignore Ctrl+C" (launcher already does) and use the pinned pwsh (D-031); `ws smoke --proxy` is not wired yet (no proxy until Phase 1).
  - Phase 4: `AskUserQuestion` is not in the `-p` tool list on 2.1.302 (D-005 note); `--max-turns` works but is unlisted in `--help`; `rate_limit_event` exposes per-window utilisation (enables D-028 (c)).
  - Phase 5: `specify init --integration claude` "installs skills by default" — check slash-command vs skill names.
  - Phase 6: s2a's driver must start claude.exe through its own launcher copy (own hidden console) for Ctrl+C (D-032).

## Decisions waiting on the human

- None blocking. Autopilot decisions the human may overturn at any time: D-033 (`SUBPROCESS_ENV_SCRUB=0` + `bypassPermissions`), D-032 (Ctrl+C), D-034 (10 GB per trial), D-031 (pinned pwsh), D-003 (repos).

## Exact next action

Phase 1 step 1: implement `benchmark/abb/harness/env.py` (`abb env warm antennapod`, then
`wikipedia`) per `phases/phase-1-environments.md` and `specs/environments.md` §3, reusing
`abb/harness/repos.py: ensure_mirror` and the platform layer. Hard stop S1 at step 6 (UAC prompt
for `abb sandbox setup`), S1b at step 10b (usage-meter readings).
