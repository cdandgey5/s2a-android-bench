# Master plan — Brownfield Android Agent Benchmark + S2A orchestrator

Version 1.2 · 2026-10-17 · Owner: S2A Framework · Start with `START-HERE.md`

## 1. What we are building and why

**Question the benchmark answers**

> On real Android codebases, does a structured brownfield workflow solve more tasks than a plain
> coding agent, and what does it cost?

**Design in one paragraph.** 30–50 tasks are mined from or authored for 3–5 open-source Android
apps. Each task is a ticket (like a GitHub issue) plus a *hidden* test patch that fails before the
fix and passes after it. Arms attempt every task with the **same model, same tools, same
container, same ticket, same wall-clock and USD limits**: (A) a plain Claude Code agent, (A′)
two cheap controls — the plain agent with the S2A workflow described in prose, and the plain
agent plus a test-running hook —, (B) GitHub Spec Kit, (C) the S2A orchestrator, plus (D) S2A
ablations. Each task is run 3 times per arm. Grading applies the hidden tests to the agent's
diff after reverting any test files and build scripts the agent touched. We report pass@1,
pass^3, paired-bootstrap confidence intervals, cost per task, one-time setup cost per repo,
interventions, and a hand-labelled failure breakdown — with one pre-registered primary
comparison and everything else labelled exploratory.

**Why not SWE-bench?** It is Python-only, mostly bug fixes, and library code. Nothing comparable
exists for Android, where Gradle, multi-module builds, Android framework code and UI are the hard
parts. That gap is the value of this project.

**Non-goals for v1.** Emulator/instrumented tests, iOS/Flutter/KMP targets, multiple model
vendors, a web leaderboard, more than ~50 tasks, S2A product features beyond v1 (PR creation,
chat UI, non-Android profiles).

## 2. Architecture at a glance

```
host (Windows 11, WSL2 ~/abb, Docker Desktop)       containers (Linux)
+--------------------------------------+           +----------------------------------------+
| benchmark/  (Python 3.12, `abb` CLI) |           | abb-base: JDK + Android SDK + agents   |
|  repos/*.yaml   tasks/<id>/          |  docker   | abb-<repo>: + repo snapshot + warm     |
|  abb/arms/{plain,speckit,s2a}/       | --------> |   Gradle deps + Robolectric jars       |
|  abb/harness/{images,workspace,      |   SDK     | abb-<repo>-s2a: + s2a package (thin)   |
|    validate,run,grade,audit,report}  |           |                                        |
| s2a/        (Python, `s2a` CLI)      | <-------- |  /work = history-free task workspace   |
| ~/abb-results/<run_id>/<arm>/<task>/ | docker cp |  agent runs here (claude -p ...)       |
+--------------------------------------+           +----------------------------------------+
                                                     egress: internal network -> abb-proxy -> api.anthropic.com only
```

Data flow per (arm, task, trial):

1. `workspace.create(task)` → container from `abb-<repo>` (or `-s2a`) image on the internal
   network; `/work` = snapshot at `base_commit` with **no git history** (`git init` + one
   commit); the full clone is deleted from the container; nothing is bind-mounted.
2. `arm.run(task, workspace, limits)` → the arm drives the agent headlessly; returns
   `RunResult` (diff, transcripts, cost, duration, turns, tool calls, exit reason,
   interventions, gate runs).
3. `grade(task, diff)` → fresh container, apply agent diff **minus test dirs and protected build
   paths**, apply hidden `test.patch`, run fail-to-pass and pass-to-pass tests, parse JUnit XML
   → `grade.json`.
4. `audit(run_id)` recomputes every total from the verbatim transcripts; `report(run_id)`
   aggregates `metrics.json` across runs → tables, CIs, charts.

The contracts for each box are in `specs/`.

**S2A itself is a product, not an adapter.** It lives in `s2a/` as a standalone CLI: you run
`s2a run "<prompt>"` in an existing repository and a deterministic orchestrator drives the
coding agent through fixed stages — intake → codebase map → locate/impact → reproduce or
characterize → spec → plan → implement (one small committed task per fresh session) →
independent verify → bounded fix loop → report — with a machine-checked gate after every stage,
budgets, and resumable state under `.s2a/`. Design: `specs/s2a-orchestrator.md`; the brownfield
principles each stage implements: `specs/brownfield-principles.md`. Arm C is a thin wrapper that
calls the same CLI in autonomous mode inside the benchmark container.

## 3. Phases

Each phase has a file in `phases/` with deliverables, steps, contracts and an **acceptance gate**.
The agent must not proceed past a gate that fails.

| # | Phase | Produces | Gate (short form) | Weeks |
|---|---|---|---|---|
| 0 | Foundations | `benchmark/` skeleton, `abb` CLI, `abb-base` images, tool verification + transcript fixtures, repo-selection experiment (2 repos), seed task `antennapod-0000`, `docs/RUNS.md` | `abb --help`; both base images; smoke-test fixtures; 2 repos built with timings; seed task exists | 1 |
| 1 | Environments | `abb-<repo>` images with warm deps (build cache off); history-free workspaces; `api-only` network + proxy; offline verification; `abb images prune` | offline tests < 10 min per repo; invariants (no upstream clone, no `/results`, no build cache, no gold classes); proxy blocks github.com, allows the API | 1 |
| 2 | Tasks & validation | task schema + lint (incl. hidden-test interface rule, identifier leak), mining, authoring guide, 3× validation, `setup_commit`, dev5 | 5 tasks + seed `validated` 3×; lint clean | 2 |
| 3 | Grading | `abb grade`, test-dir + protected-path resets, `test_compile_failed`, P2P flakiness guard, sanity matrix | 7-row sanity matrix green on ≥ 2 tasks | 1–2 |
| 4 | Arm A + controls | driver with nudge caps, transcript parser, `setup.py` + setup cache (no-op for plain), `abb audit`, plain/plain-guided/plain-gate arms, minimal runner + report → **first results table** | dev5 × 1 on plain: table with real numbers; `abb audit` passes | 1–2 |
| 5 | Arm B: Spec Kit | `abb/arms/speckit`, constitution setup, SDD/bug paths, slash-command gate | 5 tasks end-to-end, artifacts captured, setup cost separate | 1 |
| 6 | S2A orchestrator + Arm C | `s2a/` package (`s2a run` end to end, gated, resumable), thin image layer, Arm C wrapper, ablations | one dev task through every stage autonomously; resume works; S2A + ablations complete dev5 | 2 (+2 tuning) |
| 7 | Scale tasks | repos 3/4 environments (Phase 0 step 6 + Phase 1 for them), 40 tasks, tags, license notes, warm all base commits, `tasks/TASKSET.sha256`, frozen split (dev5 pinned) | ≥ 35 validated 3×; coverage within tolerance; split committed; author-isolation rules followed | 3 |
| 8 | Runner | matrix runner, parallelism, resume, budget guard, manifest, retry policy, `abb audit` in the loop | interrupted run resumes; budget stop; 2 containers in parallel on the laptop | 1 |
| 9 | Analysis | stats (pass@1, pass^3, paired bootstrap, detectable delta), tables/charts, blind labelling, LLM labeller calibrated | deterministic report; ≥ 80 % label agreement on ≥ 20 manual labels | 1–2 |
| 10 | Release | `docs/PREREG.md` frozen, held-out run once, README statements, repro package, write-up | test set run once; README complete; `abb repro` reproduces the numbers | 1 + compute |

**Dependencies and parallelism.** 0 → 1 → 2 → 3 → 4 are sequential (Phase 4 builds the driver,
runner, setup support and audit every arm reuses). **Phase 7 starts right after Phase 2** —
task mining and authoring is the long pole and it includes environment work for repos 3/4.
Phases 5 and 6 start after Phase 4. 8 needs 4 (and is only meaningful once 5–6 exist); 9 needs
8; 10 needs 7, 8 and 9. Parallel phases run in **separate agent sessions on separate git
branches** (`phase-5`, `phase-6`, `phase-7`), merged in the order 7 → 5 → 6; files several
phases touch (`abb/arms/registry.py`, `docs/DECISIONS.md`, `images.lock.json`, `repos/*.yaml`,
`README.md` status table) are edited append-only to keep merges trivial. **Shared machine state** (one Docker daemon, one tag
space, one results root): only the Phase 7 session rebuilds `abb-<repo>` images; Phase 5/6 dev
runs pin the image tag they started with (or pass `--allow-image-drift`, recorded); nobody runs
`abb images prune` while a run is active; `ABB_RESULTS_DIR` is exported in every shell.
Test-split task authoring (Phase 7) happens in a worktree without `s2a/` and S2A tuning in a
session that refuses test-split tasks (fairness-protocol.md, "Author isolation" — hygiene against
accidental reads, not a boundary; clone recipe in START-HERE.md §3).

## 4. Decisions already made (do not relitigate without a note in `docs/DECISIONS.md`)

| Area | Decision | Why |
|---|---|---|
| Model | One pinned model for every arm in the final run: **`claude-opus-5-5`** (confirmed against `/v1/models` on Day 0; if Claude Code reports a dated snapshot id, the driver matches by prefix and records the resolved id). Development runs use **`claude-sonnet-5-5`** with a $5/trial cap. The driver asserts the model from the `init` event and `modelUsage`; the image disables Claude Code autoupdate and telemetry (D-001, D-021). | Changing model and workflow at once makes the comparison uninterpretable. |
| Agent runtime | Claude Code in headless mode (`claude -p …`) inside the container, for all arms; the s2a CLI uses the same driver contract. | Same tools, same permissions, same sandbox for every arm. |
| Tests | JVM unit tests only (JUnit, Robolectric, Compose-under-Robolectric, Roborazzi/Paparazzi). No emulator in v1. | Fast, deterministic, cheap. |
| Grading | SWE-bench style: revert agent edits under test dirs **and protected build paths** (wrapper, buildSrc, build files unless gold touches them), apply hidden test patch, `cleanTest`, F2P must pass, P2P must still pass with a one-shot flakiness re-run; `test_compile_failed` reported separately (D-020, D-022, D-023). | Prevents gaming; catches regressions; separates task-quality problems from agent failures. |
| Task sources | ~50 % mined (issue + fix PR with tests), ~15 % reverted features, ~35 % authored. Hidden tests may only use interfaces that exist at base or that the ticket names. Report historical vs authored separately; the primary comparison uses all test tasks, with a pre-registered robustness check on historical post-cutoff tasks. | Realism vs contamination vs author bias. |
| Task mix | ~40 % bugfix, ~30 % feature, ~20 % refactor/migration, ~10 % cross-module. | Representative brownfield work. |
| Contamination | Post-cutoff preferred (issue and fix); history-free workspaces (upstream clone deleted); internal Docker network + allow-list proxy; WebFetch/WebSearch denied; Gradle offline, build cache off; results never mounted into agent containers; setup artifacts at the octopus merge-base and leak-linted (D-009, D-012, D-013, D-018). | With Bash available, only network and filesystem boundaries actually stop a lookup. |
| Interventions | Autonomous mode: when the agent asks a question (AskUserQuestion stays enabled so it is observable) or an implementing call ends without a diff, the harness replies once with a fixed nudge and counts it — max 2 per call, 4 per trial, identical for every arm (D-005). Assisted mode optional. | Measurable without a human; comparable across arms. |
| Fairness | Same model, tools, container, ticket, wall-clock, USD, turn total, nudge caps, environment preamble. **Wall-clock and USD are the binding limits; turns and gate runs are reported.** Control arms `plain-guided` and `plain-gate` separate prompt from harness. Transcripts are the source of truth (`abb audit`). No retries on `agent_error` for any arm (D-014, D-017). | Credibility. |
| Tuning | Dev ≈ 30 %, test ≈ 70 %, seeded stratified split; everything used before the freeze pinned to dev; S2A bring-up on dev5, tuning on dev only and only after `tasks/TASKSET.sha256` exists; test set run once; `docs/PREREG.md` fixes the primary comparison (all test tasks), the robustness check, exclusions and rerun rules before the freeze; test-split tasks authored in isolation from `s2a/` (D-010, D-011, D-019). | We wrote both the framework and the benchmark. |
| Trials | 3 per (arm, task). pass@1 and pass^3. Paired bootstrap over tasks. Honesty about power: ~±18–20 pp detectable at the headline n ≈ 28; ~±15 pp only on the exploratory all-task breakdowns. | Agents are stochastic; paired design is the most powerful we can afford. |
| Repos | **AntennaPod** (Java/XML/multi-module, GPL-3.0) and **Wikipedia Android** (Kotlin/single-module, Apache-2.0) first; **Thunderbird for Android** (Kotlin/Compose/multi-module, Apache-2.0, JDK 21) if its warm unit-test run is < 10 min; **NewPipe** as 4th. Tusky is archived → deprioritised. Avoid *Now in Android*. | See `reference/repo-candidates.md`. |
| S2A design | Standalone orchestrator (`s2a/`): deterministic Python, fixed stages with machine-checked gates, fresh sessions per stage and per implement task, reproduce/characterize before any change, independent verifier with the verdict derived in code, bounded fix loop under the same gates, resumable state, autonomous default, Android profile first; ablations as `--skip` with the skipped stage's turns removed (D-015, D-016). | Gated workflows beat free-running agents on predictability; the brownfield literature agrees. |
| Language | Python 3.12 harness, `uv`, Typer, Docker SDK, pydantic, PyYAML, pandas, matplotlib. MIT. | Boring and sufficient. |

## 5. Timeline

Two honest numbers. **Full plan, parallel sessions: ~11 weeks part-time.** **8 weeks is
achievable only with the MVP cut in §9** (2 repos, ~28 tasks, controls at 1 trial). Serial, one
person: 15–18 weeks. The per-phase effort lines in `phases/` sum to 13–17 weeks plus S2A tuning;
agents parallelise the building, not the human work (hand-editing every mined task, writing
reference fixes for authored tasks, reviewing maps, hand-labelling failures).

| Week | Milestone |
|---|---|
| 1 | Phase 0: skeleton, base images, fixtures, AntennaPod + Wikipedia built, seed task. |
| 2 | Phase 1 for both repos (offline images, proxy, invariants). |
| 3–4 | Phase 2: mining, hand-editing, authoring, 3× validation (dev5). The Phase 7 session opens mid-Phase 2, as soon as `abb tasks mine` yields candidates (Phase 2 step 3, ~end of week 3). |
| 4 | Phase 3: grader + sanity matrix (overlaps the end of Phase 2). |
| 5 | Phase 4: driver, audit, controls, minimal runner → **first results table** (the one rule: it exists by the end of week 5; best case week 4; slip rule: week 6 at the latest). **MVP decision** as soon as it exists. START-HERE.md §4 owns the week numbers. |
| 6–7 | Phases 5 and 6 in parallel sessions (bring-up on dev5); Phase 7 continues (repos 3/4 environments, authored tasks). |
| 8 | Phase 7 finishes: 40 tasks validated, task-set hash, split frozen. Merge 7 → 5 → 6. Phase 8 runner. |
| 9 | Phase 6 tuning on dev (now allowed); Phase 9 built against dev-set runs (stats, blind labelling, labeller calibrated). |
| 10 | `docs/PREREG.md` committed; dev-set confirmation on the pinned model; freeze tag; held-out run on a rented machine. |
| 11 | Phase 9 applied to the held-out run; write-up; README; publish. |

## 6. Budget

**Compute.** Laptop (32 GB) runs 2–3 containers at 6–8 GB each; fine for dev. The final run
should go to a rented 16-core/64 GB Linux box for 1–2 days. Disk: ≥ 120 GB free for images.

**API spend — measure before estimating.** Phase 4's gate records cost per run for 5 tasks per
arm in `docs/RUNS.md`. Until then, size the risk with:

```
test tasks    ~ 28 (40 x 0.7)
runs_final    = 28 x 6 arms (plain, plain-guided, speckit, s2a, s2a-nomap, s2a-noverify) x 3 = 504
runs_optional = 28 x 3 arms (plain-gate, s2a-norepro, speckit-sdd) x 1                     =  84
runs_dev      ~ 12 dev tasks x ~6 arms x ~6 iterations                                     ~ 430
cost ~ sum over runs of cost_per_run(arm)
```

Multi-phase arms (B, C) typically spend 2–5× the tokens of the plain arm; S2A's gates add
Gradle time but no tokens. Dev runs use `claude-sonnet-5-5` with `profiles.dev.max_usd: 5`;
only the final run and the last dev-set confirmation use the pinned `claude-opus-5-5`. Hard
guard: `abb run --max-usd N`. Weeks 1–2 spend only smoke tests and validation (no agent runs):
budget tens of dollars; set a Console spend alert before Phase 4.

## 7. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Repo does not build offline / needs secrets | Phase 0 experiment picks repos by actually building them; stub secrets; drop repos needing an emulator for unit tests. |
| Gradle memory blow-ups in parallel | `--memory 8g`, `org.gradle.jvmargs=-Xmx3g`, `kotlin.daemon.jvmargs=-Xmx2g`, max 2–3 parallel on laptop. |
| Robolectric downloads at test time | Warm by running tests at image build (serially); gate = tests pass with `--network none`. |
| Claude Code silently updates or switches model | Image env disables autoupdate/telemetry (version pinned ≥ 2.1.182 for the env vars to exist); driver asserts version and `modelUsage`; no `fallbackModel`/`ANTHROPIC_MODEL` set; the `switchModelsOnFlag` setting is applied only if the pinned version documents it. |
| Agent stalls behind the proxy | `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1`; Phase 1 gate runs the smoke test through the proxy. |
| Cross-trial or cross-arm leakage | Results never mounted; build cache off; invariants test greps for gold classes; `abb audit`. |
| Flaky tests | 3× validation; P2P flakiness re-run; drop or fix; record flake rate. |
| Model memorized the upstream fix | Post-cutoff (issue and fix) preferred; history-free workspace; authored tasks reported separately. |
| Agent games tests or build config | Test dirs and protected build paths reverted; `cleanTest`; "gamed tests" failure label. |
| Hidden tests encode the gold interface | Interface rule + lint in Phase 2; `test_compile_failed` reported per arm; V0/V1 validation handles new-surface tasks. |
| Author bias (we wrote tasks and S2A) | PREREG: primary = all test tasks, with a pre-registered robustness check on historical post-cutoff tasks (the mitigation for the ~35 % authored tasks inside the headline denominator) and authored tasks shown separately; task-set hash before tuning; worktree hygiene for authoring/tuning sessions (not a boundary — the author knows both sides, and the README says so). |
| Disk exhaustion | ≥ 120 GB prerequisite; `abb images prune`; `docker system df` after builds. |
| Cost overrun | `--max-usd`, dev cap $5/trial, measure 5 tasks per arm first, Console alert. |
| Too few tasks for significance | Say so; report CIs; one primary comparison; 28 test tasks detect ~±18–20 pp differences only (40 tasks ~±15 pp on exploratory breakdowns); PREREG prints the detectable delta. |
| Timeline slip | §9 MVP cut, decided when the first results table exists (target end of week 5). |
| Licensing | Tasks derived from GPL repos carry a GPL notice; repos referenced by URL + commit. |

## 8. Definition of done

See `AGENTS.md` → "What done looks like". In short: `s2a run "<prompt>"` takes a real repository
from prompt to verified, reported change; a single command runs the benchmark matrix; `abb
audit` and `abb report` reproduce the published numbers from transcripts; and the README is
honest about the split, model, trials, limits and biases.

## 9. Minimum viable cut (decide when the first results table exists)

Drop in this order, saying so in the README:
1. Repos 3/4 → two repos (relax the "no repo > 40 %" rule to 50/50).
2. Tasks 40 → 24–30 (authored 14 → 6); detectable delta grows to ~±20 pp.
3. Optional arms (`plain-gate`, `speckit-sdd`, `s2a-norepro`), lint delta, convention score,
   assisted mode.
4. The Spec Kit arm (the primary question — plain vs S2A with controls — still stands).
5. The LLM labeller → hand-label a 30-failure sample.
6. The rented box → ~3 laptop nights at 2 parallel.
