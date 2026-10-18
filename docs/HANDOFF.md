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
- Phase: `1` — step: `10b — S1b throughput probe, rescheduled by the owner to 21:02 EDT 2026-10-17 (after the Max 5x -> Pro switch at 21:00); Phase 2 work started meanwhile at the owner's request`
- Last commit: `phase 2: wip — task tooling (lint, tag, mine, validate) + 4 drafted dev5 tasks; phase 1 probe pending` on `main` (`git log -1`)
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
| `abb env verify <repo> --sandbox user` | AntennaPod 60/60 offline 126 s (113 s + 29 s copy with transforms), seed fail→pass; Wikipedia 367/367 327 s (312 s + 34 s); `seed_transforms` stays false | `C:\abb\state\env-verify-*.json` |
| Integration tests | 27 passed, 2 skipped (slot-2 concurrency → Phase 8; no gold class yet) | `$env:ABB_INTEGRATION=1; uv run pytest -q tests\test_workspace.py tests\test_junit.py tests\test_proxy.py tests\platform` |

| Phase 2 tooling (started early) | `abb tasks new|lint|tag|mine|validate|list`; lint = named rules incl. interface rule for classes + member calls; mining post-cutoff; `reverted_from_pr` | `uv run pytest -q tests/test_tasks.py` (14 passed); seed validated 1x end to end |
| dev5 drafts (agent-drafted, NOT yet human-reviewed) | 0001 legacy iTunes ns (bugfix, #8722), 0002 uppercase SubscribeOnAndroid (bugfix, #8773, ticket rewritten), 0003 FLAC vorbis description (feature, #8747, scoped by a maintainer note), 0004 M4A description (reverted #8745, new surface); 0005 authored refactor: TODO | `uv run abb tasks lint --all` (0 errors on 0000-0004) |

## Open issues / blockers

- **Stop S1b at 21:02 EDT:** owner stops other Claude use, reads the meter (session %, weekly %); then the probe; reading again after. The API's `rate_limit_event` matched the meter (verified.md) and is recorded too.
- `benchmark/tasks/antennapod-0005/` is an empty leftover folder held open by some process; delete it before creating the authored task 0005.
- Phase 8 needs one more UAC step: `abb sandbox setup --slots 2` creates `abb-agent2` for parallel trials (D-037).
- Carry-overs: Phase 4 — `AskUserQuestion` absent from the `-p` tool list (D-005 note); Phase 5 — Spec Kit installs skills by default; Phase 6 — s2a's driver needs its own launcher console for Ctrl+C (D-032).

## Decisions waiting on the human

- None blocking. Overturnable autopilot decisions: D-031…D-035 (`docs/DECISIONS.md`).

## Exact next action

At 21:02 EDT: owner reading #1, then (in `benchmark/`) `uv run abb ws smoke --sandbox user --proxy --repo antennapod
--prompt-file tasks/antennapod-0000/problem.md --max-turns 200 --max-usd 5 --deadline 2700 --model claude-sonnet-5-5`,
reading #2, record in `docs/RUNS.md` + `reference/verified.md` with the weeks estimate (Pro), Phase 1 gate + commit.
Then Phase 2: author 0005 (refactor), S2 review of 0001-0005 + seed, warm their base commits, setup_commit, validate 3x.
