# START HERE — the startable plan

Reviewed 2026-10-17 by four independent audits (consistency, start-ability, technical
correctness, benchmark validity); every finding is folded into the files. This page is the
runbook: what you do, what the agent does, in what order, and where you decide.

## 0. What you are building (one breath)

A benchmark that answers *"does a structured brownfield workflow beat a plain coding agent on
real Android repos, and at what cost?"* — and the workflow itself, **S2A**, a standalone
orchestrator (`s2a run "<prompt>"`) that drives a coding agent from prompt to a verified,
reported change. Design: `PLAN.md`; contracts: `specs/`; steps: `phases/`.

## 1. Before the first agent session (you, ~2 hours) — `docs/DAY-0.md`

Windows 11, **no WSL, no Docker**: PowerShell 7 · Git for Windows · `gh` · `uv` · Claude Code
≥ 2.1.211 pinned · Console API key with credit + spend alert · `ABB_HOME` on the drive with
≥ 60 GB free on local NTFS (short path, e.g. `C:\abb`; not the Google Drive `G:`) · the plan copied out of OneDrive to
`%USERPROFILE%\abb-src` with a private GitHub remote · decisions written down: pinned model + its
training-cutoff date (D-001), Claude Code version, first two repos (default AntennaPod +
Wikipedia Android), dev budget per trial (default $5). One elevated step comes later (Phase 1:
`abb sandbox setup`).

## 2. Kickoff prompt (paste into Claude Code running in `%USERPROFILE%\abb-src`)

```
Read AGENTS.md, then PLAN.md, then phases/phase-0-foundations.md. Execute Phase 0 step by step.
Step 1 verifies my bootstrap (docs/DAY-0.md); if anything is missing, stop and tell me exactly
what to do. Use the seed files under benchmark/ as given. Keep docs/RUNS.md current for every
API-spending action. When the Phase 0 acceptance gate passes, paste the gate output, update the
status table in README.md, commit and push, and stop. Do not start Phase 1.
```

For each later phase: `Execute Phase N from phases/phase-N-*.md. Stop at its gate and report.`

## 3. Phase sequence, sessions and gates

| Order | Phase | Session / branch | Starts when | You do during it | Gate (what you check) | Est. |
|---|---|---|---|---|---|---|
| 1 | **0 Foundations** | main session, `main` | Day 0 done | answer questions | `abb tools check` (pinned JDKs + SDK); three smoke-test fixtures (incl. the interrupt finding); 2 repos built on Windows with timings; seed task `antennapod-0000`; `abb repos check` | 4–6 days |
| 2 | **1 Environments + sandbox** | same | Phase 0 gate | **run `abb sandbox setup` once in an elevated PowerShell when asked** | offline tests < 10 min per repo as the sandbox user; invariants green (denied paths denied, no build cache); `abb sandbox check` proves firewall + proxy | 4–6 days |
| 3 | **2 Tasks & validation** | same | Phase 1 gate | **hand-edit every mined ticket; write 1 authored task** | 5 tasks + seed validated 3×; lint (incl. interface rule) clean; `setup_commit` set | 1–2 weeks |
| 3′ | **7 Scale tasks** (long pole) | **new session, branch `phase-7`, worktree without `s2a/`** | mid-Phase 2, once `abb tasks mine` yields candidates (Phase 2 step 3) | **triage mined candidates, author ~14 tasks with reference fixes; review repos 3/4 build results** | ≥ 35 validated; coverage within tolerance; `TASKSET.sha256`; split frozen with dev5 pinned | 3 weeks, parallel |
| 4 | **3 Grading** | main | Phase 2 gate | nothing | 7-row sanity matrix green on seed + 1 dev task | 3–5 days |
| 5 | **4 Arm A + controls** | main | Phase 3 gate | **read the first transcripts; record cost per run in RUNS.md** | **first results table**; `abb audit` passes; plain-guided runs | 1 week |
| 6 | **5 Spec Kit** | new session, branch `phase-5` | Phase 4 gate | spot-check one constitution | 5 tasks end-to-end; setup cost separate; `slash_commands` gate | 1 week, parallel |
| 6′ | **6 S2A orchestrator** | new session, branch `phase-6` | Phase 4 gate | **review the first codebase map by hand; read one full run's artifacts** | `s2a run` end to end on one task; resume works; S2A + ablations on dev5 | 2 weeks, parallel |
| 7 | **8 Runner** | main (after merging 7 → 5 → 6) | Phases 4–7 merged | nothing | resume, budget stop, 2 parallel on the laptop, audit in the loop | 1 week |
| 8 | **6 tuning + 9 Analysis** | main | Phase 8 gate; `TASKSET.sha256` committed | **blind-label 20–30 failures**; approve prompt changes on dev results only | deterministic report; labeller ≥ 80 % agreement | 1–2 weeks |
| 9 | **10 Release** | main | Phases 7, 8, 9 gates | **complete `docs/PREREG.md`**, approve the freeze, rent the box | held-out run once; README complete; `abb repro` identical | 1 week + 1–2 days compute |

Rules for parallel sessions: one branch per phase, merge order 7 → 5 → 6, shared files
(`abb/arms/registry.py`, `docs/DECISIONS.md`, `env.lock.json`, `repos/*.yaml`, README status)
append-only. **Shared machine state** (one toolchain, one cache tree, one results root, one sandbox user):
only the Phase 7 session re-warms `caches\gradle\<repo>`; Phase 5/6 dev runs record the
fingerprint they started with or pass `--allow-env-drift` (recorded); nobody runs `abb env prune`
while another session has a run active; `ABB_HOME` and `ABB_RESULTS_DIR` are user-level
environment variables so every shell agrees.
The Phase 7 session works in a worktree without `s2a/` and the Phase 6 tuning session runs with
`ABB_TUNING=1` (the CLI then refuses any `split: test` task id). Both are **hygiene against
accidental reads, not a security boundary** — the same person wrote the tasks and S2A, the
blobs are still in `.git`, and the README says so (D-019). Clone the Phase 7 worktree as:

```powershell
git clone --no-checkout <remote> "$env:USERPROFILE\abb-tasks"
Set-Location "$env:USERPROFILE\abb-tasks"
git sparse-checkout init --no-cone
git sparse-checkout set "/*" "!/s2a/"
git checkout -b phase-7 main
```

## 4. The first six weeks (part-time; the §3 estimates for Phases 0–4 add up to 5–6 weeks)

| Week | First half | Second half |
|---|---|---|
| 1 | Day 0 bootstrap; Phase 0 steps 1–5 (skeleton, platform layer, toolchain, three smoke-test fixtures) | Phase 0 step 6: AntennaPod + Wikipedia build experiments (hours of Gradle); steps 7–11; gate; seed task |
| 2 | Phase 1: AntennaPod warm cache, workspace, invariants; **you run `abb sandbox setup` (elevated)** | Phase 1: proxy + sandbox verify; Wikipedia cache; gate |
| 3 | Phase 2: mining tooling; mine ≥ 10 candidates; hand-edit the first 3 | Phase 2: reverted + authored task; `setup_commit`; **open the Phase 7 session** once mining works |
| 4 | Phase 2: validate 3×, fix flaky tests; gate | Phase 3: diffscope, grader |
| 5 | Phase 3: sanity matrix (7 rows × 2 tasks); gate; Phase 4: parser, driver, audit | Phase 4: plain + plain-guided; dev5 × 1 → **first results table**; `abb audit` green |
| 6 | **MVP decision** (`PLAN.md` §9); open the Phase 5 and 6 sessions | Phases 5/6 bring-up; Phase 7 continues |

This table owns the week numbers (PLAN §5 mirrors it). Target: first table by the end of week
5; best case week 4; slip rule: if the Phase 2 gate has not passed by the end of week 4, the
first table moves to week 6 and the MVP cut is taken as soon as it exists.

## 5. Where you decide

| When | Decision |
|---|---|
| When the first results table exists (target end of week 5) | Keep the full plan (~11 weeks) or take the MVP cut (2 repos, ~28 tasks, controls at 1 trial, Spec Kit optional) — `PLAN.md` §9. |
| Before Phase 6 tuning | `tasks/TASKSET.sha256` is committed; from here the tuning session never sees test tasks. |
| Before Phase 10 | `docs/PREREG.md` completed: one primary comparison, arms, exclusions, rerun rule. After the freeze nothing changes. |
| After the held-out run | Rerun only if PREREG's harness-bug criteria are met; first run stays primary unless asymmetric. |

## 6. Watchlist (first two weeks)

| Sign | Means | Do |
|---|---|---|
| `git apply` fails on every patch | CRLF conversion | `git config --global core.autocrlf false`, re-clone |
| Neither Ctrl+Break nor Ctrl+C leaves a `result` line | undocumented Windows behaviour | expected; the driver imputes cost; rely on `--max-turns`/`--max-budget-usd` as the primary bounds |
| smoke test 404 on the model id | ids changed | update D-001; the agent continues |
| `android-all` or `Could not resolve` in `abb env verify` | warm step incomplete | add the test run / SDK level to `warm_commands` |
| workspace delete fails ("being used by another process") | Gradle daemon or Explorer lock | `gradlew.bat --stop`; the robust delete retries and reports leftovers |
| `CreateProcessWithLogonW` logon failure | sandbox user lacks logon rights | `sandbox-setup.ps1` grants them; fallback `Start-Process -Credential` |
| smoke test through the proxy hangs or retries | non-essential traffic not disabled, or DNS | agent env `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1` + `CLAUDE_CODE_PROXY_RESOLVES_HOSTS=1`; check `results/<run>/proxy.log` |
| the `ABB_HOME` drive under 20 GB free | workspaces piling up | `abb env prune` when no run is active |
| `init.model` reports a dated snapshot id | the CLI resolved the pinned id | fine: the driver matches by prefix and records it; update D-001 with the mapping |
| < 2 of 10 mined candidates validate | tickets leak the fix or tests need hooks | author 3 of the 5 dev tasks yourself (Phase 2 pitfalls) |
| Console spend climbing with no RUNS.md row | untracked runs | every run gets a row; dev cap $5/trial |
| grader reports every test `missing` | wrong flavor task name or JUnit path | `./gradlew :m:tasks --all`; fix `test_task_for_module` |

## 7. Done looks like

`s2a run "<prompt>" --profile android` takes a real repo from prompt to a verified, reported
change · one command runs the benchmark matrix · `abb audit` and `abb report` reproduce the
published numbers from transcripts · the README states the split, model, trials, limits, biases
and the single pre-registered comparison.
