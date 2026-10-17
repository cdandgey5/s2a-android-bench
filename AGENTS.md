# Instructions for the agent building this benchmark

You are building the **Brownfield Android Agent Benchmark** described in `PLAN.md`. Read this
file fully before doing anything.

## Working rules

1. **Work one phase at a time.** Read `PLAN.md`, then the phase file in `phases/`. Build exactly
   the deliverables it lists. Do not start the next phase until the current phase's
   **Acceptance gate** passes and you have reported the gate output to the user.
2. **Contracts live in `specs/`.** When a phase says "see `specs/x.md`", that file is the source
   of truth. If you must deviate, change the spec first, say why in `docs/DECISIONS.md`, then
   change the code.
3. **Never fabricate results.** A table of numbers must come from files under
   `benchmark/results/`. If a run did not happen, say so.
4. **Re-verify external facts before building on them.** `reference/` was written on
   2026-10-16. Before Phase 0 ends, re-check: Claude Code CLI flags (`claude --help`), Spec Kit
   command names (`specify --version`, `specify init --help`), the Android command-line-tools
   filename, and each candidate repo's default branch, JDK and test task names. Record what you
   found in `reference/verified.md` with the date.
5. **Everything runs inside Docker.** The host is Windows 11 with WSL2 + Docker Desktop. Gradle,
   the agents and grading all run in Linux containers. Host-side code is Python 3.12 (managed
   with `uv`). Do not run Gradle on the Windows host. Work from the git clone on the WSL
   filesystem (`~/abb`, set up by the human per `docs/DAY-0.md`), never from `/mnt/c/...` or
   OneDrive; results go to `ABB_RESULTS_DIR` (default `~/abb-results`), which is never mounted
   into a container.
6. **Secrets never enter images or the repo.** The API key arrives only as `-e ANTHROPIC_API_KEY`
   on `docker run`, read from the host environment or a git-ignored `.env` (a five-line parser in
   `abb/config.py`; no dotenv dependency). Log every API-spending activity in `docs/RUNS.md`.
7. **No employer code.** The S2A arm (Phase 6) is written from scratch in this repo. Do not
   import prompts, skills or scripts from anywhere else.
8. **Keep the fairness protocol** (`specs/fairness-protocol.md`). In particular: once Phase 7
   freezes the dev/test split, the held-out test set is run **once**, in Phase 10, and never
   used for tuning.
9. **Prefer boring tools.** Python + Typer + Docker SDK + PyYAML + pydantic + pandas. JUnit XML
   via `xml.etree`. No frameworks beyond that unless a phase names one.
10. **Commit at every gate.** `git commit -m "phase N: <gate summary>"`. Keep `README.md` status
    table current.
11. **Transcripts are the truth.** `run.json` and `calls.jsonl` are derived; `abb audit` recomputes
    them from the verbatim transcripts for every arm and a report is not valid until it passes.
12. **Two packages, one contract.** `s2a/` (the framework) and `benchmark/` (the harness) are
    separate Python packages. Neither imports the other: the benchmark shells out to the `s2a`
    CLI, and the only shared things are the headless-driver contract
    (`specs/headless-agent-driving.md`) and the transcript test fixtures. Nothing in `s2a/`
    may mention hidden tests, grading, gold/test patches or task ids — the orchestrator is a
    product and must behave identically whether or not a benchmark is watching.

## Conventions

- Package name: `abb` (android brownfield bench). CLI entry point: `abb` (e.g. `abb images build antennapod`).
- All paths in configs are relative to `benchmark/`.
- Task IDs: `<repo>-<NNNN>` with 4 digits, e.g. `antennapod-0012`. `dev5` = the five tasks
  validated in Phase 2 **plus** the seed `antennapod-0000` (six tasks); it is the fixed
  bring-up set and is pinned to `dev`.
- Run IDs: `<YYYYMMDD>-<HHMM>-<label>`, e.g. `20261103-0915-devset-plain`.
- Timestamps: ISO 8601 UTC.
- Money: USD floats with 4 decimals. Tokens: ints.
- Log everything the agent did to `transcript.jsonl` verbatim; never summarize it away.

## What "done" looks like for the whole project

- `s2a run "<prompt>" --profile android` in a real Android repository runs every stage to a
  verified change and a report, and `s2a resume` continues an interrupted run.
- `abb run --arm plain --arm speckit --arm s2a --tasks test --trials 3` completes on a rented
  machine and writes `benchmark/results/<run_id>/`.
- `abb audit <run_id>` passes and `abb report <run_id>` produces `report/summary.md` with the
  pre-registered primary comparison, pass@1, pass^3, paired-bootstrap CIs, cost per task,
  one-time setup cost per repo, interventions, control-arm comparison, and a failure breakdown.
- The README of the published benchmark states the dev/test split, the pinned model, the number
  of trials, the known limits of the sample size, and the date of the single held-out run.
