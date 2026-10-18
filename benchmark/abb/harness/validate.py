"""`abb tasks validate` (specs/task-format.md, "Validation"; phases/phase-2 step 5).

Each run: a fresh history-free workspace as the harness user, Gradle offline with the pristine
(harness-only) Gradle home, one Gradle invocation per module (a `--tests` filter that matches
nothing in a module would fail that module):
  V0 base                 -> every P2P test passes
  V1 base + test.patch    -> every F2P test fails or errors (new_surface: the F2P module's test
                             source set fails to compile, as expected); P2P outside F2P passes
  V2 + gold.patch         -> every F2P and P2P test passes
A task is `validated` when all runs agree and pass; disagreement -> `flaky` with the differing
tests; a consistent failure leaves it `draft` and is reported. Logs: tasks/<id>/.validation/<ts>/.
"""
from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

from abb import paths
from abb.config import RepoConfig, TaskConfig, TestRef, load_repo, load_task
from abb.harness import gradle, junit
from abb.harness.env import gradle_pristine, load_env_lock
from abb.harness.tasks import task_dir, update_task_yaml
from abb.harness.workspace import Workspace
from abb.log import get_logger
from abb.util import stamp, utcnow_iso

log = get_logger("abb.validate")
TEST_COMPILE = re.compile(r"Task (:\S+):compile\w*UnitTest(?:JavaWithJavac|Kotlin)\w* FAILED")
MAIN_COMPILE = re.compile(r"Task (:\S+):compile(?!\w*UnitTest)\w*(?:JavaWithJavac|Kotlin) FAILED")


def _selector(e: TestRef) -> str:
    return e.test + (f".{e.method}" if e.method else "")


def _is_f2p(test_id: str, f2p: list[TestRef]) -> bool:
    for e in f2p:
        if e.method:
            if test_id == f"{e.test}.{e.method}" or test_id.startswith(f"{e.test}.{e.method}["):
                return True
        elif test_id.rsplit(".", 1)[0] == e.test:
            return True
    return False


def _run_module(ws: Workspace, repo: RepoConfig, module: str, selectors: list[str] | None, out: Path) -> dict:
    env = gradle.harness_gradle_env(repo, guh=gradle_pristine(repo), home=ws.dirs.home)
    args = gradle.test_args(repo, module, selectors)
    r = gradle.run(gradle.expand_cmd("{gradlew}", ws.dirs.work) + args, src=ws.dirs.work, env=env, out_dir=out,
                   timeout_s=repo_timeout_s(), memory_mb=10240)
    text = r.stdout() + "\n" + r.stderr()
    jr = junit.parse_dir(gradle.junit_dir(repo, ws.dirs.work, module))
    return {"module": module, "exit_code": r.exit_code, "duration_s": r.duration_s, "tests": jr.tests,
            "times_ok": jr.times_ok, "test_compile_failed": bool(TEST_COMPILE.search(text)),
            "main_compile_failed": bool(MAIN_COMPILE.search(text)), "offline_failures": gradle.offline_failures(text),
            "log": str(out)}


def repo_timeout_s() -> int:
    return 30 * 60


def _stage(ws: Workspace, repo: RepoConfig, t: TaskConfig, label: str, logs: Path) -> dict:
    """Run every module that F2P/P2P name; whole-module P2P runs unfiltered."""
    whole = {e.module for e in t.pass_to_pass if not e.test}
    mods = sorted({e.module for e in t.fail_to_pass + t.pass_to_pass})
    res = {}
    for m in mods:
        if m in whole:
            sel = None
        else:
            sel = sorted({_selector(e) for e in t.fail_to_pass + t.pass_to_pass if e.module == m and e.test})
            if label == "v0":  # F2P tests do not exist yet at base; P2P classes only
                sel = sorted({_selector(e) for e in t.pass_to_pass if e.module == m and e.test})
                if not sel:
                    continue
        res[m] = _run_module(ws, repo, m, sel, logs / f"{label}-{m.strip(':').replace(':', '_') or 'root'}")
    return res


def _evaluate(t: TaskConfig, stage: dict, label: str) -> dict:
    f2p_status = {}
    for e in t.fail_to_pass:
        mr = stage.get(e.module)
        st = None
        if mr:
            jr = junit.JUnitResult(tests=mr["tests"])
            st = jr.status_of(e.test, e.method)
        f2p_status[_selector(e)] = st
    p2p_fail, p2p_pass = [], []
    for m, mr in stage.items():
        scoped_classes = {e.test for e in t.pass_to_pass if e.module == m and e.test}
        whole = any(e.module == m and not e.test for e in t.pass_to_pass)
        for tid, st in mr["tests"].items():
            if _is_f2p(tid, t.fail_to_pass):
                continue
            cls = tid.rsplit(".", 1)[0]
            if not whole and not any(cls == c or cls.startswith(c + "$") for c in scoped_classes):
                continue
            (p2p_pass if st in ("passed", "skipped") else p2p_fail).append(tid)
    problems = []
    for m, mr in stage.items():
        if mr["offline_failures"]:
            problems.append(f"{m}: offline failure {mr['offline_failures']}")
        if mr["main_compile_failed"]:
            problems.append(f"{m}: main sources do not compile")
    test_compile = any(mr["test_compile_failed"] for mr in stage.values())
    if label == "v0":
        ok = not p2p_fail and not problems and all(mr["exit_code"] == 0 for mr in stage.values())
    elif label == "v1":
        f2p_ok = all(s in ("failed", "error") for s in f2p_status.values())
        if t.tags.new_surface and test_compile:
            f2p_ok = True
        ok = f2p_ok and not p2p_fail and not problems
    else:
        ok = all(s == "passed" for s in f2p_status.values()) and not p2p_fail and not problems \
            and all(mr["exit_code"] == 0 for mr in stage.values()) and all(mr["times_ok"] for mr in stage.values())
    return {"ok": ok, "f2p": f2p_status, "p2p_failed": sorted(p2p_fail), "p2p_passed": sorted(p2p_pass),
            "test_compile_failed": test_compile, "problems": problems}


def run_once(t: TaskConfig, k: int, logs_root: Path) -> dict:
    repo = load_repo(t.repo)
    d = task_dir(t.id)
    ws = Workspace(repo, paths.work_dir() / "validate" / t.id / f"{stamp()}-run{k}", "none")
    ws.snapshot(t.base_commit)
    logs = logs_root / f"run{k}"
    out: dict = {"run": k}
    try:
        out["v0"] = _evaluate(t, _stage(ws, repo, t, "v0", logs), "v0")
        if not ws.apply_patch(d / t.test_patch):
            out["error"] = "test.patch does not apply"
            return out
        out["v1"] = _evaluate(t, _stage(ws, repo, t, "v1", logs), "v1")
        if not ws.apply_patch(d / t.gold_patch):
            out["error"] = "gold.patch does not apply on top of test.patch"
            return out
        out["v2"] = _evaluate(t, _stage(ws, repo, t, "v2", logs), "v2")
    finally:
        ws.cleanup()
    return out


def validate(task_id: str, runs: int = 3) -> dict:
    t = load_task(task_id)
    if t.needs_emulator:
        return {"task": task_id, "status": "rejected", "reason": "needs_emulator"}
    logs_root = task_dir(task_id) / ".validation" / stamp()
    logs_root.mkdir(parents=True)
    results = []
    for k in range(1, runs + 1):
        r = run_once(t, k, logs_root)
        results.append(r)
        log.info("%s run %d: %s", task_id, k, {s: (r.get(s) or {}).get("ok") for s in ("v0", "v1", "v2")} | (
            {"error": r["error"]} if "error" in r else {}))
    (logs_root / "results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    all_ok = [all((r.get(s) or {}).get("ok") for s in ("v0", "v1", "v2")) and "error" not in r for r in results]
    # agreement: same F2P outcome per stage and same P2P failures in every run
    sig = [json.dumps({s: {"f2p": (r.get(s) or {}).get("f2p"), "p2p_failed": (r.get(s) or {}).get("p2p_failed")}
                       for s in ("v0", "v1", "v2")}, sort_keys=True) for r in results]
    agree = len(set(sig)) == 1
    flaky: set[str] = set()
    if not agree:
        for s in ("v1", "v2"):
            vals = [(r.get(s) or {}) for r in results]
            for sel in {k for v in vals for k in (v.get("f2p") or {})}:
                if len({str((v.get("f2p") or {}).get(sel)) for v in vals}) > 1:
                    flaky.add(sel)
            fails = [set(v.get("p2p_failed") or []) for v in vals]
            if fails:
                flaky |= set.union(*fails) - set.intersection(*fails)
    passed_sets = [set(r[s]["p2p_passed"]) for r in results for s in ("v0", "v1", "v2") if r.get(s)]
    p2p_stable = sorted(set.intersection(*passed_sets)) if passed_sets else []
    if all(all_ok) and agree and runs >= 3:
        status = "validated"
    elif all(all_ok) and agree:
        status = t.status  # fewer than 3 runs never promotes a task (specs/task-format.md: 3 agreeing runs)
    elif not agree:
        status = "flaky"
    else:
        status = "draft"
    fp = (load_env_lock().get(t.repo) or {}).get("fingerprint")
    v1_compile = "failed_as_expected" if any((r.get("v1") or {}).get("test_compile_failed") for r in results) else "ok"
    block = {"runs": runs, "last_validated": utcnow_iso(), "env_fingerprint": fp, "p2p_stable": p2p_stable,
             "v1_test_compile": v1_compile, "flaky_tests": sorted(flaky)}
    update_task_yaml(task_id, {"validation": block, "status": status})
    summary = {"task": task_id, "status": status, "runs_ok": all_ok, "agree": agree, "flaky": sorted(flaky),
               "p2p_stable": len(p2p_stable), "logs": str(logs_root)}
    if status == "draft":
        summary["why"] = [{s: {"f2p": (r.get(s) or {}).get("f2p"), "p2p_failed": (r.get(s) or {}).get("p2p_failed", [])[:5],
                               "problems": (r.get(s) or {}).get("problems")} for s in ("v0", "v1", "v2")} | (
            {"error": r["error"]} if "error" in r else {}) for r in results[:1]]
    return summary


def validate_cli(ids: list[str], runs: int = 3, keep_going: bool = False) -> int:
    if not ids:
        print("give a task id or --all")
        return 2
    rows, code = [], 0
    for tid in ids:
        try:
            s = validate(tid, runs)
        except Exception as e:  # noqa: BLE001 - reported per task with --keep-going
            s = {"task": tid, "status": "error", "why": repr(e)[:300]}
        rows.append(s)
        print(json.dumps(s, indent=2, default=str))
        if s["status"] != "validated":
            code = 1
            if not keep_going:
                break
    print(f"\n{'task':<18} {'status':<10} runs_ok")
    for s in rows:
        print(f"{s['task']:<18} {s['status']:<10} {s.get('runs_ok')}")
    shutil.rmtree(paths.work_dir() / "validate", ignore_errors=True)
    return code
