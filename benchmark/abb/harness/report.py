"""`abb report <run_id> [--out DIR]` (phases/phase-9-analysis.md, specs/metrics-and-stats.md): every number,
table and chart of the write-up, regenerated from `<results>/<run_id>/` alone (AGENTS.md rule 3).

Output: `summary.md`, `tables/*.csv`, `charts/*.png|svg`. Deterministic: sorted rows, fixed float formats,
seeded bootstrap, no wall clock (the only date is `manifest.created_at`), so two reports of one run are
byte-identical (`abb report-diff`). Costs are "est. API-equivalent USD" (no bill under the subscription).
The unit of analysis is the task: trials are averaged within a task; CIs are paired bootstraps over tasks.
"""
from __future__ import annotations

import itertools
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

from abb import paths
from abb.harness import stats

BREAKDOWNS = ["repo", "category", "source", "post_cutoff", "files_bucket", "lang", "ui", "split"]
ORDER = ["s2a", "s2a-nomap", "s2a-noverify", "s2a-norepro", "speckit", "speckit-sdd", "plain-guided", "plain-gate", "plain"]
LOST = "harness_error"


def _load(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def arm_order(arms) -> list[str]:
    arms = list(dict.fromkeys(arms))
    return [a for a in ORDER if a in arms] + sorted(a for a in arms if a not in ORDER)


def _fmt(x, nd: int = 4) -> str:
    if x is None or (isinstance(x, float) and (np.isnan(x) or np.isinf(x))):
        return ""
    if isinstance(x, (bool, np.bool_)):
        return "true" if x else "false"
    if isinstance(x, (int, np.integer)):
        return str(int(x))
    if isinstance(x, (float, np.floating)):
        return f"{float(x):.{nd}f}"
    return str(x)


def write_csv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [",".join(df.columns)]
    for _, r in df.iterrows():
        cells = []
        for v in r.tolist():
            s = _fmt(v)
            cells.append(f'"{s}"' if ("," in s or '"' in s) else s)
        lines.append(",".join(cells))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def md_table(df: pd.DataFrame) -> list[str]:
    if df.empty:
        return ["(none)"]
    out = ["| " + " | ".join(df.columns) + " |", "|" + "---|" * len(df.columns)]
    for _, r in df.iterrows():
        out.append("| " + " | ".join(_fmt(v) for v in r.tolist()) + " |")
    return out


# ---------------------------------------------------------------------------- rows
def _trial_row(rec: Path, cut: bool = False) -> dict:
    run, g, m = _load(rec / "run.json"), _load(rec / "grade.json"), _load(rec / "metrics.json")
    cost = run.get("cost_usd") if run.get("cost_usd") is not None else run.get("cost_usd_imputed")
    arm = run.get("arm") or rec.parent.parent.name
    task = run.get("task_id") or rec.parent.name
    trial = int(run.get("trial") or re.sub(r"\D.*", "", rec.name[1:]) or 0)
    stage_turns: dict[str, int] = {}
    for c in run.get("calls") or []:
        stage = re.split(r"[-.]", c.get("name") or "")[0]
        stage_turns[stage] = stage_turns.get(stage, 0) + int(c.get("num_turns") or 0)
    row = {"arm": arm, "task_id": task, "trial": trial, "cut": cut,
           "resolved": bool(g.get("resolved")) if not cut else False, "reason": g.get("reason"),
           "exit_reason": run.get("exit_reason"), "cost": float(cost or 0.0), "null_cost": run.get("cost_usd") is None,
           "turns": int(run.get("num_turns") or 0), "tool_calls": int(run.get("tool_calls") or 0),
           "interventions": int(run.get("interventions") or 0), "duration_s": (run.get("duration_ms") or 0) / 1000,
           "gate_gradle_runs": int(run.get("gate_gradle_runs") or 0), "gate_seconds": float(run.get("gate_seconds") or 0),
           "rate_limit_retries": int(m.get("rate_limit_retries") or 0), "other_retries": int(m.get("other_retries") or 0),
           "build_ok": m.get("build_ok"), "regressions_n": int(m.get("regressions_n") or 0),
           "scope_creep_files": int(m.get("scope_creep_files") or 0), "agent_touched_tests": m.get("agent_touched_tests"),
           "diff_lines": int(m.get("diff_insertions") or 0) + int(m.get("diff_deletions") or 0),
           "diff_files": int(m.get("diff_files") or 0), "input_tokens": int(m.get("input_tokens") or 0),
           "output_tokens": int(m.get("output_tokens") or 0), "cache_read_tokens": int(m.get("cache_read_tokens") or 0),
           "cache_write_tokens": int(m.get("cache_write_tokens") or 0), "cache_hit_rate": m.get("cache_hit_rate"),
           "agent_gradle_ok": int(m.get("agent_gradle_ok") or 0), "agent_env_errors": int(m.get("agent_env_errors") or 0),
           "stage_turns": stage_turns}
    for b in BREAKDOWNS:
        row[b] = m.get(b, m.get(f"tags.{b}"))
    return row


def load_rows(run_id: str, root: Path | None = None) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, list[str]]:
    """(trials, setups, cut attempts, missing trial ids). Setup rows never mix with trial rows."""
    root = root or paths.results_dir() / run_id
    trials = [_trial_row(rj.parent) for rj in sorted(root.glob("*/*/t*/run.json"))
              if rj.parts[-4] not in ("usage_limited", "setup", "salvaged")]
    cuts = [_trial_row(rj.parent, cut=True) for rj in sorted(root.glob("usage_limited/*/*/t*/run.json"))]
    setups = []
    for sp in sorted(root.glob("setup/*/*/run.json")):
        sd = _load(sp)
        usd = sd.get("cost_usd") if sd.get("cost_usd") is not None else sd.get("cost_usd_imputed")
        setups.append({"setup_kind": sd.get("setup_kind"), "repo": sd.get("repo"), "cost_this_run": float(usd or 0.0),
                       "produced_cost": float(sd.get("produced_cost_usd") if sd.get("reused_from") else (usd or 0.0)),
                       "reused_from": sd.get("reused_from") or "", "turns": int(sd.get("num_turns") or 0),
                       "is_setup": True})
    man = _load(root / "manifest.json")
    have = {(r["arm"], r["task_id"], r["trial"]) for r in trials}
    missing = [f"{a}/{t}/t{k}" for k in range(1, int(man.get("trials") or 1) + 1) for t in man.get("task_ids") or []
               for a in man.get("arms") or [] if (a, t, k) not in have]
    cols = ["arm", "task_id", "trial", "resolved", "cost"]
    return (pd.DataFrame(trials) if trials else pd.DataFrame(columns=cols)), pd.DataFrame(setups), \
        (pd.DataFrame(cuts) if cuts else pd.DataFrame(columns=cols)), missing


def counted(trials: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(rows in the denominators, lost trials): harness_error trials that could not be re-run are excluded."""
    if trials.empty:
        return trials, trials
    lost = trials.exit_reason == LOST
    return trials[~lost].copy(), trials[lost].copy()


def labels_for(root: Path) -> dict:
    return (_load(root / "labels.json").get("items") or {})


# ---------------------------------------------------------------------------- tables
def headline(rows: pd.DataFrame, setups: pd.DataFrame, k: int) -> pd.DataFrame:
    out = []
    for arm in arm_order(rows.arm):
        r = rows[rows.arm == arm]
        c = stats.describe(r.cost)
        res = int(r.resolved.sum())
        out.append({"arm": arm, "tasks": r.task_id.nunique(), "trials": len(r), "pass@1": stats.pass_at_1(rows, arm),
                    f"pass^{k}": stats.pass_hat_k(rows, arm, k), "pass@any": stats.pass_at_any(rows, arm),
                    "cost_mean": c["mean"], "cost_median": c["median"], "cost_p90": c["p90"],
                    "cost_per_resolved": float(r.cost.sum() / res) if res else float("nan"),
                    "null_cost_share": float(r.null_cost.mean()), "interventions_mean": float(r.interventions.mean()),
                    "interventions_any": float((r.interventions > 0).mean()),
                    "build_break_rate": float((r.build_ok == False).mean()),   # noqa: E712 - None is "unknown"
                    "regression_rate": float((r.regressions_n > 0).mean()), "duration_mean_s": float(r.duration_s.mean()),
                    "turns_mean": float(r.turns.mean()),
                    "tokens_out_mean": float(r.output_tokens.mean()),
                    "tokens_in_mean": float((r.input_tokens + r.cache_read_tokens + r.cache_write_tokens).mean())})
    return pd.DataFrame(out)


def by_breakdown(rows: pd.DataFrame, col: str) -> pd.DataFrame:
    out = []
    for val in sorted(rows[col].dropna().astype(str).unique()):
        sub = rows[rows[col].astype(str) == val]
        for arm in arm_order(sub.arm):
            r = sub[sub.arm == arm]
            out.append({col: val, "arm": arm, "tasks": r.task_id.nunique(), "trials": len(r),
                        "pass@1": stats.pass_at_1(sub, arm), "cost_mean": float(r.cost.mean())})
    return pd.DataFrame(out)


def pairs(rows: pd.DataFrame, n: int = 10_000) -> pd.DataFrame:
    out = []
    for a, b in itertools.combinations(arm_order(rows.arm), 2):
        p, c, w = stats.paired_bootstrap(rows, a, b, n=n), stats.paired_bootstrap(rows, a, b, "cost", n=n), \
            stats.win_loss_tie(rows, a, b)
        out.append({"arm_a": a, "arm_b": b, "tasks": p["n_tasks"], "d_pass@1": p["diff"], "d_pass@1_lo": p["ci95"][0],
                    "d_pass@1_hi": p["ci95"][1], "p_d_le_0": p["p_diff_le_0"], "d_cost": c["diff"],
                    "d_cost_lo": c["ci95"][0], "d_cost_hi": c["ci95"][1], "win": w["win"], "loss": w["loss"],
                    "tie": w["tie"]})
    return pd.DataFrame(out)


def failures(rows: pd.DataFrame, labels: dict) -> pd.DataFrame:
    lab = {(v.get("arm"), v.get("task"), int(v.get("trial") or 0)): (v.get("primary") or "unlabelled")
           for v in labels.values()}
    out = []
    for arm in arm_order(rows.arm):
        r = rows[(rows.arm == arm) & (~rows.resolved)]
        counts: dict[str, int] = {}
        for _, x in r.iterrows():
            key = lab.get((arm, x.task_id, int(x.trial)), "unlabelled")
            counts[key] = counts.get(key, 0) + 1
        for key in sorted(counts):
            out.append({"arm": arm, "label": key, "trials": counts[key]})
    return pd.DataFrame(out, columns=["arm", "label", "trials"])


def setup_table(setups: pd.DataFrame, rows: pd.DataFrame) -> pd.DataFrame:
    if setups.empty:
        return pd.DataFrame(columns=["setup_kind", "repo", "produced_cost", "cost_this_run", "reused_from",
                                     "tasks_in_run", "amortised_per_task"])
    out = []
    for _, s in setups.sort_values(["setup_kind", "repo"]).iterrows():
        n = rows[rows.get("repo", pd.Series(dtype=str)) == s.repo].task_id.nunique() if "repo" in rows else 0
        out.append({"setup_kind": s.setup_kind, "repo": s.repo, "produced_cost": s.produced_cost,
                    "cost_this_run": s.cost_this_run, "reused_from": s.reused_from, "tasks_in_run": n,
                    "amortised_per_task": (s.produced_cost / n) if n else float("nan")})
    return pd.DataFrame(out)


def controls(rows: pd.DataFrame, n: int = 10_000) -> pd.DataFrame:
    """s2a against its controls: does the workflow in prose (plain-guided) or one harness test run (plain-gate)
    explain the difference?"""
    out = []
    if "s2a" not in set(rows.arm):
        return pd.DataFrame(columns=["arm", "pass@1", "d_vs_s2a", "lo", "hi"])
    for arm in [a for a in ["plain-guided", "plain-gate", "plain"] if a in set(rows.arm)]:
        p = stats.paired_bootstrap(rows, "s2a", arm, n=n)
        out.append({"arm": arm, "pass@1": stats.pass_at_1(rows, arm), "d_vs_s2a": p["diff"], "lo": p["ci95"][0],
                    "hi": p["ci95"][1]})
    return pd.DataFrame(out)


def budget(rows: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    out, stages = [], []
    for arm in arm_order(rows.arm):
        r = rows[rows.arm == arm]
        ex = r.exit_reason.value_counts().sort_index()
        out.append({"arm": arm, "turns_mean": float(r.turns.mean()), "tool_calls_mean": float(r.tool_calls.mean()),
                    "gate_runs_mean": float(r.gate_gradle_runs.mean()), "gate_seconds_mean": float(r.gate_seconds.mean()),
                    "rate_limit_retries": int(r.rate_limit_retries.sum()), "other_retries": int(r.other_retries.sum()),
                    "null_cost_share": float(r.null_cost.mean()),
                    "exit_reasons": "; ".join(f"{k} {v}" for k, v in ex.items())})
        if arm.startswith("s2a"):
            tot: dict[str, int] = {}
            for st in r.stage_turns:
                for k, v in st.items():
                    tot[k] = tot.get(k, 0) + v
            for k in sorted(tot):
                stages.append({"arm": arm, "stage": k, "turns_mean": tot[k] / max(1, len(r))})
    return pd.DataFrame(out), pd.DataFrame(stages, columns=["arm", "stage", "turns_mean"])


def interface(rows: pd.DataFrame) -> pd.DataFrame:
    out = []
    for arm in arm_order(rows.arm):
        for cat in sorted(rows[rows.arm == arm].category.dropna().astype(str).unique()) if "category" in rows else []:
            r = rows[(rows.arm == arm) & (rows.category.astype(str) == cat)]
            tc = r[(r.reason == "test_compile_failed") & (r.diff_lines > 0)]
            out.append({"arm": arm, "category": cat, "trials": len(r), "test_compile_failed": len(tc),
                        "share": len(tc) / len(r) if len(r) else float("nan")})
    return pd.DataFrame(out, columns=["arm", "category", "trials", "test_compile_failed", "share"])


def usage_limit_sensitivity(rows: pd.DataFrame, cuts: pd.DataFrame) -> pd.DataFrame:
    """D-028: pass@1 with each slot's first attempt — a cut attempt counts as unresolved."""
    out = []
    for arm in arm_order(rows.arm):
        c = cuts[cuts.arm == arm] if not cuts.empty else cuts
        first = rows[rows.arm == arm].copy()
        if len(c):
            for _, x in c.iterrows():
                m = (first.task_id == x.task_id) & (first.trial == x.trial)
                first.loc[m, "resolved"] = False
        out.append({"arm": arm, "pass@1": stats.pass_at_1(rows, arm),
                    "pass@1_first_attempt": float(first.groupby("task_id").resolved.mean().mean()) if len(first) else float("nan"),
                    "cuts": len(c), "cut_rate": len(c) / max(1, len(rows[rows.arm == arm]) + len(c)),
                    "cut_mean_s": float(c.duration_s.mean()) if len(c) else float("nan"),
                    "cut_mean_tokens_out": float(c.output_tokens.mean()) if len(c) else float("nan")})
    return pd.DataFrame(out)


# ---------------------------------------------------------------------------- summary
def primary_pair(man: dict, arms: list[str]) -> tuple[str, str, bool]:
    """(arm_a, arm_b, pre-registered?) — PREREG names s2a vs plain; without a PREREG hash it is exploratory."""
    a, b = ("s2a", "plain") if {"s2a", "plain"} <= set(arms) else (tuple(arm_order(arms)[:2]) + ("",))[:2]
    return a, b, bool(man.get("prereg_sha256"))


def render(run_id: str, out: Path | None = None, n_boot: int = 10_000) -> str:
    from abb.harness import charts

    root = paths.results_dir() / run_id
    man, aud = _load(root / "manifest.json"), _load(root / "audit.json")
    trials, setups, cuts, missing = load_rows(run_id, root)
    rows, lost = counted(trials)
    out = Path(out) if out else root / "report"
    (out / "tables").mkdir(parents=True, exist_ok=True)
    k = int(man.get("trials") or (int(rows.trial.max()) if len(rows) else 1))
    arms = arm_order(rows.arm) if len(rows) else []
    audit_ok = bool(aud.get("ok")) and man.get("audit_ok") is not False
    labels = labels_for(root)
    tbl = {"headline": headline(rows, setups, k) if len(rows) else pd.DataFrame(),
           "pairs": pairs(rows, n_boot) if len(arms) > 1 else pd.DataFrame(),
           "failures": failures(rows, labels) if len(rows) else pd.DataFrame(columns=["arm", "label", "trials"]),
           "setup": setup_table(setups, rows), "controls": controls(rows, n_boot) if len(rows) else pd.DataFrame(),
           "interface": interface(rows) if len(rows) else pd.DataFrame(),
           "usage_limit_sensitivity": usage_limit_sensitivity(rows, cuts) if len(rows) else pd.DataFrame()}
    tbl["budget"], tbl["stage_turns"] = budget(rows) if len(rows) else (pd.DataFrame(), pd.DataFrame())
    for b in BREAKDOWNS:
        if b in rows and rows[b].notna().any():
            tbl[f"by_{b}"] = by_breakdown(rows, b)
    for name, df in tbl.items():
        write_csv(df, out / "tables" / f"{name}.csv")
    chart_files = charts.render_all(rows, labels, out / "charts", run_id=run_id,
                                    model=(man.get("limits") or {}).get("model", ""), k=k, n_boot=n_boot) if len(rows) else []

    a, b, prereg = primary_pair(man, arms)
    L = [f"# Run {run_id}", "",
         f"- Created: {man.get('created_at')} · label `{man.get('label')}` · model {(man.get('limits') or {}).get('model')} "
         f"· Claude Code {man.get('agent_version')} · profile {man.get('profile')}",
         f"- Arms: {', '.join(man.get('arms') or [])} · tasks: {man.get('task_set')} ({len(man.get('task_ids') or [])}) · "
         f"trials per task: {k} · parallel: {man.get('parallel') or 1} · sandbox: {man.get('sandbox_mode')}",
         f"- Split sha256: {man.get('split_sha256')} · task set sha256: {man.get('task_set_sha256')} · "
         f"s2a {man.get('s2a_git_sha')} · Spec Kit {man.get('speckit_version')} · harness {man.get('harness_git_sha')}",
         f"- Limits: {json.dumps(man.get('limits'), sort_keys=True)}",
         f"- Plan: {man.get('plan')} ({man.get('auth_mode')}) · aborted: {man.get('aborted_reason')} · scheduler pauses: "
         f"{man.get('scheduler_pauses', 0)} · usage-limited attempts: {len(cuts)}", ""]
    if man.get("invalid"):
        L += [f"> **INVALID run ({man['invalid'].get('decision')}):** {man['invalid'].get('reason')}. Its numbers are kept "
              "for the cost log only and enter no comparison.", ""]
    if missing:
        L += [f"> **Incomplete:** {len(missing)} trial(s) missing: {', '.join(missing[:20])}"
              + (" …" if len(missing) > 20 else ""), ""]
    if not audit_ok:
        L += ["> **Withheld: `abb audit` does not pass for this run** (the transcripts do not reproduce run.json, or a "
              "token leaked, or the audit was not run). Headline numbers are not printed; fix and re-run `abb audit`.", ""]
    L += ["Costs are **est. API-equivalent USD** (Claude Code's client-side estimate at list price; there is no bill under "
          "the subscription). The unit of analysis is the task: per-task pass@1 is the share of its trials resolved; "
          "confidence intervals are 95 % paired bootstraps over tasks (10,000 resamples, seed 0).", ""]
    if audit_ok and len(rows):
        L += ["## Headline", ""] + md_table(tbl["headline"][["arm", "tasks", "trials", "pass@1", f"pass^{k}", "pass@any",
                                                           "cost_mean", "cost_per_resolved", "interventions_mean",
                                                           "build_break_rate", "regression_rate"]]) + [""]
        if a and b and len(tbl["pairs"]):
            pr = tbl["pairs"]
            row = pr[((pr.arm_a == a) & (pr.arm_b == b))]
            if len(row):
                r0 = row.iloc[0]
                # pooled pass@1 of both arms, kept off 0 and 1 (a perfect arm would make every Δ "detectable")
                p_pool = min(0.9, max(0.1, (stats.pass_at_1(rows, a) + stats.pass_at_1(rows, b)) / 2))
                dd = stats.detectable_delta(int(r0.tasks), k, p_pool)
                L += [f"## {'Pre-registered primary comparison' if prereg else 'Primary comparison (exploratory: no PREREG for this run)'}",
                      "", f"**{a} vs {b}, pass@1:** Δ = {_fmt(r0['d_pass@1'], 3)} (95 % CI {_fmt(r0['d_pass@1_lo'], 3)} to "
                      f"{_fmt(r0['d_pass@1_hi'], 3)}) over {int(r0.tasks)} tasks; Δ est. USD per trial "
                      f"{_fmt(r0.d_cost, 3)} ({_fmt(r0.d_cost_lo, 3)} to {_fmt(r0.d_cost_hi, 3)}); per task "
                      f"{int(r0.win)} better / {int(r0.loss)} worse / {int(r0.tie)} equal. Detectable Δ at 80 % power with "
                      f"{int(r0.tasks)} tasks × {k} trials (pooled p = {_fmt(p_pool, 2)}, clipped to 0.1–0.9): "
                      f"{_fmt(dd, 3)}.", ""]
        L += ["## All arm pairs (exploratory)", "",
              "With many pairs and breakdowns, some 95 % intervals will exclude zero by chance.", ""] + md_table(
            tbl["pairs"]) + [""]
        if len(tbl["controls"]):
            L += ["## Controls: s2a against plain-guided and plain-gate", ""] + md_table(tbl["controls"]) + [""]
        L += ["## Usage-limit sensitivity (D-028)", ""] + md_table(tbl["usage_limit_sensitivity"]) + [""]
        for bname in BREAKDOWNS:
            if f"by_{bname}" in tbl:
                L += [f"### By {bname}", ""] + md_table(tbl[f"by_{bname}"]) + [""]
        cal = (_load(root / "labels.json").get("calibration") or {})
        L += ["## Failures", "", f"Labeller: {cal.get('status', 'agreement: not measured (uncalibrated)')}", ""] + md_table(
            tbl["failures"]) + [""]
        L += ["## Budget and verification", ""] + md_table(tbl["budget"]) + [""]
        if len(tbl["stage_turns"]):
            L += ["Per-stage turns (S2A arms, mean per trial):", ""] + md_table(tbl["stage_turns"]) + [""]
        L += ["## Interface failures (`test_compile_failed` on a non-empty diff)", ""] + md_table(tbl["interface"]) + [""]
    L += ["## One-time setup", "", "Reported separately from per-task numbers; amortised over the run's tasks of that repo.",
          ""] + md_table(tbl["setup"]) + [""]
    L += ["## Caveats", "",
          f"- Sample: {rows.task_id.nunique() if len(rows) else 0} tasks × {k} trials; detectable Δ pass@1 at 80 % power is "
          "printed with the primary comparison. Interventions are the harness's nudges (≤ 4 per trial, every arm).",
          f"- Trials lost (harness_error, excluded from denominators): {len(lost)}"
          + (f" ({', '.join(f'{r.arm}/{r.task_id}/t{r.trial}' for r in lost.itertuples())})" if len(lost) else ""),
          "- Environment check (D-043): " + (", ".join(
              f"{r.arm}/{r.task_id}/t{r.trial}" for r in rows.itertuples()
              if r.agent_env_errors and not r.agent_gradle_ok) or "no trial whose Gradle never succeeded with "
              "offline-resolution or cache-access errors") + (" — the agent's Gradle never succeeded and hit environment "
              "errors there; check them before using this run" if len(rows) and ((rows.agent_env_errors > 0) &
                                                                                 (rows.agent_gradle_ok == 0)).any() else ""),
          f"- Audit: {'PASS' if audit_ok else 'FAIL or not run'}"
          + (f" (token leaks: {aud.get('token_leak_files')})" if aud.get("token_leak_files") else ""), ""]
    if chart_files:
        L += ["## Charts", ""] + [f"![{p.stem}](charts/{p.name})" for p in chart_files if p.suffix == ".png"] + [""]
    if len(trials):
        L += ["## Appendix: every trial", "", "| arm | task | trial | resolved | reason | exit | turns | est. USD | s |",
              "|---|---|---|---|---|---|---|---|---|"]
        for r in trials.sort_values(["arm", "task_id", "trial"]).itertuples():
            L.append(f"| {r.arm} | {r.task_id} | {r.trial} | {_fmt(r.resolved)} | {r.reason or ''} | {r.exit_reason} | "
                     f"{r.turns} | {_fmt(r.cost)} | {_fmt(r.duration_s, 1)} |")
    text = "\n".join(L) + "\n"
    (out / "summary.md").write_text(text, encoding="utf-8", newline="\n")
    return text


def diff_dirs(a: Path, b: Path) -> list[str]:
    """Files that differ between two report directories (empty: identical)."""
    fa = {p.relative_to(a).as_posix(): p for p in a.rglob("*") if p.is_file()}
    fb = {p.relative_to(b).as_posix(): p for p in b.rglob("*") if p.is_file()}
    out = sorted(set(fa) ^ set(fb))
    out += sorted(k for k in set(fa) & set(fb) if fa[k].read_bytes() != fb[k].read_bytes())
    return out
