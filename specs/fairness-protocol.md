# Spec: Fairness and credibility protocol

We wrote both the framework under test (S2A) and the benchmark. These rules exist so the result
survives a sceptical reader. `docs/PREREG.md` turns them into a pre-registration that is
committed before the freeze.

## Held constant across arms (enforced by the runner, recorded in `manifest.json`)

| Item | Rule |
|---|---|
| Model | One exact model id per run for every arm and every call, including sub-agents. `switchModelsOnFlag: false`, and the driver fails a call as `harness_error` if `modelUsage` shows any non-background foreign model. |
| Auth | Same subscription token for every arm, in the environment block only; no API key anywhere (`specs/auth-and-usage.md`). |
| Agent runtime | Same pinned `claude.exe` (version asserted from the `init` event), same permission mode, same shell set (`CLAUDE_CODE_USE_POWERSHELL_TOOL=1`, Bash via Git Bash), same **baseline** tool deny list (`WebFetch,WebSearch`); an arm may deny *more* tools in some of its own calls (S2A's read-only stages do), never fewer. Autoupdate and telemetry disabled in the agent env. |
| Environment | Same environment fingerprint (toolchain + warm cache + platform) for every arm; the `s2a-*` arms additionally have the `s2a` package installed for the sandbox user at `s2a_git_sha`. |
| Input | Byte-identical `problem.md`. Arms may wrap it in their own prompt template, but may not add task-specific hints. |
| Environment preamble | `abb/arms/common/environment.md` is the first part of `--append-system-prompt` on every call of every arm, byte-identical (the s2a arm passes it via `s2a run --append-system-prompt-file`; s2a's own stage preamble follows it). |
| Limits | Same wall-clock timeout, USD cap, turn total, nudge caps (2 per call, 4 per trial). **Wall-clock and USD are the binding, comparable limits.** Turns are identical but not comparable work units: an orchestrator-run Gradle gate costs no turn while a plain-arm Gradle run does. Turns, gate runs and gate seconds are reported per arm so the reader can see it. |
| Sandbox | Same `user` sandbox for every arm (sandbox user, outbound firewall block, allow-list proxy on loopback). |
| Repo instructions | `strip_agent_instructions` identical for all arms; repo-shipped hooks/MCP removed for all. |
| Retries | None on `agent_error` for any arm; one re-queue on `harness_error` for every arm. Counts reported. |

## What "the workflow" includes (state this in the write-up)

S2A's orchestrator runs compiles and tests between stages. That verification is part of the
product a user gets, so it is part of what Arm C measures — but a reader may ask whether gates or
prompts drive the result. Two cheap **control arms** answer that: `plain-guided` (plain agent
whose system prompt describes the S2A workflow in prose; no orchestrator) and `plain-gate`
(plain agent plus a harness hook that runs the affected module's tests once and feeds failures
back). The write-up reports S2A against both, not only against `plain`.

## Reported separately

| Item | How |
|---|---|
| One-time per-repo setup (Spec Kit constitution; S2A codebase map) | `results/<run>/setup/<setup_kind>/<repo>/run.json`. Report as "setup cost per repo" and *also* as an amortised per-task number (`setup / tasks_in_repo`) in a clearly labelled column. Never fold silently into cost per task. |
| Historical (mined/reverted) vs authored tasks | Separate rows in every headline table. The primary comparison uses all test tasks; the pre-registered **contamination-robustness** check repeats it on historical post-cutoff tasks, and authored tasks are shown on their own (the framework author wrote them). |
| Pre- vs post-cutoff tasks | `upstream.fix_date` **and** `upstream.issue_created` vs the pinned model's published training cutoff (D-001); a task is post-cutoff only if both are. |
| Trials with no cost line | `cost_usd` null; `cost_usd_imputed` reported alongside; share per arm shown. All `cost_usd` figures are Claude Code's client-side estimate at API list price ("est. API-equivalent USD"); tokens are the primary unit. |
| Usage-limit pauses | `usage_limited` trials (subscription window exhausted) are re-queued and not counted in the primary metric; the cut attempt is kept under `<run>/usage_limited/` and enters the pre-registered usage-limit sensitivity check; cut count, cut rate and elapsed time/tokens at the cut reported per arm (D-028). |
| `test_compile_failed` outcomes (interface table) | Per arm and category (non-empty diff touching the F2P module whose test source set did not compile); blind `INTERFACE` labels say how many were correct fixes with a different shape. |
| Retries, rate-limit retries, gate runs, per-stage turns | Per arm. |

## Author isolation (we wrote both sides)

These measures are **hygiene against accidental reads, not a security boundary**: the same
person wrote the tasks and the orchestrator, and a sparse worktree still has every blob in
`.git`. The README says this plainly; the stronger option — moving `s2a/` into its own
repository, with the benchmark pinning `s2a_git_sha` — is recommended once the product has a
life of its own.

- Test-split tasks are authored and triaged in a worktree **without `s2a/`** (non-cone sparse
  checkout, recipe in START-HERE.md §3), and `tasks/TRIAGE.md` is timestamped. S2A tuning runs
  with `ABB_TUNING=1`, under which `abb run`, `abb tasks show` and `abb labels show` refuse any
  `split: test` task id (enforced in code).
- Phase 6 steps 1–17 are **bring-up** on the pinned-dev `dev5` set only; **tuning** (step 18:
  any prompt/pipeline change judged by results) may not start before the task set's sha256
  (`abb tasks hash` → `tasks/TASKSET.sha256`) is committed in Phase 7; every task records the
  `s2a_git_sha` current at its creation. The published report shows both.
- `s2a/CHANGELOG.md` records every prompt/pipeline change with dev-only before/after numbers;
  it is published.
- A candidate task is never dropped after any trial has run on it (`tasks/DROPPED.md` carries
  the reason and the date; `events.jsonl` proves no trial preceded it).

## Dev/test split

- `abb split --seed 20261101 --dev-frac 0.30` stratifies on `repo × category`, writes
  `benchmark/tasks/split.yaml` with the seed and a sha256 of the task list. Committed in Phase 7.
- **Pinned dev tasks.** Every task that has *any* trial under `results/` before the split is
  frozen (dev5 and anything else used while building Phases 4–6) is forced into `dev`:
  `abb split --pin-dev` defaults to exactly that list, writes it to `split.yaml: pinned_dev`,
  and the README states it.
- S2A prompts, pipeline and limits are tuned **only** on `split: dev` tasks.
- The test set is run **once** (Phase 10). `docs/PREREG.md` fixes, before the freeze: the
  primary comparison, the exclusion rules, the objective harness-bug criteria that permit a
  rerun, and the rule that the first run stays primary unless the bug is shown to affect arms
  asymmetrically. If a rerun happens, both runs are published.
- Any task added after the split lands in `dev` unless the split is explicitly regenerated
  (which resets the "run once" clock and is noted in the README).

## One-time setup artifacts must not leak fixes

Spec Kit's constitution and S2A's codebase map are generated once per repo and copied into
every task workspace. They are generated at `repos.<repo>.build.setup_commit` =
`git merge-base --octopus <all task base commits of the repo>` — an ancestor of every task's
base (never at `cache_commit`, which already contains every mined/reverted fix). `abb tasks lint
--setup-leak` fails if a setup artifact mentions a path or class name that any task's
`gold.patch` adds, and reports counts of mentions of files any gold patch *modifies*. Cache key:
(**setup kind**, repo, setup_commit, environment fingerprint, prompt hash), where setup kind is
`speckit-constitution` or `s2a-map`; all `s2a-*` arms except `s2a-nomap` share one map.

## Things an arm may NOT do

- Read `test.patch` or `gold.patch` (the runner hides them).
- See another trial's output or the hidden tests: the results root, the bare mirror and the code
  checkout are access-denied to the sandbox user.
- Reach the network beyond the model API (per-user firewall block + loopback proxy;
  `WebFetch`/`WebSearch` denied; no git remotes; Gradle offline).
- Find compiled artifacts of later commits: caches are warmed with `org.gradle.caching=false`
  and `--no-daemon`, daemon directories are removed, and Phase 1's invariants test greps the warm
  caches for class names added by any gold patch.
- Receive per-task hints, file lists or test names beyond `problem.md`.
- Retry silently. All retries are the counted nudge protocol.

## Ablations

`s2a-nomap`, `s2a-noverify`, `s2a-norepro` differ from `s2a` in exactly one skipped stage, use the
same shared map (except `nomap`), keep every gate on, and pass `--max-turns 200 − <skipped stage
cap>` so the skipped stage's turns are not reallocated. They are labelled **exploratory**: at
~28 test tasks they cannot resolve differences below ~18–20 percentage points.

## Trials and statistics

- 3 trials per (arm, task). pass@1 = mean resolved rate; pass^3 = all three resolved.
- Paired bootstrap over tasks (10 000 resamples) for the difference between arms; report 95 % CI.
- One pre-registered primary comparison (`s2a` vs `plain`, pass@1, all test-split tasks) plus
  one pre-registered robustness check (same, historical post-cutoff tasks only, with its own
  detectable delta); everything else is exploratory and labelled so.
- Denominators: `harness_error` trials that could not be re-run are excluded from the
  denominator and counted in a "trials lost" line; `agent_error` trials are unresolved.
- State the detectable effect size for the **headline denominator**: with ~28 test tasks,
  differences below ~18–20 percentage points are within noise (the 40-task all-task breakdowns
  reach ~15 pp; the robustness subset is wider). PREREG prints the computed numbers. Say so in
  the README.

## Known limits to state in the README

- The sandbox is a low-privilege **user** boundary (NTFS ACLs + per-user firewall + proxy), not
  a kernel or VM boundary; it answers the questions this benchmark asks (fix lookup, cross-trial
  leakage, egress) and nothing more.

## Known biases to state in the README

- Mined-task selection (linked issue, tests in the PR, ≤ 8 non-test files) favours well-scoped,
  test-friendly changes.
- The Spec Kit arm skips its human-in-the-loop commands (`clarify`, `checklist`, `analyze`);
  the `speckit-sdd` variant exists and the skipped commands are listed.
- The LLM failure labeller is calibrated on 20–30 manual labels; that agreement estimate has a
  wide CI.
- The benchmark author is also the S2A author; authored tasks (~35 %) sit inside the headline
  denominator, mitigated only by the pre-registered robustness check on historical post-cutoff
  tasks and the separate authored-task rows.

## Contamination statement (README must include)

- Which tasks post-date the model's training cutoff (issue and fix).
- That workspaces contain no git history, that the only network egress is the model API, that
  web tools are disabled, and that results are never visible to agents.
- That mined tasks are reported separately from authored tasks.

## Licensing statement

- Repos are referenced by URL + commit; the published benchmark contains task metadata,
  `problem.md`, `test.patch`, `gold.patch` and license notes — not repo copies.
- Patches derived from GPL-3.0 repos (AntennaPod, NewPipe) are GPL-3.0; from Apache-2.0 repos
  (Wikipedia, Thunderbird) Apache-2.0. Each task has `LICENSE-NOTE.md`.
- The harness and `s2a` are MIT (`benchmark/LICENSE`, `s2a/LICENSE`).
- No prompts, skills or scripts from any employer; the S2A orchestrator is written in this repo
  from scratch.
