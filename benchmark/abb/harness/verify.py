"""`abb env verify <repo>` (phases/phase-1-environments.md step 4).

Fresh history-free workspace at cache_commit, the repo's verify_modules unit tests run OFFLINE
(proxy stopped; as the sandbox user, the firewall proves it) with a freshly seeded gradle-home,
once without and once with seeded transforms; then each of the repo's seed/draft tasks: hidden
test at base must fail, with gold.patch must pass.
"""
from __future__ import annotations

import json
import time

from abb import paths
from abb.config import load_repo, load_sandbox, load_task
from abb.harness import gradle, junit
from abb.harness.workspace import Workspace
from abb.log import get_logger
from abb.util import stamp, utcnow_iso

log = get_logger("abb.verify")


def _run_modules(ws: Workspace, modules: list[str], *, as_agent: bool, label: str, tests: list[str] | None = None,
                 clean: bool = False) -> dict:
    env = ws.agent_env(None, proxy=True)  # the proxy is NOT running: any network attempt fails
    args = ["--offline", "--console=plain", "--continue", "--no-daemon"]
    for m in modules:
        if clean:
            args.append(f"{m}:cleanTest")
        args.append(f"{m}:{ws.repo.tests.task_for(m)}")
    for t in tests or []:
        args += ["--tests", t]
    out = ws.dirs.agent_out / f"verify-{label}"  # agent-writable: the launcher runs as the sandbox user
    t0 = time.monotonic()
    r = ws.exec(gradle.expand_cmd("{gradlew}", ws.dirs.work) + args, env=env, timeout_s=3600, out_dir=out,
                as_agent=as_agent)
    wall = round(time.monotonic() - t0, 1)
    text = r.stdout() + "\n" + r.stderr()
    per = {}
    for m in modules:
        jr = junit.parse_dir(gradle.junit_dir(ws.repo, ws.dirs.work, m))
        per[m] = {**jr.counts(), "times_ok": jr.times_ok,
                  "failed": [k for k, v in jr.tests.items() if v in ("failed", "error")][:20]}
    return {"label": label, "exit_code": r.exit_code, "wall_s": wall, "peak_memory_mb": r.peak_memory_mb,
            "job_memory_hit": r.job_memory_hit, "offline_failures": gradle.offline_failures(text),
            "build_successful": "BUILD SUCCESSFUL" in text, "modules": per, "log": str(out)}


def verify(key: str, *, sandbox: str = "user", transforms: str = "both", keep: bool = False) -> dict:
    repo = load_repo(key)
    as_agent = sandbox == "user"
    variants = {"both": [False, True], "off": [False], "on": [True]}[transforms]
    report: dict = {"repo": key, "sandbox": sandbox, "at": utcnow_iso(), "cache_commit": repo.build.cache_commit,
                    "runs": [], "seed_tasks": []}
    for st in variants:
        ws = Workspace(repo, paths.work_dir() / "verify" / f"{stamp()}-{key}-{'tf' if st else 'notf'}", sandbox)  # type: ignore[arg-type]
        t0 = time.monotonic()
        ws.snapshot(repo.build.cache_commit, seed_transforms=st)
        snap_s = round(time.monotonic() - t0, 1)
        run = _run_modules(ws, repo.tests.verify_modules, as_agent=as_agent, label="verify")
        run.update(seed_transforms=st, snapshot_s=snap_s, trial_dir=str(ws.dirs.root))
        report["runs"].append(run)
        log.info("verify %s transforms=%s: exit %s, %.0fs, %s", key, st, run["exit_code"], run["wall_s"],
                 {m: (v["total"], v["passed"]) for m, v in run["modules"].items()})
        if not keep:
            run["leftovers"] = len(ws.cleanup())
    for p in sorted(paths.tasks_dir().glob("*/task.yaml")):
        if p.parent.name.startswith("_"):
            continue
        t = load_task(p.parent.name)
        if t.repo != key or t.status == "dropped":
            continue
        d = paths.tasks_dir() / t.id
        ws = Workspace(repo, paths.work_dir() / "verify" / f"{stamp()}-{t.id}", sandbox)  # type: ignore[arg-type]
        ws.snapshot(t.base_commit, seed_transforms=load_sandbox().process.seed_transforms)
        mods = sorted({e.module for e in t.fail_to_pass})
        sel = [e.test + (f".{e.method}" if e.method else "") for e in t.fail_to_pass]
        rec: dict = {"task": t.id}
        if not ws.apply_patch(d / t.test_patch):
            rec["error"] = "test.patch does not apply"
        else:
            v1 = _run_modules(ws, mods, as_agent=as_agent, label="v1", tests=sel, clean=True)
            if not ws.apply_patch(d / t.gold_patch):
                rec["error"] = "gold.patch does not apply"
            v2 = _run_modules(ws, mods, as_agent=as_agent, label="v2", tests=sel, clean=True)

            def f2p_status(run: dict) -> list[str | None]:
                res = []
                for e in t.fail_to_pass:
                    jr = junit.parse_dir(gradle.junit_dir(repo, ws.dirs.work, e.module))
                    res.append(jr.status_of(e.test, e.method))
                return res

            rec.update(v1_exit=v1["exit_code"], v2_exit=v2["exit_code"], v1_offline_failures=v1["offline_failures"],
                       v2_offline_failures=v2["offline_failures"])
            # JUnit files are rewritten by v2; v1 status comes from its own counts
            rec["v1_failed"] = [k for m in v1["modules"].values() for k in m["failed"]]
            rec["v2_f2p"] = f2p_status(v2)
            # D-020: on a new_surface task the hidden tests may not compile at base (v1 fails with no failed test)
            rec["v1_test_compile_failed"] = bool(t.tags.new_surface and v1["exit_code"] and not rec["v1_failed"])
            rec["fail_to_pass_ok"] = ((bool(rec["v1_failed"]) or rec["v1_test_compile_failed"])
                                      and all(s == "passed" for s in rec["v2_f2p"]))
        report["seed_tasks"].append(rec)
        log.info("seed task %s: %s", t.id, rec)
        if not keep:
            ws.cleanup()
    out = paths.state_dir() / f"env-verify-{key}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    report["report_file"] = str(out)
    return report


def verdict(report: dict) -> tuple[bool, list[str]]:
    msgs, ok = [], True
    for r in report["runs"]:
        tag = f"seed_transforms={r['seed_transforms']}"
        tests = sum(m["total"] for m in r["modules"].values())
        passed = sum(m["passed"] for m in r["modules"].values())
        good = r["exit_code"] == 0 and r["build_successful"] and not r["offline_failures"] and tests > 0 \
            and r["wall_s"] < 600 and not r["job_memory_hit"]
        ok &= good
        msgs.append(f"{'OK  ' if good else 'FAIL'} tests {passed}/{tests} passed, wall {r['wall_s']:.0f}s "
                    f"(+{r['snapshot_s']:.0f}s snapshot), peak {r['peak_memory_mb']} MB, offline: "
                    f"{'OK' if not r['offline_failures'] else r['offline_failures']} [{tag}]")
    for s in report["seed_tasks"]:
        good = bool(s.get("fail_to_pass_ok")) and not s.get("error")
        ok &= good
        msgs.append(f"{'OK  ' if good else 'FAIL'} seed task {s['task']}: base+test fails {s.get('v1_failed')}, "
                    f"+gold F2P {s.get('v2_f2p')} {s.get('error') or ''}")
    return ok, msgs
