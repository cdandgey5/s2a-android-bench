# Phase 4 — Arm A (plain agent), the controls, and the first results table

**Goal.** The headless driver with the nudge protocol, the plain-agent adapter, a minimal
sequential runner, and a report that prints **real numbers** for dev5. This is the milestone
that proves the whole pipeline.

**Prerequisites.** Phase 3 gate. `ABB_OAUTH_TOKEN` set and `abb auth check` green (subscription; no API key). Dev model `claude-sonnet-5-5`.

**Effort.** ~1 week part-time.

## Deliverables

```
benchmark/abb/harness/agent_driver.py     # run_headless() per specs/headless-agent-driving.md
benchmark/abb/harness/transcript.py       # stream-json parser: tool calls, last text, result fields, model_usage
benchmark/abb/arms/__init__.py
benchmark/abb/arms/base.py                # seed provided (Limits, PhaseCall, RunResult, Arm)
benchmark/abb/arms/registry.py            # {"plain": PlainArm}
benchmark/abb/arms/common/environment.md  # shared environment preamble, byte-identical for every arm (below)
benchmark/abb/arms/plain/arm.py
benchmark/abb/arms/plain/config.yaml      # turn_cap: null  (single call gets the whole total)
benchmark/abb/arms/plain/prompts/system.md   # plain-specific lines appended after environment.md
benchmark/abb/arms/plain/prompts/task.md     # prompt template with {{ticket}}
benchmark/abb/harness/setup.py            # one_time_setup support + results/_setup_cache (no-op for plain; used by Phases 5, 6, 8)
benchmark/abb/harness/audit.py            # `abb audit <run_id>`: recompute totals from transcripts, fail on mismatch; fail if any file under the run contains the token or an sk-ant-… key (D-026)
benchmark/config/prices.yaml              # list prices per model id, dated; used only for cost_usd_imputed and the fallback estimate
benchmark/abb/harness/run.py              # minimal: one arm, sequential, writes results layout
benchmark/abb/harness/report.py           # minimal table + setup section (grows in Phase 9)
benchmark/abb/arms/plain/prompts/guided.md   # plain-guided control: the S2A workflow described in prose
# plain-gate control lives in arms/plain/arm.py (gate=True): a harness-side test run + one resume, no Claude Code hook
benchmark/tests/test_transcript.py        # fixtures: recorded stream-json files
benchmark/tests/fixtures/transcripts/*.jsonl
CLI: abb run --arm plain --tasks dev5|<ids> --trials 1 [--model …] [--label …]     abb report <run_id>
```

## Steps

1. **Transcript parser** (`transcript.py`). Phase 0 saved the two smoke-test `stream-json`
   outputs as fixtures (`smoke-success`, `smoke-maxturns1`); add one with an `api_retry` event
   and one without a `result` line (killed). Parse: per `assistant`
   message count `tool_use` blocks and names; last text block; `result` fields
   (`subtype`, `session_id`, `num_turns`, `duration_ms`, `duration_api_ms`, `total_cost_usd`,
   `usage.*`, **`modelUsage`** (camelCase), `permission_denials`, `stop_reason`); `system`
   events: the `init` model name, `claude_code_version`, `slash_commands`, and `api_retry`
   split by `error` (`rate_limit` vs other). Handle a transcript with no `result` line (cost
   `null`, `cost_usd_imputed` from per-message usage). Tolerate unknown event types.
2. **Driver** (`agent_driver.py`): implement `run_headless` exactly as specified, including the
   nudge protocol with both caps (2 per call, 4 per trial), prompt saving/hashing, verbatim
   transcript streaming, timeout via the workspace exec timeout (124/137 → timeout; 143 →
   agent_error), model/version assertions (`init`, `modelUsage`), and budget bookkeeping
   (`limits_left` mutated). Redact the OAuth token from any logged argv/env. Implement the
   `usage_limited` outcome and the **probe** (`specs/headless-agent-driving.md` §2,
   `specs/auth-and-usage.md` §3): limit text → `usage_limited`; any call without a `success`
   result and without an explaining subtype → run the probe through the launch path, keep its
   transcript under `<run>/probes/` (outside the trial), and classify from it (limit/429 →
   `usage_limited`; 401/403 → abort `auth`; model rejected → abort `model`; other → `harness_error`;
   ok → the call's own outcome; no `assistant` message + probe ok → `harness_error`); parse
   `resets <time>` when present; surface `paused_until` (hint) to the runner. Fixtures: add
   `probe-ok.jsonl` and a hand-written `probe-limited.jsonl` until the canary replaces it.
3. **Confirm question handling in `-p` mode.** The docs (2026-10) say an `AskUserQuestion`
   call is denied with no permission host, the model is told nobody can approve, the run
   continues, and the denial appears in `result.permission_denials`. Confirm once on the pinned
   CLI version: run a prompt designed to make the model ask ("Before doing anything, ask me
   which of two options I prefer using your question tool, then stop."), check the transcript
   for the `tool_use`, the denial, and whether `--resume` continues the session. Write the
   findings into `reference/verified.md`; the nudge detection in the spec covers the documented
   outcome and the "session ended" outcome.
4. **Shared preamble + plain arm.** `abb/arms/common/environment.md` (every arm, every call):
   > You are working in an existing Android repository checked out in the current directory. There is no
   > network access except the model API; Gradle must be run with `--offline`. No human is
   > available: make reasonable assumptions and state them briefly. Keep changes consistent
   > with the surrounding code and the repository's own conventions. Do not disable, delete or
   > weaken existing tests. Do not modify build configuration to skip tests.

   `abb/arms/plain/arm.py`: one call, `call_name="plain"`, `turn_cap=None` (whole budget),
   prompt = `task.md` rendered with the ticket; `append_system_prompt` = environment.md +
   `system.md`:
   > Implement the change described in the ticket, keep the change minimal, add or extend
   > unit tests where the repo has them, and make sure the affected module's unit tests pass.
   > Do not modify unrelated code.

   `task.md`:
   > ## Ticket
   >
   > {{ticket}}
   >
   > Resolve this ticket in this repository. When finished, summarise what you changed
   > and which tests you ran.

   After the call: `diff.patch` (scoped) and `diff.full.patch`; `RunResult` with
   `exit_reason` mapped from subtype (`success`→completed, `error_max_turns`→max_turns,
   `error_max_budget_usd`→budget, timeout→timeout, else agent_error).
5. **Minimal runner** (`run.py`): resolve task set (`dev5` = the 5 validated tasks of repo #1
   plus the seed, or explicit ids, or `split: dev|test` later); for each task × trial:
   `Workspace(sandbox="user")`, `snapshot`, `put` only `problem.md`'s text via the prompt,
   `arm.run`, pull `run.json`, prompts, transcripts, diffs with `Workspace.get`. Run
   `one_time_setup` once per (setup kind, repo) through `setup.py` (a no-op for plain). Then
   call the grader (`abb grade <run_id>` or inline `--grade`) and `abb audit`. Write
   `manifest.json` first (so a crash still leaves a manifest). Sequential only in this phase.
6. **Minimal report**: `abb report <run_id>` prints a table: task · trial · resolved ·
   reason · exit_reason · turns · tool_calls · interventions · cost_usd · duration · f2p summary;
   a setup section (per setup kind × repo); and a footer with totals: resolved n/N, mean cost,
   total cost, mean duration, audit pass/fail. Writes `report/summary.md`.
6b. **Controls.** `plain-guided`: the same adapter with `prompts/guided.md` appended after
   `system.md` (describes map → locate → reproduce → spec → plan → small steps → self-review in
   prose; no file paths, no task hints). `plain-gate`: after the single call, the harness runs
   the modules touched by the diff through their unit tests once; on failure it resumes the
   session once with the failing test output (recorded in `gate_gradle_runs`/`gate_seconds`,
   not as an intervention; S2A allows ≤ 2 retries per task, plain-gate exactly 1 — say so in the
   report), then stops. Both register in `registry.py`; `plain-gate` is optional in the final
   matrix.
7. **Pin versions.** Set `claude_code.version` in `config/toolchain.yaml` to the exact version used
   (≥ 2.1.280, D-026), reinstall for both users (`abb tools install`, `abb sandbox setup --refresh`), and
   record it in `env.lock.json`.
8. **Run dev5 × 1 trial on Sonnet 5.5.** Then run it again (trial 2) to see variance. Keep both
   run ids in `docs/RUNS.md` with tokens, est. USD and a one-line note each (this file is the lab
   notebook from now on). Record **trials completed per session window** — the number `PLAN.md`
   §6 uses for dev scheduling. **Usage-limit canary:** the first time any trial ends on a usage
   limit, copy the exact transcript tail, stderr, error text and exit code into
   `reference/verified.md` and adjust the detector. If dev5 × 2 never hits a limit, run
   `abb ws smoke --until-limit --max-calls 200` once when the window is nearly spent (loops the
   probe prompt through the launcher until the limit answers or the cap is reached; costs the
   rest of that window and locks your chats out until it resets) — Phase 8
   refuses `--tasks test` or > 30-trial runs without the canary unless `--allow-no-canary`.
9. Commit `phase 4: plain arm + first results`.

## Acceptance gate

```
uv run pytest -q tests/test_transcript.py
uv run abb run --arm plain --tasks dev5 --trials 1 --model claude-sonnet-5-5 --label dev5-plain-1 --grade
uv run abb report <run_id>                      # table with 6 rows of real numbers (dev5 = 5 validated tasks + the seed)
uv run abb audit <run_id>                       # all trials: run.json == transcripts
uv run abb run --arm plain-guided --tasks dev5 --trials 1 --model claude-sonnet-5-5 --label dev5-guided-1 --grade
Get-ChildItem $env:ABB_RESULTS_DIR\<run_id>\plain\*\t1   # run.json transcript\ prompts\ diff.patch grade.json metrics.json
Get-Content reference\verified.md                 # has the AskUserQuestion-in-print-mode finding
```

Passes when the table exists with real grades and costs, every trial dir is complete per the
results spec, and the cost per run for the plain arm is recorded in `docs/RUNS.md` (this number
drives the budget in PLAN.md §6).

## Pitfalls

- Output capture: the agent process writes stream-json to a file in the trial directory (cross-user
  handle inheritance is unreliable); the driver tails the file and parses newline-delimited JSON.
- If `-p` ever defaults to `--bare` in a newer version, repo `CLAUDE.md` would be ignored for
  the plain arm but not for others — the version pin protects you; re-check on every upgrade.
- The nudge heuristic will have false positives (a summary ending in "?"). Cap is 2; the cost
  is one extra short turn. Accept it; it is identical across arms.
- Keep `--max-budget-usd` ≥ 3× the observed mean so it only catches runaways (it caps the
  client-side estimate; there is no bill).

## Next (autopilot, `RUN-ALL.md`)

Gate passed → paste the gate output, rewrite `docs/HANDOFF.md`, update the README status table,
commit, push. **Report the first results table and apply the MVP default (`RUN-ALL.md` §3),
logging it as `D-0xx (autopilot default)` — Phase 7's step 1 and gate depend on it.** Then start
Phase 7: `phase-7-scale-tasks.md` (on `main`, same checkout; before any S2A code). Hard stop points ahead in it: S2 — review of drafted tasks (steps 2–4); S3 — the 3× validation nights (step 8).
