# Phase 6 — The S2A orchestrator (the framework) and Arm C

**Goal.** Build `s2a/` — the standalone orchestrator from `specs/s2a-orchestrator.md` — so that
`s2a run "<prompt>"` executes a change in an existing Android repo end to end (intake → map →
locate → reproduce/characterize → spec → plan → implement → verify → fix → report) with
machine-checked gates, budgets and resumable state. Then install it for the sandbox user
and wrap it as Arm C with its ablations. After Phase 7 freezes the split, tune on the dev set
only.

**Prerequisites.** Phase 4 gate (the driver contract and transcript fixtures exist). Phase 1
environments. Written from scratch in this repo; no external prompts or scripts.

**Effort.** ~2 weeks to build; ~2 weeks of dev-set tuning interleaved with Phases 7–9. Can run
in parallel with Phases 5 and 7.

## Deliverables

```
s2a/pyproject.toml  s2a/README.md                                                        # seeds provided
s2a/s2a/pipeline.yaml  s2a/s2a/profiles/android.yaml  s2a/s2a/prompts/*.md              # seeds provided; data lives inside the package
s2a/s2a/{__init__,cli,orchestrator,state,driver,gates,render,profile}.py
s2a/s2a/stages/{base,intake,map,locate,reproduce,spec,plan,implement,verify,fix,report}.py
s2a/tests/{test_gates,test_state,test_render,test_plan_parse,test_verdict,test_driver_parser}.py
s2a/tests/fixtures/                      # sample artifacts; transcript fixtures shared with the benchmark
s2a/CHANGELOG.md                         # every prompt/pipeline change with date and dev-set result before/after
benchmark/abb/harness/sandbox.py         # + `abb sandbox install-s2a`: uv tool install <repo>\s2a into ABB_HOME\tools\uvtools (s2a.exe in tools\bin) at s2a_git_sha; harness user
benchmark/abb/arms/s2a/arm.py            # Arm C wrapper: one_time_setup -> `s2a map`; run -> `s2a run …` (env `S2A_AUTONOMOUS=1`)
benchmark/abb/arms/s2a/config.yaml       # ablation -> --skip mapping; limits pass-through
benchmark/abb/arms/registry.py           # + s2a, s2a-nomap, s2a-noverify, s2a-norepro
benchmark/tests/test_s2a_arm.py          # calls.jsonl -> PhaseCall mapping; ablation flags; artifact capture
docs/DECISIONS.md                        # D-015 (orchestrator), D-016 (principles) already drafted; confirm
```

## Steps

1. **Package skeleton.** `uv init` in `s2a/`; `s2a --help` lists `run|resume|status|map|show`
   with the flags from the spec (`--map`, `--append-system-prompt-file`, `--interactive`,
   `--skip`, limits). Data files are loaded with `importlib.resources` from `s2a/s2a/`
   (`S2A_PIPELINE`/`S2A_PROFILE_DIR`/`S2A_PROMPT_DIR` override). Pydantic models for
   `pipeline.yaml` (stages, gates, budgets) and `profiles/*.yaml` (`extra="forbid"`); the seeds
   must load. `state.py`: `RunState` with atomic save, `load`, `next_stage()`, `mark()`,
   `exit_reason`, and `progress.md` rendering.
2. **Driver.** `s2a/driver.py` implements `run_headless` per `specs/headless-agent-driving.md`
   (same flags, nudge protocol, verbatim transcript, PhaseCall records, model assertion, and the
   probe rule: a stage call without a `success` result and without an explaining subtype runs
   one probe; limit/429 → `state.json.exit_reason: usage_limited`, exit 6; 401/403 →
   `auth_failed`, exit 6; `s2a resume` continues from the same stage). Copy the benchmark's
   transcript fixtures — including `probe-ok.jsonl` and `probe-limited.jsonl` — into
   `s2a/tests/fixtures/transcripts/` and make `test_driver_parser.py` identical in intent to
   the benchmark's parser test; both must pass. Test exit 6 + resume with the limited fixture.
3. **Rendering.** `render.py`: templates with `{{…}}` placeholders; section extraction from
   `map.md` by heading (`map_commands` = "Commands" + "Test infrastructure"; `map_conventions`
   = "Conventions" + "Pitfalls"); size caps (`{{map}}` 40 kB — a 400-line map is ~25–35 kB —,
   other placeholders 12 kB, diff 60 kB with per-file truncation and a `--stat` header);
   `question_policy` and `assumptions_or_questions_heading` filled from the mode.
4. **Stage framework.** `stages/base.py`: `Stage.build_prompt(ctx)`, `Stage.run(ctx) ->
   StageResult`, `Stage.gate(ctx) -> GateResult`; the orchestrator loop: for each stage in
   `pipeline.yaml` → skip if `--skip`/cached → run (fresh session; per-task for implement) →
   gate → retry per config → record → save state. Budgets: pass `--max-turns
   min(stage.turns, remaining)` and the remaining USD; stop with exit 4 when exhausted.
5. **Gates** (`gates.py`), each a pure function `(ctx) -> (ok, message)`: `artifact_exists`,
   `ticket_type_parses`, `ticket_size_parses`, `map_json_valid`, `map_test_command_runs`
   (render `profile.commands.test_smoke` with `map.json.smoke`, run, parse JUnit XML; store the
   result as that module's baseline), `listed_paths_exist`, `min_candidates`,
   `repro_tests_behave` (run listed tests; bug → all fail with assertion failures, refactor →
   all pass, feature → compiles),
   `min_criteria`, `every_criterion_has_verification`, `criteria_ids_unique`,
   `unchanged_behaviour_present_for_bugs`, `plan_json_valid`, `one_fixes_repro_task_for_bugs`,
   `every_criterion_covered`, `modules_and_tasks_known` (every task's `module`/`task` pair is in
   `map.json`; with `--skip map`, validated by one `./gradlew <module>:tasks --all` run per
   module, cached in state), `paths_exist_or_new`, `compiles` (renders `profile.commands.build`
   with the module's `compile_task` from `map.json` or the profile defaults), `task_tests_pass`,
   `repro_tests_pass_from_fixing_task` (applies to the `fixes_repro` task and every later one),
   `characterization_tests_pass_if_refactor`, `skeletons_enabled_and_pass_if_feature`,
   `repro_tests_pass` (fix stage), `verdict_consistent` (derive REJECT from any FAIL line),
   `map_lint_timed` (soft post-check: runs the lint command once on the smoke module; non-zero
   or > 300 s → `lint_seconds: null` + reason; never fails the stage),
   `no_weakened_tests` (diff of `profile.test_dirs` files: removed `@Test`/`assert*` lines or
   added `weakened_test_patterns` → fail), `lint_if_enabled` (only when `lint_seconds` is a
   number < 120), `affected_modules_tests_pass` (relative to the cached baseline), `verdict_parses`.
   Every Gradle run is capped by `gate_timeout_s`. **Gates render commands from profile
   templates + `plan.json` fields; they never execute an agent-written command string.**
   Unit-test every gate with fixtures (sample JUnit XML, sample diffs, a baseline with
   pre-existing failures).
6. **Read-only stages** (`intake`, `locate`, `spec`, `plan`, `verify`, `report` polish): run with
   `Edit,Write,MultiEdit,NotebookEdit` denied; the artifact is the last assistant message that
   passes the stage's parse gate (question heuristic (b) disabled for these stages); the
   orchestrator writes it to the artifact file; `plan` also extracts the fenced JSON into
   `plan.json`. After each read-only stage run the `clean_tree` post-check: `git status
   --porcelain` must be empty, else revert and record `stray_edits`.
7. **Map stage.** Cache under `.s2a/map.{md,json}` keyed by `(git rev-parse HEAD, profile,
   prompt hash)`; `s2a map --refresh` rebuilds; staleness = key mismatch or
   `stale_after_days`; `--map PATH` bypasses the cache entirely. `s2a map` writes its
   `PhaseCall` records to `.s2a/map.calls.jsonl`. The gate actually runs the smoke test command
   the map claims works and times the lint command once. **Review the first map of each repo
   by hand** (module list, task names, conventions) and fix the prompt, not the map, if it is
   wrong — the map is regenerated, never hand-edited.
8. **Reproduce stage.** Tests are written straight into the module's test source set (so they
   ship with the change); `repro/` keeps a copy and a `manifest.json` (paths, test ids, kind,
   observed result). On gate success the orchestrator commits exactly the listed paths
   (`s2a: reproduction tests`) so the later clean-tree checks and retry resets cannot delete
   them. Gate failure after one retry → revert, `repro: unavailable` in state and
   `progress.md`; later prompts receive that note.
9. **Implement stage.** For each task in `plan.json`: fresh session with the rendered
   `implement.md`; after the session run the per-task gates; on failure `git checkout -- . &&
   git clean -fdq -e .s2a` and retry ≤ 2 times, **each in a fresh session**, with the gate
   message under `{{previous_attempt_errors}}`; if the task still fails, mark it `failed`,
   skip the remaining tasks (`on_task_exhausted`), and continue to verify/report; on success
   `git add -A && git commit -qm
   "s2a: <id> — <title>"` (configure a local git identity if none) and append the session's
   "Learned"/"Assumptions" to `progress.md`; task turn cap 35, stage total 75. After the last
   task: `affected_modules_tests_pass` relative to baseline (modules from `locate` + plan
   files) and, for features, `skeletons_enabled_and_pass_if_feature`.
10. **Verify + fix loop.** Commit before verify (`s2a: pre-verify`), run verify read-only,
    reset/clean after (keep `.s2a`), write `verify.md`, parse `VERDICT`, then apply
    `verdict_consistent` (any FAIL line ⇒ REJECT, whatever the agent wrote). On REJECT run `fix`
    (full tools), apply the fix gates (`compiles`, `no_weakened_tests`, `repro_tests_pass`,
    `affected_modules_tests_pass`; a failed gate reverts the fix and counts as the loop's
    attempt), commit `s2a: fix <k>`, then verify again; at most `fix_loops` cycles and only
    while turns remain; final verdict recorded.
11. **Report.** Generate `report.md` from artifacts (criteria table from `verify.md`,
    assumptions from state, `git diff --stat`, commands); optional 5-turn polish call if budget
    remains. Exit code per spec §2.
12. **Modes.** `--interactive`: after `spec` and `plan` write the artifact, print its path,
    save state `paused_at`, exit 5; `s2a resume` re-reads the (possibly edited) artifact,
    re-runs its gate, continues. Default (autonomous): never pauses; nudge protocol applies;
    `S2A_AUTONOMOUS=1` overrides `--interactive`.
13. **Local end-to-end.** `abb ws open antennapod --commit <dev task base> --as-agent` →
    `s2a.exe` comes from `ABB_HOME\tools\bin` (installed by step 14) → `$env:
    S2A_AUTONOMOUS=1; s2a run (Get-Content problem.md -Raw) --profile android --model
    claude-sonnet-5-5` → inspect `.s2a\runs\<id>\`. Iterate on prompts/gates until one dev task
    runs through all stages.
14. **Install the package.** `abb sandbox install-s2a` (harness user) runs `uv tool install
    <repo>\s2a` into `ABB_HOME\tools\uvtools` with `s2a.exe` in `ABB_HOME\tools\bin` (read/execute
    for the sandbox user, on the agent PATH) and
    writes `s2a_git_sha` into `env.lock.json`; the manifest records it. Re-run after every
    prompt/pipeline change (seconds); per-repo fingerprints are unaffected.
15. **Arm C wrapper** (`abb/arms/s2a/arm.py`), with `s2a.exe` on the agent PATH: `one_time_setup`
    (setup kind `s2a-map`, shared by all `s2a-*` arms except `nomap`) → `s2a map --repo <workspace>
    --profile android --model <limits.model> --max-turns 25 --max-usd <limits.max_usd>
    --timeout-min 20 --append-system-prompt-file <environment.md>` at `setup_commit`; copy
    `.s2a/map.md`, `map.json`, `map.calls.jsonl`, `map/transcripts/`, `map/prompts/` into the
    setup artifacts (the calls become the setup `PhaseCall`s). `run` → copy `map.md` +
    `map.json` into `<workspace>/.s2a/` (unless `nomap`), then (env `S2A_AUTONOMOUS=1`) `s2a run
    "<problem.md>" --repo <workspace> --profile android --map <workspace>/.s2a/map.md
    --append-system-prompt-file <environment.md> --model <limits.model> --max-turns
    <limits.max_turns_total> --max-usd <limits.max_usd> --timeout-min <limits.timeout_minutes>
    [--skip map|verify|reproduce]`; then read `.s2a/runs/<id>/calls.jsonl` → `PhaseCall`s; copy
    `transcripts/*.jsonl` → trial `transcript/` and `prompts/*.md` → trial `prompts/`, rewriting
    `transcript_path`; map `state.json.exit_reason` → `exit_reason` (`usage_limited` → trial
    `usage_limited`, attempt kept under `<run>/usage_limited/` and re-queued (D-028), scheduler pauses; `auth_failed` → run aborted `auth`;
    `gate_failed`/`paused` → `agent_error` with a note; exit code 1 or no `state.json` →
    `agent_error` too — the product crashed, never re-run); ablations pass `--max-turns 200 − <skipped stage cap>`; copy
    `.s2a/runs/<id>/*.md` + `state.json` + `plan.json` to `artifacts/`; produce the scoped diff
    against the `base` tag. Registry: `s2a`, `s2a-nomap`, `s2a-noverify`, `s2a-norepro`.
16. **Tests.** Gates, state resume (kill after task 1 → resume finishes task 2), plan.json
    parsing, verdict parsing, render caps, arm mapping. `uv run pytest` green in both packages.
17. Run `s2a`, `s2a-nomap`, `s2a-noverify` (and `s2a-norepro` if budget allows) on dev5 × 1
    (Sonnet 5.5). Grade. Report. Compare stage costs in `docs/RUNS.md`.
18. **Tuning protocol (until Phase 10):** steps 1–17 are *bring-up* (making the pipeline run at
    all) on the pinned-dev `dev5` set; *tuning* — any change judged by results — starts only
    after `tasks/TASKSET.sha256` is committed (Phase 7 step 10). Change one thing at a time
    (prompt, gate, budget split); re-run on `split: dev` tasks (≥ 2 trials); log before/after in
    `s2a/CHANGELOG.md`;
    never read test-set tickets or results — the tuning session runs with `ABB_TUNING=1`, under
    which `abb run`, `abb tasks show` and `abb labels show` refuse any `split: test` id (hygiene,
    not a boundary; fairness-protocol.md), and tuning may not begin before `tasks/TASKSET.sha256`
    is committed (Phase 7). Prompt hashes in `calls.jsonl` are the audit trail; `abb audit` must
    pass on every tuning run.
    **Calibrate the verifier**: take 6 dev-set diffs (3 that grading resolved, 3 it did not),
    run `verify` on each, and compare verdicts to the grade; if agreement < 5/6, revise
    `verify.md` (add two short scored examples, one ACCEPT and one REJECT, drawn from dev tasks)
    and re-check. Record the agreement in `CHANGELOG.md`.
19. Commit `phase 6: s2a orchestrator + arm`.

## Acceptance gate

```
cd s2a && uv run pytest -q && uv run s2a --help
# inside a dev-task workspace as the sandbox user, autonomous end-to-end on one task:
$env:S2A_AUTONOMOUS=1; s2a run (Get-Content <trial>\problem.md -Raw) --repo <workspace> --profile android --model claude-sonnet-5-5
s2a status <run_id>                         # every stage done; verdict recorded; exit code 0 or 2
Get-ChildItem <workspace>\.s2a\runs\<run_id>       # ticket.md locate.md spec.md plan.md plan.json verify.md report.md calls.jsonl progress.md state.json
# kill a run during implement, then:
s2a resume <run_id>                         # continues at the first unfinished task, no re-done work
# benchmark:
uv run pytest -q tests/test_s2a_arm.py
uv run abb run --arm s2a --arm s2a-nomap --arm s2a-noverify --tasks dev5 --trials 1 --model claude-sonnet-5-5 --label dev5-s2a-1 --grade
uv run abb report <run_id>                  # arm sections; setup section shows `s2a map` cost per repo (absent for s2a-nomap)
```

Passes when one dev task runs through every stage with gates enforced, resume works, the
reproduction gate demonstrably fails-then-passes on a bug task, the map's commands match Phase
0's discovered commands, and all ablations complete dev5 with artifacts captured.

## Pitfalls

- **Prompt size.** The verify diff and the map can be large; cap sizes in `render.py` and
  prefer section extraction over whole files. Fresh sessions mean no cache reuse across stages;
  keep artifacts compact.
- **Gates must not depend on the agent's honesty.** Every gate runs commands itself (tests,
  compiles, path checks); it never trusts "Tests: passed" in the final message.
- **Reproduce stage on features.** Skeleton tests that are disabled must still compile; the
  gate compiles the test source set.
- **`.s2a/` hygiene.** Append `.s2a/` to `.git/info/exclude` (not `.gitignore`, which would
  change the repo); the benchmark's `diff_exclude` already lists `.s2a/**`.
- **Git identity.** The sandbox user has none; the orchestrator sets `-c user.name=s2a -c
  user.email=s2a@local` on every commit.
- **Verifier isolation** is three layers (prompt, denied edit tools, reset after); Bash remains
  available because Gradle needs it, so the reset is the real guard.
- **Do not let any prompt mention hidden tests or grading** — the orchestrator is a product;
  benchmark concerns stay in `abb/`.
