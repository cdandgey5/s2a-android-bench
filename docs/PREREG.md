# Pre-registration (complete and commit BEFORE `v1.0-frozen`; sha256 goes into the manifest)

Status: **DRAFT for S5 (2026-10-22)** — every field the harness already knows is filled from the repository and
the run records. Fields marked **[S5]** are the owner's decisions at the hard stop; fields marked **[confirm]** are
filled from the Opus dev-set confirmation run (`dev-opus-confirm`) before the freeze. Nothing in this file may
change after the freeze tag; if it must, the run is a new, labelled run.

## Primary hypothesis and comparison

- H1: The S2A orchestrator resolves more held-out tasks than the plain agent.
- **Primary comparison:** `s2a` vs `plain`, metric **pass@1**, task set **all 15 `split: test` tasks**, 3 trials
  per task, paired bootstrap over tasks (trials averaged within a task), 10 000 resamples, seed 0, 95 % CI. The
  headline is this one interval. `stats.detectable_delta(15, 3, p)` at 80 % power: **≈ 24 pp at pooled pass@1
  0.80** (25.6 pp at 0.75, 21.1 pp at 0.85). Smaller true differences are unlikely to be detected; the README
  says so.
- **Pre-registered robustness check:** the same comparison on historical post-cutoff test tasks (mined/reverted
  with both `issue_created` and `fix_date` after the pinned model's June 2026 cutoff, D-001): **n = 3**
  (antennapod-0006, -0007, -0008); detectable delta ≈ 53-57 pp — **reported for completeness, essentially
  uninformative at this n**. The authored test tasks (7 of 15) are reported as a separate row.
- Secondary (reported, not headline): `s2a` vs `plain-guided` (prompt vs harness); `s2a` vs `speckit`; cost per
  task and per resolved task.
- Exploratory (labelled as such): every other arm pair, every breakdown (repo, category, source, cutoff, files,
  lang, ui), the ablations, pass^3, interventions.

## Arms in the matrix and trials

- Final arms at **3 trials**: `plain`, `plain-guided`, `speckit`, `s2a`, `s2a-nomap`, `s2a-noverify`
  (15 tasks x 3 x 6 = 270 trials). Optional at 1 trial if the budget allows: `plain-gate`, `s2a-norepro`,
  `speckit-sdd` (MVP cut, D-045). **[confirm]** whether the optional arms run.
- Model: **`claude-opus-5-5`** (D-001; profile `final`); Claude Code **2.1.302**; Spec Kit **v1.2.1**;
  `s2a_git_sha` **8f8fc504e39ba792daa4b91b91bda78f689de1a3** (frozen 2026-10-22, s2a/CHANGELOG.md).
- Limits: 45 min, $15 est., 200 turns, nudges 2/call 4/trial. Binding: wall-clock and est. USD. One-time setups
  (Spec Kit constitution, s2a map) are built per repo with the pinned model (D-058) and reported separately.
- Parallelism: `--parallel 2` on the laptop (two sandbox users, D-037/D-056).
- **[S5] `auth_mode`:** `subscription` (batches across usage windows; plan **Max** since 2026-10-21; expected
  windows **[confirm]**) | `subscription after asking Anthropic` (answer kept in `docs/`) | `api_key` — see
  `specs/auth-and-usage.md` §5.
- Budget: `--max-usd` = 1.3 x the estimate from the confirmation run = **[confirm]**.

## Task set

- `tasks/TASKSET.sha256` = **80b55a02e489c1600c2073bd7d943964b8f8580237d7328ea266a65aea625010**. First committed
  2026-10-18 (`2eeddcff…`, commit `466e8fb`) before any S2A tuning (tuning began 2026-10-21); re-hashed
  2026-10-21 after one logged fix to a **dev** task (wikipedia-0007, `tasks/CHANGELOG.md`). No test task has been
  edited after the split.
- Split: seed **20261101**, dev **10**, test **15**; pinned dev ids: antennapod-0000 … antennapod-0005 (dev5).
- Test tasks: **15** (AntennaPod 7, Wikipedia 8; 8 mined, 7 authored) — the primary denominator; historical
  post-cutoff among them: **3** — the robustness denominator.
- Dropped tasks and reasons: `tasks/DROPPED.md` — 7 candidates, all dropped before any trial ran on them.

## Exclusion and denominator rules (fixed now)

- `agent_error` trials (including orchestrator crashes and S2A's own gate stops) are **unresolved** and stay in
  the denominator.
- `harness_error` trials are re-queued once; if still failing they are **excluded** from the denominator and
  listed in "trials lost" with their reason. If any arm loses > 5 % of its trials this way, the whole task is
  excluded for all arms (paired design).
- **Trials spoiled by a proven harness bug** (criterion (d) below, e.g. D-056's ACL race) are set aside with
  `abb run invalidate` (kept under `<run>/invalidated/`, audited, reported with the bug) and run again; the
  re-run counts.
- `test_compile_failed` outcomes are unresolved in the primary metric; those on a non-empty diff touching the F2P
  module are reported in the interface table with their LLM `INTERFACE` labels.
- `flaky_p2p` tests are excluded from regressions (D-023).
- `usage_limited` trials (subscription window exhausted) are re-run and **not counted** in the primary metric;
  the cut attempt is kept under `<run>/usage_limited/` (never graded); the scheduler pauses before the window is
  spent (five-hour utilisation ≥ 0.9) to keep cuts rare (D-028, D-054). A call with no model response at all is
  never `agent_error`.

## Harness-bug criteria and rerun rule

A rerun of the held-out set is permitted only if, during or after the run, one of these is shown from the stored
artifacts: (a) `patch_apply_failed` on a diff that applies cleanly by hand; (b) `abb audit` fails for a reason
traceable to the harness, not the agent; (c) the grading environment fingerprint differs from the manifest; (d) a
gate/revert/ACL bug that changes `resolved` for ≥ 1 trial. The **first run remains primary**; a rerun replaces it
only if the bug affected arms asymmetrically (shown per arm in the report). Both runs are published. Single
spoiled trials under (d) are handled by invalidation and re-run (above), not by a whole rerun.

## Analysis plan

- `abb audit` must pass before `abb report` prints headline numbers.
- Report the detectable effect size for the primary denominator (`stats.detectable_delta`).
- Failure labelling: **LLM labels only; the labeller is uncalibrated** — the owner skipped the manual labels at
  S4 (D-057), so agreement is reported as "not measured".
- Cost: tokens first; `cost_usd` as est. API-equivalent USD with null-cost share and `cost_usd_imputed`; setup cost
  per setup kind and amortised; gate runs, per-stage turns and `usage_limited` pauses per arm.
- **Usage-limit sensitivity check (D-028):** the primary comparison recomputed with each (arm, task, trial) slot's
  first attempt, a `usage_limited` attempt scored unresolved; reported next to the headline with its own CI,
  together with the cut count, cut rate and mean elapsed time and tokens at the cut, per arm. If the headline and
  this check disagree in sign, the write-up says so.
- Dev-set results (`20261020-2049-dev-baseline-1`, tuning runs, the Opus confirmation) are reported as dev, never
  pooled with the held-out run.

## Sign-off

- Author isolation: **ordering-only (single session, RUN-ALL.md)** — all tasks were drafted (Phase 7) before any
  `s2a/` code existed (`created_with_s2a_sha` f045be1 for all 25), `TASKSET.sha256` was committed before any
  tuning, and tuning sessions ran with `ABB_TUNING=1` (test ids refused). Hygiene, not a boundary: the same agent
  session wrote tasks and S2A, and the README says so.
- Task drafting: **25** tasks `drafted_by: agent` (model `claude-opus-5-5`), human-reviewed at S2 (2026-10-18);
  **0** `drafted_by: human`; the README limitations state this.
- **[S5]** This file's sha256 recorded in `manifest.prereg_sha256`: `[at the freeze]`.
- **[S5]** Freeze tag `v1.0-frozen` = `[commit]`, date `[ ]`; the held-out run uses a fresh `claude setup-token`
  token (D-026), retired after the run.
