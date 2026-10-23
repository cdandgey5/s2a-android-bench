# abb — Android Brownfield Bench

Does a staged orchestrator (**S2A**: map → intake → locate → spec → plan → implement → verify) make Claude Code
better at real changes to existing Android apps than Claude Code on its own? This benchmark answers that for two
open-source apps, with hidden tests, a frozen pre-registration and a single held-out run.

> **Status:** the held-out run is in progress (2026-10-22 →). Every number below marked *[after the run]* is
> filled from `results/<run_id>/report/summary.md` after `abb audit` passes; nothing here is a number until then.

## What is compared

| Arm | What it is |
|---|---|
| `plain` | Claude Code, one headless call with the ticket. The baseline. |
| `plain-guided` | `plain` plus the S2A workflow written as prose in the prompt (prompt vs harness control). |
| `speckit` | GitHub Spec Kit v1.2.1, automated: bug path (`/speckit-bug-*`) for bugfixes, SDD path (specify → plan → tasks → implement) otherwise. |
| `s2a` | The S2A orchestrator (`../s2a`), driven only through its CLI. |
| `s2a-nomap`, `s2a-noverify` | Ablations: no codebase map; no verify/fix loop. |
| optional, 1 trial | `plain-gate` (plain + one harness test run), `s2a-norepro` (no reproduce stage), `speckit-sdd` (SDD path for every task). |

Every arm gets the same budget per trial: **45 min wall clock, $15 est. USD, 200 turns, nudges ≤ 2 per call and ≤ 4
per trial**. Wall clock and est. USD are the binding limits. Spec Kit's `/speckit-clarify`, `/speckit-checklist` and
`/speckit-analyze` are skipped because they expect a human (D-006); `speckit-sdd` is kept as the tool's own-routing
ablation. One-time per-repo setups (Spec Kit constitution, S2A codebase map) are built once with the pinned model,
cached, and reported separately from per-task cost.

An **intervention** is a nudge: a fixed, content-free message ("No human is available. Make reasonable
assumptions … and proceed") the harness sends when a call ends in success but asked a question (through the tool or
in its last message), or when an implementing call left the workspace unchanged (`../specs/headless-agent-driving.md`
§3). Nudges count against the same budgets and are reported per arm.

## Tasks

| | AntennaPod | Wikipedia | Total |
|---|---|---|---|
| Repo | [AntennaPod/AntennaPod](https://github.com/AntennaPod/AntennaPod) (GPL-3.0, Java, JDK 21) | [wikimedia/apps-android-wikipedia](https://github.com/wikimedia/apps-android-wikipedia) (Apache-2.0, Kotlin, JDK 17) | |
| Setup commit | `bb6daf84` | `97ff25cb` | |
| Tasks (dev / test) | 13 (6 / 7) | 12 (4 / 8) | **25 (10 / 15)** |
| Test: bugfix / feature / refactor / cross-module | 3 / 1 / 2 / 1 | 3 / 3 / 1 / 1 | 6 / 4 / 3 / 2 |
| Test: mined / authored | 4 / 3 | 4 / 4 | 8 / 7 |

- A task is a ticket (`problem.md`), a base commit, hidden fail-to-pass and pass-to-pass JUnit/Robolectric tests,
  and a gold patch. Each was validated three times (fails at base, passes with the gold patch, offline).
- **Mined** tasks come from merged upstream PRs; **authored** tasks were written for the benchmark (drafted by the
  agent, `claude-opus-5-5`, and reviewed by the owner). Three test tasks are historical and post-date the pinned
  model's June 2026 cutoff (antennapod-0006/7/8).
- 7 candidates were dropped before any trial ran on them (22 %; `tasks/DROPPED.md`).
- Selection bias: mined tasks need a PR with unit tests that fail before the fix, so the set over-represents
  logic that is testable on the JVM and under-represents UI and Compose work (`tasks/COVERAGE-NOTES.md`).
- **Split:** seed 20261101, dev 10 (including the six pinned bring-up tasks antennapod-0000…0005), test 15
  (`tasks/split.yaml`). Task-set hash `tasks/TASKSET.sha256` = `80b55a02…`. S2A was tuned on `dev` only, with test ids
  refused by the harness (`ABB_TUNING=1`).

## Pre-registration and the single held-out run

- `../docs/PREREG.md`, frozen at tag `v1.0-frozen` (commit `207ebfe`, 2026-10-22); sha256
  `7253364deb16d1ff04ef93fab49f1e70d6c2bf561a4a9e6ad6057d2c4baa7b93`, recorded in the held-out run's manifest. The runner
  refuses a test-split run unless PREREG and the tasks are unchanged since the tag (D-063).
- **Primary comparison:** `s2a` vs `plain`, pass@1 on all 15 test tasks, 3 trials per task, paired bootstrap over
  tasks (10 000 resamples, 95 % CI).
- **Detectable effect:** with 15 tasks × 3 trials, a difference smaller than **≈ 24 pp** (at pass@1 ≈ 0.8, 80 %
  power) is unlikely to be detected. The post-cutoff robustness check has n = 3 and is uninformative by design.
- Model **`claude-opus-5-5`**, Claude Code **2.1.302**, Spec Kit **v1.2.1**, s2a **`5ca7283`**; subscription auth
  (Max 5x), `--parallel 2` on one Windows laptop.
- The test set is run **once**: `20261022-2104-heldout-final` (started 2026-10-22), then `heldout-optional`. A
  re-run is allowed only for a proven harness bug under PREREG's criteria, and both runs are published.

## Results *[after the run]*

<!-- RESULTS: headline table with CIs, cost per task and per resolved task, one-time setup cost, controls,
usage-limit sensitivity, failure breakdown — copied from report/summary.md of the audited held-out run -->

## Contamination

- Agents run as a separate low-privilege Windows user in a history-free snapshot (no `.git` history past the base,
  no upstream remote), with **no web access** (an egress proxy allows only the model API) and no hidden tests or
  gold patch anywhere in the workspace.
- Setup artifacts are generated at the setup commit, an ancestor of every task's base, and linted for leaked fix
  content (`abb tasks lint --setup-leak`: 0 leaks, D-062).
- Mined tasks may still be in the model's training data; the post-cutoff rows and the authored rows are reported
  separately so the reader can compare.

## Author isolation (hygiene, not a boundary)

All 25 tasks were drafted before any S2A code existed, the task-set hash was committed before tuning began, and
tuning ran with test ids refused. The same agent session wrote the tasks and S2A, so this is ordering hygiene, not
independence.

## Known limitations

- 15 test tasks × 3 trials: only large differences are detectable (≈ 24 pp).
- Two repositories, JVM unit and Robolectric tests only (no instrumented or UI tests); Claude Code only.
- Failure labels come from an uncalibrated LLM labeller (the manual calibration labels were skipped, D-057).
- One machine (32 GB, Windows 11); subscription usage windows pause the run, never the scored trials (a trial cut
  by a usage limit is re-run and not counted).

## Reproduce

```powershell
cd benchmark
uv sync
uv run abb tools install                  # pinned JDKs, Android SDK, CPython, pwsh, claude.exe, specify -> ABB_HOME\tools
uv run abb env warm antennapod --warm-commits-from-tasks   # offline Gradle caches for every task base commit
uv run abb env warm wikipedia --warm-commits-from-tasks
uv run abb sandbox setup --slots 2        # one UAC prompt: the low-privilege agent users
uv run abb run --arm plain --arm s2a --tasks test --trials 3 --parallel 2 --model claude-opus-5-5 --label mine --grade
uv run abb audit <run_id>
uv run abb report <run_id>
uv run abb repro <run_id>                 # re-grade 3 trials, re-audit, re-render the report: identical numbers
```

The token from `claude setup-token` is read from the user environment variable `ABB_OAUTH_TOKEN` (or the git-ignored
`.env`) and reaches `claude.exe` only through the per-run environment block, as `CLAUDE_CODE_OAUTH_TOKEN`. Never set
that name, or `ANTHROPIC_API_KEY`, globally: the harness refuses to start if its own environment has either.
Everything runs natively on Windows through the platform layer (`abb/harness/platform/`); no WSL, no Docker.

Licence: MIT (`LICENSE`); task patches derived from upstream repositories carry their upstream licence
(`tasks/<id>/LICENSE-NOTE.md`). Design: `../PLAN.md`, `../specs/`; decisions: `../docs/DECISIONS.md`; every run:
`../docs/RUNS.md`.
