"""Minimal report (phases/phase-4 step 6; Phase 9 grows it): one row per trial + setup section + totals.

Every number comes from files under the run directory (metrics.json, run.json, grade.json,
audit.json): AGENTS.md rule 3. Costs are "est. API-equivalent USD" (no bill under the subscription).
"""
from __future__ import annotations

import json
from pathlib import Path

from abb import paths


def _load(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def rows(root: Path) -> list[dict]:
    out = []
    for rj in sorted(root.glob("*/*/t*/run.json")):
        rec = rj.parent
        if rec.parts[-4] in ("usage_limited", "setup"):
            continue
        run, g, m = _load(rj), _load(rec / "grade.json"), _load(rec / "metrics.json")
        f2p = g.get("f2p") or {}
        out.append({
            "arm": rec.parent.parent.name, "task": rec.parent.name, "trial": int(rec.name[1:]),
            "resolved": g.get("resolved"), "reason": g.get("reason"), "exit_reason": run.get("exit_reason"),
            "turns": run.get("num_turns"), "tool_calls": run.get("tool_calls"), "interventions": run.get("interventions"),
            "cost_usd": run.get("cost_usd"), "cost_usd_imputed": run.get("cost_usd_imputed"),
            "duration_s": round((run.get("duration_ms") or 0) / 1000, 1),
            "f2p": f"{sum(1 for v in f2p.values() if v == 'passed')}/{len(f2p)}",
            "regressions": len(g.get("regressions") or []), "gate_runs": run.get("gate_gradle_runs"),
            "builds": f"{m.get('agent_gradle_ok', '?')}/{m.get('agent_gradle_failed', '?')}/{m.get('agent_env_errors', '?')}",
            "env_errors": m.get("agent_env_errors") or 0, "gradle_ok": m.get("agent_gradle_ok") or 0,
            "tokens_out": m.get("output_tokens"), "tokens_in_total": (m.get("input_tokens") or 0) + (m.get("cache_read_tokens") or 0)
            + (m.get("cache_write_tokens") or 0) if m else None,
        })
    return out


def render(run_id: str) -> str:
    root = paths.results_dir() / run_id
    man, aud = _load(root / "manifest.json"), _load(root / "audit.json")
    rs = rows(root)
    lines = [f"# Run {run_id}", "",
             f"Arms: {', '.join(man.get('arms', []))} · tasks: {man.get('task_set')} ({len(man.get('task_ids', []))}) · "
             f"trials: {man.get('trials')} · model: {(man.get('limits') or {}).get('model')} · Claude Code "
             f"{man.get('agent_version')} · sandbox: {man.get('sandbox_mode')} · plan: {man.get('plan')} · "
             f"aborted: {man.get('aborted_reason')}", ""]
    if man.get("invalid"):
        lines += [f"> **INVALID run ({man['invalid'].get('decision')}):** {man['invalid'].get('reason')}. Its numbers are "
                  "kept for the cost log only and enter no comparison.", ""]
    lines += [
             "Cost columns are **est. API-equivalent USD** (Claude Code's client-side estimate at list price; there is no "
             "bill under the subscription). Tokens: output / total input incl. cache reads and writes.", "",
             "| arm | task | trial | resolved | reason | exit | turns | tools | nudges | est. USD | duration s | F2P | regr. | gate runs | builds ok/failed/env | out tok | in tok |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rs:
        usd = f"{r['cost_usd']:.4f}" if r["cost_usd"] is not None else (
            f"~{r['cost_usd_imputed']:.4f}" if r["cost_usd_imputed"] else "—")
        lines.append(f"| {r['arm']} | {r['task']} | {r['trial']} | {r['resolved']} | {r['reason'] or ''} | {r['exit_reason']} | "
                     f"{r['turns']} | {r['tool_calls']} | {r['interventions']} | {usd} | {r['duration_s']} | {r['f2p']} | "
                     f"{r['regressions']} | {r['gate_runs'] or 0} | {r['builds']} | {r['tokens_out']} | {r['tokens_in_total']} |")
    lines += ["", "## Setup (one-time, per repo)", "", "None for these arms." if not (root / "setup").exists() else
              "\n".join(f"- {p.relative_to(root)}" for p in sorted((root / "setup").glob("*/*/run.json")))]
    lines += ["", "## Totals", ""]
    by_arm: dict[str, list[dict]] = {}
    for r in rs:
        by_arm.setdefault(r["arm"], []).append(r)
    lines += ["| arm | resolved | mean est. USD | total est. USD | mean duration s | mean turns |", "|---|---|---|---|---|---|"]
    for arm, rr in by_arm.items():
        costs = [r["cost_usd"] if r["cost_usd"] is not None else (r["cost_usd_imputed"] or 0) for r in rr]
        n_res = sum(1 for r in rr if r["resolved"])
        lines.append(f"| {arm} | {n_res}/{len(rr)} | {sum(costs) / len(rr):.4f} | {sum(costs):.4f} | "
                     f"{sum(r['duration_s'] for r in rr) / len(rr):.0f} | {sum((r['turns'] or 0) for r in rr) / len(rr):.1f} |")
    lines += ["", f"Audit: {'PASS' if aud.get('ok') else ('FAIL' if aud else 'not run')}"
              + (f" (token leaks: {aud.get('token_leak_files')})" if aud.get("token_leak_files") else ""),
              f"Usage-limited attempts kept: {aud.get('usage_limited_attempts', 0)}; probes: {aud.get('probes', 0)}", ""]
    sus = [f"{r['arm']}/{r['task']}/t{r['trial']}" for r in rs if r["env_errors"] and not r["gradle_ok"]]
    if sus:
        lines.append(f"**Environment check:** the agent's Gradle never succeeded and hit offline-resolution or cache-access "
                     f"errors in {len(sus)} trial(s): {', '.join(sus)} (D-043). Check them before using this run.")
    if any(r["gate_runs"] for r in rs):
        lines.append("plain-gate: exactly one harness test run + one resume per trial (S2A allows up to 2 fix rounds per task).")
    text = "\n".join(lines) + "\n"
    out = root / "report"
    out.mkdir(exist_ok=True)
    (out / "summary.md").write_text(text, encoding="utf-8", newline="\n")
    return text
