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
5. **Everything runs natively on Windows, through the platform layer.** No WSL, no Docker, no
   `.sh` scripts, no Linux-only tools. Humans use PowerShell 7; the harness and `s2a` are Python
   3.12 (`uv`) and start every process (Gradle, git, `claude.exe`) through
   `abb/harness/platform/` (`specs/platform-layer.md`), which is the only place OS-specific code
   may live (macOS comes later as `posix.py`). Work in `%USERPROFILE%\abb-src` (set up by the human
   per `docs/DAY-0.md`), never under OneDrive; data lives under `ABB_HOME` (toolchain, caches,
   workspaces) and `ABB_RESULTS_DIR`. Agent runs execute as the low-privilege sandbox user
   (`specs/environments.md`).
6. **Secrets never enter the repo or any config file.** There is no API key anywhere in this
   project. The subscription token from `claude setup-token` lives in the user environment
   variable `ABB_OAUTH_TOKEN` (or the git-ignored `benchmark/.env`, read by a five-line parser in
   `abb/config.py`; no dotenv dependency) and reaches agent processes only through the
   environment block the platform layer builds, where it is named `CLAUDE_CODE_OAUTH_TOKEN`.
   Never set `CLAUDE_CODE_OAUTH_TOKEN` or `ANTHROPIC_API_KEY` globally, never print the token,
   never put it in argv. Log every run (tokens, est. USD, usage-limit pauses) in `docs/RUNS.md`.
   See `specs/auth-and-usage.md`.
7. **No employer code.** The S2A arm (Phase 6) is written from scratch in this repo. Do not
   import prompts, skills or scripts from anywhere else.
8. **Keep the fairness protocol** (`specs/fairness-protocol.md`). In particular: once Phase 7
   freezes the dev/test split, the held-out test set is run **once**, in Phase 10, and never
   used for tuning.
9. **Prefer boring tools.** Python + Typer + PyYAML + pydantic + pandas + keyring, pywin32/ctypes only inside the platform layer. JUnit XML
   via `xml.etree`. No frameworks beyond that unless a phase names one.
10. **Commit at every gate.** `git commit -m "phase N: <gate summary>"`. Keep `README.md` status
    table current.
11. **Transcripts are the truth.** `run.json` and `calls.jsonl` are derived; `abb audit` recomputes
    them from the verbatim transcripts for every arm and a report is not valid until it passes.
12. **Files are the memory; the session is disposable.** The default is one Claude Code session
    running every phase in order (`phases/RUN-ALL.md`, autopilot: gate → handoff → commit → next
    phase, stopping only at its hard stop points, applying its defaults). At every phase gate,
    and whenever the user says stop or asks for a handoff, rewrite the handoff file (template
    kept; exact step, what exists, what is verified, blockers, next action) and commit. On `main`
    that file is `docs/HANDOFF.md`; in the per-phase-session variant a parallel branch
    `phase-<N>` uses `docs/HANDOFF-phase-<N>.md` and never touches `docs/HANDOFF.md` (the merge
    deletes the branch file). A continued or new session starts from `AGENTS.md` + the handoff
    file + `git log`; never assume anything from earlier conversation that is not in those
    files (context auto-compacts).
13. **Two packages, one contract.** `s2a/` (the framework) and `benchmark/` (the harness) are
    separate Python packages. Neither imports the other: the benchmark shells out to the `s2a`
    CLI, and the only shared things are the headless-driver contract
    (`specs/headless-agent-driving.md`) and the transcript test fixtures. Nothing in `s2a/`
    may mention hidden tests, grading, gold/test patches or task ids — the orchestrator is a
    product and must behave identically whether or not a benchmark is watching.

## Conventions

- Package name: `abb` (android brownfield bench). CLI entry point: `abb` (e.g. `abb env warm antennapod`).
- All paths in configs are relative to `benchmark/`; code uses `pathlib` only (no string joins,
  no `/tmp`, no hard-coded separators).
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
- `abb run --arm plain --arm speckit --arm s2a --tasks test --trials 3` completes on the laptop (or a Windows VM) and writes `benchmark/results/<run_id>/`.
- `abb audit <run_id>` passes and `abb report <run_id>` produces `report/summary.md` with the
  pre-registered primary comparison, pass@1, pass^3, paired-bootstrap CIs, cost per task,
  one-time setup cost per repo, interventions, control-arm comparison, and a failure breakdown.
- The README of the published benchmark states the dev/test split, the pinned model, the number
  of trials, the known limits of the sample size, and the date of the single held-out run.
