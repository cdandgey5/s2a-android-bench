# Spec: The S2A orchestrator (the framework itself)

S2A is a standalone tool, not a benchmark adapter. You start it in an existing repository, give
it one prompt, and it drives a coding agent through a fixed sequence of stages until the prompt
is fully executed: code changed, tests added, verified by an independent pass, and a report
written. The benchmark's Arm C (`abb/arms/s2a/`) is a thin wrapper that calls this tool in
autonomous mode.

```
s2a run "Playback speed resets to 1.0x after the app is restarted; it should persist." \
        --repo <workspace> --profile android          # autonomous by default; --interactive adds two approval pauses
```

The orchestrator is **deterministic Python**; the agent does the thinking inside each stage.
This is the "workflow, not free-running agent" choice: predefined code paths, machine-checked
gates between stages, bounded loops, resumable state. The brownfield-specific stages (map,
locate, reproduce/characterize, independent verify) implement the principles in
`specs/brownfield-principles.md`; each stage row below names the principles it applies.

## 1. Package layout (`S2AFramework/s2a/`)

```
s2a/
  pyproject.toml                 # package `s2a`, console script `s2a`
  README.md
  s2a/                           # the Python package; data files live INSIDE it so the wheel ships them
    __init__.py
    pipeline.yaml                # default stage order, sessions, turn budgets, gates (seed provided)
    profiles/android.yaml        # build/test/lint commands and conventions for Android (seed provided)
    prompts/                     # one Markdown template per stage + shared preamble (seeds provided)
      preamble.md intake.md map.md locate.md reproduce.md spec.md plan.md implement.md verify.md fix.md report.md
      android/                   # optional per-profile overrides, same file names
    cli.py                       # s2a run | resume | status | map | show
    orchestrator.py              # state machine: loads pipeline, runs stages, enforces gates and budgets
    state.py                     # .s2a/runs/<run_id>/state.json (atomic writes), progress.md
    driver.py                    # headless Claude Code driver: SAME contract as specs/headless-agent-driving.md
    gates.py                     # machine checks (file exists, schema valid, tests fail/pass, paths exist, diff rules)
    render.py                    # prompt rendering ({{ticket}}, {{map}}, …) with size caps
    profile.py                   # profile loading; command templates (test for module/class/method)
    platform/{base,windows,posix}.py   # same contract as specs/platform-layer.md (own copy; no import from the benchmark)
    stages/
      __init__.py base.py intake.py map.py locate.py reproduce.py spec.py plan.py implement.py verify.py fix.py report.py
  tests/
```

Data files (`pipeline.yaml`, `profiles/`, `prompts/`) are loaded with `importlib.resources`, so
`uv tool install <repo>\s2a` and `pip install git+…` both work; `S2A_PIPELINE`, `S2A_PROFILE_DIR`
and `S2A_PROMPT_DIR` env vars override them for experiments.

Everything the orchestrator writes lives under `.s2a/` in the target repo:

```
.s2a/
  map.md  map.json  map.calls.jsonl   # per repo; cached by (commit, profile, prompt hash); calls = the map stage's PhaseCall records
  map/transcripts/  map/prompts/       # the map stage's raw stream-json and exact prompts
  baseline/<module>.json               # test results at base_commit, cached once per module (gates compare against this)
  runs/<run_id>/
    state.json                   # machine state (below)
    progress.md                  # human-readable log: what is done, what is next, assumptions so far
    ticket.md locate.md spec.md plan.md plan.json verify.md report.md
    repro/                       # copy of the reproduction / characterization tests + manifest.json (the tests live in the module's test source set)
    calls.jsonl                  # one PhaseCall-compatible record per headless call (cost, turns, tokens)
    prompts/<stage>[-k].md       # exact prompt text sent (audit)
    transcripts/<stage>[-k].jsonl
```

`.s2a/` is git-ignored by the orchestrator (it appends to `.git/info/exclude`), so it never
lands in the user's commits or in the benchmark's graded diff.

## 2. CLI

```
s2a run "<prompt>" [--repo PATH] [--profile android] [--interactive]
        [--model ID] [--max-turns N] [--max-usd X] [--timeout-min T]
        [--skip STAGE[,STAGE]] [--run-id ID] [--branch NAME]
        [--map PATH]                      # use this map as-is (no cache-key or staleness check)
        [--append-system-prompt-file PATH] # text placed BEFORE s2a's own preamble on every call
s2a resume <run_id>                 # continue from the first stage that is not done
s2a status <run_id>                 # stage table, budgets used, tool-error counts, next action
s2a map [--refresh] [--repo PATH] [--profile P] [--model ID] [--append-system-prompt-file PATH]
        [--max-turns N] [--max-usd X] [--timeout-min T]
                                    # (re)build the codebase map only; records calls in .s2a/map.calls.jsonl
s2a show <run_id> <artifact>        # print ticket | spec | plan | verify | report
```

Defaults: `--repo .`, `--profile` auto-detected (`settings.gradle*` → android), **autonomous
mode** (the run goes from prompt to report without stopping; `--interactive` opts into the two
approval pauses), `--max-turns 200`, `--max-usd 15`, `--timeout-min 45`,
`--branch s2a/<run_id>`. `S2A_AUTONOMOUS=1` forces autonomous even if `--interactive` is given
(used by CI and the benchmark).

Exit codes: 0 = report written with verdict ACCEPT; 2 = finished with verdict REJECT after the
fix loop (report explains); 3 = stopped at a gate that could not be passed; 4 = budget/timeout
exhausted; 5 = paused for human input (interactive mode); 6 = the model service refused the
request (usage limit or authentication) — state is saved and `s2a resume` continues once it is
available; 1 = orchestrator error.

## 3. Modes

| Mode | Questions | Checkpoints | Use |
|---|---|---|---|
| `autonomous` (default) | Never. Every stage prompt says: make the most likely assumption, record it under `## Assumptions`, continue. The orchestrator also applies the nudge protocol (`specs/headless-agent-driving.md`) if a call still ends with a question. | none | "give a prompt, get the change"; benchmark; CI |
| `interactive` (`--interactive`) | The `spec` stage may list `## Open questions`. The orchestrator **pauses** after `spec` and after `plan` (exit code 5) and prints the artifact; the human edits the file and runs `s2a resume`. | after spec, after plan | teams that want to approve the spec and plan |

Both modes run the same stages with the same prompts; the only differences are the question
policy and the two pause points.

**Nudges on artifact-returning stages.** For read-only stages (intake, locate, spec, plan,
verify, report) the artifact is the **last assistant message that passes the stage's parse
gate**; the question heuristic (b) of the nudge protocol is disabled for them (their formats
legitimately contain "Unknowns"/"Open questions"), while trigger (a) (an `AskUserQuestion`
call) still nudges. For editing stages the full protocol applies.

## 4. Stages

All stages run in **fresh sessions** with just the artifacts they need (just-in-time context,
no accumulated transcript), except `implement`, which runs one fresh session **per plan task**.
`turns` are per-stage caps from `pipeline.yaml`; the orchestrator passes the smaller of the stage
cap and the remaining total (default 200) to every call. The caps sum to 170 without `map`
(5+15+15+15+15+75+15+15, which already includes one verify and one fix), so the first fix's
re-verify (+15 = 185) fits in 200; a second fix loop (+30) and the report polish are
opportunistic. `map` (40; 25 until D-059) counts against the total only when it
actually runs in this invocation (it is cached per repo, or supplied with `--map`).

Gate failures and turns (D-051). A call's work always reaches its gate, even when the call used
up the turn budget (gates cost no turns); the budget check before the next call is what ends a
run on `max_turns`. Every stage whose gate can fail gets **one retry** in a fresh session with the
failed check (and, for test gates, the tail of the Gradle output) appended — `intake`, `locate`,
`spec` and `plan` as well as `map` and `reproduce` — within the stage's own turn cap; a retry is
not started when fewer than 5 of the stage's turns are left. After that, the read-only stages stop
the run with exit 3 and `reproduce` records `repro: unavailable`.

| # | Stage | Reads | Writes | Gate (machine-checked by the orchestrator) | Turns | Principles applied |
|---|---|---|---|---|---|---|
| 0 | `intake` | prompt, profile | `ticket.md`: title; `type` ∈ bug/feature/refactor/chore; `size` ∈ S/M/L; description; "done when"; constraints; unknowns | file exists; `type:` and `size:` lines parse | 5 | Normalize the request and agree "done" before touching code; `size` lets a deployment scale ceremony (`pipeline.yaml: small_change_skips`; empty in the benchmark) |
| 1 | `map` | repository | `map.md` + `map.json`: modules (purpose, deps, **per-module unit-test task and compile task**), **exact** build/test/lint commands (flavors!), test infrastructure (frameworks, Robolectric, fixtures), conventions (DI, threading, persistence, navigation, UI toolkit, error handling), 15 central files ranked by references, pitfalls; `lint_seconds` (the gate times the lint command once) | `map.json` validates; the smoke test command it names **actually runs** (orchestrator renders `profile.commands.test_smoke` with `map.json.smoke`, runs it, parses JUnit, and records the result as that module's baseline; a compile failure → retry map once). **Soft post-check** `map_lint_timed`: times `profile.commands.lint` once on the smoke module; non-zero exit (e.g. lint dependencies not cached offline) or > 300 s → `lint_seconds: null` + reason, lint gate disabled — never fails the stage | 40 (D-059; one-time per repo; cached by commit + profile + prompt hash; `--refresh` or staleness rebuilds; **`--map PATH` uses a supplied map as-is with no key check** — this is how the benchmark injects the map built at `setup_commit` into history-free workspaces) | Repository map; document the project before changing it; reviewed once by a human per repo |
| 2 | `locate` | ticket, map | `locate.md`: ranked candidate files/symbols with evidence; callers/callees; existing tests touching them; **blast radius** (modules/features affected, persisted data, public APIs); entry points for reproduction | every path listed exists; ≥ 1 candidate | 15 | Hierarchical localization; read before write; impact analysis |
| 3 | `reproduce` (bug) / `characterize` (refactor) / `acceptance-skeleton` (feature) | ticket, locate, map | `repro/`: bug → a unit test that **fails now** and encodes the expected behaviour; refactor → characterization tests that **pass now** and pin current behaviour of the code about to change; feature → acceptance test skeletons (compile, may be disabled) | orchestrator runs them: bug tests must fail with assertions; characterization must pass; skeleton must compile. On failure: one retry with the test output; then `repro: unavailable` is recorded and the run continues (never silently). On success the orchestrator **commits the listed test files** (`s2a: reproduction tests`) — otherwise the clean-tree check after `spec`/`plan` and the implement retries would delete them | 15 | Reproduce before fixing; characterization tests before changing legacy code; tests as the spec |
| 4 | `spec` | ticket, map, locate, repro result | `spec.md`: goal; scope / out of scope; **acceptance criteria** (numbered, EARS-style "WHEN … THE SYSTEM SHALL …", each with its verification: test name or concrete observation); **unchanged behaviour** ("THE SYSTEM SHALL CONTINUE TO …", mandatory for bugs); assumptions (autonomous) or open questions (interactive); **compatibility constraints** (public API, DB schema/migrations, persisted formats, i18n strings, feature flags); risks | ≥ 1 criterion; ids unique; every criterion has a verification method; bugs have ≥ 1 unchanged-behaviour item; interactive: human approval | 15 | Specify the change, not the system; testable criteria; unchanged behaviour explicit (Hyrum) |
| 5 | `plan` | spec, locate, map | `plan.md` + `plan.json`: ordered **small** tasks (each independently verifiable), per task: files, approach (`sprout` new code / `wrap` existing / `modify` in place — prefer the least invasive that fits the codebase's conventions), tests to add or extend, exact commands, criteria covered, and for bugs exactly one task flagged `fixes_repro: true` (the task after which the reproduction test must pass); **preparatory refactoring tasks first** when a change is hard to make safely; rollback note | every criterion covered by ≥ 1 task; every task's `module` + `task` pair appears in the map (`modules_and_tasks_known`; with `--skip map` the orchestrator validates them with one `./gradlew <module>:tasks --all` run per module and uses `profile.commands.defaults` for the compile task — gates stay on, so the ablation measures the map, not the gates); every path exists or is marked `new`; bugs: exactly one `fixes_repro` task; interactive: human approval. **Gates never execute an agent-written command string**; they render profile templates from `module`/`task`/`tests` | 15 | Make the change easy then make the easy change; small reviewable steps; seams/sprout/wrap |
| 6 | `implement` | plan task *k*, spec criteria, map (commands + conventions), `progress.md`, `git diff --stat` | code + tests; the orchestrator commits `s2a: <id> - <title>` after each task; `progress.md` updated with what was done, what was learned, what is next | per task: compile OK; the task's tests pass; from the `fixes_repro` task onward the bug repro tests pass; for refactors the characterization tests still pass after every task; **no existing test assertion weakened** (diff check against `profile.test_dirs`: deletions of `assert*`/`@Test` lines, added `@Ignore`/`@Disabled` → task fails); lint if `lint_seconds` < 120; on failure: `git checkout -- . && git clean -fdq -e .s2a`, then retry the task ≤ 2 times, **each retry in a fresh session** with the gate output appended; a task that still fails stops `implement` (fail fast) — remaining tasks are skipped, `verify` runs and will REJECT, `report` names the task; after the last task: the affected modules' unit tests pass **relative to baseline** (no test that passed at `base_commit` fails now), and for features the acceptance skeletons are enabled and pass. The orchestrator makes every commit; agents never commit | 75 (shared across tasks; a task may not exceed 35) | One task at a time in a fresh session; baseline check first; verify after every step; leave a clean state; never game tests; fail fast and reset context |
| 7 | `verify` | ticket, spec, `git diff <base>`, repro, map | `verify.md` (returned as the final message; the orchestrator writes the file): per acceptance criterion and per unchanged-behaviour item PASS/FAIL with evidence; full unit tests of affected modules; regression scan (tests outside the change that now fail; observable behaviour changed that the spec does not require = defect); scope creep (files outside `locate` without justification); convention check (names, package layout, patterns used by neighbours); last line `VERDICT: ACCEPT` or `VERDICT: REJECT` + defect list | `verdict_parses`; **`verdict_consistent`: the orchestrator derives the verdict itself — any AC/UB line marked FAIL ⇒ REJECT, overriding the agent's last line** (hard threshold enforced in code, not trusted to the model); working tree reset to the pre-verify commit (`git reset --hard && git clean -fdq -e .s2a`), `verifier_modified_tree` recorded | 15 | Independent evaluator with fresh context and hard thresholds, never self-grading; evaluator–optimizer loop |
| 8 | `fix` | verify defects, plan, progress | code changes addressing exactly the listed defects; the orchestrator commits them (`s2a: fix k`) | same gates as a task: compiles; no weakened tests; repro/characterization tests pass; affected modules' tests pass relative to baseline; then re-run `verify`; loop ≤ 2 (`fix_loops`; the second only if turns remain) | 15 | Bounded repair loop with the same guardrails as implementation |
| 9 | `report` | everything | `report.md`: summary; criteria → evidence table; assumptions; residual risks; files changed; how to run the tests; suggested PR description | exists (the orchestrator always writes the draft from artifacts; the polish call is skipped when no turns remain) | 5, optional | Reviewable change; traceability |

`--skip map` removes stage 1 (prompts fall back to "discover commands yourself"); `--skip
verify` removes 7 and 8; `--skip reproduce` removes 3. These are the benchmark ablations
(`s2a-nomap`, `s2a-noverify`, `s2a-norepro`).

## 5. Budgets and limits

The orchestrator owns a `Limits` object identical to `specs/adapter-interface.md`
(`timeout_minutes`, `max_turns_total`, `max_usd`, `max_interventions`,
`max_interventions_per_trial`, `grade_timeout_minutes`, `model`). Each call
gets `--max-turns min(stage_cap, remaining)` and `--max-budget-usd remaining`. When the total
is exhausted the run ends with exit code 4 and a report of what was completed (the committed
tasks are kept). Stage caps live in `pipeline.yaml` and are recorded in `state.json`.

**Gate wall-clock.** Gates run Gradle themselves (compile, tests, baseline runs). That time
counts against `--timeout-min` but not against turns; each Gradle invocation is capped by
`pipeline.yaml: gate_timeout_s` (default 900) and a cap hit fails the gate. Expect 3 tasks ×
up to 3 attempts × (compile + targeted tests) plus two affected-module runs per run.

**Baseline-relative test gates.** Brownfield repos often have tests that already fail. The
first time a module's tests are needed, the orchestrator runs them at `base_commit`
(`.s2a/baseline/<module>.json`); `task_tests_pass`, `affected_modules_tests_pass` and the fix
gates fail only on tests that passed at baseline and fail now, plus the tests the task itself
names. `map_test_command_runs` is satisfied by a run that compiles and produces JUnit XML even
if some tests fail; those failures become the baseline.

## 6. State and resumability (`state.json`)

```json
{
  "run_id": "20261105-1412-playback-speed",
  "prompt": "...", "mode": "autonomous", "profile": "android", "branch": "s2a/20261105-1412-playback-speed",
  "base_commit": "abc123", "model": "claude-opus-5-5",
  "limits": {...}, "used": {"turns": 87, "usd": 3.41, "seconds": 1260},
  "stages": {
    "intake": {"status": "done", "attempts": 1, "calls": ["intake"]},
    "map": {"status": "done", "cached": true},
    "locate": {"status": "done"},
    "reproduce": {"status": "done", "result": "failing_test_written"},
    "spec": {"status": "done", "approved": null},
    "plan": {"status": "done", "tasks": 3},
    "implement": {"status": "running", "current_task": 2, "task_status": {"1": "done", "2": "running"}, "turns_used": 41},
    "verify": {"status": "pending"}, "fix": {"status": "pending"}, "report": {"status": "pending"}
  },
  "assumptions": ["Persist speed per app, not per podcast (ticket does not say)"],
  "exit_code": null,
  "exit_reason": null              # completed | max_turns | timeout | budget | agent_error | harness_error | gate_failed | paused | usage_limited | auth_failed
}
```

`exit_reason` uses the benchmark's `ExitReason` enum plus `gate_failed`, `paused` and
`auth_failed`, so Arm C maps it directly (exit code 4 alone does not say whether turns, time or money ran out). Per-stage
`turns_used` is recorded so the benchmark can report where the budget went. With
`--skip verify` there is no verdict: the run exits 0 when `implement` finished with every gate
green (`verdict: null` in state and report), 3 otherwise.

`s2a resume` re-enters at the first stage not `done`; `implement` resumes at the first task not
`done` (tasks are committed individually, so the tree is clean). Every write is atomic (tmp +
rename). `progress.md` is the human-readable mirror and is also given to every implement
session (this is how context survives fresh sessions).

## 7. Driver contract

`s2a/driver.py` implements `run_headless` exactly as `specs/headless-agent-driving.md`
(flags, verbatim transcript, nudge protocol, PhaseCall records, model assertion, **and the probe
rule**: a stage call that ends without a `success` result and without an explaining subtype
triggers one probe call, `claude -p "ping" --tools "" --max-turns 1` on the same model, kept
as `.s2a/runs/<id>/transcripts/probe-<stage>-<n>.jsonl`; limit text or 429 → the orchestrator
writes `state.json` with `exit_reason: usage_limited` and exits 6 without consuming a fix
attempt; 401/403 → `exit_reason: auth_failed`, exit 6; probe ok → the stage's own outcome
stands), plus one harness-health field: `tool_errors` (count of `tool_result` blocks with `is_error`), reported per
stage in `status`. It runs `claude` as a **local subprocess** of whatever user runs `s2a` (inside
the benchmark that is the sandbox user; no sandboxing of its own) with the same argv, and enforces its own per-call deadline through its platform
layer exactly as the benchmark does: the interrupt named in `sandbox.yaml: process.interrupt`
(`sandbox.yaml: process.interrupt` — Ctrl+C to its own launcher console since D-032; SIGINT elsewhere), wait 30 s for the
`result` line, then kill the process tree; a harness-initiated stop is `timeout`. When the outer
harness interrupts the orchestrator itself (SIGBREAK/`KeyboardInterrupt`), it forwards the same
interrupt to its running child, waits `grace_s`, writes `state.json` with `exit_reason: timeout`
and exits 4. The benchmark
does **not** import it (the benchmark's own driver serves the plain and Spec Kit arms); both are
kept identical by a shared test fixture set (`benchmark/tests/fixtures/transcripts/`) that both
packages' parsers must pass. The orchestrator writes `calls.jsonl` in the `PhaseCall` schema so
the benchmark arm can lift the records straight into `run.json`.

Tool policy per stage: `intake`, `locate`, `spec`, `plan`, `verify`, `report` run with
`Edit,Write,MultiEdit,NotebookEdit` denied (they return their artifact as the final message;
the orchestrator writes the file). Because Bash remains available, **after every read-only
stage the orchestrator runs `git status --porcelain`**: any change is reverted (`git checkout
-- . && git clean -fdq -e .s2a`) and recorded as `stray_edits` for that stage, so nothing
leaks into the next task's `git add -A`. `map`, `reproduce`, `implement`, `fix` have full
tools. `WebFetch,WebSearch` are denied everywhere.

System prompt on every call = (optional `--append-system-prompt-file` text) + s2a's own
`prompts/preamble.md` (rendered). The sha256 of the combined text is recorded per call in
`calls.jsonl`, so a benchmark can prove the shared environment preamble was identical across arms.

## 8. Profiles

A profile is what makes S2A Android-first now and extensible later. `profiles/android.yaml`
(seed) defines: how to detect the profile; command templates (`build`, `test_module`,
`test_class`, `test_method`, `lint`, `test_smoke`); `test_dirs` globs; flavor detection hints;
offline flags; Robolectric notes; a conventions checklist the `verify` stage uses; and
stage-prompt overrides (`prompts/android/*.md` win over `prompts/*.md` when present). Adding a
stack later = one profile file + optional prompt overrides; the orchestrator does not change.

## 9. How the benchmark uses it (Arm C)

- S2A is installed by the **harness user** via `abb sandbox install-s2a`: `uv tool install
  <repo>\s2a` into `ABB_HOME\tools\uvtools` with `s2a.exe` in `ABB_HOME\tools\bin` (read/execute
  for the sandbox user) at the current `s2a_git_sha`,
  which goes into `env.lock.json` and the manifest. Prompt tweaks during tuning re-run that
  install in seconds; the per-repo environment fingerprint is unaffected. All arms share the same
  toolchain, warm caches and Claude Code version.
- `one_time_setup` (setup kind `s2a-map`, **shared by every `s2a-*` arm except `s2a-nomap`**, so
  ablations differ only in the skipped stage, not in a re-rolled map): `s2a map --repo <workspace>
  --profile android --model <pinned> --max-turns 25 --max-usd <X> --timeout-min 20
  --append-system-prompt-file environment.md` in a workspace at `setup_commit`; the arm copies
  `.s2a/map.md`, `map.json`, `map.calls.jsonl`, `map/transcripts/`, `map/prompts/` into
  `setup/s2a-map/<repo>/` (the calls become the setup `PhaseCall`s) and later `map.md` +
  `map.json` into every S2A task workspace.
- `run`: `s2a run <problem.md text> --repo <workspace> --profile android` with `S2A_AUTONOMOUS=1` in the environment block
  --map <workspace>/.s2a/map.md --append-system-prompt-file environment.md --model <pinned>
  --max-turns 200 --max-usd <X> --timeout-min 45 [--skip …]`. `--map` is essential: task
  workspaces are history-free (`git init` + one commit), so a cache keyed on the commit would
  never match and the map would be rebuilt per task, at the wrong commit. The arm then reads
  `.s2a/runs/<id>/calls.jsonl` → `PhaseCall`s; copies `.s2a/runs/<id>/transcripts/*.jsonl` into
  the trial's `transcript/` and `.s2a/runs/<id>/prompts/*.md` into `prompts/`, rewriting each
  `PhaseCall.transcript_path` to the copied location; maps `state.json.exit_reason` →
  `exit_reason` (**`usage_limited` → the trial is `usage_limited`: attempt kept under
  `<run>/usage_limited/`, re-queued, not counted in the primary metric (D-028), scheduler
  pauses — the same rule as every other arm, `specs/auth-and-usage.md` §3;
  `auth_failed` → the run aborts with `aborted_reason: auth`**; `gate_failed`/`paused` →
  `agent_error` with a note; **exit code 1 or a missing `state.json` → `agent_error` too — the
  product crashed; it is never re-run, D-017**); copies `.s2a/runs/<id>/*.md` + `state.json` + `plan.json`
  to `artifacts/`; and produces the scoped diff against the `base` tag (commits on the `s2a/*`
  branch are part of the diff; `.s2a/` is excluded).
- Ablations pass `--max-turns 200 − <skipped stage cap>` (`noverify`: 170, `norepro`: 185;
  `nomap`: 200 because the map is one-time setup) so skipped turns are not reallocated.
- Fairness: the arm passes the same model and limits as every other arm; the orchestrator's
  driver uses the same flags; the shared `environment.md` goes in front of s2a's preamble via
  `--append-system-prompt-file`; prompt hashes go into `run.json`.

## 10. What is deliberately out of scope for v1

Parallel task execution, multi-repository changes, UI screenshot verification, automatic PR
creation, routing open questions to a chat UI, non-Android profiles (the mechanism exists; the
profiles do not yet).
