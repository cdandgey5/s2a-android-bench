"""Phase 6 steps 13 + gate: one dev task through `s2a run` as the sandbox user, stopped during implement,
then `s2a resume` — through the same launch path, environment block, proxy and map setup as a real
S2A trial (abb/arms/s2a). Writes everything under <results>/<run_id>/e2e/ and prints a summary.

    .venv\\Scripts\\python.exe scripts\\s2a_e2e.py --task antennapod-0001 [--no-interrupt] [--grade]

The interrupt is the harness's own (the STOP file the launcher turns into Ctrl+C): once one implement
task is done and the next is running, or after --after-s seconds of a single running task.
"""
from __future__ import annotations

import argparse
import json
import threading
import time
from pathlib import Path

from abb.arms.base import Limits
from abb.arms.registry import get_arm
from abb.arms.s2a import arm as s2
from abb.config import load_repo, load_task
from abb.harness import grade as grading
from abb.harness.agent_driver import DriverContext, TrialBudget
from abb.harness.proxy import from_sandbox_config
from abb.harness.run import Runner, new_run_id
from abb.harness.tasks import task_dir
from abb.harness.workspace import Workspace
from abb import paths


def watch(state_file: Path, stop_file: Path, after_s: float, done: threading.Event, log: list) -> None:
    started: dict[str, float] = {}
    while not done.is_set():
        time.sleep(3)
        try:
            st = json.loads(state_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        impl = (st.get("stages") or {}).get("implement") or {}
        ts = impl.get("task_status") or {}
        running = [k for k, v in ts.items() if v == "running"]
        for k in running:
            started.setdefault(k, time.monotonic())
        two = any(v == "done" for v in ts.values()) and running
        long = running and time.monotonic() - started[running[0]] >= after_s
        if impl.get("status") == "running" and (two or long):
            stop_file.parent.mkdir(parents=True, exist_ok=True)
            stop_file.write_text("stop", encoding="utf-8")
            log.append({"at": time.time(), "task_status": dict(ts), "why": "one done, next running" if two else
                        f"{running[0]} ran {after_s:.0f}s"})
            return


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", required=True)
    ap.add_argument("--model", default="claude-sonnet-5-5")
    ap.add_argument("--no-interrupt", action="store_true")
    ap.add_argument("--after-s", type=float, default=150.0)
    ap.add_argument("--grade", action="store_true")
    a = ap.parse_args()

    task = load_task(a.task)
    repo = load_repo(task.repo)
    run_id = new_run_id("s2a-e2e")
    runner = Runner(run_id=run_id, label="s2a-e2e", arms=["s2a"], tasks=[a.task], trials=1, model=a.model, grade=False,
                    sandbox="user", allow_env_drift=False, profile=None, task_set=a.task)
    runner.root.mkdir(parents=True, exist_ok=True)
    runner.write_manifest()
    runner.preflight()
    proxy = from_sandbox_config("user", runner.root / "proxy.log")
    proxy.start()
    arm = get_arm("s2a")
    rec = runner.root / "e2e"
    rec.mkdir(parents=True, exist_ok=True)
    summary: dict = {"run_id": run_id, "task": a.task}
    ws = None
    try:
        setup = runner.setup_for(arm, task.repo)
        summary["setup"] = {"reused": setup["reused"], "key": setup["key"]}
        ws = Workspace(repo, paths.work_dir() / run_id / "e2e", "user")
        ws.snapshot(task.base_commit)
        arm.install_setup(ws, setup["artifacts"])
        limits: Limits = runner.limits
        ctx = DriverContext(ws=ws, record_dir=rec, run_dir=runner.root, tag=f"e2e-{a.task}", token=runner.token or "",
                            budget=TrialBudget.start(limits), as_agent=True)
        ticket = (task_dir(a.task) / task.problem_statement).read_text(encoding="utf-8")
        inp = s2.write_inputs(ctx, ticket)
        work = ws.dirs.work
        secs = ctx.budget.seconds_left()
        argv = [str(s2.exe()), "run", "--prompt-file", str(inp["problem"]), "--repo", str(work), "--profile", "android",
                "--model", a.model, "--max-turns", str(limits.max_turns_total), "--max-usd", f"{limits.max_usd:.4f}",
                "--timeout-min", f"{secs / 60:.2f}", "--run-id", s2.RUN_ID, "--append-system-prompt-file",
                str(inp["environment"]), "--map", str(work / ".s2a" / "map.md")]
        rd = work / ".s2a" / "runs" / s2.RUN_ID
        done, log = threading.Event(), []
        if not a.no_interrupt:
            threading.Thread(target=watch, args=(rd / "state.json", ws.dirs.stop_file, a.after_s, done, log),
                             daemon=True).start()
        r1 = s2.invoke(ctx, argv, "s2a-run", secs + 60)
        done.set()
        st1 = s2.read_state(rd) or {}
        summary["first"] = {"exit": r1.exit_code, "stopped_by_harness": r1.stopped_by_harness, "interrupt": log,
                            "state_exit": [st1.get("exit_code"), st1.get("exit_reason")],
                            "task_status": ((st1.get("stages") or {}).get("implement") or {}).get("task_status")}
        names1 = [json.loads(x)["name"] for x in (rd / "calls.jsonl").read_text(encoding="utf-8").splitlines() if x]
        if log:
            ws.dirs.stop_file.unlink(missing_ok=True)
            r2 = s2.invoke(ctx, [str(s2.exe()), "resume", s2.RUN_ID, "--repo", str(work)], "s2a-resume",
                           ctx.budget.seconds_left() + 60)
            st2 = s2.read_state(rd) or {}
            names2 = [json.loads(x)["name"] for x in (rd / "calls.jsonl").read_text(encoding="utf-8").splitlines() if x]
            done_before = [k for k, v in (summary["first"]["task_status"] or {}).items() if v == "done"]
            redone = [n for n in names2[len(names1):] if any(n.startswith(f"implement-{t}") for t in done_before)]
            summary["resume"] = {"exit": r2.exit_code, "state_exit": [st2.get("exit_code"), st2.get("exit_reason")],
                                 "verdict": st2.get("verdict"), "new_calls": names2[len(names1):], "redone": redone,
                                 "task_status": ((st2.get("stages") or {}).get("implement") or {}).get("task_status")}
        r3 = s2.invoke(ctx, [str(s2.exe()), "status", s2.RUN_ID, "--repo", str(work)], "s2a-status", 120)
        summary["status"] = r3.stdout()
        calls = s2.collect_calls(rd, rec, a.model)
        summary["calls"] = len(calls)
        summary["turns"] = sum(c.num_turns for c in calls)
        summary["cost_usd"] = round(sum((c.cost_usd if c.cost_usd is not None else (c.cost_usd_imputed or 0))
                                        for c in calls), 4)
        summary["artifacts"] = sorted(p.name for p in rd.iterdir() if p.is_file())
        s2.copy_artifacts(rd, rec / "artifacts")
        (rec / "diff.patch").write_bytes(ws.diff().encode("utf-8"))
        if a.grade:
            g = grading.grade(a.task, rec / "diff.patch", out_dir=rec)
            summary["grade"] = {"resolved": g["resolved"], "reason": g["reason"]}
    finally:
        proxy.stop()
        (rec / "summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
        if ws is not None:
            ws.cleanup()
    print(json.dumps({k: v for k, v in summary.items() if k != "status"}, indent=2, default=str))
    print(summary.get("status", ""))


if __name__ == "__main__":
    main()
