# Phase 8 — Runner: full matrix, parallelism, resume, budget guard

**Goal.** `abb run` executes any arms × tasks × trials matrix unattended, in parallel,
resumably, within a USD cap, writing a manifest that makes the run reproducible.

**Prerequisites.** Phase 4 gate (minimal runner), ideally Phases 5–6 so the matrix is real.

**Effort.** ~1 week part-time.

## Deliverables

```
benchmark/abb/harness/run.py              # replaces the minimal runner
benchmark/abb/harness/scheduler.py        # worker pool over trials (one Job Object each); per-repo setup gating
benchmark/abb/harness/manifest.py
benchmark/abb/harness/costmeter.py        # running USD total (thread-safe), --max-usd stop
benchmark/scripts/vm-setup.ps1            # optional Windows VM: winget installs, clone, `abb tools install`, `abb env warm`, `abb sandbox setup`
benchmark/tests/test_scheduler.py         # resume rule, retry-once on harness_error, budget stop (with a fake arm)
docs/RUNS.md                              # lab notebook continues
CLI: abb run --arm A [--arm B …] --tasks dev|test|all|<ids> --trials k --parallel n --model m --label L
             [--max-usd X] [--grade] [--resume <run_id>] [--dry-run] [--allow-env-drift]
     abb run status <run_id>       abb run abort <run_id>
```

## Steps

1. **Matrix + manifest.** Expand (arm, task, trial); write `manifest.json` per
   `specs/results-layout.md` before starting (model, limits, environment fingerprints, toolchain lock hash, versions, `s2a_git_sha`,
   `sandbox_mode`, `allow_env_drift`,
   `task_set_sha256`, split sha, `prereg_sha256`, host info, harness git sha); append to
   `resumes[]` on every `--resume` and set `aborted_reason` on budget/SIGINT stops. `--sandbox
   none` is refused when the task set includes `split: test` tasks. `--dry-run` prints the matrix and
   estimated cost (mean cost per arm from `docs/RUNS.md` numbers if provided via
   `config/cost_estimates.yaml`).
2. **Environment drift guard.** Each task's `validation.env_fingerprint` must equal the current lock
   digest for its repo, else refuse (or `--allow-env-drift`, recorded in the manifest).
3. **Scheduler.** Thread pool of `--parallel` workers; each job = one trial: workspace →
   `arm.run` → write files → (optional) grade in a second, harness-user workspace. Before the first job of
   (arm, repo), run `one_time_setup` once (lock per key) and store under `setup/`. Order jobs
   so that trials of the same task are spread over time (not back to back) and arms are
   interleaved — this evens out API-side variance and rate limits.
4. **Resume rule.** `--resume <run_id>` skips trial dirs that are complete (run.json +
   diff.patch + grade.json); partial dirs are wiped and re-run. Append to a `events.jsonl`
   log (job start/end/skip/retry) for auditing.
5. **Retry policy.** `exit_reason == harness_error` (platform failure, unparsable transcript, model
   drift) → re-queue once, identically for every arm; still failing → leave the dir with
   `run.json` and no grade (a "trial lost" line in the report, excluded from denominators).
   `agent_error` — including an orchestrator crash — is never retried. Retry counts per arm go
   into `events.jsonl` and the report.
6. **Cost meter and usage pauses.** Sum est. `cost_usd` and tokens as trials finish; when
   `--max-usd` is crossed, stop *launching* new jobs, let running ones finish, mark
   `manifest.aborted_reason = "budget"`. `--pause-on-usage-limit` (default on): a `usage_limited`
   trial wipes its directory, re-queues, and pauses all workers; first wake-up = parsed reset
   time + 2 min if one parsed, else 30 min; then probe every 15 min (`specs/auth-and-usage.md`
   §3; the run's `limits.model`, through the launcher as the sandbox user in a scratch
   `ABB_HOME\work\probe\<ts>`, transcript kept at `<run>/probes/<ts>-scheduler-<n>.jsonl`)
   until a probe succeeds; a 401/403 aborts the run (`auth`) at once; `--max-pause-h` (default
   48) → `aborted_reason = "usage_limit"`, resumable. `abb run status` shows `paused until …` /
   `probing`; probe events go to `events.jsonl` and `abb audit` recounts `usage_limited_pauses`
   from `<run>/probes/`;
   the pause count per arm goes into the manifest. A **matrix** run (`--tasks test`, or > 30
   trials) refuses to start if `reference/verified.md` has no usage-limit canary (Phase 4 step 8)
   unless `--allow-no-canary`, which is recorded in the manifest. At start, warn if
   `powercfg /q` shows a non-zero AC standby timeout (`docs/DAY-0.md` §2).
   Also stop on SIGINT gracefully (`abb run abort` writes a stop-file the scheduler polls).
7. **Rate limits.** Claude Code retries transient 429s internally and reports them as `system` events
   (`subtype: api_retry`); the driver counts them into `PhaseCall.rate_limit_retries`. When a
   call ends **without a `result` line** or with an unexplained error result, the driver's
   probe decides (`specs/headless-agent-driving.md` §2): limit/429 → `usage_limited` → the
   pause/probe loop of step 6; 401/403 → abort `auth`; model rejected → abort `model`; probe
   succeeds → the call's own classification stands (`harness_error` re-queued
   once per step 5; `agent_error` never retried). No trial is ever counted as a failure because
   the window closed on it. Report retry, probe and pause counts per arm.
8. **Optional Windows VM.** `scripts/vm-setup.ps1` (PowerShell 7) installs Git, `gh`, `uv`,
   Claude Code (pinned), clones the repo, runs `abb tools install`, `abb env warm` for every repo
   and `abb sandbox setup`, then a smoke trial; fingerprints must equal `env.lock.json`.
   Document in `benchmark/README.md` (section "Running the full matrix"); the default is three
   laptop nights.
9. **Laptop parallelism check**: `--parallel 2` on dev5 for two arms while watching Job Object
   peak memory (`abb run status` prints it) and Task Manager; no memory-limit kills. Record the
   numbers in `docs/RUNS.md`.
10. **Audit in the loop.** `abb run … --grade` ends by calling `abb audit <run_id>`; a failing
    audit marks the run `audit_ok: false` in the manifest and the report refuses to print
    headline numbers until it passes.
11. Commit `phase 8: runner`.

## Acceptance gate

```
uv run pytest -q tests/test_scheduler.py
uv run abb run --arm plain --arm s2a --tasks dev5 --trials 2 --parallel 2 --model claude-sonnet-5-5 --label p8-resume-test --grade
# kill it (Ctrl-C) after ~3 trials complete, then:
uv run abb run --resume <run_id>                 # skips completed trials; finishes the rest
uv run abb run --arm plain --tasks dev5 --trials 1 --max-usd 0.50 --label p8-budget-test   # stops after the first trial crosses the cap; manifest says aborted_reason: budget
uv run abb run status <run_id>                   # done/running/pending counts, cost so far
```

Passes when resume skips exactly the completed trials, the budget stop works, two trials
run in parallel on the laptop without memory-limit kills, and the manifest records everything listed in the
results spec.

## Pitfalls

- One Job Object per trial, created and closed by the worker that owns it; `KILL_ON_JOB_CLOSE`
  means a harness crash takes its trials down with it.
- Workspaces left behind after a crash: `abb run abort` / the startup sweep of `abb run` call
  `Workspace.cleanup()` on every unfinished trial of the run, and `abb env prune` reports leftovers.
- Prompt-cache benefits come from running the same repo's trials close together **per arm**;
  interleaving arms reduces that a little — accept it, record it.
