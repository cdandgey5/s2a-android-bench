# Pre-registration (complete and commit BEFORE `v1.0-frozen`; sha256 goes into the manifest)

Status: **TEMPLATE** — fields marked `[ ]` are filled in Phase 10 step 1, before the held-out run.
Nothing in this file may change after the freeze tag; if it must, the run is a new, labelled run.

## Primary hypothesis and comparison

- H1: The S2A orchestrator resolves more held-out tasks than the plain agent.
- **Primary comparison:** `s2a` vs `plain`, metric **pass@1**, task set **all `split: test`
  tasks** (n ≈ 28), paired bootstrap over tasks, 10 000 resamples, 95 % CI. The headline is this
  one interval. `stats.detectable_delta` for this denominator: `[ ]` pp.
- **Pre-registered robustness check:** the same comparison restricted to historical
  post-cutoff tasks (mined/reverted with both `issue_created` and `fix_date` after the pinned
  model's cutoff, D-001); n = `[ ]`, detectable delta `[ ]` pp. It is reported next to the
  headline with its own CI and is expected to be wide.
- Secondary (reported, not headline): `s2a` vs `plain-guided` (prompt vs harness); `s2a` vs
  `speckit`; cost per task and per resolved task.
- Exploratory (labelled as such): every other arm pair, every breakdown (repo, category,
  source, cutoff, files, lang, ui), the ablations, pass^3, interventions, convention score.

## Arms in the matrix and trials

- [ ] Final arms: `plain`, `plain-guided`, `speckit`, `s2a`, `s2a-nomap`, `s2a-noverify` at 3
  trials; optional at 1 trial if budget allows: `plain-gate`, `s2a-norepro`, `speckit-sdd`.
- [ ] Model: `claude-opus-5-5`; Claude Code version: `[ ]`; Spec Kit ref: `[ ]`; `s2a_git_sha`: `[ ]`.
- [ ] Limits: 45 min, $15, 200 turns, nudges 2/call 4/trial. Binding: wall-clock and USD.

## Task set

- [ ] `tasks/TASKSET.sha256` = `[ ]` (committed on `[date]`, before S2A tuning began on `[date]`).
- [ ] Split: seed `[ ]`, dev `[n]`, test `[n]`, pinned dev ids: `[ ]`.
- [ ] Test tasks: `[n]` (the primary denominator); historical post-cutoff among them: `[n]` (the robustness denominator).
- [ ] Dropped tasks and reasons: `tasks/DROPPED.md` (none dropped after any trial ran on them).

## Exclusion and denominator rules (fixed now)

- `agent_error` trials (including orchestrator crashes) are **unresolved** and stay in the
  denominator.
- `harness_error` trials are re-queued once; if still failing they are **excluded** from the
  denominator and listed in "trials lost" with their reason. If any arm loses > 5 % of its
  trials this way, the whole task is excluded for all arms (paired design).
- `test_compile_failed` outcomes are unresolved in the primary metric; those on a non-empty diff
  touching the F2P module are reported in the interface table with their blind `INTERFACE` labels.
- `flaky_p2p` tests are excluded from regressions (D-023).

## Harness-bug criteria and rerun rule

A rerun of the held-out set is permitted only if, during or after the run, one of these is
shown from the stored artifacts: (a) `patch_apply_failed` on a diff that applies cleanly by
hand; (b) `abb audit` fails for a reason traceable to the harness, not the agent; (c) the
grading container or image differs from the manifest digest; (d) a gate/revert bug that
changes `resolved` for ≥ 1 trial. The **first run remains primary**; a rerun replaces it only
if the bug affected arms asymmetrically (shown per arm in the report). Both runs are published.

## Analysis plan

- `abb audit` must pass before `abb report` prints headline numbers.
- Report the detectable effect size for the primary denominator (`stats.detectable_delta`).
- Failure labelling: blind manual labels on ≥ 20 stratified failures, LLM labels for the rest,
  agreement reported per arm.
- Cost: `cost_usd` with null-cost share and `cost_usd_imputed`; setup cost per setup kind and
  amortised; gate runs and per-stage turns per arm.

## Sign-off

- [ ] Author isolation confirmed: test-split tasks authored in sessions without `s2a/`
  (`tasks/TRIAGE.md` timestamps; task `created_with_s2a_sha` ≤ the hash date).
- [ ] This file's sha256 recorded in `manifest.prereg_sha256`: `[ ]`.
- [ ] Freeze tag `v1.0-frozen` = `[commit]`, date `[ ]`.
