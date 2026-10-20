"""Failure labelling (phases/phase-9-analysis.md steps 6-8, specs/failure-taxonomy.md).

`<run>/labels.json` holds one item per unresolved trial under an opaque id (`L` + 8 hex), so the person
labelling never sees the arm: {"taxonomy_version", "items": {id: {arm, task, trial, manual?, llm?, primary,
source}}, "calibration"}. `primary` is the effective label: manual when present, else llm.

The LLM labeller: `claude.exe -p --output-format json --json-schema <taxonomy schema> --tools "" --max-turns 1
--model <pinned>` with the blind bundle on stdin, as the harness user in a scratch trial dir (no tools, no
files), the subscription token through the platform layer's environment block. No SDK, no API key.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from abb import paths
from abb.config import load_sandbox, load_task, load_toolchain
from abb.harness.agent_env import TrialDirs, build_agent_env, claude_template_dir, preflight
from abb.harness.platform import ProcSpec, get_platform
from abb.harness.tasks import task_dir
from abb.util import stamp, utcnow_iso

TAXONOMY = paths.repo_clone() / "specs" / "failure-taxonomy.md"
SECONDARY = ["asked_question", "ignored_repo_conventions", "wrote_tests", "touched_build_files"]
TAXONOMY_VERSION = 1
DIFF_CHARS = 30_000


def taxonomy_table() -> str:
    text = TAXONOMY.read_text(encoding="utf-8")
    start = text.index("| code |")
    end = text.index("\n\n", start)
    return text[start:end]


def codes() -> list[str]:
    return re.findall(r"^\| `([A-Z_]+)` \|", taxonomy_table(), re.M)


def schema() -> dict:
    return {"type": "object", "additionalProperties": False, "required": ["primary", "confidence", "rationale"],
            "properties": {"primary": {"type": "string", "enum": codes()},
                           "secondary": {"type": "array", "items": {"type": "string", "enum": SECONDARY}},
                           "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                           "rationale": {"type": "string", "maxLength": 600}}}


def item_id(run_id: str, arm: str, task: str, trial: int) -> str:
    return "L" + hashlib.sha256(f"{run_id}|{arm}|{task}|{trial}".encode()).hexdigest()[:8]


def path(run_id: str) -> Path:
    return paths.results_dir() / run_id / "labels.json"


def load(run_id: str) -> dict:
    p = path(run_id)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {"taxonomy_version": TAXONOMY_VERSION,
                                                                         "items": {}, "calibration": {}}


def save(run_id: str, data: dict) -> None:
    p = path(run_id)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(p)


def init(run_id: str) -> dict:
    """A skeleton item for every unresolved trial (kept: items already labelled)."""
    root = paths.results_dir() / run_id
    data = load(run_id)
    for rj in sorted(root.glob("*/*/t*/run.json")):
        if rj.parts[-4] in ("usage_limited", "setup", "salvaged"):
            continue
        g = json.loads((rj.parent / "grade.json").read_text(encoding="utf-8")) if (rj.parent / "grade.json").exists() else {}
        if g.get("resolved"):
            continue
        arm, task, trial = rj.parts[-4], rj.parts[-3], int(rj.parts[-2][1:])
        iid = item_id(run_id, arm, task, trial)
        data["items"].setdefault(iid, {"arm": arm, "task": task, "trial": trial, "primary": None, "source": None})
    save(run_id, data)
    return data


def _rec(run_id: str, item: dict) -> Path:
    return paths.results_dir() / run_id / item["arm"] / item["task"] / f"t{item['trial']}"


def bundle(run_id: str, iid: str, *, with_transcript: bool = False) -> str:
    """The blind bundle: the ticket, the scoped diff and the grade summary. No arm name, no artifacts, no transcript
    (those identify the arm) unless `with_transcript` (the secondary-flag pass only)."""
    item = load(run_id)["items"][iid]
    rec = _rec(run_id, item)
    t = load_task(item["task"])
    ticket = (task_dir(t.id) / t.problem_statement).read_text(encoding="utf-8")
    diff = (rec / "diff.patch").read_text(encoding="utf-8", errors="replace") if (rec / "diff.patch").exists() else ""
    if len(diff) > DIFF_CHARS:
        diff = diff[:DIFF_CHARS] + f"\n… [{len(diff) - DIFF_CHARS} more characters of diff not shown]\n"
    g = json.loads((rec / "grade.json").read_text(encoding="utf-8")) if (rec / "grade.json").exists() else {}
    m = json.loads((rec / "metrics.json").read_text(encoding="utf-8")) if (rec / "metrics.json").exists() else {}
    run = json.loads((rec / "run.json").read_text(encoding="utf-8")) if (rec / "run.json").exists() else {}
    f2p = g.get("f2p") or {}
    summary = {"resolved": g.get("resolved"), "reason": g.get("reason"), "build_ok": g.get("build_ok"),
               "fail_to_pass": {"total": len(f2p), "passed": sum(1 for v in f2p.values() if v == "passed")},
               "regressions": len(g.get("regressions") or []), "exit_reason": run.get("exit_reason"),
               "agent_touched_tests": m.get("agent_touched_tests"), "test_config_suspect": m.get("test_config_suspect"),
               "build_config_changed": m.get("build_config_changed"), "diff_files": m.get("diff_files"),
               "diff_lines": int(m.get("diff_insertions") or 0) + int(m.get("diff_deletions") or 0),
               "scope_creep_files": m.get("scope_creep_files"), "asked_question": run.get("asked_question"),
               "interventions": run.get("interventions")}
    parts = [f"# Item {iid}", "", "## Ticket", "", ticket.strip(), "", "## Grade summary", "",
             "```json", json.dumps(summary, indent=2, sort_keys=True), "```", "", "## Diff (scoped)", "", "```diff",
             diff.rstrip() or "(empty diff)", "```"]
    if with_transcript:
        texts = []
        for f in sorted((rec / "transcript").glob("*.jsonl")):
            for ln in f.read_text(encoding="utf-8", errors="replace").splitlines():
                if '"type":"assistant"' in ln:
                    texts += re.findall(r'"type":"text","text":"((?:[^"\\]|\\.){0,400})', ln)
        parts += ["", "## Agent messages (excerpt; secondary-flag pass only)", ""] + [f"- {x}" for x in texts[-30:]]
    return "\n".join(parts) + "\n"


def prompt(bundle_text: str) -> str:
    return ("You label why one attempt at a coding task failed. Read the ticket, the grade summary and the diff, and "
            "pick exactly one primary label from this taxonomy (and any secondary flags that apply). Judge only from "
            "what is shown; the hidden tests are not shown. For INTERFACE, the reason must be test_compile_failed, the "
            "diff non-empty in the right place, and the behaviour you can see must be correct.\n\n"
            + taxonomy_table() + "\n\nSecondary flags: " + ", ".join(SECONDARY) + "\n\nReturn the JSON object only.\n\n"
            + bundle_text)


def call_llm(bundle_text: str, *, model: str, timeout_s: int = 300) -> dict:
    """One headless call; {primary, secondary, confidence, rationale, cost_usd} or {primary: None, error}."""
    token = preflight()
    plat = get_platform()
    trial = TrialDirs(paths.work_dir() / "labeller" / f"{stamp()}-{hashlib.sha256(bundle_text.encode()).hexdigest()[:6]}")
    trial.create(claude_template=claude_template_dir())
    env = build_agent_env(trial, token=token, proxy=False)
    argv = [str(plat.claude_exe()), "-p", "--output-format", "json", "--json-schema", json.dumps(schema()),
            "--tools", "", "--max-turns", "1", "--model", model]
    out: dict = {"primary": None}
    for attempt in (1, 2):
        spec = ProcSpec(argv=argv, cwd=trial.work, env=env, stdin_text=prompt(bundle_text), timeout_s=timeout_s,
                        memory_mb=load_sandbox().process.memory_mb, as_user=None, interrupt=load_sandbox().process.interrupt,
                        out_dir=trial.agent_out / f"a{attempt}", stop_file=trial.stop_file, grace_s=10)
        r = plat.wait(plat.run(spec))
        try:
            res = json.loads(r.stdout().strip().splitlines()[-1])
        except (ValueError, IndexError):
            out = {"primary": None, "error": f"unparsable output (exit {r.exit_code}): {r.stderr()[-300:]}"}
            continue
        so = res.get("structured_output") or {}
        out = {"primary": so.get("primary"), "secondary": so.get("secondary") or [], "confidence": so.get("confidence"),
               "rationale": so.get("rationale"), "cost_usd": res.get("total_cost_usd"), "subtype": res.get("subtype"),
               "model": model, "claude_code_version": load_toolchain().claude_code.version, "at": utcnow_iso()}
        if out["primary"] in codes():
            break
        out["error"] = f"no valid label (subtype {res.get('subtype')})"
    plat.rmtree_robust(trial.root)
    return out


def run_llm(run_id: str, *, model: str, calibrate: bool = False, ids: list[str] | None = None) -> dict:
    """Label with the LLM: every item without a label, or (calibrate) every manually labelled item."""
    data = init(run_id)
    todo = ids or [i for i, v in sorted(data["items"].items())
                   if (v.get("manual") if calibrate else not v.get("primary"))]
    n, cost = 0, 0.0
    for iid in todo:
        res = call_llm(bundle(run_id, iid), model=model)
        data = load(run_id)
        it = data["items"][iid]
        it["llm"] = res
        if not it.get("manual"):
            it["primary"], it["source"] = (res.get("primary") or "unlabelled"), "llm"
        save(run_id, data)
        n += 1
        cost += float(res.get("cost_usd") or 0)
    return {"labelled": n, "cost_usd": round(cost, 4)}


def set_manual(run_id: str, iid: str, primary: str, secondary: list[str] | None = None) -> dict:
    if primary not in codes():
        raise SystemExit(f"{primary} is not a taxonomy code: {codes()}")
    data = load(run_id)
    it = data["items"][iid]
    it["manual"] = {"primary": primary, "secondary": secondary or [], "at": utcnow_iso()}
    it["primary"], it["source"] = primary, "manual"
    save(run_id, data)
    return it


def agreement(run_id: str) -> dict:
    """Manual vs llm on the items that have both: agreement %, confusion pairs, per arm; stored as calibration."""
    data = load(run_id)
    both = [v for v in data["items"].values() if v.get("manual") and (v.get("llm") or {}).get("primary")]
    if not both:
        data["calibration"] = {"status": "agreement: not measured (uncalibrated)", "n": 0}
        save(run_id, data)
        return data["calibration"]
    agree = [v["manual"]["primary"] == v["llm"]["primary"] for v in both]
    conf: dict[str, int] = {}
    per_arm: dict[str, list[bool]] = {}
    for v, a in zip(both, agree):
        key = f"{v['manual']['primary']} -> {v['llm']['primary']}"
        conf[key] = conf.get(key, 0) + 1
        per_arm.setdefault(v["arm"], []).append(a)
    pct = sum(agree) / len(agree)
    cal = {"n": len(both), "agreement": round(pct, 4), "calibrated": pct >= 0.8 and len(both) >= 20,
           "confusion": dict(sorted(conf.items())),
           "per_arm": {k: round(sum(v) / len(v), 4) for k, v in sorted(per_arm.items())},
           "status": (f"calibrated: {sum(agree)}/{len(agree)} = {pct:.0%} primary-label agreement with manual labels "
                      "(±15 pp at this n)") if pct >= 0.8 and len(both) >= 20 else
                     f"uncalibrated: {sum(agree)}/{len(agree)} = {pct:.0%} agreement on {len(both)} manual labels"}
    data["calibration"] = cal
    save(run_id, data)
    return cal
