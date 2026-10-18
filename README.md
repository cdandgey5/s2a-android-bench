# S2A Framework — Task #1: Brownfield Android Agent Benchmark

**S2A (Specs → App)** is a spec-driven workflow for building and changing software with coding
agents. It starts with Android and will expand to other stacks later.

This folder holds the **complete, agent-executable plan** for S2A's first deliverable:

> **Brownfield Android agent benchmark.** 30–50 real tasks (bug fixes, features, refactors) across
> 3–5 open-source Android apps, each graded by hidden tests. Compares a plain coding agent,
> GitHub Spec Kit, and the S2A workflow on pass rate, cost per task, human interventions and a
> failure breakdown. Timeline: one autopilot session (the default) is serial — 15–18 weeks
> part-time, ~12–14 with the MVP cut in `PLAN.md` §9; parallel agent sessions ~11 weeks.

Nothing here is the benchmark itself yet. The plan is written so that a coding agent (Claude Code
or similar) can build the whole thing phase by phase, with a verifiable gate at the end of each
phase.

## How to use this folder

1. Do the human bootstrap in `docs/DAY-0.md` (PowerShell 7, `gh`, `uv`, Claude Code ≥ 2.1.280, a
   `claude setup-token` subscription token, `ABB_HOME`, the clone at `%USERPROFILE%\abb-src`).
   **No WSL, no Docker, no API key.**
2. Open one Claude Code session in `%USERPROFILE%\abb-src` and paste the kickoff prompt from
   `phases/RUN-ALL.md`. It runs Phases 0 → 10 by itself, stops only where you must act (UAC
   prompt, task review, pre-registration, the held-out run), and rewrites `docs/HANDOFF.md` at
   every gate — so an interrupted session is continued, or replaced by a new one with the same
   prompt, without losing anything.
3. Prefer to review each gate? `START-HERE.md` §2 has one-session-per-phase prompts (with
   parallel branches for Phases 5/6/7). Both modes share the same files.
4. Order in autopilot: 0 → 1 → 2 → 3 → 4 → 7 → 5 → 6 (bring-up) → 8 → 6 tuning + 9 → 10, all on
   `main` (tasks are drafted before any S2A code exists). In the per-phase variant Phase 7 opens mid-Phase 2 and Phases 5/6 after Phase 4, each
   in its own session and branch.
5. Never work from this OneDrive folder: it is the original import. `%USERPROFILE%\abb-src` with
   a private GitHub remote is the working tree (`docs/DAY-0.md`).

Everything the agent needs is in three places:

| Folder | What it is |
|---|---|
| `START-HERE.md` | The startable runbook: prerequisites, kickoff prompt, session map, first-six-weeks calendar (owns the week numbers), MVP cut. **Start here.** |
| `PLAN.md` | The master plan: goals, phases, gates, timeline, risks, cost. |
| `phases/` | One file per phase: deliverables, exact steps, code contracts, acceptance checks. |
| `specs/` | Contracts shared across phases: task format, grading protocol, adapter interface, results layout, metrics, fairness rules, environments (Windows-native, no containers), platform layer, headless-agent driving, auth and usage (subscription, no API key). |
| `reference/` | Facts gathered on 2026-10-16 (repo candidates, tool versions, sources) with "re-verify" notes. |
| `benchmark/` | Seed files that are concrete contracts (repo configs, `config/{limits,sandbox,toolchain}.yaml`, task template, `pyproject.toml`, adapter base class). The harness code is built here by the agent. |
| `docs/` | `DAY-0.md` (human bootstrap), `HANDOFF.md` (the state a new chat starts from), `PREREG.md` (pre-registration, completed before the freeze), `DECISIONS.md`, `RUNS.md` (lab notebook). |
| `s2a/` | **The S2A framework itself**: a standalone orchestrator CLI (`s2a run "<prompt>"`) that drives a coding agent through gated stages to a verified change, autonomously by default. Seeds inside the package: `s2a/s2a/pipeline.yaml`, `profiles/android.yaml`, `prompts/*.md`. Design in `specs/s2a-orchestrator.md`; principles in `specs/brownfield-principles.md`; built in Phase 6. |

## The one rule

**By the end of Phase 4 — target end of week 5 — a results table with real numbers must
exist**, even if it is 6 tasks, 1 arm and 1 trial. Every later phase improves something that
already works end to end.

## Status

| Phase | Name | Status |
|---|---|---|
| 0 | Foundations (Windows-native): CLI skeleton, platform layer, pinned toolchain, repo selection experiment | **passed 2026-10-17** — toolchain locked, `abb auth check` → `oauth_token`, 5 smoke fixtures, AntennaPod + Wikipedia chosen (`reference/build-experiments.md`), seed task `antennapod-0000`; findings D-030…D-035 |
| 1 | Environments + sandbox: warm caches, history-free workspaces, sandbox user + firewall + proxy | **passed 2026-10-18** — both repos' unit tests offline as `abb-agent` (AntennaPod 130 s, Wikipedia 347 s), `abb sandbox check` green, invariants 28/1 skipped, throughput probe on Pro ~3 % session per trial (lower bound); D-036…D-038 |
| 2 | Tasks & validation: task format, mining, authoring, 3× flakiness validation | **passed 2026-10-18** — dev5 + seed validated 3× (3 mined, 1 reverted, 2 authored; 3 bugfix, 2 feature, 1 refactor), lint clean, S2 approved |
| 3 | Grading: hidden-test grading, anti-gaming resets, secondary metrics | **passed 2026-10-18** — 7-row sanity matrix green on 2 tasks (14/14), `abb grade-patch` / `abb grade`, metrics.json; no lint delta (D-039) |
| 4 | Arm A + controls, driver, setup support, `abb audit`, first results table | **passed 2026-10-18** — first results table: plain 12/12 (2 trials) and plain-guided 6/6 on dev5 (Sonnet 5.5), est. $0.20–0.22 and ~3.4 min per trial, ~1.3–1.8 % of the Pro five-hour window per trial; audit PASS; usage-limit canary captured; three earlier runs invalid (D-043); MVP cut taken (D-045); D-040…D-045 |
| 5 | Arm B: GitHub Spec Kit adapter | not started |
| 6 | S2A orchestrator (`s2a/`) + Arm C wrapper + ablations | not started |
| 7 | Scale to 40 tasks across 3–5 repos; freeze dev/test split (**MVP cut, D-045: 24–30 tasks, 2 repos, 6 authored**) | in progress (autopilot) — 25 tasks drafted (13 AntennaPod / 12 Wikipedia, 10 authored), all pass a single validation run; **S2 review pending**; D-046, D-047 |
| 8 | Runner: full matrix, parallelism, resumability, budget guard | not started |
| 9 | Analysis: pass@1 / pass^3, paired bootstrap, cost, failure labelling, charts | not started |
| 10 | Release: final held-out run, write-up, reproducibility package | not started |

Update this table as phases complete.

**Scope (MVP cut, D-045, 2026-10-18):** two repositories (AntennaPod, Wikipedia; at most 50 % of tasks from either), 24–30 tasks of which 6 authored (detectable difference ~±20 pp), laptop only. The optional arms (`plain-gate`, `speckit-sdd`, `s2a-norepro`) and the Spec Kit arm run 1 trial each; no lint delta (D-039), no convention score, no assisted mode.
