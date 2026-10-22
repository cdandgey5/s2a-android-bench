"""One-time per-repo setup (specs/adapter-interface.md: `one_time_setup`), reported separately.

Cached per (setup_kind, repo, setup_commit, environment fingerprint, prompt hash, model; D-058) under
<results>/_setup_cache/<key>/ so arms that share a setup kind share the artifact (D-012). The run
that produces a setup records it under <run>/setup/<kind>/<repo>/ (run.json, calls.jsonl,
transcript/, prompts/, artifacts/) and pays its cost there; later runs record a reference
(`reused_from`) at cost 0. The setup workspace is a snapshot at `repos.<repo>.build.setup_commit`
(fairness-protocol.md, "One-time setup artifacts must not leak fixes").
"""
from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import asdict
from pathlib import Path
from typing import Callable

from abb import paths
from abb.config import load_repo
from abb.harness.env import load_env_lock
from abb.util import utcnow_iso

OK_SUBTYPES = ("success", "error_max_turns")   # a turn-capped constitution is still a (partial) setup


class SetupError(RuntimeError):
    def __init__(self, subtype: str, detail: str) -> None:
        super().__init__(f"setup ended {subtype}: {detail}")
        self.subtype = subtype


def cache_key(setup_kind: str, repo_key: str, prompt_hash: str, model: str) -> str:
    repo = load_repo(repo_key)
    fp = (load_env_lock().get(repo_key) or {}).get("fingerprint", "")
    raw = json.dumps([setup_kind, repo_key, repo.build.setup_commit, fp, prompt_hash, model])
    return f"{setup_kind}-{repo_key}-{hashlib.sha256(raw.encode()).hexdigest()[:16]}"


def cache_dir(key: str) -> Path:
    return paths.results_dir() / "_setup_cache" / key


def _write_record(rec_dir: Path, data: dict) -> None:
    from abb.harness.agent_driver import write_json

    rec_dir.mkdir(parents=True, exist_ok=True)
    write_json(rec_dir / "run.json", data)
    with open(rec_dir / "calls.jsonl", "w", encoding="utf-8") as f:
        for c in data.get("calls") or []:
            f.write(json.dumps(c, default=str) + "\n")


def ensure_setup(arm, repo_key: str, run_dir: Path, *, run_id: str,
                 make_context: Callable[[object, str, Path], tuple], model: str) -> dict | None:
    """The setup artifacts for (arm.setup_kind, repo): from the cache, or produced now.

    `make_context(arm, repo_key, rec_dir) -> (workspace, DriverContext)` builds the sandboxed
    workspace at setup_commit and the setup's own budget. Returns {key, artifacts, reused, record}.
    """
    from abb.harness.agent_driver import phasecall_dict

    if getattr(arm, "setup_kind", None) is None:
        return None
    key = cache_key(arm.setup_kind, repo_key, arm.setup_prompt_hash(), model)   # D-058: the trials' model
    cdir = cache_dir(key)
    rec_dir = run_dir / "setup" / arm.setup_kind / repo_key
    if (cdir / "record.json").exists() and (cdir / "artifacts").exists():
        record = json.loads((cdir / "record.json").read_text(encoding="utf-8"))
        if not (rec_dir / "run.json").exists() and record.get("run_id") != run_id:
            _write_record(rec_dir, {"setup_kind": arm.setup_kind, "repo": repo_key, "cache_key": key,
                                    "reused_from": record.get("run_id"), "produced_cost_usd": record.get("cost_usd"),
                                    "cost_usd": 0.0, "cost_usd_imputed": 0.0, "num_turns": 0, "calls": [],
                                    "limits": record.get("limits"), "recorded_at": utcnow_iso()})
        return {"key": key, "artifacts": cdir / "artifacts", "reused": True, "record": record}
    ws, ctx = make_context(arm, repo_key, rec_dir)
    try:
        calls = arm.one_time_setup(repo_key, ws, ctx.budget.limits, ctx=ctx)
        # an arm whose setup can fail after a successful call (s2a map: its gate) reports the real ending
        final = getattr(arm, "setup_subtype", None) or (calls[-1].subtype if calls else "agent_error")
        art = rec_dir / "artifacts"
        for d in arm.setup_dirs:
            if (ws.dirs.work / d).exists():
                shutil.copytree(ws.dirs.work / d, art / d, dirs_exist_ok=True)
        costs = [c.cost_usd if c.cost_usd is not None else (c.cost_usd_imputed or 0.0) for c in calls]
        data = {"setup_kind": arm.setup_kind, "repo": repo_key, "cache_key": key, "run_id": run_id,
                "setup_commit": load_repo(repo_key).build.setup_commit,
                "env_fingerprint": (load_env_lock().get(repo_key) or {}).get("fingerprint"),
                "prompt_hash": arm.setup_prompt_hash(), "exit_subtype": final,
                "cost_usd": None if any(c.cost_usd is None for c in calls) else round(sum(costs), 4),
                "cost_usd_imputed": round(sum(costs), 4), "num_turns": sum(c.num_turns for c in calls),
                "tool_calls": sum(c.tool_calls for c in calls), "duration_ms": sum(c.duration_ms for c in calls),
                "calls": [phasecall_dict(c) for c in calls], "limits": asdict(ctx.budget.limits),
                "recorded_at": utcnow_iso()}
        _write_record(rec_dir, data)
        if final not in OK_SUBTYPES:
            raise SetupError(final, f"{arm.setup_kind} for {repo_key}; record {rec_dir}")
        cdir.mkdir(parents=True, exist_ok=True)
        shutil.copytree(art, cdir / "artifacts", dirs_exist_ok=True)
        (cdir / "record.json").write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
        return {"key": key, "artifacts": cdir / "artifacts", "reused": False, "record": data}
    finally:
        ws.cleanup()
