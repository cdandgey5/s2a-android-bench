"""`grade(task, diff)` (specs/grading-protocol.md): deterministic, anti-gaming grading of one diff.

Fresh history-free workspace as the HARNESS user, offline, pristine (harness-only) Gradle home:
apply the diff (plain `git apply`, no 3-way) -> revert touched test paths -> restore protected
build paths and build files gold.patch does not touch -> apply test.patch -> run F2P + P2P per
module (cleanTest, fresh JUnit with `time`) -> one-shot re-run of failing P2P in a fresh
workspace (flaky_p2p) -> resolved / regressions / secondary metrics -> grade.json.
The grader reads gold.patch only for the protected-path exception and scope_creep.
"""
from __future__ import annotations

import json
import os
import shutil
import time
from pathlib import Path

from abb import paths
from abb.config import RepoConfig, TaskConfig, load_limits, load_repo, load_task
from abb.harness import diffscope, gradle, junit
from abb.harness.env import gradle_pristine, load_env_lock
from abb.harness.tasks import module_of, patch_files, task_dir, tree
from abb.harness.validate import MAIN_COMPILE, TEST_COMPILE, _is_f2p, _selector
from abb.harness.workspace import Workspace
from abb.log import get_logger
from abb.util import stamp, utcnow_iso

log = get_logger("abb.grade")


class _Ctx:
    def __init__(self, t: TaskConfig, repo: RepoConfig, diff: bytes, out_dir: Path):
        self.t, self.repo, self.diff, self.out_dir = t, repo, diff, out_dir
        self.gold = (task_dir(t.id) / t.gold_patch).read_text(encoding="utf-8", errors="replace")
        self.gold_files = set(patch_files(self.gold))
        self.timeout_s = load_limits().default.grade_timeout_minutes * 60


def _prepare(ctx: _Ctx, label: str) -> tuple[Workspace, dict]:
    """Fresh workspace, agent diff applied, resets done, test.patch applied. Returns (ws, flags)."""
    t, repo = ctx.t, ctx.repo
    ws = Workspace(repo, paths.work_dir() / "grade" / f"{stamp()}-{t.id}-{label}", "none")
    ws.snapshot(t.base_commit)
    flags = {"agent_touched_tests": False, "build_config_changed": False, "build_config_reverted": [],
             "test_config_suspect": False, "reverted_test_paths": [], "patch_apply_failed": False}
    text = ctx.diff.decode("utf-8", errors="replace")
    if ctx.diff.strip():
        pf = ws.dirs.root / "agent.diff"
        pf.write_bytes(ctx.diff)
        r = ws.git("apply", "--index", "--whitespace=nowarn", str(pf), check=False)
        if r.exit_code != 0:
            flags["patch_apply_failed"] = True
            flags["apply_error"] = r.stderr()[-500:]
            return ws, flags
    changed = [p for p in patch_files(text) if diffscope.classify(p, repo) != "excluded"]
    tests = [p for p in changed if diffscope.classify(p, repo) == "test"]
    builds = [p for p in changed if diffscope.classify(p, repo) in ("protected_build", "build_config")]
    for p in tests:
        _restore(ws, p)
    flags["agent_touched_tests"] = bool(tests)
    flags["reverted_test_paths"] = tests
    flags["build_config_changed"] = bool(builds)
    reverted = [p for p in builds if p not in ctx.gold_files]
    for p in reverted:
        _restore(ws, p)
    flags["build_config_reverted"] = reverted
    surviving = {p for p in builds if p in ctx.gold_files}
    flags["test_config_suspect"] = bool(diffscope.suspect_test_config(text, repo, surviving))
    tp = task_dir(t.id) / t.test_patch
    if not ws.apply_patch(tp):
        flags["test_patch_apply_failed"] = True
    return ws, flags


def _restore(ws: Workspace, path: str) -> None:
    exists = ws.git("cat-file", "-e", f"base:{path}", check=False).exit_code == 0
    if exists:
        ws.git("checkout", "base", "--", path)
    else:
        target = ws.dirs.work / path
        if target.exists():
            target.unlink()
        ws.git("rm", "-q", "--cached", "--ignore-unmatch", "--", path, check=False)


def _run(ctx: _Ctx, ws: Workspace, module: str, selectors: list[str] | None, label: str) -> dict:
    repo = ctx.repo
    env = gradle.harness_gradle_env(repo, guh=gradle_pristine(repo), home=ws.dirs.home)
    out = ws.dirs.root / "grade-logs" / label
    started = time.time()
    r = gradle.run(gradle.expand_cmd("{gradlew}", ws.dirs.work) + gradle.test_args(repo, module, selectors),
                   src=ws.dirs.work, env=env, out_dir=out, timeout_s=ctx.timeout_s, memory_mb=10240)
    text = r.stdout() + "\n" + r.stderr()
    jdir = gradle.junit_dir(repo, ws.dirs.work, module)
    fresh = [p for p in jdir.glob("TEST-*.xml") if p.stat().st_mtime >= started - 1]
    jr = junit.JUnitResult()
    for p in fresh:
        junit.parse_file(p, jr)
    no_tests = "No tests found for given includes" in text
    return {"module": module, "exit_code": r.exit_code, "timed_out": r.stopped_by_harness, "tests": jr.tests,
            "times_ok": jr.times_ok, "fresh_xml": len(fresh), "no_tests_found": no_tests,
            "test_compile_failed": bool(TEST_COMPILE.search(text)), "main_compile_failed": bool(MAIN_COMPILE.search(text)),
            "offline_failures": gradle.offline_failures(text), "log": str(out), "junit_dir": str(jdir),
            "duration_s": r.duration_s}


def _p2p_scope(t: TaskConfig) -> dict[str, dict]:
    """module -> {"whole": bool, "classes": set} from pass_to_pass."""
    s: dict[str, dict] = {}
    for e in t.pass_to_pass:
        m = s.setdefault(e.module, {"whole": False, "classes": set()})
        if e.test:
            m["classes"].add(e.test)
        else:
            m["whole"] = True
    return s


def _run_all(ctx: _Ctx, ws: Workspace, label: str, only: dict[str, list[str]] | None = None) -> dict[str, dict]:
    t = ctx.t
    scope = _p2p_scope(t)
    mods = sorted({e.module for e in t.fail_to_pass} | set(scope))
    res = {}
    for m in mods:
        if only is not None:
            if m not in only:
                continue
            sel = only[m]
        elif scope.get(m, {}).get("whole"):
            sel = None
        else:
            sel = sorted({_selector(e) for e in t.fail_to_pass if e.module == m} | scope.get(m, {}).get("classes", set()))
        res[m] = _run(ctx, ws, m, sel, f"{label}-{m.strip(':').replace(':', '_') or 'root'}")
    return res


def _p2p_failures(t: TaskConfig, runs: dict[str, dict]) -> tuple[list[str], dict[str, str]]:
    """Failing P2P test ids (whole-module entries restricted to validation.p2p_stable) + per-entry status."""
    stable = set(t.validation.p2p_stable) if t.validation and t.validation.p2p_stable else None
    scope = _p2p_scope(t)
    failing: list[str] = []
    entries: dict[str, str] = {}
    for m, sc in scope.items():
        mr = runs.get(m)
        tests = (mr or {}).get("tests") or {}
        bad = []
        for tid, st in tests.items():
            if _is_f2p(tid, t.fail_to_pass):
                continue
            cls = tid.rsplit(".", 1)[0]
            in_class = any(cls == c or cls.startswith(c + "$") for c in sc["classes"])
            in_whole = sc["whole"] and (stable is None or tid in stable)
            if (in_class or in_whole) and st not in ("passed", "skipped"):
                bad.append(tid)
        failing += bad
        for c in sorted(sc["classes"]):
            entries[c] = "failed" if any(b.rsplit(".", 1)[0] == c for b in bad) else ("passed" if mr else "missing")
        if sc["whole"]:
            entries[m] = "failed" if bad else ("passed" if mr else "missing")
    return sorted(set(failing)), entries


def grade(task_id: str, diff_path: Path | None, *, out_dir: Path | None = None) -> dict:
    t = load_task(task_id)
    repo = load_repo(t.repo)
    diff = diff_path.read_bytes() if diff_path and diff_path.exists() else b""
    out_dir = out_dir or (paths.work_dir() / "grade-out" / f"{stamp()}-{task_id}")
    out_dir.mkdir(parents=True, exist_ok=True)
    ctx = _Ctx(t, repo, diff, out_dir)
    t0 = time.monotonic()
    result: dict = {"task_id": task_id, "resolved": False, "build_ok": True, "reason": None, "f2p": {}, "p2p": {},
                    "regressions": [], "flaky_p2p": [], "flags": {}, "diff_stats": {}, "scope_creep": {},
                    "lint_delta": None, "interface_candidate": False,
                    "env_fingerprint": (load_env_lock().get(t.repo) or {}).get("fingerprint")}
    ws, flags = _prepare(ctx, "main")
    result["flags"] = flags
    workspaces = [ws]
    try:
        if flags.get("patch_apply_failed"):
            result.update(build_ok=False, reason="patch_apply_failed")
            return _finish(ctx, result, t0, workspaces)
        if flags.get("test_patch_apply_failed"):
            result.update(build_ok=False, reason="test_patch_apply_failed")
            return _finish(ctx, result, t0, workspaces)
        runs = _run_all(ctx, ws, "grade")
        _copy_artifacts(runs, out_dir)
        # build status
        if any(r["offline_failures"] for r in runs.values()):
            result.update(build_ok=False, reason="env_incomplete")
        elif any(r["timed_out"] for r in runs.values()):
            result.update(build_ok=False, reason="grade_timeout")
        elif any(r["main_compile_failed"] for r in runs.values()):
            result.update(build_ok=False, reason="build_failed")
        elif any(r["test_compile_failed"] for r in runs.values()):
            result.update(build_ok=True, reason="test_compile_failed")
        elif any(r["exit_code"] != 0 and r["fresh_xml"] == 0 and not r["no_tests_found"] for r in runs.values()):
            result.update(build_ok=False, reason="build_failed")
        # F2P
        for e in t.fail_to_pass:
            mr = runs.get(e.module) or {}
            st = junit.JUnitResult(tests=mr.get("tests") or {}).status_of(e.test, e.method)
            if st is not None and not mr.get("times_ok", True):
                st = "error"  # stale or forged XML: every F2P testcase must carry a time attribute
            result["f2p"][_selector(e)] = st or "missing"
        # P2P + flakiness guard
        failing, entries = _p2p_failures(t, runs)
        result["p2p"] = entries
        if failing and result["build_ok"] and result["reason"] is None:
            ws2, _ = _prepare(ctx, "rerun")
            workspaces.append(ws2)
            only: dict[str, list[str]] = {}
            for tid in failing:
                m = next((mm for mm, r in runs.items() if tid in (r.get("tests") or {})), None)
                if m:
                    only.setdefault(m, []).append(tid)
            reruns = _run_all(ctx, ws2, "rerun", only=only)
            passed_now = {tid for r in reruns.values() for tid, st in (r.get("tests") or {}).items() if st == "passed"}
            result["flaky_p2p"] = sorted(set(failing) & passed_now)
            failing = sorted(set(failing) - passed_now)
        result["regressions"] = failing
        result["resolved"] = (result["build_ok"] and result["reason"] is None
                              and all(s == "passed" for s in result["f2p"].values()) and not failing)
        # secondary metrics on what survives the resets
        text = diff.decode("utf-8", errors="replace")
        kept = "".join(sec for p, sec in diffscope.patch_sections(text).items()
                       if diffscope.classify(p, repo) == "source"
                       or (diffscope.classify(p, repo) in ("protected_build", "build_config") and p in ctx.gold_files))
        stats = diffscope.diff_stats(kept)
        trs = set(tree(repo, t.base_commit))
        stats["modules"] = sorted({module_of(p, trs) for p in stats["paths"]})
        gold_mods = {module_of(p, trs) for p in ctx.gold_files}
        outside = [p for p in stats["paths"] if module_of(p, trs) not in gold_mods]
        result["diff_stats"] = {k: stats[k] for k in ("files", "insertions", "deletions", "modules")}
        result["scope_creep"] = {"files_outside_gold_modules": len(outside), "paths": outside}
        f2p_mods = {e.module for e in t.fail_to_pass}
        result["interface_candidate"] = (result["reason"] == "test_compile_failed" and bool(stats["paths"])
                                         and bool(set(stats["modules"]) & f2p_mods))
        return _finish(ctx, result, t0, workspaces)
    except Exception:
        for w in workspaces:
            w.cleanup()
        raise


def _copy_artifacts(runs: dict[str, dict], out_dir: Path) -> None:
    jd = out_dir / "junit"
    jd.mkdir(exist_ok=True)
    logs = []
    for m, r in runs.items():
        for p in Path(r["junit_dir"]).glob("TEST-*.xml"):
            shutil.copy2(p, jd / p.name)
        for f in ("stdout.txt", "stderr.txt"):
            lp = Path(r["log"]) / f
            if lp.exists():
                logs.append(f"===== {m} {f}\n" + lp.read_text(encoding="utf-8", errors="replace"))
    (out_dir / "gradle.log").write_text("\n".join(logs), encoding="utf-8")


def _finish(ctx: _Ctx, result: dict, t0: float, workspaces: list[Workspace]) -> dict:
    result["grade_duration_s"] = round(time.monotonic() - t0, 1)
    result["graded_at"] = utcnow_iso()
    tmp = ctx.out_dir / "grade.json.tmp"
    tmp.write_text(json.dumps(result, indent=2), encoding="utf-8")
    os.replace(tmp, ctx.out_dir / "grade.json")
    for w in workspaces:
        left = w.cleanup()
        if left:
            log.warning("grade workspace leftovers: %d", len(left))
    return result
