"""Verifier calibration (phases/phase-6-s2a-orchestrator.md step 18): re-run s2a's verify stage on finished
dev trials and compare the verdict with the grade. Per trial: a fresh sandbox workspace at the task's base,
the trial's full diff applied, its .s2a run artifacts and the cached map restored, then `s2a verify trial`
as the sandbox user. Dev tasks only (refuses split: test under ABB_TUNING=1, like every tuning tool).

    $env:ABB_TUNING=1; .venv\\Scripts\\python.exe scripts\\verify_calibration.py <run_id>/<arm>/<task>/t<k> ...
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

from abb import paths
from abb.arms.base import Limits
from abb.arms.registry import get_arm
from abb.arms.s2a import arm as s2
from abb.config import load_repo, load_task
from abb.harness.agent_driver import DriverContext, TrialBudget
from abb.harness.proxy import from_sandbox_config
from abb.harness.run import Runner, new_run_id
from abb.harness.tasks import refuse_held_out_while_tuning
from abb.harness.workspace import Workspace
from abb.util import stamp

KEEP = ("state.json", "ticket.md", "locate.md", "spec.md", "plan.md", "plan.json", "progress.md")


def main() -> None:
    specs = sys.argv[1:]
    trials = [(Path(s).parts[0], Path(s).parts[1], Path(s).parts[2], int(Path(s).parts[3][1:])) for s in specs]
    refuse_held_out_while_tuning(sorted({t[2] for t in trials}))
    run_id = new_run_id("verify-calibration")
    runner = Runner(run_id=run_id, label="verify-calibration", arms=["s2a"], tasks=sorted({t[2] for t in trials}),
                    trials=1, model="claude-sonnet-5-5", grade=False, sandbox="user", allow_env_drift=False,
                    profile=None, task_set="calibration", parallel=2)
    runner.root.mkdir(parents=True, exist_ok=True)
    runner.write_manifest()
    runner.preflight()
    proxy = from_sandbox_config("user", runner.root / "proxy.log")
    proxy.start()
    arm = get_arm("s2a")
    out = []
    try:
        for src_run, arm_name, tid, k in trials:
            rec_src = paths.results_dir() / src_run / arm_name / tid / f"t{k}"
            task, repo = load_task(tid), load_repo(load_task(tid).repo)
            setup = runner.setup_for(arm, task.repo)
            name = f"{src_run}-{arm_name}-{tid}-t{k}"
            rec = runner.root / name
            rec.mkdir(parents=True, exist_ok=True)
            ws = Workspace(repo, paths.work_dir() / run_id / name, "user", run_as=runner.slot_user(2))  # slot 2: never the validation user
            try:
                ws.snapshot(task.base_commit)
                arm.install_setup(ws, setup["artifacts"])
                patch = rec_src / "diff.full.patch"
                if patch.stat().st_size and not ws.apply_patch(patch):
                    raise RuntimeError(f"{name}: diff.full.patch does not apply")
                rd = ws.dirs.work / ".s2a" / "runs" / s2.RUN_ID
                rd.mkdir(parents=True, exist_ok=True)
                for f in KEEP:
                    if (rec_src / "artifacts" / f).exists():
                        shutil.copyfile(rec_src / "artifacts" / f, rd / f)
                if (rec_src / "artifacts" / "repro").exists():
                    shutil.copytree(rec_src / "artifacts" / "repro", rd / "repro", dirs_exist_ok=True)
                st = json.loads((rd / "state.json").read_text(encoding="utf-8"))
                old = st.get("verdict")
                st["base_commit"] = ws.git("rev-parse", "base").stdout().strip()
                st["branch"] = "s2a/calibration"
                st["exit_code"], st["exit_reason"] = None, None
                (rd / "state.json").write_text(json.dumps(st, indent=2), encoding="utf-8")
                ctx = DriverContext(ws=ws, record_dir=rec, run_dir=runner.root, tag=name, token=runner.token or "",
                                    budget=TrialBudget.start(Limits()), as_agent=True)
                r = s2.invoke(ctx, [str(s2.exe()), "verify", s2.RUN_ID, "--repo", str(ws.dirs.work),
                                    "--note", "verifier calibration"], "s2a-verify", 30 * 60)
                new = (s2.read_state(rd) or {}).get("verdict")
                calls = s2.collect_calls(rd, rec, "claude-sonnet-5-5")
                n = len(json.loads((rec_src / "artifacts" / "state.json").read_text(encoding="utf-8"))["stages"]
                        .get("verify", {}).get("rounds") or [])
                verify_calls = [c for c in calls if c.name.startswith("verify")][n:] if len(calls) > n else calls
                for f in rd.glob("verify-*.md"):
                    shutil.copyfile(f, rec / f.name)
                g = json.loads((rec_src / "grade.json").read_text(encoding="utf-8"))
                row = {"trial": f"{src_run}/{arm_name}/{tid}/t{k}", "resolved": bool(g.get("resolved")),
                       "old_verdict": old, "new_verdict": new, "exit": r.exit_code,
                       "cost_usd": round(sum((c.cost_usd or c.cost_usd_imputed or 0) for c in verify_calls), 4)}
            except Exception as e:  # noqa: BLE001 - one bad trial must not lose the others
                row = {"trial": f"{src_run}/{arm_name}/{tid}/t{k}", "error": str(e)[:300]}
            finally:
                ws.cleanup()
            out.append(row)
            print(json.dumps(row), flush=True)
    finally:
        proxy.stop()
    ok_old = sum(1 for r in out if "error" not in r and (r["old_verdict"] == "ACCEPT") == r["resolved"])
    ok_new = sum(1 for r in out if "error" not in r and (r["new_verdict"] == "ACCEPT") == r["resolved"])
    n = sum(1 for r in out if "error" not in r)
    summary = {"run_id": run_id, "trials": out, "agree_old": f"{ok_old}/{n}", "agree_new": f"{ok_new}/{n}",
               "at": stamp()}
    (runner.root / "calibration.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k != "trials"}))


if __name__ == "__main__":
    main()
