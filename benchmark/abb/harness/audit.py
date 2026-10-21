"""`abb audit <run_id>` (specs/headless-agent-driving.md, "Source of truth"; AGENTS.md rule 11).

Recomputes every call's turns, cost, tool calls and tokens from the verbatim transcripts
(nudge continuations included), checks the init model/version and the modelUsage keys, checks
that a trial's turns stay within max_turns_total, compares everything with run.json and
calls.jsonl, and fails if ANY file under the run directory contains the OAuth token value or an
`sk-ant-...` key shape (the failure names the file, never the match; D-026). Writes audit.json.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from abb import paths
from abb.config import load_toolchain, oauth_token
from abb.harness import transcript as tx
from abb.util import utcnow_iso

KEY = re.compile(rb"sk-ant-[a-z]+\d{2}-")


def _close(a, b, tol: float = 1e-6) -> bool:
    if a is None or b is None:
        return a is None and b is None
    return abs(float(a) - float(b)) <= tol + 1e-9 * abs(float(b))


def audit_trial(rec: Path, pin: str) -> list[str]:
    errs: list[str] = []
    rj = json.loads((rec / "run.json").read_text(encoding="utf-8"))
    if rj.get("exit_reason") == "harness_error" and not rj.get("calls"):
        return errs
    model = (rj.get("limits") or {}).get("model") or rj.get("model") or ""
    total_turns = 0
    history: list[tx.Transcript] = []  # execution order: calls in order, each call's nudges after it
    for c in rj.get("calls") or []:
        name = c["name"]
        files = [rec / "transcript" / f"{name}.jsonl"] + [Path(p) for p in c.get("nudge_transcript_paths") or []]
        files = [f if f.is_absolute() else rec / f for f in files]
        files = [rec / "transcript" / f.name for f in files]  # trial dirs may move (usage_limited/): use the local copy
        turns = tools = 0
        tok = {"input_tokens": 0, "output_tokens": 0, "cache_read_tokens": 0, "cache_write_tokens": 0}
        cost = 0.0
        cost_known = True
        for f in files:
            if not f.exists():
                errs.append(f"{name}: transcript {f.name} missing")
                continue
            t = tx.parse_file(f)
            own = tx.invocation_cost(t, history)
            history.append(t)
            turns += t.num_turns
            tools += t.tool_calls
            for k, v in t.usage_totals().items():
                tok[k] += v
            if own is None:
                cost_known = False
            else:
                cost += own
            if t.init:
                if not str(t.init.get("model") or "").startswith(model):
                    errs.append(f"{name}: init.model {t.init.get('model')} != {model}")
                if t.init.get("claude_code_version") != pin:
                    errs.append(f"{name}: claude_code_version {t.init.get('claude_code_version')} != {pin}")
            for k in t.model_usage:
                if not (k.startswith(model) or k.startswith("claude-haiku")):
                    errs.append(f"{name}: foreign model in modelUsage: {k}")
        total_turns += turns
        if turns != c.get("num_turns"):
            errs.append(f"{name}: num_turns run.json {c.get('num_turns')} != transcripts {turns}")
        if tools != c.get("tool_calls"):
            errs.append(f"{name}: tool_calls run.json {c.get('tool_calls')} != transcripts {tools}")
        for k, v in tok.items():
            if v != c.get(k):
                errs.append(f"{name}: {k} run.json {c.get(k)} != transcripts {v}")
        if cost_known and not _close(c.get("cost_usd"), round(cost, 6), 1e-4):
            errs.append(f"{name}: cost_usd run.json {c.get('cost_usd')} != transcripts {round(cost, 6)}")
        if not cost_known and c.get("cost_usd") is not None:
            errs.append(f"{name}: cost_usd set although a transcript has no result line")
    if total_turns != rj.get("num_turns"):
        errs.append(f"trial num_turns run.json {rj.get('num_turns')} != transcripts {total_turns}")
    limit = (rj.get("limits") or {}).get("max_turns_total")
    if limit and total_turns > limit + 2 * len(rj.get("calls") or []):  # --max-turns may overshoot by one turn per process
        errs.append(f"trial used {total_turns} turns > max_turns_total {limit}")
    lines = (rec / "calls.jsonl").read_text(encoding="utf-8").splitlines() if (rec / "calls.jsonl").exists() else []
    if [json.loads(x)["name"] for x in lines] != [c["name"] for c in rj.get("calls") or []]:
        errs.append("calls.jsonl does not match run.json calls")
    return errs


def token_scan(root: Path) -> list[str]:
    tok = (oauth_token() or "").encode("utf-8")
    bad = []
    for f in root.rglob("*"):
        if not f.is_file():
            continue
        data = f.read_bytes()
        if (tok and tok in data) or KEY.search(data):
            bad.append(str(f.relative_to(root)))
    return bad


def audit(run_id: str) -> dict:
    root = paths.results_dir() / run_id
    pin = load_toolchain().claude_code.version
    trials = {}
    for rj in (sorted(root.glob("*/*/t*/run.json")) + sorted(root.glob("usage_limited/*/*/t*/run.json")) + sorted(root.glob("invalidated/*/*/t*/run.json"))
               + sorted(root.glob("setup/*/*/run.json"))):  # one-time setup calls are audited like trials
        rec = rj.parent
        key = str(rec.relative_to(root)).replace("\\", "/")
        trials[key] = audit_trial(rec, pin)
    leaks = token_scan(root)
    probes = sorted(p.name for p in (root / "probes").glob("*.jsonl")) if (root / "probes").exists() else []
    ok = not leaks and all(not v for v in trials.values())
    out = {"run_id": run_id, "ok": ok, "trials": {k: (v or "ok") for k, v in trials.items()}, "token_leak_files": leaks,
           "probes": len(probes), "usage_limited_attempts": len(list(root.glob("usage_limited/*/*/t*")))}
    tmp = root / "audit.json.tmp"
    tmp.write_text(json.dumps(out, indent=2), encoding="utf-8")
    tmp.replace(root / "audit.json")
    for mf in root.glob("*/*/t*/metrics.json"):
        m = json.loads(mf.read_text(encoding="utf-8"))
        key = str(mf.parent.relative_to(root)).replace("\\", "/")
        m["audit_ok"] = not trials.get(key) and not leaks
        mf.write_text(json.dumps(m, indent=2, default=str), encoding="utf-8")
    return out


# ---------------------------------------------------------------------------- re-derivation
DERIVED = ("num_turns", "tool_calls", "tool_errors", "input_tokens", "output_tokens", "cache_read_tokens",
           "cache_write_tokens", "rate_limit_retries", "other_retries", "cost_usd", "cost_usd_imputed")


def recompute_calls(rec: Path, rj: dict) -> list[dict]:
    """Every call's derived fields from its transcripts, by the driver's rules (invocation_cost per
    process in execution order; imputed when a process's own cost is unknown)."""
    model = (rj.get("limits") or {}).get("model") or rj.get("model") or ""
    history: list[tx.Transcript] = []
    out = []
    for c in rj.get("calls") or []:
        d = {k: 0 for k in DERIVED}
        known, cost, est = True, 0.0, 0.0
        files = [rec / "transcript" / f"{c['name']}.jsonl"] + [
            rec / "transcript" / Path(x).name for x in c.get("nudge_transcript_paths") or []]
        for f in files:
            t = tx.parse_file(f)
            own = tx.invocation_cost(t, history)
            history.append(t)
            d["num_turns"] += t.num_turns
            d["tool_calls"] += t.tool_calls
            d["tool_errors"] += t.tool_errors
            d["rate_limit_retries"] += t.rate_limit_retries
            d["other_retries"] += t.other_retries
            for k, v in t.usage_totals().items():
                d[k] += v
            if own is None:
                known = False
                est += tx.impute_cost(t, model) or 0.0
            else:
                cost += own
                est += own
        d["cost_usd"] = round(cost, 6) if known else None
        d["cost_usd_imputed"] = None if known else round(est, 6)
        out.append(d)
    return out


def _same(a, b) -> bool:
    if isinstance(a, float) or isinstance(b, float):
        return _close(a, b, 1e-6)
    return a == b


def rederive_trial(rec: Path, *, run_id: str, reason: str) -> dict:
    """Rewrite run.json / calls.jsonl / metrics.json from the transcripts (AGENTS.md rule 11: they
    are derived). Returns {field: [old, new]} for what changed; the caller logs it."""
    from abb.harness import metrics
    from abb.harness.agent_driver import write_json

    rj = json.loads((rec / "run.json").read_text(encoding="utf-8"))
    calls = rj.get("calls") or []
    changes: dict = {}
    for c, new in zip(calls, recompute_calls(rec, rj)):
        for k, v in new.items():
            if not _same(c.get(k), v):
                changes[f"{c['name']}.{k}"] = [c.get(k), v]
                c[k] = v
    totals = {
        "cost_usd": None if any(c.get("cost_usd") is None for c in calls) else round(sum(c["cost_usd"] for c in calls), 4),
        "cost_usd_imputed": round(sum((c["cost_usd"] if c.get("cost_usd") is not None else (c.get("cost_usd_imputed") or 0.0))
                                      for c in calls), 4),
        "num_turns": sum(int(c.get("num_turns") or 0) for c in calls),
        "tool_calls": sum(int(c.get("tool_calls") or 0) for c in calls),
    }
    for k, v in totals.items():
        if not _same(rj.get(k), v):
            changes[k] = [rj.get(k), v]
            rj[k] = v
    if changes:
        rj.setdefault("rederived", []).append({"at": utcnow_iso(), "reason": reason, "changes": changes})
        write_json(rec / "run.json", rj)
        with open(rec / "calls.jsonl", "w", encoding="utf-8") as f:
            for c in calls:
                f.write(json.dumps(c, default=str) + "\n")
        if (rec / "grade.json").exists():
            metrics.build(rec, run_id=run_id, arm=rec.parent.parent.name, task_id=rec.parent.name,
                          trial=int(rec.name[1:].split("-")[0]))
    return changes


def rederive(run_id: str, reason: str) -> dict:
    root = paths.results_dir() / run_id
    done = {}
    for rj in sorted(root.glob("*/*/t*/run.json")):
        rec = rj.parent
        if rec.parts[-4] in ("usage_limited", "setup") or json.loads(rj.read_text(encoding="utf-8")).get("exit_reason") == "harness_error":
            continue
        ch = rederive_trial(rec, run_id=run_id, reason=reason)
        if ch:
            key = str(rec.relative_to(root)).replace("\\", "/")
            done[key] = ch
            with open(root / "events.jsonl", "a", encoding="utf-8") as f:
                f.write(json.dumps({"at": utcnow_iso(), "event": "rederived", "trial": key, "reason": reason,
                                    "changes": ch}, default=str) + "\n")
    return done
