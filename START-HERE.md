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

Windows 11, **no WSL, no Docker, no API key**: PowerShell 7 · Git for Windows · `gh` · `uv` · Claude
Code ≥ 2.1.280 pinned · a one-year subscription token from `claude setup-token` stored as the
user variable `ABB_OAUTH_TOKEN` (only the harness maps it to `CLAUDE_CODE_OAUTH_TOKEN`, inside
each trial; `specs/auth-and-usage.md`) · `ABB_HOME` on the drive with
≥ 60 GB free on local NTFS (short path, e.g. `C:\abb`; not the Google Drive `G:`) · the plan copied out of OneDrive to
`%USERPROFILE%\abb-src` with a private GitHub remote · decisions written down: pinned model + its
training-cutoff date (D-001), Claude Code version, first two repos (default AntennaPod +
Wikipedia Android), dev estimate cap per trial (default $5 est. API-equivalent). One elevated step comes later (Phase 1:
`abb sandbox setup`).

## 2. Running the phases in Claude Code (no API, your subscription)

"Session" and "chat" below always mean a **Claude Code session** — the desktop app's Code tab or
`claude.exe` in a PowerShell 7 window, opened on `%USERPROFILE%\abb-src` — never claude.ai.
Nothing needs an API key: the benchmark's headless runs use the subscription token
(`specs/auth-and-usage.md`), and the session itself runs on your normal login (the token is
stored under a name Claude Code never reads).

**Default: one session builds everything — `phases/RUN-ALL.md`.** Paste its kickoff prompt into
one Claude Code session; it executes Phases 0 → 10 in order, applies the autopilot defaults,
and stops only at the hard stop points where you must act (UAC prompt, task review, PREREG and
the held-out run). A long session auto-compacts; every gate rewrites `docs/HANDOFF.md` and
commits, so if the session is interrupted (usage limit, restart) you continue it
(`claude --continue`, or pick it in the app's sidebar) or start a new one with the same prompt.

```
Read AGENTS.md, then phases/RUN-ALL.md, and run the plan in autopilot: execute every phase in
the order RUN-ALL.md gives, from the phase docs/HANDOFF.md names (Phase 0 if it is still the
template). Apply the autopilot defaults for every decision; stop only at the hard stop points,
tell me exactly what you need, and wait. At every gate rewrite docs/HANDOFF.md and commit.
```

**Alternative: one session per phase** (review each gate yourself; parallel branches for
Phases 5/6/7). The prompts below do that; both modes share the same files and handoff, and you
can switch at any gate.

Phase files: `phase-0-foundations.md`, `phase-1-environments.md`, `phase-2-tasks-and-validation.md`,
`phase-3-grading.md`, `phase-4-arm-plain.md`, `phase-5-arm-speckit.md`, `phase-6-s2a-orchestrator.md`,
`phase-7-scale-tasks.md`, `phase-8-runner.md`, `phase-9-analysis.md`, `phase-10-release.md`.

**Kickoff (first chat, Phase 0):**

```
Read AGENTS.md, then PLAN.md, then phases/phase-0-foundations.md. Execute Phase 0 step by step.
Step 1 verifies my bootstrap (docs/DAY-0.md); if anything is missing, stop and tell me exactly
what to do. Use the seed files under benchmark/ as given. Keep docs/RUNS.md current for every
run. When the Phase 0 acceptance gate passes, paste the gate output, rewrite docs/HANDOFF.md,
update the status table in README.md, commit and push, and stop. Do not start Phase 1.
```

**Next phase (a new chat each time):**

```
Read AGENTS.md, docs/HANDOFF.md and `git log --oneline -20`, then phases/phase-N-<name>.md.
Confirm the previous phase's gate still passes (re-run its gate commands; fix only what the
rerun proves broken). Then execute Phase N step by step. At its gate: paste the output, rewrite
docs/HANDOFF.md, update README.md's status table, commit and push, and stop.
```

**When a chat gets long mid-phase:** tell it `Write the handoff file for this branch
(docs/HANDOFF.md on main, docs/HANDOFF-phase-N.md on branch phase-N) with the exact step you are
on, what is done and what is next, commit, and stop.` Then open a new chat with:

```
Read AGENTS.md, the handoff file for this branch (docs/HANDOFF.md on main; docs/HANDOFF-phase-N.md
on branch phase-N), `git status` and `git log --oneline -20`. If the tree holds uncommitted work
the handoff does not mention, inspect it before continuing. Continue Phase N from the step named
there; do not redo finished steps. At the gate: paste the output, rewrite the handoff file, commit,
push, stop.
```

**Parallel phase, first chat (Phases 5, 6, 7 — own branch, own handoff file):**

```
Read AGENTS.md, docs/HANDOFF.md and `git log --oneline -20`, then phases/phase-N-<name>.md.
Create branch phase-N from main (`git checkout -b phase-N main`) and create docs/HANDOFF-phase-N.md
from the template in docs/HANDOFF.md; on this branch never edit docs/HANDOFF.md. Confirm the gate
this phase starts from (its Prerequisites line) still passes. Execute Phase N step by step. At its
gate: paste the output, rewrite docs/HANDOFF-phase-N.md, update README.md's status table, commit,
push the branch, and stop. Do not merge.
```

Phase 7's chats are opened in `%USERPROFILE%\abb-tasks` — the sparse worktree without `s2a/`
created with the PowerShell block in §3 (which already creates branch `phase-7`) — and its
starting gate is Phase 2 step 3 (`abb tasks mine` yields candidates). Later chats of a parallel
phase use the next-phase and resume prompts above with `docs/HANDOFF-phase-N.md` and `git
checkout phase-N` first.

**Merge (one chat on `main`, before Phase 8):**

```
Read AGENTS.md and docs/HANDOFF.md. On main, `git merge --no-ff` phase-7, then phase-5, then
phase-6, in that order. Shared files (abb/arms/registry.py, docs/DECISIONS.md, env.lock.json,
repos/*.yaml, README.md's status table) are append-only: keep both sides. In each merge commit
delete that branch's docs/HANDOFF-phase-N.md after folding its open items into docs/HANDOFF.md.
Then run `uv run pytest -q`, `uv run abb tasks lint --all` and `uv run abb sandbox install-s2a`,
and re-run the Phase 4, 5, 6 and 7 gate commands. Rewrite docs/HANDOFF.md, commit, push, stop.
```

Habits that keep this cheap: `/compact` when the context gets heavy instead of starting over;
ask for the handoff before the chat is unusable, not after; one phase per chat (per-phase
variant). **Your chats and
the headless trials draw on the same account's usage windows**: a dev run or the canary
(`abb ws smoke --until-limit`) also locks out the chat you are building in, so run them at the
end of a work session, and build on Sonnet (`/model claude-sonnet-5-5`) on days an Opus run is
scheduled (Pro/Max chats default to Opus 5.5). Claude Code's auto memory is machine-local
and not relied on — `HANDOFF.md`, `RUNS.md`, `verified.md`, `DECISIONS.md` and git are the state.
A "session" in §3 is one chat, or a chain of chats joined by `HANDOFF.md`, on one branch.

## 3. Phase sequence, sessions and gates

In **autopilot** (`phases/RUN-ALL.md`, the default) there is one session and one branch
(`main`): the "Session / branch" column below does not apply, nothing is merged, and the order
is 0 → 1 → 2 → 3 → 4 → 7 → 5 → 6 (bring-up) → 8 → 6 tuning + 9 → 10. The table is the
per-phase variant with parallel branches.

| Order | Phase | Session / branch | Starts when | You do during it | Gate (what you check) | Est. |
|---|---|---|---|---|---|---|
| 1 | **0 Foundations** | main session, `main` (autopilot: the one session, always `main`) | Day 0 done | answer questions | `abb tools check` (pinned JDKs + SDK); three smoke-test fixtures (incl. the interrupt finding); 2 repos built on Windows with timings; seed task `antennapod-0000`; `abb repos check` | 4–6 days |
| 2 | **1 Environments + sandbox** | same | Phase 0 gate | **run `abb sandbox setup` once in an elevated PowerShell when asked; read the usage meter before and after the throughput probe (step 10b), then decide Pro / Max / MVP cut** | offline tests < 10 min per repo as the sandbox user; invariants green (denied paths denied, no build cache); `abb sandbox check` proves firewall + proxy; throughput probe recorded (D-027) | 4–6 days |
| 3 | **2 Tasks & validation** | same | Phase 1 gate | **review every drafted task (S2) — or hand-edit/write them yourself in the per-phase variant** | 5 tasks + seed validated 3×; lint (incl. interface rule) clean; `setup_commit` set | 1–2 weeks |
| 3′ | **7 Scale tasks** (long pole) | **new session, branch `phase-7`, worktree without `s2a/`** | mid-Phase 2, once `abb tasks mine` yields candidates (Phase 2 step 3) | **triage mined candidates, author ~14 tasks with reference fixes; review repos 3/4 build results** | ≥ 35 validated; coverage within tolerance; `TASKSET.sha256`; split frozen with dev5 pinned | 3 weeks, parallel |
| 4 | **3 Grading** | main | Phase 2 gate | nothing | 7-row sanity matrix green on seed + 1 dev task | 3–5 days |
| 5 | **4 Arm A + controls** | main | Phase 3 gate | **read the first transcripts; record cost per run in RUNS.md** | **first results table**; `abb audit` passes; plain-guided runs | 1 week |
| 6 | **5 Spec Kit** | new session, branch `phase-5` | Phase 4 gate | spot-check one constitution | 5 tasks end-to-end; setup cost separate; `slash_commands` gate | 1 week, parallel |
| 6′ | **6 S2A orchestrator** | new session, branch `phase-6` | Phase 4 gate | **review the first codebase map by hand; read one full run's artifacts** | `s2a run` end to end on one task; resume works; S2A + ablations on dev5 | 2 weeks, parallel |
| 7 | **8 Runner** | main (after merging 7 → 5 → 6) | Phases 4–7 merged | nothing | resume, budget stop, 2 parallel on the laptop, audit in the loop | 1 week |
| 8 | **6 tuning + 9 Analysis** | main | Phase 8 gate; `TASKSET.sha256` committed | **blind-label 20–30 failures**; approve prompt changes on dev results only | deterministic report; labeller ≥ 80 % agreement | 1–2 weeks |
| 9 | **10 Release** | main | Phases 7, 8, 9 gates | **complete `docs/PREREG.md` incl. `auth_mode`**, approve the freeze, plan the usage windows (optionally a Windows VM) | held-out run once; README complete; `abb repro` identical | 1 week + 1–2 days compute |

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

Autopilot is serial: full plan 15–18 weeks, ~12–14 with the MVP default (`PLAN.md` §5); the
parallel-branch variant is ~11 weeks. Weeks 1–5 differ only in the "open the Phase 7 session"
cell (not applicable in autopilot); from week 6 autopilot runs Phase 7, then 5, 6, 8 one after
another in the same session.

| Week | First half | Second half |
|---|---|---|
| 1 | Day 0 bootstrap; Phase 0 steps 1–5 (skeleton, platform layer, toolchain, three smoke-test fixtures) | Phase 0 step 6: AntennaPod + Wikipedia build experiments (hours of Gradle); steps 7–11; gate; seed task |
| 2 | Phase 1: AntennaPod warm cache, workspace, invariants; **you run `abb sandbox setup` (elevated)** | Phase 1: proxy + sandbox verify; Wikipedia cache; gate |
| 3 | Phase 2: mining tooling; mine ≥ 10 candidates; draft/review the first 3 | Phase 2: reverted + authored task; `setup_commit`; per-phase variant: **open the Phase 7 session** once mining works |
| 4 | Phase 2: validate 3×, fix flaky tests; gate | Phase 3: diffscope, grader |
| 5 | Phase 3: sanity matrix (7 rows × 2 tasks); gate; Phase 4: parser, driver, audit | Phase 4: plain + plain-guided; dev5 × 1 → **first results table**; `abb audit` green |
| 6 | **MVP decision** (`PLAN.md` §9; autopilot applies its default) | Per-phase variant: open the Phase 5 and 6 sessions, Phase 7 continues. Autopilot: Phase 7 drafting + S2 review |

This table owns the week numbers (PLAN §5 mirrors it). Target: first table by the end of week
5; best case week 4; slip rule: if the Phase 2 gate has not passed by the end of week 4, the
first table moves to week 6 and the MVP cut is taken as soon as it exists.

## 5. Where you decide

| When | Decision |
|---|---|
| After the Phase 1 throughput probe (step 10b, end of week 2; D-027) | With the measured trials per window and per week: stay on Pro, move to Max, or take the MVP cut (`PLAN.md` §9) now rather than at week 5. Record the choice in `docs/DECISIONS.md`. |
| Before the held-out run | `docs/PREREG.md: auth_mode` — run the matrix under your subscription in batches across usage windows, or ask Anthropic first (`specs/auth-and-usage.md` §5). |
| When the first results table exists (target end of week 5) | Keep the full plan (~11 weeks) or take the MVP cut (2 repos, ~28 tasks, controls at 1 trial, Spec Kit optional) — `PLAN.md` §9. |
| Before Phase 6 tuning | `tasks/TASKSET.sha256` is committed; from here the tuning session never sees test tasks. |
| Before Phase 10 | `docs/PREREG.md` completed: one primary comparison, arms, exclusions, rerun rule. After the freeze nothing changes. |
| After the held-out run | Rerun only if PREREG's harness-bug criteria are met; first run stays primary unless asymmetric. |

## 6. Watchlist (first two weeks)

| Sign | Means | Do |
|---|---|---|
| `git apply` fails on every patch | CRLF conversion | `git config --global core.autocrlf false`, re-clone |
| Neither Ctrl+Break nor Ctrl+C leaves a `result` line | undocumented Windows behaviour | expected; the driver imputes cost; rely on `--max-turns`/`--max-budget-usd` as the primary bounds |
| smoke test rejects the model id | ids changed, or the plan does not allow Opus | update D-001 (Sonnet fallback); the agent continues |
| `android-all` or `Could not resolve` in `abb env verify` | warm step incomplete | add the test run / SDK level to `warm_commands` |
| workspace delete fails ("being used by another process") | Gradle daemon or Explorer lock | `gradlew.bat --stop`; the robust delete retries and reports leftovers |
| `CreateProcessWithLogonW` logon failure | sandbox user lacks logon rights | `sandbox-setup.ps1` grants them; fallback `Start-Process -Credential` |
| smoke test through the proxy hangs or retries | non-essential traffic not disabled, or DNS | agent env `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1` + `CLAUDE_CODE_PROXY_RESOLVES_HOSTS=1`; check `results/<run>/proxy.log` |
| the `ABB_HOME` drive under 20 GB free | workspaces piling up | `abb env prune` when no run is active |
| `init.model` reports a dated snapshot id | the CLI resolved the pinned id | fine: the driver matches by prefix and records it; update D-001 with the mapping |
| < 2 of 10 mined candidates validate | tickets leak the fix or tests need hooks | author 3 of the 5 dev tasks yourself (Phase 2 pitfalls) |
| a trial ends with "hit your session limit" | subscription usage window exhausted | expected; the runner marks it `usage_limited`, pauses, probes every 15 min and re-queues (Phase 4 canary records the exact output) |
| `abb auth check` fails or reports `api_key` | a stray `ANTHROPIC_API_KEY`/`CLAUDE_CODE_OAUTH_TOKEN` in the user environment, or `ABB_OAUTH_TOKEN` missing or expired | unset the strays; `claude setup-token` → `ABB_OAUTH_TOKEN` (`docs/DAY-0.md` §3) |
| a long or paused run died overnight | the laptop slept: trials were suspended and their deadlines fired on wake | `powercfg /change standby-timeout-ac 0` while runs are active (`docs/DAY-0.md` §2); `--resume` |
| dev runs never hit a usage limit, Phase 8 refuses the matrix | no canary recorded | `abb ws smoke --until-limit` at the end of a session window (costs the rest of it), or `--allow-no-canary` (recorded) |
| grader reports every test `missing` | wrong flavor task name or JUnit path | `./gradlew :m:tasks --all`; fix `test_task_for_module` |

## 7. Done looks like

`s2a run "<prompt>" --profile android` takes a real repo from prompt to a verified, reported
change · one command runs the benchmark matrix · `abb audit` and `abb report` reproduce the
published numbers from transcripts · the README states the split, model, trials, limits, biases
and the single pre-registered comparison.
