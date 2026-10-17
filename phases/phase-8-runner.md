# Phase 8 — Runner: full matrix, parallelism, resume, budget guard

**Goal.** `abb run` executes any arms × tasks × trials matrix unattended, in parallel,
resumably, within a USD cap, writing a manifest that makes the run reproducible.

**Prerequisites.** Phase 4 gate (minimal runner), ideally Phases 5–6 so the matrix is real.

**Effort.** ~1 week part-time.

## Deliverables

```
benchmark/abb/harness/run.py              # replaces the minimal runner
benchmark/abb/harness/scheduler.py        # worker pool over containers; per-repo setup gating
benchmark/abb/harness/manifest.py
benchmark/abb/harness/costmeter.py        # running USD total (thread-safe), --max-usd stop
benchmark/scripts/rented-box-setup.sh     # Ubuntu 24.04: docker, uv, git, clone, load images or rebuild
benchmark/tests/test_scheduler.py         # resume rule, retry-once on harness_error, budget stop (with a fake arm)
docs/RUNS.md                              # lab notebook continues
CLI: abb run --arm A [--arm B …] --tasks dev|test|all|<ids> --trials k --parallel n --model m --label L
             [--max-usd X] [--grade] [--resume <run_id>] [--dry-run] [--allow-image-drift]
     abb run status <run_id>       abb run abort <run_id>
```

## Steps

1. **Matrix + manifest.** Expand (arm, task, trial); write `manifest.json` per
   `specs/results-layout.md` before starting (model, limits, image digests incl. the s2a layer
   tags and base digests, versions, `s2a_git_sha`, network mode, `allow_image_drift`,
   `task_set_sha256`, split sha, `prereg_sha256`, host info, harness git sha); append to
   `resumes[]` on every `--resume` and set `aborted_reason` on budget/SIGINT stops. `--network
   open` is refused when the task set includes `split: test` tasks. `--dry-run` prints the matrix and
   estimated cost (mean cost per arm from `docs/RUNS.md` numbers if provided via
   `config/cost_estimates.yaml`).
2. **Image drift guard.** Each task's `validation.image_digest` must equal the current lock
   digest for its repo, else refuse (or `--allow-image-drift`, recorded in the manifest).
3. **Scheduler.** Thread pool of `--parallel` workers; each job = one trial: workspace →
   `arm.run` → write files → (optional) grade in a second container. Before the first job of
   (arm, repo), run `one_time_setup` once (lock per key) and store under `setup/`. Order jobs
   so that trials of the same task are spread over time (not back to back) and arms are
   interleaved — this evens out API-side variance and rate limits.
4. **Resume rule.** `--resume <run_id>` skips trial dirs that are complete (run.json +
   diff.patch + grade.json); partial dirs are wiped and re-run. Append to a `events.jsonl`
   log (job start/end/skip/retry) for auditing.
5. **Retry policy.** `exit_reason == harness_error` (docker down, unparsable transcript, model
   drift) → re-queue once, identically for every arm; still failing → leave the dir with
   `run.json` and no grade (a "trial lost" line in the report, excluded from denominators).
   `agent_error` — including an orchestrator crash — is never retried. Retry counts per arm go
   into `events.jsonl` and the report.
6. **Cost meter.** Sum `cost_usd` as trials finish; when `--max-usd` is crossed, stop
   *launching* new jobs, let running ones finish, mark `manifest.aborted_reason = "budget"`.
   Also stop on SIGINT gracefully (`abb run abort` writes a stop-file the scheduler polls).
7. **Rate limits.** Claude Code retries 429s internally and reports them as `system` events
   (`subtype: api_retry`); the driver counts them into `PhaseCall.rate_limit_retries`. Only when
   a call ends **without a `result` line** because retries or auth were exhausted does the
   scheduler back off that worker 60 s and re-queue the trial once (logged as `rate_limited`,
   not as an agent failure). Report the total retry count per run.
8. **Rented machine.** `scripts/rented-box-setup.sh` installs Docker + uv, clones the repo,
   rebuilds images (or `docker load`s them from a tarball you `docker save`d — faster), and
   runs a smoke trial. Document in `benchmark/README.md` (section "Running the full matrix").
9. **Laptop parallelism check**: `--parallel 2` on dev5 for two arms with `docker stats` open;
   no OOM kills (`dmesg`/Docker events). Record memory numbers in `docs/RUNS.md`.
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

Passes when resume skips exactly the completed trials, the budget stop works, two containers
run in parallel on the laptop without OOM, and the manifest records everything listed in the
results spec.

## Pitfalls

- Docker SDK calls are not all thread-safe; create one client per worker.
- Containers left behind after a crash: name them with the run id and have `abb run abort`
  / startup sweep `docker ps -a --filter name=abb-<run_id>`.
- Prompt-cache benefits come from running the same repo's trials close together **per arm**;
  interleaving arms reduces that a little — accept it, record it.
