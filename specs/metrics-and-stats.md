# Spec: Metrics and statistics (`abb/harness/report.py`, `abb/harness/stats.py`)

Unit of analysis: one `metrics.json` row per (arm, task, trial).

## Primary metrics

| Metric | Definition |
|---|---|
| **pass@1** | For each (arm, task): `resolved_trials / trials`. Arm value = mean over tasks. |
| **pass^k** (k = trials = 3) | For each (arm, task): 1 if all trials resolved else 0. Arm value = mean over tasks. |
| **pass@any** | 1 if any trial resolved. Reported but not headline (optimistic). |
| **Tokens per task** | Mean/median over (task, trial) of input, output and cache tokens — the primary cost unit under a subscription. |
| **Est. cost per task** | Mean over (task, trial) of `cost_usd` — Claude Code's client-side estimate at API list price ("est. API-equivalent USD"; there is no bill) (trials with a null cost use `cost_usd_imputed` and are counted in a "null-cost share" column). Also median and p90. Setup cost shown in its own column. |
| **Cost per resolved task** | Σ cost / Σ resolved. |
| **Interventions per trial** | Mean `interventions` (capped at 4 per trial for every arm); share of trials with ≥ 1; also per call. |
| **Wall-clock per trial** | Mean/median `duration_ms`. |
| **Usage-limit sensitivity** (D-028) | pass@1 and the primary paired-bootstrap CI recomputed with each slot's first attempt, a cut (`usage_limited`) attempt counted as unresolved (from `<run>/usage_limited/`); plus per arm: cut count, cut rate, mean elapsed and tokens at the cut. Shown next to the headline. |

## Secondary metrics

| Metric | Definition |
|---|---|
| Build-break rate | share of trials with `build_ok == false` |
| Regression rate | share of trials with `regressions_n > 0` |
| Turns, tool calls | mean per trial |
| Tokens | input/output/cache; `cache_hit_rate` |
| Diff size | insertions + deletions; files |
| Scope creep | share of trials with `scope_creep_files > 0` |
| Touched tests | share with `agent_touched_tests` |
| Convention score | 1–5 LLM grade (Phase 9, calibrated), mean |
| Exit reasons | distribution |
| Interface table | share of trials with `reason == test_compile_failed` on a non-empty diff touching the F2P module(s), per arm and category (D-020); the blind `INTERFACE` label says how many were correct fixes with a different shape |
| Gate verification | `gate_gradle_runs`, `gate_seconds` per trial (S2A, plain-gate) |
| Retries | `harness_error` re-queues, rate-limit retries per arm |
| Per-stage turns | for S2A and its ablations (where the budget went) |

## Breakdowns (every primary metric, as separate tables)

repo · category · source (historical vs authored) · pre/post-cutoff · files_bucket · lang ·
ui · split.

## Pre-registered primary comparison

`docs/PREREG.md` (committed before the freeze) names **one** primary comparison: `s2a` vs
`plain`, pass@1, **all test-split tasks** (n ≈ 28). Its CI is the headline. The pre-registered
contamination-robustness check repeats it on historical post-cutoff test tasks (a smaller n;
its `detectable_delta` is printed next to it). Every other
pair, breakdown and ablation is reported in an "exploratory" section with the same method and
an explicit note that with ten arm pairs and eight breakdowns some 95 % intervals will exclude
zero by chance. Denominators: `harness_error` trials that could not be re-run are excluded and
counted in a "trials lost" line; `agent_error` trials are unresolved.

## Paired bootstrap (`stats.paired_bootstrap`)

```python
def paired_bootstrap(rows, arm_a, arm_b, metric="pass1", n=10_000, seed=0):
    tasks = sorted(set(rows.task_id))
    per_task = {arm: {t: value_for(arm, t) for t in tasks} for arm in (arm_a, arm_b)}  # pass@1 per task
    diffs = []
    rng = numpy.random.default_rng(seed)
    for _ in range(n):
        sample = rng.choice(tasks, size=len(tasks), replace=True)
        diffs.append(mean(per_task[arm_a][t] for t in sample) - mean(per_task[arm_b][t] for t in sample))
    return {"diff": mean(diffs), "ci95": (percentile(diffs, 2.5), percentile(diffs, 97.5)),
            "p_diff_le_0": mean(d <= 0 for d in diffs)}
```

Report for every arm pair: Δ pass@1 with 95 % CI, and Δ cost with 95 % CI. Also a per-task
win/loss/tie table (S2A vs plain, S2A vs Spec Kit).

## Effect-size honesty

`stats.detectable_delta(n_tasks, trials, p_base)` prints the minimum detectable difference at
80 % power (normal approximation on paired proportions). Put the number in the README.

## Tables (`report/tables/*.csv`) and charts (`report/charts/*.png`)

1. `headline.csv`: arm × {pass@1, pass^3, cost/task, setup/repo, interventions, build-break, regressions}
2. `by_<breakdown>.csv` for each breakdown
3. `pairs.csv`: bootstrap deltas
4. `failures.csv`: arm × failure label counts
5. Charts (four): pass@1 bars with CI whiskers; cost vs pass@1 scatter (one point per arm,
   ablations hollow); stacked failure-label bars per arm; per-task heatmap (task rows × arm
   columns, cell = resolved trials/3). All saved with `metadata={"Date": None}` so output is
   byte-reproducible.

`report/summary.md` embeds all of the above and the manifest facts (model, trials, split hash,
date, limits).
