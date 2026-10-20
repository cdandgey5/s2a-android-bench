"""Statistics for the report (specs/metrics-and-stats.md). The unit of analysis is the task: trials are
averaged within a task, and confidence intervals come from a paired bootstrap over tasks (never over
trials as if they were independent).

Input everywhere: a pandas DataFrame with one row per (arm, task_id, trial) and at least `resolved`
(bool) and, for cost, `cost` (est. USD; the caller fills nulls with the imputed estimate).
"""
from __future__ import annotations

import math
from statistics import NormalDist

import numpy as np
import pandas as pd


def per_task(rows: pd.DataFrame, arm: str, value: str = "resolved") -> pd.Series:
    """task_id -> mean of `value` over that task's trials, for one arm."""
    r = rows[rows.arm == arm]
    return r.groupby("task_id")[value].mean().astype(float)


def pass_at_1(rows: pd.DataFrame, arm: str) -> float:
    s = per_task(rows, arm)
    return float(s.mean()) if len(s) else float("nan")


def pass_hat_k(rows: pd.DataFrame, arm: str, k: int | None = None) -> float:
    """pass^k: share of tasks where every one of k trials resolved (k defaults to the trials each task has)."""
    r = rows[rows.arm == arm]
    if r.empty:
        return float("nan")
    vals = []
    for _, g in r.groupby("task_id"):
        g = g.sort_values("trial")
        if k is not None and len(g) < k:
            continue
        take = g if k is None else g.head(k)
        vals.append(float(take.resolved.all()))
    return float(np.mean(vals)) if vals else float("nan")


def pass_at_any(rows: pd.DataFrame, arm: str) -> float:
    r = rows[rows.arm == arm]
    return float(r.groupby("task_id").resolved.any().mean()) if len(r) else float("nan")


def paired_bootstrap(rows: pd.DataFrame, arm_a: str, arm_b: str, metric: str = "resolved", n: int = 10_000,
                     seed: int = 0) -> dict:
    """Δ = mean over resampled tasks of (arm_a per-task mean − arm_b per-task mean), tasks both arms ran.
    `metric` is a column averaged within each task (`resolved` -> Δ pass@1, `cost` -> Δ est. USD per trial)."""
    a, b = per_task(rows, arm_a, metric), per_task(rows, arm_b, metric)
    tasks = sorted(set(a.index) & set(b.index))
    if not tasks:
        return {"arm_a": arm_a, "arm_b": arm_b, "metric": metric, "n_tasks": 0, "diff": float("nan"),
                "ci95": (float("nan"), float("nan")), "p_diff_le_0": float("nan")}
    d = np.array([a[t] - b[t] for t in tasks], dtype=float)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(tasks), size=(n, len(tasks)))
    diffs = d[idx].mean(axis=1)
    return {"arm_a": arm_a, "arm_b": arm_b, "metric": metric, "n_tasks": len(tasks), "diff": float(d.mean()),
            "boot_mean": float(diffs.mean()),
            "ci95": (float(np.percentile(diffs, 2.5)), float(np.percentile(diffs, 97.5))),
            "p_diff_le_0": float((diffs <= 0).mean())}


def win_loss_tie(rows: pd.DataFrame, arm_a: str, arm_b: str) -> dict:
    """Per task, by pass@1: arm_a better / worse / equal."""
    a, b = per_task(rows, arm_a), per_task(rows, arm_b)
    tasks = sorted(set(a.index) & set(b.index))
    w = sum(1 for t in tasks if a[t] > b[t])
    lo = sum(1 for t in tasks if a[t] < b[t])
    return {"win": w, "loss": lo, "tie": len(tasks) - w - lo, "tasks": len(tasks)}


def detectable_delta(n_tasks: int, trials: int, p_base: float, alpha: float = 0.05, power: float = 0.8) -> float:
    """Smallest Δ pass@1 a paired comparison over n_tasks detects with the given power (normal approximation).
    Each arm's per-task pass@1 is a mean of `trials` Bernoulli(p) draws (variance p(1-p)/trials); the paired
    difference of two independent arms has twice that variance; the task effect cancels in the pairing."""
    if n_tasks <= 0 or trials <= 0:
        return float("nan")
    sd = math.sqrt(2 * p_base * (1 - p_base) / trials)
    z = NormalDist().inv_cdf(1 - alpha / 2) + NormalDist().inv_cdf(power)
    return z * sd / math.sqrt(n_tasks)


def describe(values: pd.Series) -> dict:
    v = pd.to_numeric(values, errors="coerce").dropna()
    if v.empty:
        return {"mean": float("nan"), "median": float("nan"), "p90": float("nan")}
    return {"mean": float(v.mean()), "median": float(v.median()), "p90": float(np.percentile(v, 90))}
