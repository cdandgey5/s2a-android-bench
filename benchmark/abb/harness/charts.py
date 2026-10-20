"""The report's four charts (specs/metrics-and-stats.md): pass@1 bars with 95 % CI whiskers; est. cost vs
pass@1 (one point per arm, ablations hollow); stacked failure labels per arm; per-task heatmap (resolved
trials / trials). PNG + SVG, fixed sizes and DPI, readable in grayscale (hatching), byte-reproducible:
no dates in the metadata, a fixed SVG hash salt, no unseeded randomness."""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from abb.harness import stats  # noqa: E402

plt.rcParams.update({"svg.hashsalt": "abb-report", "font.size": 9, "axes.spines.top": False,
                     "axes.spines.right": False, "figure.dpi": 100})
# one hue per arm family, lighter for variants; hatching carries the ablation in grayscale
COLORS = {"s2a": "#1f4e79", "s2a-nomap": "#5b8bbf", "s2a-noverify": "#5b8bbf", "s2a-norepro": "#5b8bbf",
          "speckit": "#7a4f01", "speckit-sdd": "#c08a2b", "plain": "#555555", "plain-guided": "#8c8c8c",
          "plain-gate": "#b3b3b3"}
HATCH = {"s2a-nomap": "//", "s2a-noverify": "\\\\", "s2a-norepro": "xx", "speckit-sdd": "..", "plain-guided": "--",
         "plain-gate": "++"}
LABEL_COLORS = ["#1f4e79", "#7a4f01", "#2e7d32", "#8e24aa", "#c62828", "#00838f", "#f9a825", "#5d4037", "#455a64",
                "#9e9e9e", "#ad1457", "#283593", "#cfd8dc"]


def _save(fig, out: Path, name: str) -> list[Path]:
    out.mkdir(parents=True, exist_ok=True)
    png, svg = out / f"{name}.png", out / f"{name}.svg"
    fig.savefig(png, dpi=150, metadata={"Software": None})
    fig.savefig(svg, metadata={"Date": None, "Creator": None})
    plt.close(fig)
    return [png, svg]


def _arm_ci(rows: pd.DataFrame, arm: str, n: int) -> tuple[float, float]:
    s = stats.per_task(rows, arm).to_numpy(dtype=float)
    if len(s) == 0:
        return float("nan"), float("nan")
    rng = np.random.default_rng(0)
    m = s[rng.integers(0, len(s), size=(n, len(s)))].mean(axis=1)
    return float(np.percentile(m, 2.5)), float(np.percentile(m, 97.5))


def pass_bars(rows, arms, out, title, n_boot) -> list[Path]:
    fig, ax = plt.subplots(figsize=(6.4, 3.6))
    vals = [stats.pass_at_1(rows, a) for a in arms]
    cis = [_arm_ci(rows, a, n_boot) for a in arms]
    err = np.array([[v - lo for v, (lo, _) in zip(vals, cis)], [hi - v for v, (_, hi) in zip(vals, cis)]])
    ax.bar(range(len(arms)), vals, yerr=err, capsize=3, color=[COLORS.get(a, "#777777") for a in arms],
           hatch=None, edgecolor="black", linewidth=0.6)
    for i, a in enumerate(arms):
        if a in HATCH:
            ax.patches[i].set_hatch(HATCH[a])
    ax.set_xticks(range(len(arms)), arms, rotation=20, ha="right")
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("pass@1 (95 % CI over tasks)")
    ax.set_title(title)
    fig.tight_layout()
    return _save(fig, out, "pass_at_1")


def cost_scatter(rows, arms, out, title) -> list[Path]:
    fig, ax = plt.subplots(figsize=(5.2, 3.8))
    for a in arms:
        x = float(rows[rows.arm == a].cost.mean())
        y = stats.pass_at_1(rows, a)
        hollow = a.startswith("s2a-") or a == "speckit-sdd"
        ax.scatter([x], [y], s=60, facecolors="none" if hollow else COLORS.get(a, "#777777"),
                   edgecolors=COLORS.get(a, "#777777"), linewidths=1.5)
        ax.annotate(a, (x, y), textcoords="offset points", xytext=(5, 4), fontsize=8)
    ax.set_xlabel("est. API-equivalent USD per trial (mean)")
    ax.set_ylabel("pass@1")
    ax.set_ylim(0, 1.05)
    ax.set_xlim(left=0)
    ax.set_title(title)
    fig.tight_layout()
    return _save(fig, out, "cost_vs_pass")


def failure_stack(rows, labels, arms, out, title) -> list[Path]:
    from abb.harness.report import failures

    f = failures(rows, labels)
    names = sorted(f.label.unique()) if len(f) else ["unlabelled"]
    fig, ax = plt.subplots(figsize=(6.4, 3.6))
    bottom = np.zeros(len(arms))
    for i, lab in enumerate(names):
        h = np.array([int(f[(f.arm == a) & (f.label == lab)].trials.sum()) for a in arms], dtype=float)
        ax.bar(range(len(arms)), h, bottom=bottom, label=lab, color=LABEL_COLORS[i % len(LABEL_COLORS)],
               edgecolor="black", linewidth=0.4, hatch=["", "//", "..", "\\\\"][i % 4])
        bottom += h
    ax.set_xticks(range(len(arms)), arms, rotation=20, ha="right")
    ax.set_ylabel("unresolved trials")
    ax.set_title(title)
    ax.legend(fontsize=7, ncol=2, frameon=False)
    fig.tight_layout()
    return _save(fig, out, "failures")


def heatmap(rows, arms, out, title) -> list[Path]:
    tasks = sorted(rows.task_id.unique())
    grid = np.full((len(tasks), len(arms)), np.nan)
    for j, a in enumerate(arms):
        s = stats.per_task(rows, a)
        for i, t in enumerate(tasks):
            if t in s.index:
                grid[i, j] = s[t]
    fig, ax = plt.subplots(figsize=(1.2 + 0.9 * len(arms), 1.0 + 0.28 * len(tasks)))
    im = ax.imshow(grid, vmin=0, vmax=1, cmap="Greys", aspect="auto")
    for i in range(len(tasks)):
        for j in range(len(arms)):
            if not np.isnan(grid[i, j]):
                ax.text(j, i, f"{grid[i, j]:.2f}", ha="center", va="center", fontsize=7,
                        color="white" if grid[i, j] > 0.5 else "black")
    ax.set_xticks(range(len(arms)), arms, rotation=30, ha="right")
    ax.set_yticks(range(len(tasks)), tasks, fontsize=7)
    fig.colorbar(im, ax=ax, label="resolved trials / trials")
    ax.set_title(title)
    fig.tight_layout()
    return _save(fig, out, "per_task")


def render_all(rows: pd.DataFrame, labels: dict, out: Path, *, run_id: str, model: str, k: int,
               n_boot: int = 10_000) -> list[Path]:
    from abb.harness.report import arm_order

    arms = arm_order(rows.arm)
    t = f"{run_id} · {model}"
    files: list[Path] = []
    files += pass_bars(rows, arms, out, f"pass@1 — {t}", n_boot)
    files += cost_scatter(rows, arms, out, f"cost vs pass@1 — {t}")
    files += failure_stack(rows, labels, arms, out, f"unresolved trials by label — {t}")
    files += heatmap(rows, arms, out, f"per task (k = {k}) — {t}")
    return files
