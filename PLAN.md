# Master plan — Brownfield Android Agent Benchmark + S2A orchestrator

Version 1.2 · 2026-10-17 · Owner: S2A Framework · Start with `START-HERE.md`

## 1. What we are building and why

**Question the benchmark answers**

> On real Android codebases, does a structured brownfield workflow solve more tasks than a plain
> coding agent, and what does it cost?

**Design in one paragraph.** 30–50 tasks are mined from or authored for 3–5 open-source Android
apps. Each task is a ticket (like a GitHub issue) plus a *hidden* test patch that fails before the
fix and passes after it. Arms attempt every task with the **same model, same tools, same
sandbox, same ticket, same wall-clock and USD limits**: (A) a plain Claude Code agent, (A′)
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
Windows 11 host (PowerShell 7, Python 3.12 via uv)          runs as the SANDBOX USER `abb-agent`
+-----------------------------------------------+          +------------------------------------------+
| %USERPROFILE%\abb-src  (code; agent: DENIED)   |          | ABB_HOME\work\<run>\<arm>\<task>\t<k>\work |
|  benchmark/abb/{arms,harness/platform,...}     | platform |   history-free snapshot (git init, 1 commit)|
|  s2a/ (`s2a` CLI)   tasks/ (hidden tests)      | layer    |   claude.exe -p ... (Job Object, 10 GB)      |
| ABB_HOME\tools   (pinned JDKs + SDK + claude)  | -------> | ABB_HOME\caches\gradle-ro\<repo> (read-only) |
| ABB_HOME\caches\repos\<repo>.git (DENIED)     |          |                                             |
| ABB_HOME\results (DENIED)                       | <------- |  outbound: firewall BLOCK for abb-agent,     |
|  harness proxy 127.0.0.1:8888 (allow-list)      |  files   |  loopback -> proxy -> api.anthropic.com only |
+-----------------------------------------------+          +------------------------------------------+
```

Data flow per (arm, task, trial):

1. `workspace.create(task)` → a fresh directory under `ABB_HOME\work`, snapshot at `base_commit`
   with **no git history** (`git init` + one commit), ACL-granted to the sandbox user; the bare
   mirror, the results root and the code checkout are access-denied to that user.
2. `arm.run(task, workspace, limits)` → the arm drives the agent headlessly; returns
   `RunResult` (diff, transcripts, cost, duration, turns, tool calls, exit reason,
   interventions, gate runs).
3. `grade(task, diff)` → fresh workspace as the harness user, offline, apply agent diff **minus
   test dirs and protected build paths**, apply hidden `test.patch`, run fail-to-pass and
   pass-to-pass tests, parse JUnit XML → `grade.json`.
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
calls the same CLI in autonomous mode inside the benchmark sandbox.

## 3. Phases

Each phase has a file in `phases/` with deliverables, steps, contracts and an **acceptance gate**.
The agent must not proceed past a gate that fails.

| # | Phase | Produces | Gate (short form) | Weeks |
|---|---|---|---|---|
| 0 | Foundations (Windows-native) | `benchmark/` skeleton, `abb` CLI, platform layer (Windows), pinned toolchain under `ABB_HOME\tools` (`abb tools install`), tool verification + transcript fixtures (incl. Ctrl+Break behaviour), repo-selection experiment (2 repos), seed task `antennapod-0000`, `docs/RUNS.md` | `abb --help`; `abb tools check`; smoke-test fixtures; 2 repos built with timings; seed task exists | 1 |
| 1 | Environments + sandbox | warm per-repo caches (build cache off) + fingerprints; history-free workspaces; sandbox user + outbound firewall + allow-list proxy (`abb sandbox setup`, one elevated step by the human); offline verification; `abb env prune` | offline tests < 10 min per repo as the sandbox user; invariants (denied paths denied, no build cache, no gold classes); `abb sandbox check` proves the boundary | 1 |
| 2 | Tasks & validation | task schema + lint (incl. hidden-test interface rule, identifier leak), mining, authoring guide, 3× validation, `setup_commit`, dev5 | 5 tasks + seed `validated` 3×; lint clean | 2 |
| 3 | Grading | `abb grade`, test-dir + protected-path resets, `test_compile_failed`, P2P flakiness guard, sanity matrix | 7-row sanity matrix green on ≥ 2 tasks | 1–2 |
| 4 | Arm A + controls | driver with nudge caps, transcript parser, `setup.py` + setup cache (no-op for plain), `abb audit`, plain/plain-guided/plain-gate arms, minimal runner + report → **first results table** | dev5 × 1 on plain: table with real numbers; `abb audit` passes | 1–2 |
| 5 | Arm B: Spec Kit | `abb/arms/speckit`, constitution setup, SDD/bug paths, slash-command gate | 5 tasks end-to-end, artifacts captured, setup cost separate | 1 |
| 6 | S2A orchestrator + Arm C | `s2a/` package (`s2a run` end to end, gated, resumable), installed for the sandbox user, Arm C wrapper, ablations | one dev task through every stage autonomously; resume works; S2A + ablations complete dev5 | 2 (+2 tuning) |
| 7 | Scale tasks | repos 3/4 environments (Phase 0 step 6 + Phase 1 for them), 40 tasks, tags, license notes, warm all base commits, `tasks/TASKSET.sha256`, frozen split (dev5 pinned) | ≥ 35 validated 3×; coverage within tolerance; split committed; author-isolation rules followed | 3 |
| 8 | Runner | matrix runner, parallelism, resume, budget guard, manifest, retry policy, `abb audit` in the loop | interrupted run resumes; budget stop; 2 trials in parallel on the laptop | 1 |
| 9 | Analysis | stats (pass@1, pass^3, paired bootstrap, detectable delta), tables/charts, blind labelling, LLM labeller calibrated | deterministic report; ≥ 80 % label agreement on ≥ 20 manual labels | 1–2 |
| 10 | Release | `docs/PREREG.md` frozen, held-out run once, README statements, repro package, write-up | test set run once; README complete; `abb repro` reproduces the numbers | 1 + compute |

**Dependencies and parallelism.** 0 → 1 → 2 → 3 → 4 are sequential (Phase 4 builds the driver,
runner, setup support and audit every arm reuses). Phase 7 needs only Phase 2's tooling; Phases
5 and 6 need Phase 4; 8 needs 4 (and is only meaningful once 5–6 exist); 9 needs 8; 10 needs
7, 8 and 9. **Autopilot (the default, `phases/RUN-ALL.md`, D-029):** one session, one branch,
order 0 → 1 → 2 → 3 → 4 → 7 → 5 → 6 (bring-up) → 8 → 6 tuning + 9 → 10, nothing merged.
**Per-phase variant:** Phase 7 starts right after Phase 2 (task mining and authoring is the
long pole and includes environment work for repos 3/4); parallel phases run in **separate
agent sessions on separate git branches** (`phase-5`, `phase-6`, `phase-7`), merged in the
order 7 → 5 → 6; files several
phases touch (`abb/arms/registry.py`, `docs/DECISIONS.md`, `env.lock.json`, `repos/*.yaml`,
`README.md` status table) are edited append-only to keep merges trivial. **Shared machine state** (one toolchain, one cache tree,
one results root, one sandbox user): only the Phase 7 session re-warms `caches/gradle/<repo>`;
Phase 5/6 dev runs record the fingerprint they started with (or pass `--allow-env-drift`,
recorded); nobody runs `abb env prune` while a run is active; `ABB_HOME`/`ABB_RESULTS_DIR` are
user-level environment variables so every shell agrees.
Test-split task authoring (Phase 7) happens in a worktree without `s2a/` (per-phase variant;
autopilot: ordering-only — tasks drafted before any `s2a/` code, hash before tuning) and S2A
tuning in a session that refuses test-split tasks (fairness-protocol.md, "Author isolation" —
hygiene against accidental reads, not a boundary; clone recipe in START-HERE.md §3).

## 4. Decisions already made (do not relitigate without a note in `docs/DECISIONS.md`)

| Area | Decision | Why |
|---|---|---|
| Model | One pinned model for every arm in the final run: **`claude-opus-5-5`** if the Phase 0 smoke test accepts it on the owner's plan, else `claude-sonnet-5-5` for everything (if Claude Code reports a dated snapshot id, the driver matches by prefix and records the resolved id). Development runs use **`claude-sonnet-5-5`** with a $5/trial estimate cap. The driver asserts the model from the `init` event and `modelUsage`; the agent environment disables Claude Code autoupdate and telemetry (D-001, D-021). | Changing model and workflow at once makes the comparison uninterpretable. |
| Agent runtime | Claude Code in headless mode (`claude.exe -p …`), launched natively on Windows as the sandbox user through the platform layer, for all arms; the s2a CLI uses the same driver contract. | Same tools, same permissions, same sandbox for every arm. |
| Tests | JVM unit tests only (JUnit, Robolectric, Compose-under-Robolectric, Roborazzi/Paparazzi). No emulator in v1. | Fast, deterministic, cheap. |
| Grading | SWE-bench style: revert agent edits under test dirs **and protected build paths** (wrapper, buildSrc, build files unless gold touches them), apply hidden test patch, `cleanTest`, F2P must pass, P2P must still pass with a one-shot flakiness re-run; `test_compile_failed` reported separately (D-020, D-022, D-023). | Prevents gaming; catches regressions; separates task-quality problems from agent failures. |
| Task sources | ~50 % mined (issue + fix PR with tests), ~15 % reverted features, ~35 % authored. Hidden tests may only use interfaces that exist at base or that the ticket names. Report historical vs authored separately; the primary comparison uses all test tasks, with a pre-registered robustness check on historical post-cutoff tasks. | Realism vs contamination vs author bias. |
| Task mix | ~40 % bugfix, ~30 % feature, ~20 % refactor/migration, ~10 % cross-module. | Representative brownfield work. |
| Contamination | Post-cutoff preferred (issue and fix); history-free workspaces; the bare mirror, results and code checkout are ACL-denied to the sandbox user; outbound firewall block for that user + allow-list proxy; WebFetch/WebSearch denied; Gradle offline, build cache off; setup artifacts at the octopus merge-base and leak-linted (D-009, D-012, D-013, D-018, D-024). | With Bash available, only network and filesystem boundaries actually stop a lookup. |
| Interventions | Autonomous mode: when the agent asks a question (AskUserQuestion stays enabled so it is observable) or an implementing call ends without a diff, the harness replies once with a fixed nudge and counts it — max 2 per call, 4 per trial, identical for every arm (D-005). Assisted mode optional. | Measurable without a human; comparable across arms. |
| Fairness | Same model, tools, sandbox, ticket, wall-clock, USD, turn total, nudge caps, environment preamble. **Wall-clock and USD are the binding limits; turns and gate runs are reported.** Control arms `plain-guided` and `plain-gate` separate prompt from harness. Transcripts are the source of truth (`abb audit`). No retries on `agent_error` for any arm (D-014, D-017). | Credibility. |
| Tuning | Dev ≈ 30 %, test ≈ 70 %, seeded stratified split; everything used before the freeze pinned to dev; S2A bring-up on dev5, tuning on dev only and only after `tasks/TASKSET.sha256` exists; test set run once; `docs/PREREG.md` fixes the primary comparison (all test tasks), the robustness check, exclusions and rerun rules before the freeze; test-split tasks authored in isolation from `s2a/` (D-010, D-011, D-019). | We wrote both the framework and the benchmark. |
| Trials | 3 per (arm, task). pass@1 and pass^3. Paired bootstrap over tasks. Honesty about power: ~±18–20 pp detectable at the headline n ≈ 28; ~±15 pp only on the exploratory all-task breakdowns. | Agents are stochastic; paired design is the most powerful we can afford. |
| Repos | **AntennaPod** (Java/XML/multi-module, GPL-3.0) and **Wikipedia Android** (Kotlin/single-module, Apache-2.0) first; **Thunderbird for Android** (Kotlin/Compose/multi-module, Apache-2.0, JDK 21) if its warm unit-test run is < 10 min; **NewPipe** as 4th. Tusky is archived → deprioritised. Avoid *Now in Android*. | See `reference/repo-candidates.md`. |
| S2A design | Standalone orchestrator (`s2a/`): deterministic Python, fixed stages with machine-checked gates, fresh sessions per stage and per implement task, reproduce/characterize before any change, independent verifier with the verdict derived in code, bounded fix loop under the same gates, resumable state, autonomous default, Android profile first; ablations as `--skip` with the skipped stage's turns removed (D-015, D-016). | Gated workflows beat free-running agents on predictability; the brownfield literature agrees. |
| Execution mode | One Claude Code session runs all phases in order (`phases/RUN-ALL.md`, autopilot with defaults and hard stop points, D-029); per-phase sessions with parallel branches remain the alternative (`START-HERE.md` §2–3). | The owner starts one session, gives it the plan, and lets it build; files carry the state. |
| Auth & usage | Subscription only, no API key: building in Claude Code on the owner's login, headless trials via a `claude setup-token` OAuth token stored as `ABB_OAUTH_TOKEN` and mapped to `CLAUDE_CODE_OAUTH_TOKEN` only inside the trial block (never under the repo or `ABB_HOME`), `ANTHROPIC_API_KEY` scrubbed; tokens are the primary cost unit, `cost_usd` is est. API-equivalent; usage limits pause the runner, never count against a trial; the held-out matrix's auth is a PREREG decision (D-025). | The owner has no API key and does not plan to use one. |
| Platform | **Windows-first, no WSL, no Docker.** PowerShell 7 for humans; Python 3.12 (`uv`) for everything else; Typer, pydantic, PyYAML, pandas, matplotlib, keyring, pywin32/ctypes — the OS-specific parts only inside `abb/harness/platform/` and `s2a/s2a/platform/` (`specs/platform-layer.md`); macOS later via `posix.py`; no `.sh` scripts anywhere. MIT (D-024). | The owner develops and runs on Windows; the framework must be independent of any one OS. |

## 5. Timeline

Two honest numbers. **Full plan, parallel sessions: ~11 weeks part-time.** **8 weeks is
achievable only with the MVP cut in §9** (2 repos, ~28 tasks, controls at 1 trial). Serial, one
person — which is what the default autopilot mode is (`phases/RUN-ALL.md`, one session, D-029):
15–18 weeks, ~12–14 with the MVP default. The per-phase effort lines in `phases/` sum to 13–17 weeks plus S2A tuning;
agents parallelise the building, not the human work (hand-editing every mined task, writing
reference fixes for authored tasks, reviewing maps, hand-labelling failures).

| Week | Milestone |
|---|---|
| 1 | Phase 0: skeleton, platform layer, pinned toolchain, fixtures, AntennaPod + Wikipedia built, seed task. |
| 2 | Phase 1 for both repos (warm caches, sandbox user + firewall + proxy, invariants). |
| 3–4 | Phase 2: mining, drafting/review, 3× validation (dev5). Per-phase variant: the Phase 7 session opens mid-Phase 2, as soon as `abb tasks mine` yields candidates (Phase 2 step 3, ~end of week 3). |
| 4 | Phase 3: grader + sanity matrix (overlaps the end of Phase 2). |
| 5 | Phase 4: driver, audit, controls, minimal runner → **first results table** (the one rule: it exists by the end of week 5; best case week 4; slip rule: week 6 at the latest). **MVP decision** as soon as it exists. START-HERE.md §4 owns the week numbers. |
| 6–7 | Per-phase variant: Phases 5 and 6 in parallel sessions (bring-up on dev5); Phase 7 continues (repos 3/4 environments, authored tasks). Autopilot: Phase 7 (drafting, S2 review, validation nights), then 5, then 6 — serially, weeks 6–10. |
| 8 | Phase 7 finishes: 40 tasks validated (MVP: ≥ 24), task-set hash, split frozen. Per-phase variant: merge 7 → 5 → 6. Phase 8 runner (autopilot: ~week 11). |
| 9 | Phase 6 tuning on dev (now allowed); Phase 9 built against dev-set runs (stats, blind labelling, labeller calibrated). |
| 10 | `docs/PREREG.md` committed; dev-set confirmation on the pinned model; freeze tag; held-out run (three laptop nights or a Windows VM). |
| 11 | Phase 9 applied to the held-out run; write-up; README; publish. |

## 6. Usage (there is no API bill)

Everything runs on the owner's Claude subscription: the building chats in Claude Code and the
headless trials through a one-year `claude setup-token` token (`specs/auth-and-usage.md`). There
is no per-token charge, so **tokens are the primary cost metric** and `cost_usd` is reported as
"est. API-equivalent USD" (Claude Code's own client-side estimate at list price). The binding
constraint is the plan's **usage windows** (session and weekly limits; Opus has its own):

- The runner pauses on a usage limit and probes its way back (reset time is only a hint);
  paused trials are re-run from scratch and not counted (`usage_limited`), identically for
  every arm; the cut attempt is kept, and a pre-registered sensitivity check scores it
  unresolved, because re-running favours short trials (D-028). Any call that got no model response at all is never counted as an agent failure.
- **Throughput probe (D-027):** an earlier, coarser measurement at the end of Phase 1
  (step 10b): one realistic sandboxed agent session on the seed task, with the usage meter read
  before and after. The owner's plan is Pro, so whether the matrix fits at all is the biggest
  unknown; this answers it in week 2 instead of week 5, and feeds a decision (Pro / Max / MVP
  cut now — START-HERE §5).
- Phase 4's gate measures **trials per session window** for the plain arm on Sonnet — the
  number for scheduling dev work. The held-out run is planned from the **Opus dev-set
  confirmation run** (Phase 10 prerequisite), per arm: Opus has its own limit and multi-stage
  arms use 2–5× the tokens, so the Sonnet figure is the wrong input for it.
- Dev work uses `claude-sonnet-5-5` (its own, larger limit) and keeps the Opus window for the
  pinned runs. `profiles.dev.max_usd: 5` and `--max-usd` cap the *estimate* and remain the
  runaway guards.
- Sizing (upper bound, before measurement): test tasks ≈ 28; `runs_final = 28 × 6 arms × 3 = 504`;
  `runs_optional = 28 × 3 × 1 = 84`; `runs_dev ≈ 430`. Under a subscription this is weeks of
  windows, not days — the MVP cut (§9) is the realistic default, and the **held-out run is a
  decision recorded in `docs/PREREG.md: auth_mode`** (subscription in batches, or ask Anthropic
  first; the docs reserve OAuth for "ordinary, individual usage" — `specs/auth-and-usage.md` §5).

**Compute.** The laptop (32 GB, 32 logical CPUs) runs 2 trials in parallel at 10 GB each (D-034); wall
clock is bounded by usage windows long before CPU. Disk: ~40–60 GB for two repos under `ABB_HOME`.

## 7. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Repo does not build offline / needs secrets | Phase 0 experiment picks repos by actually building them; stub secrets; drop repos needing an emulator for unit tests. |
| Gradle memory blow-ups in parallel | Job Object limit 10 GB per trial (measured, D-034), `org.gradle.jvmargs=-Xmx3g`, `kotlin.daemon.jvmargs=-Xmx2g`, max 2 parallel on the laptop. |
| Robolectric downloads at test time | Warm by running tests during `abb env warm` (serially); gate = tests pass as the sandbox user with the proxy stopped. |
| Claude Code silently updates or switches model | The agent env disables autoupdate/telemetry (version pinned ≥ 2.1.280, the Opus 5.5 floor); the driver calls the pinned `claude.exe` by absolute path and asserts version and `modelUsage`; no `fallbackModel`/`ANTHROPIC_MODEL` set; `switchModelsOnFlag` only if documented. |
| Agent stalls behind the proxy / firewall | `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1`, `CLAUDE_CODE_PROXY_RESOLVES_HOSTS=1`; Phase 1 gate runs the smoke test as the sandbox user through the proxy. |
| Graceful stop on Windows undocumented | Phase 0 measures whether Ctrl+Break (or Ctrl+C) yields a `result` line and both drivers use the same signal; the driver marks harness-initiated stops as `timeout` and imputes cost identically for every arm; `--max-turns`/`--max-budget-usd` are the primary bounds. |
| Windows file-system traps | `core.autocrlf=false`, `core.longpaths=true` + `LongPathsEnabled`, short `ABB_HOME`, Defender exclusion (optional), Gradle daemons stopped before deleting workspaces, case-collision check in `abb repos check`. |
| Sandbox-user launch (`CreateProcessWithLogonW`) misbehaves | fallback `pwsh Start-Process -Credential`; no profile loaded (`dwLogonFlags=0`); `runas /user:abb-agent cmd` as the diagnostic; dev work continues in `--sandbox none` (never for test tasks). |
| Cross-trial or cross-arm leakage | Results and mirrors ACL-denied to the sandbox user; build cache off; invariants test (run as that user) greps for gold classes; `abb audit`. |
| Flaky tests | 3× validation; P2P flakiness re-run; drop or fix; record flake rate. |
| Model memorized the upstream fix | Post-cutoff (issue and fix) preferred; history-free workspace; authored tasks reported separately. |
| Agent games tests or build config | Test dirs and protected build paths reverted; `cleanTest`; "gamed tests" failure label. |
| Hidden tests encode the gold interface | Interface rule + lint in Phase 2; `test_compile_failed` reported per arm; V0/V1 validation handles new-surface tasks. |
| Author bias (we wrote tasks and S2A) | PREREG: primary = all test tasks, with a pre-registered robustness check on historical post-cutoff tasks (the mitigation for the ~35 % authored tasks inside the headline denominator) and authored tasks shown separately; task-set hash before tuning; worktree hygiene for authoring/tuning sessions (not a boundary — the author knows both sides, and the README says so). |
| Disk exhaustion | ≥ 60 GB on the `ABB_HOME` drive; `abb env prune`; cache sizes printed by `abb env fingerprint`. |
| Usage-limit stalls | Runner pauses and probes its way back (the parsed reset time is only the first wake-up); `usage_limited` trials re-queued for every arm equally, including inside the S2A orchestrator; throughput measured in Phase 4 before any matrix is scheduled. |
| Subscription policy for bulk headless runs | Dev-scale runs are ordinary personal use; the held-out matrix is an explicit PREREG decision (batches under the subscription, or ask Anthropic); no API key is assumed anywhere (`specs/auth-and-usage.md` §5). |
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
6. The optional Windows VM → three laptop nights at 2 parallel (the default).
