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
            turns += t.num_turns
            tools += t.tool_calls
            for k, v in t.usage_totals().items():
                tok[k] += v
            if t.cost_usd is None:
                cost_known = False
            else:
                cost += t.cost_usd
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
    for rj in sorted(root.glob("*/*/t*/run.json")) + sorted(root.glob("usage_limited/*/*/t*/run.json")):
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
