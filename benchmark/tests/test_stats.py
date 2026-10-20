"""Known-answer tests for abb/harness/stats.py (phases/phase-9-analysis.md step 2)."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from abb.harness import stats


def toy() -> pd.DataFrame:
    """4 tasks x 3 trials, two arms. By hand:
    s2a   t1 1,1,1  t2 1,0,1  t3 0,0,0  t4 1,1,0 -> pass@1 = (1 + 2/3 + 0 + 2/3)/4 = 7/12; pass^3 = 1/4; any = 3/4
    plain t1 1,1,0  t2 0,0,0  t3 0,0,0  t4 1,0,0 -> pass@1 = (2/3 + 0 + 0 + 1/3)/4 = 1/4;  pass^3 = 0;   any = 2/4"""
    grid = {"s2a": {"t1": [1, 1, 1], "t2": [1, 0, 1], "t3": [0, 0, 0], "t4": [1, 1, 0]},
            "plain": {"t1": [1, 1, 0], "t2": [0, 0, 0], "t3": [0, 0, 0], "t4": [1, 0, 0]}}
    rows = [{"arm": a, "task_id": t, "trial": k + 1, "resolved": bool(v), "cost": (1.0 if a == "s2a" else 0.25)}
            for a, ts in grid.items() for t, vs in ts.items() for k, v in enumerate(vs)]
    return pd.DataFrame(rows)


def test_pass_metrics_by_hand() -> None:
    r = toy()
    assert stats.pass_at_1(r, "s2a") == pytest.approx(7 / 12)
    assert stats.pass_at_1(r, "plain") == pytest.approx(1 / 4)
    assert stats.pass_hat_k(r, "s2a", 3) == pytest.approx(1 / 4) and stats.pass_hat_k(r, "plain", 3) == 0
    assert stats.pass_at_any(r, "s2a") == pytest.approx(3 / 4) and stats.pass_at_any(r, "plain") == pytest.approx(1 / 2)
    assert stats.pass_hat_k(r, "s2a", 4) != stats.pass_hat_k(r, "s2a", 4)   # nan: no task has 4 trials


def test_paired_bootstrap_is_seeded_and_centred_on_the_paired_mean() -> None:
    r = toy()
    a = stats.paired_bootstrap(r, "s2a", "plain", n=5000, seed=7)
    b = stats.paired_bootstrap(r, "s2a", "plain", n=5000, seed=7)
    assert a == b                                                   # same seed -> same CI
    assert a["diff"] == pytest.approx(7 / 12 - 1 / 4)               # per-task diffs 1/3, 2/3, 0, 1/3
    lo, hi = a["ci95"]
    assert 0 <= lo <= a["diff"] <= hi <= 2 / 3                       # resampling 4 diffs in [0, 2/3]
    assert a["p_diff_le_0"] < 0.05 and a["n_tasks"] == 4
    c = stats.paired_bootstrap(r, "s2a", "plain", metric="cost", n=1000)
    assert c["diff"] == pytest.approx(0.75) and c["ci95"] == pytest.approx((0.75, 0.75))


def test_win_loss_tie() -> None:
    assert stats.win_loss_tie(toy(), "s2a", "plain") == {"win": 3, "loss": 0, "tie": 1, "tasks": 4}


def test_detectable_delta_matches_a_simulation() -> None:
    dd = stats.detectable_delta(40, 3, 0.4)
    assert 0.15 < dd < 0.2
    # simulate: true Δ = dd, paired per-task differences, z-test at alpha 0.05 -> power ≈ 0.8
    rng = np.random.default_rng(0)
    hits, sims = 0, 2000
    for _ in range(sims):
        a = rng.binomial(3, 0.4 + dd, size=40) / 3
        b = rng.binomial(3, 0.4, size=40) / 3
        d = a - b
        z = d.mean() / (d.std(ddof=1) / math.sqrt(40))
        hits += z > 1.96
    assert 0.7 < hits / sims < 0.9


def test_describe() -> None:
    d = stats.describe(pd.Series([1.0, 2.0, 3.0, None, 10.0]))
    assert d["mean"] == pytest.approx(4.0) and d["median"] == pytest.approx(2.5)
