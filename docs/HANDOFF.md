# Handoff (rewritten by the agent at every phase gate and whenever it is told to stop)

Any new chat can continue the project from this file plus `git log`. Keep it short and exact;
no narrative. `docs/RUNS.md` holds run history, `reference/verified.md` holds verified facts,
`docs/DECISIONS.md` holds decisions — do not duplicate them here, link to them.

**One handoff per branch.** This file belongs to `main`. A parallel-phase chat (Phases 5, 6, 7)
works on branch `phase-<N>` and keeps **`docs/HANDOFF-phase-<N>.md`** instead (same template);
it never edits this file. The merge commit (order 7 → 5 → 6) deletes the branch's handoff file
and folds its open items into this one.

## Where we are

- Mode: `autopilot (RUN-ALL.md)` | `per-phase sessions`
- Phase: `0` — step: `1 (bootstrap check); blocked: Day-0 incomplete (README status, reference/verified.md run 3)`
- Last commit: `<sha> <subject>` on branch `<branch>`
- Working tree: `<clean | N uncommitted files: …>`
- Date: `<ISO date>`

## What exists and is verified

| Item | State | Proof |
|---|---|---|
| `abb` CLI skeleton | not started | — |
| Toolchain (`abb tools check`) | not started | — |
| Auth (`abb auth check` → `oauth_token`) | not started | — |
| Smoke fixtures (`tests/fixtures/transcripts/*.jsonl`) | not started | — |
| Repo experiments (`reference/build-experiments.md`) | not started | — |
| Seed task `antennapod-0000` | not started | — |

## Open issues / blockers

- `<none>`

## Decisions waiting on the human

- `<none>`

## Exact next action

`<the single next step, with the command to run and the file to read>`
