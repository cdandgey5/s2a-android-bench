"""`metrics.json`: one flat row per trial (specs/results-layout.md), merged from run.json, grade.json, the
task and the manifest. Missing sources leave their fields null; Phase 4+ fills run.json."""
from __future__ import annotations

import json
import os
from pathlib import Path

from abb.config import load_task
from abb.harness.tasks import is_post_cutoff


def _load(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def _agent_builds(trial_dir: Path) -> dict:
    """Gradle outcomes in the agent's tool results over all transcripts (D-043 health signal)."""
    from abb.harness import transcript as tx

    out = {"agent_gradle_ok": 0, "agent_gradle_failed": 0, "agent_env_errors": 0}
    for f in sorted((trial_dir / "transcript").glob("*.jsonl")):
        t = tx.parse_file(f)
        out["agent_gradle_ok"] += t.gradle_ok
        out["agent_gradle_failed"] += t.gradle_failed
        out["agent_env_errors"] += t.env_errors
    return out


def build(trial_dir: Path, *, run_id: str, arm: str, task_id: str, trial: int, manifest: dict | None = None) -> dict:
    t = load_task(task_id)
    run = _load(trial_dir / "run.json")
    g = _load(trial_dir / "grade.json")
    flags = g.get("flags") or {}
    calls = run.get("calls") or []
    tok = {k: sum(int(c.get(k) or 0) for c in calls) for k in ("input_tokens", "output_tokens", "cache_read_tokens",
                                                               "cache_write_tokens")}
    denom = tok["input_tokens"] + tok["cache_read_tokens"] + tok["cache_write_tokens"]
    row = {
        "run_id": run_id, "arm": arm, "task_id": task_id, "trial": trial,
        "repo": t.repo, "category": t.category, "source": t.source, "split": t.split, "post_cutoff": is_post_cutoff(t),
        **{f"tags.{k}": v for k, v in t.tags.model_dump().items()},
        "resolved": g.get("resolved"), "build_ok": g.get("build_ok"), "reason": g.get("reason"),
        "interface_table": g.get("interface_candidate"),
        "regressions_n": len(g.get("regressions") or []), "flaky_p2p_n": len(g.get("flaky_p2p") or []),
        "agent_touched_tests": flags.get("agent_touched_tests"), "build_config_changed": flags.get("build_config_changed"),
        "build_config_reverted": flags.get("build_config_reverted"), "test_config_suspect": flags.get("test_config_suspect"),
        "diff_files": (g.get("diff_stats") or {}).get("files"), "diff_insertions": (g.get("diff_stats") or {}).get("insertions"),
        "diff_deletions": (g.get("diff_stats") or {}).get("deletions"),
        "scope_creep_files": (g.get("scope_creep") or {}).get("files_outside_gold_modules"),
        **{k: run.get(k) for k in ("exit_reason", "duration_ms", "cost_usd", "cost_usd_imputed", "num_turns", "tool_calls",
                                   "interventions", "asked_question", "gate_gradle_runs", "gate_seconds", "model",
                                   "agent_version", "workspace_base")},
        "tool_errors": sum(int(c.get("tool_errors") or 0) for c in calls) if calls else None,
        "rate_limit_retries": sum(int(c.get("rate_limit_retries") or 0) for c in calls) if calls else None,
        "other_retries": sum(int(c.get("other_retries") or 0) for c in calls) if calls else None,
        "model_drift": any(c.get("model_drift") for c in calls) if calls else None,
        **(tok if calls else {k: None for k in tok}),
        "cache_hit_rate": round(tok["cache_read_tokens"] / denom, 4) if calls and denom else None,
        "calls_n": len(calls), "calls": [{"name": c.get("name"), "cost_usd": c.get("cost_usd"),
                                          "num_turns": c.get("num_turns")} for c in calls],
        "retried": None, "retry_reason": None,
        "env_fingerprint": g.get("env_fingerprint"), "platform": (manifest or {}).get("platform", "windows"),
        "audit_ok": None, "failure_label": None, "failure_label_source": None, "label_confidence": None,
        "convention_score": None,
        **_agent_builds(trial_dir),
    }
    tmp = trial_dir / "metrics.json.tmp"
    tmp.write_text(json.dumps(row, indent=2, default=str), encoding="utf-8")
    os.replace(tmp, trial_dir / "metrics.json")
    return row
