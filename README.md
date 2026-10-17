# S2A Framework — Task #1: Brownfield Android Agent Benchmark

**S2A (Specs → App)** is a spec-driven workflow for building and changing software with coding
agents. It starts with Android and will expand to other stacks later.

This folder holds the **complete, agent-executable plan** for S2A's first deliverable:

> **Brownfield Android agent benchmark.** 30–50 real tasks (bug fixes, features, refactors) across
> 3–5 open-source Android apps, each graded by hidden tests. Compares a plain coding agent,
> GitHub Spec Kit, and the S2A workflow on pass rate, cost per task, human interventions and a
> failure breakdown. Timeline: ~11 weeks part-time with parallel agent sessions; 8 weeks with the
> MVP cut in `PLAN.md` §9.

Nothing here is the benchmark itself yet. The plan is written so that a coding agent (Claude Code
or similar) can build the whole thing phase by phase, with a verifiable gate at the end of each
phase.

## How to use this folder

1. Do the human bootstrap in `docs/DAY-0.md` (PowerShell 7, `gh`, `uv`, Claude Code ≥ 2.1.211, key,
   `ABB_HOME`, the clone at `%USERPROFILE%\abb-src`). **No WSL, no Docker.**
2. Open Claude Code in `%USERPROFILE%\abb-src` and paste the kickoff prompt from `START-HERE.md`
   (it says: read `AGENTS.md`, then `PLAN.md`, then execute Phase 0 and stop at its gate).
3. Review the gate output. Then: *"Execute Phase 1."* And so on.
4. Phases 0–4 are sequential (Phase 4 builds the agent driver and runner the other arms reuse).
   Phase 7 (tasks at scale) opens mid-Phase 2, as soon as mining yields candidates; Phases 5 and
   6 open after Phase 4; each runs in its own agent session and branch. Then 8 → 9 → 10.
5. Never work from this OneDrive folder: it is the original import. `%USERPROFILE%\abb-src` with
   a private GitHub remote is the working tree (`docs/DAY-0.md`).

Everything the agent needs is in three places:

| Folder | What it is |
|---|---|
| `START-HERE.md` | The startable runbook: prerequisites, kickoff prompt, session map, first-six-weeks calendar (owns the week numbers), MVP cut. **Start here.** |
| `PLAN.md` | The master plan: goals, phases, gates, timeline, risks, cost. |
| `phases/` | One file per phase: deliverables, exact steps, code contracts, acceptance checks. |
| `specs/` | Contracts shared across phases: task format, grading protocol, adapter interface, results layout, metrics, fairness rules, environments (Windows-native, no containers), platform layer, headless-agent driving. |
| `reference/` | Facts gathered on 2026-10-16 (repo candidates, tool versions, sources) with "re-verify" notes. |
| `benchmark/` | Seed files that are concrete contracts (repo configs, `config/{limits,sandbox,toolchain}.yaml`, task template, `pyproject.toml`, adapter base class). The harness code is built here by the agent. |
| `docs/` | `DAY-0.md` (human bootstrap), `PREREG.md` (pre-registration, completed before the freeze), `DECISIONS.md`, `RUNS.md` (lab notebook). |
| `s2a/` | **The S2A framework itself**: a standalone orchestrator CLI (`s2a run "<prompt>"`) that drives a coding agent through gated stages to a verified change, autonomously by default. Seeds inside the package: `s2a/s2a/pipeline.yaml`, `profiles/android.yaml`, `prompts/*.md`. Design in `specs/s2a-orchestrator.md`; principles in `specs/brownfield-principles.md`; built in Phase 6. |

## The one rule

**By the end of Phase 4 — target end of week 5 — a results table with real numbers must
exist**, even if it is 6 tasks, 1 arm and 1 trial. Every later phase improves something that
already works end to end.

## Status

| Phase | Name | Status |
|---|---|---|
| 0 | Foundations (Windows-native): CLI skeleton, platform layer, pinned toolchain, repo selection experiment | not started |
| 1 | Environments + sandbox: warm caches, history-free workspaces, sandbox user + firewall + proxy | not started |
| 2 | Tasks & validation: task format, mining, authoring, 3× flakiness validation | not started |
| 3 | Grading: hidden-test grading, anti-gaming resets, secondary metrics | not started |
| 4 | Arm A + controls, driver, setup support, `abb audit`, first results table | not started |
| 5 | Arm B: GitHub Spec Kit adapter | not started |
| 6 | S2A orchestrator (`s2a/`) + Arm C wrapper + ablations | not started |
| 7 | Scale to 40 tasks across 3–5 repos; freeze dev/test split | not started |
| 8 | Runner: full matrix, parallelism, resumability, budget guard | not started |
| 9 | Analysis: pass@1 / pass^3, paired bootstrap, cost, failure labelling, charts | not started |
| 10 | Release: final held-out run, write-up, reproducibility package | not started |

Update this table as phases complete.
