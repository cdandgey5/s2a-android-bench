"""docs/RUNS.md rows for one run, from <results>/<run_id>/ only (AGENTS.md rule 3: never fabricated).

    .venv\\Scripts\\python.exe scripts\\runs_rows.py <run_id> [--note "text appended to every row"]

One row per trial (time = trial start UTC, tokens summed over its calls, est. USD = cost_usd or the
imputed estimate, five-hour / seven-day = the `rate_limit_event` utilisation at the first and last
event of the trial), one row per one-time setup, and a bold total row.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from abb import paths
from abb.harness import transcript as tx


def windows(rec: Path) -> tuple[str, str]:
    evs = []
    for f in sorted((rec / "transcript").glob("*.jsonl"), key=lambda p: p.stat().st_mtime):
        evs += tx.parse_file(f).rate_limit_events
    w = [((e.get("rate_limit_info") or {}).get("unifiedWindows") or {}) for e in evs]
    w = [x for x in w if x]
    if not w:
        return "—", "—"
    five = f"{w[0].get('five_hour', {}).get('utilization')} → {w[-1].get('five_hour', {}).get('utilization')}"
    return five, str(w[-1].get("seven_day", {}).get("utilization"))


def tokens(calls: list[dict]) -> tuple[int, int, int, int, float]:
    t = [sum(int(c.get(k) or 0) for c in calls) for k in ("input_tokens", "output_tokens", "cache_read_tokens",
                                                           "cache_write_tokens")]
    usd = sum((c["cost_usd"] if c.get("cost_usd") is not None else (c.get("cost_usd_imputed") or 0.0)) for c in calls)
    return t[0], t[1], t[2], t[3], usd


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("run_id")
    ap.add_argument("--note", default="")
    a = ap.parse_args()
    root = paths.results_dir() / a.run_id
    model = json.loads((root / "manifest.json").read_text(encoding="utf-8")).get("limits", {}).get("model", "")
    rows, tot, n, ok, secs = [], [0, 0, 0, 0, 0.0], 0, 0, 0.0
    for rj in sorted(root.glob("setup/*/*/run.json")):
        d = json.loads(rj.read_text(encoding="utf-8"))
        if d.get("reused_from"):
            continue
        i, o, cr, cw, usd = tokens(d.get("calls") or [])
        five, seven = windows(rj.parent)
        rows.append(f"| {str(d.get('recorded_at', ''))[11:16]} | `{a.run_id}` setup {d['setup_kind']}/{d['repo']} | {model} "
                    f"| {d.get('exit_subtype')}, {d.get('num_turns')} turns | {i:,} | {o:,} | {cr:,} | {cw:,} | {usd:.4f} | 0 "
                    f"| one-time setup (reported separately); five-hour {five}, seven-day {seven}"
                    + (f"; {a.note}" if a.note else "") + " |")
        for k, v in enumerate((i, o, cr, cw, usd)):
            tot[k] += v
    for rj in sorted(root.glob("*/*/t*/run.json")):
        if rj.parts[-4] in ("setup", "usage_limited"):
            continue
        d = json.loads(rj.read_text(encoding="utf-8"))
        rec = rj.parent
        g = json.loads((rec / "grade.json").read_text(encoding="utf-8")) if (rec / "grade.json").exists() else {}
        i, o, cr, cw, usd = tokens(d.get("calls") or [])
        five, seven = windows(rec)
        dur = (d.get("duration_ms") or 0) / 1000
        n += 1
        ok += bool(g.get("resolved"))
        secs += dur
        rows.append(f"| {str(d.get('started_at', ''))[11:16]} | `{a.run_id}` {d['arm']}/{d['task_id']}/t{d['trial']} | "
                    f"{model} | {d['exit_reason']}, {d.get('num_turns')} turns, {dur:.0f} s | {i:,} | {o:,} | {cr:,} | "
                    f"{cw:,} | {usd:.4f} | 0 | resolved={g.get('resolved')}; nudges {d.get('interventions')}; "
                    f"five-hour {five}, seven-day {seven}" + (f"; {a.note}" if a.note else "") + " |")
        for k, v in enumerate((i, o, cr, cw, usd)):
            tot[k] += v
    e2e = root / "e2e"
    if (e2e / "summary.json").exists():   # scripts/s2a_e2e.py: one task, s2a's own calls.jsonl
        sm = json.loads((e2e / "summary.json").read_text(encoding="utf-8"))
        cf = e2e / "artifacts" / "calls.jsonl"
        calls = [json.loads(x) for x in cf.read_text(encoding="utf-8").splitlines() if x.strip()] if cf.exists() else []
        i, o, cr, cw, usd = tokens(calls)
        five, seven = windows(e2e)
        first, res = sm.get("first") or {}, sm.get("resume") or {}
        n += 1
        ok += bool((sm.get("grade") or {}).get("resolved"))
        rows.append(f"| {a.run_id[9:11]}:{a.run_id[11:13]} | `{a.run_id}` s2a e2e {sm.get('task')} | {model} | "
                    f"first {first.get('state_exit')}, resume {res.get('state_exit')}, {sum(c.get('num_turns') or 0 for c in calls)} "
                    f"turns, {len(calls)} calls | {i:,} | {o:,} | {cr:,} | {cw:,} | {usd:.4f} | 0 | "
                    f"resolved={(sm.get('grade') or {}).get('resolved')}; verdict {res.get('verdict')}; five-hour {five}, "
                    f"seven-day {seven}" + (f"; {a.note}" if a.note else "") + " |")
        for k, v in enumerate((i, o, cr, cw, usd)):
            tot[k] += v
    rows.append(f"| | **`{a.run_id}` total ({n} trials, {ok} resolved)** | | mean {secs / max(n, 1):.0f} s | "
                f"**{tot[0]:,}** | **{tot[1]:,}** | **{tot[2]:,}** | **{tot[3]:,}** | **{tot[4]:.4f}** | 0 | "
                f"incl. one-time setup" + (f"; {a.note}" if a.note else "") + " |")
    print("\n".join(rows))


if __name__ == "__main__":
    main()
