"""Minimal sequential runner (phases/phase-4 step 5): `abb run --arm A --tasks dev5 --trials 1 --grade`.

Writes the results layout (specs/results-layout.md): manifest.json first, events.jsonl, proxy.log,
<arm>/<task>/t<k>/{run.json, calls.jsonl, transcript/, prompts/, diff.patch, diff.full.patch,
grade.json, metrics.json}, probes/, usage_limited/. A trial is complete iff run.json, diff.patch and
grade.json exist (or run.json + diff.patch without --grade); `--resume <run_id>` skips complete ones.
One slot (abb-agent): strictly sequential until Phase 8 (D-037). On a usage limit the cut attempt is
kept under usage_limited/ and the run stops (aborted_reason: usage_limit); Phase 8 adds the pause loop.
"""
from __future__ import annotations

import hashlib
import json
import os
import platform as _pyplatform
import shutil
import subprocess
from dataclasses import asdict, replace
from datetime import datetime, timezone
from pathlib import Path

from abb import paths
from abb.arms.registry import get_arm
from abb.config import load_limits, load_repo, load_sandbox, load_task, load_toolchain
from abb.harness import auth, grade as grading, metrics
from abb.harness.agent_driver import AbortRun, DriverContext, HarnessError, TrialBudget, phasecall_dict, write_json
from abb.harness.agent_env import preflight
from abb.harness.env import load_env_lock
from abb.harness.platform import get_platform
from abb.harness.proxy import from_sandbox_config
from abb.harness.tasks import task_dir, task_ids
from abb.harness.workspace import Workspace
from abb.harness.setup import SetupError, ensure_setup
from abb.log import get_logger
from abb.util import sha256_file, utcnow_iso

log = get_logger("abb.run")


def resolve_tasks(spec: str) -> list[str]:
    if spec == "dev5":
        ids = [t for t in task_ids("antennapod") if load_task(t).status == "validated"][:6]
        if len(ids) != 6:
            raise SystemExit(f"dev5 needs 6 validated antennapod tasks, found {ids}")
        return ids
    if spec in ("dev", "test"):
        return [t for t in task_ids() if load_task(t).split == spec and load_task(t).status == "validated"]
    return [s.strip() for s in spec.split(",") if s.strip()]


def _split_sha() -> str | None:
    from abb.harness.taskset import split_sha256

    return split_sha256()


def task_set_sha(ids: list[str]) -> str:
    h = hashlib.sha256()
    for tid in ids:
        for f in sorted(p for p in task_dir(tid).iterdir() if p.is_file()):
            h.update(f"{tid}/{f.name}".encode())
            h.update(f.read_bytes())
    return h.hexdigest()


def complete(rec: Path, graded: bool) -> bool:
    need = ["run.json", "diff.patch"] + (["grade.json"] if graded else [])
    return all((rec / n).exists() for n in need)


class Runner:
    def __init__(self, *, run_id: str, label: str, arms: list[str], tasks: list[str], trials: int, model: str,
                 grade: bool, sandbox: str, allow_env_drift: bool, profile: str | None, task_set: str):
        self.run_id, self.label, self.arms, self.tasks, self.trials = run_id, label, arms, tasks, trials
        self.model, self.grade, self.sandbox, self.allow_env_drift = model, grade, sandbox, allow_env_drift
        self.task_set = task_set
        self.profile = profile or ("final" if model.startswith("claude-opus") else "dev")
        self.root = paths.results_dir() / run_id
        self.limits = load_limits().resolve(self.profile, model=model)
        self.token: str | None = None
        self.aborted: str | None = None
        self._setups: dict[tuple[str, str], dict | None] = {}  # (setup_kind, repo) -> ensure_setup() result
        self.env_suspect_streak = 0  # D-043 circuit breaker

    # ---------------------------------------------------------------- manifest / events
    def event(self, **kw) -> None:
        with open(self.root / "events.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps({"at": utcnow_iso(), **kw}, default=str) + "\n")

    def write_manifest(self, **updates) -> None:
        p = self.root / "manifest.json"
        m = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
        if not m:
            lock = load_env_lock()
            authrec = {}
            ap = paths.state_dir() / "auth.json"
            if ap.exists():
                authrec = json.loads(ap.read_text(encoding="utf-8"))
            sha = subprocess.run(["git", "-C", str(paths.repo_clone()), "rev-parse", "HEAD"], capture_output=True,
                                 text=True).stdout.strip()
            tl = paths.config_dir() / "toolchain.lock.yaml"
            m = {
                "run_id": self.run_id, "created_at": utcnow_iso(), "label": self.label, "prereg_sha256": None,
                "arms": self.arms, "task_set": self.task_set, "task_ids": self.tasks,
                "task_set_sha256": task_set_sha(self.tasks), "split_sha256": _split_sha(), "trials": self.trials,
                "limits": asdict(self.limits), "profile": self.profile,
                "agent_version": load_toolchain().claude_code.version, "speckit_version": None, "s2a_git_sha": None,
                "platform": get_platform().id,
                "env_fingerprints": {r: (lock.get(r) or {}).get("fingerprint") for r in sorted({load_task(t).repo for t in self.tasks})},
                "toolchain_lock_sha256": sha256_file(tl) if tl.exists() else None,
                "interrupt": load_sandbox().process.interrupt, "sandbox_mode": self.sandbox,
                "auth_mode": "subscription", "plan": authrec.get("subscriptionType") or "pro",
                "plan_source": authrec.get("plan_source") or "owner (reference/verified.md)",
                "usage_limited_pauses": {}, "strip_agent_instructions": False, "allow_env_drift": self.allow_env_drift,
                "allow_no_canary": None, "harness_git_sha": sha, "split_file_sha256": None, "resumes": [],
                "aborted_reason": None, "finished_at": None,
                "host": {"os": "windows", "release": f"{_pyplatform.release()} {_pyplatform.version()}",
                         "cpus": os.cpu_count(), "mem_gb": 32},
            }
        m.update(updates)
        write_json(p, m)

    # ---------------------------------------------------------------- checks
    def preflight(self) -> None:
        self.token = preflight()
        rec = auth.check()
        if not rec.get("ok"):
            raise SystemExit("abb auth check failed: the token is not accepted (docs/DAY-0.md §3)")
        if self.sandbox == "user":
            user = load_sandbox().modes["user"].run_as
            if not get_platform().as_user_available(user):
                raise SystemExit("sandbox user missing: abb sandbox setup")
            from abb.harness.sandbox import check_fs

            bad = [f"{n}: {d}" for n, ok, d in check_fs(user) if not ok]  # D-043: real attempts as the user
            if bad:
                raise SystemExit("sandbox filesystem check failed (see `abb sandbox check`; lost cache grants "
                                 "come back with `abb sandbox setup --prepare-only`):\n  " + "\n  ".join(bad))
        lock = load_env_lock()
        for tid in self.tasks:
            t = load_task(tid)
            if t.status != "validated":
                raise SystemExit(f"{tid} is {t.status}, not validated")
            cur = (lock.get(t.repo) or {}).get("fingerprint")
            if t.validation and t.validation.env_fingerprint != cur and not self.allow_env_drift:
                raise SystemExit(f"{tid} was validated against {t.validation.env_fingerprint}, environment is {cur}: "
                                 "re-validate or pass --allow-env-drift (recorded)")
        for a in self.arms:
            get_arm(a)

    # ---------------------------------------------------------------- run
    def run(self) -> dict:
        self.root.mkdir(parents=True, exist_ok=True)
        resumed = (self.root / "manifest.json").exists()
        self.write_manifest()
        if resumed:
            m = json.loads((self.root / "manifest.json").read_text(encoding="utf-8"))
            self.write_manifest(resumes=m.get("resumes", []) + [{"at": utcnow_iso(), "reason": "--resume"}],
                                aborted_reason=None)
        self.preflight()
        stale = paths.work_dir() / self.run_id  # a killed harness leaves a live trial open to the sandbox user (D-037)
        if stale.exists():
            # keep the verbatim streams of the interrupted processes first: they exist only in agent-out/
            for so in stale.glob("*/*/t*/agent-out/*/stdout.txt"):
                trial = so.parents[2]
                dst = self.root / trial.relative_to(stale) / "transcript" / f"{so.parent.name}.salvaged.jsonl"
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(so, dst)
                self.event(event="stream_salvaged", file=str(dst.relative_to(self.root)), bytes=so.stat().st_size)
            left = get_platform().rmtree_robust(stale)
            self.event(event="stale_workspaces_removed", path=str(stale), leftovers=len(left))
            if left:
                raise SystemExit(f"could not delete stale workspaces under {stale} ({len(left)} leftovers)")
        self.event(event="run_start", arms=self.arms, tasks=self.tasks, trials=self.trials, model=self.model)
        proxy = from_sandbox_config("user", self.root / "proxy.log")
        proxy.start()
        try:
            for tid in self.tasks:
                for arm in self.arms:
                    for k in range(1, self.trials + 1):
                        if self.aborted:
                            break
                        self.trial(arm, tid, k)
        except BaseException as e:  # a harness crash must not end as a clean run (resume with --resume)
            self.aborted = self.aborted or f"harness_crash: {type(e).__name__}: {str(e)[:200]}"
            raise
        finally:
            proxy.stop()
            self.write_manifest(finished_at=utcnow_iso(), aborted_reason=self.aborted)
            self.event(event="run_end", aborted_reason=self.aborted)
        return {"run_id": self.run_id, "aborted_reason": self.aborted}

    def setup_for(self, arm, repo_key: str) -> dict | None:
        """One-time setup per (setup kind, repo), cached across runs (abb/harness/setup.py)."""
        key = (arm.setup_kind, repo_key)
        if key not in self._setups:
            self.event(event="setup_start", setup_kind=arm.setup_kind, repo=repo_key)
            holder: dict = {}

            def make_context(a, rk: str, rec_dir: Path):
                repo = load_repo(rk)
                root = paths.work_dir() / self.run_id / "_setup" / a.setup_kind / rk
                if root.exists():
                    get_platform().rmtree_robust(root)
                ws = Workspace(repo, root, self.sandbox)  # type: ignore[arg-type]
                ws.snapshot(repo.build.setup_commit)
                rec_dir.mkdir(parents=True, exist_ok=True)
                ctx = DriverContext(ws=ws, record_dir=rec_dir, run_dir=self.root, tag=f"setup-{a.setup_kind}-{rk}",
                                    token=self.token or "", budget=TrialBudget.start(replace(self.limits, **a.setup_limits())),
                                    as_agent=self.sandbox == "user")
                holder["ctx"] = ctx
                return ws, ctx

            try:
                res = ensure_setup(arm, repo_key, self.root, run_id=self.run_id, make_context=make_context)
            finally:
                for ev in (holder["ctx"].events if "ctx" in holder else []):
                    self.event(**ev)
            self._setups[key] = res
            self.event(event="setup_end", setup_kind=arm.setup_kind, repo=repo_key, reused=res["reused"] if res else None,
                       cache_key=res["key"] if res else None)
        return self._setups[key]

    def trial(self, arm_name: str, tid: str, k: int, attempt: int = 1) -> None:
        rec = self.root / arm_name / tid / f"t{k}"
        if complete(rec, self.grade):
            self.event(event="trial_skip", arm=arm_name, task=tid, trial=k, reason="complete")
            return
        if rec.exists() and not (rec / "run.json").exists():
            shutil.rmtree(rec)
        task = load_task(tid)
        repo = load_repo(task.repo)
        if not (rec / "run.json").exists():
            rec.mkdir(parents=True, exist_ok=True)
            trial_root = paths.work_dir() / self.run_id / arm_name / tid / f"t{k}"
            if trial_root.exists():
                get_platform().rmtree_robust(trial_root)
            ws = Workspace(repo, trial_root, self.sandbox)  # type: ignore[arg-type]
            ws.snapshot(task.base_commit)
            budget = TrialBudget.start(self.limits)
            ctx = DriverContext(ws=ws, record_dir=rec, run_dir=self.root, tag=f"{arm_name}-{tid}-t{k}",
                                token=self.token or "", budget=budget, as_agent=self.sandbox == "user")
            arm = get_arm(arm_name)
            if getattr(arm, "setup_kind", None):
                try:
                    setup = self.setup_for(arm, task.repo)
                except SetupError as e:
                    self.event(event="setup_failed", arm=arm_name, repo=task.repo, subtype=e.subtype, error=str(e)[:300])
                    self.aborted = "usage_limit" if e.subtype == "usage_limited" else "setup_failed"
                    ws.cleanup()
                    shutil.rmtree(rec, ignore_errors=True)
                    return
                arm.install_setup(ws, setup["artifacts"])
            ticket = (task_dir(tid) / task.problem_statement).read_text(encoding="utf-8")
            arm_task = task.model_copy(update={"test_patch": None, "gold_patch": None})
            self.event(event="trial_start", arm=arm_name, task=tid, trial=k, attempt=attempt)
            started = utcnow_iso()
            try:
                rr = arm.run(arm_task, ws, self.limits, ctx=ctx, ticket=ticket, trial=k)
            except HarnessError as e:
                self.event(event="harness_error", arm=arm_name, task=tid, trial=k, attempt=attempt, error=str(e)[:500])
                ws.cleanup()
                shutil.rmtree(rec, ignore_errors=True)
                if attempt == 1:
                    return self.trial(arm_name, tid, k, attempt=2)
                (rec).mkdir(parents=True, exist_ok=True)
                write_json(rec / "run.json", {"arm": arm_name, "task_id": tid, "trial": k, "exit_reason": "harness_error",
                                             "error": str(e)[:2000], "calls": []})
                (rec / "diff.patch").write_bytes(b"")
                return
            except AbortRun as e:
                self.aborted = e.reason
                self.event(event="abort", reason=e.reason, detail=e.detail[:500])
                ws.cleanup()
                shutil.rmtree(rec, ignore_errors=True)
                return
            finally:
                for ev in ctx.events:
                    self.event(**ev)
            ws.cleanup()
            data = asdict(rr)
            data["calls"] = [phasecall_dict(c) for c in rr.calls]
            data.update(diff_path=str(rr.diff_path), transcript_dir=str(rr.transcript_dir), started_at=started,
                        finished_at=utcnow_iso(), limits=asdict(self.limits), attempt=attempt,
                        budget_left={"turns": budget.turns_left, "usd": round(budget.usd_left, 4),
                                     "seconds": budget.seconds_left()})
            write_json(rec / "run.json", data)
            with open(rec / "calls.jsonl", "w", encoding="utf-8") as f:
                for c in data["calls"]:
                    f.write(json.dumps(c, default=str) + "\n")
            self.event(event="trial_end", arm=arm_name, task=tid, trial=k, exit_reason=rr.exit_reason,
                       turns=rr.num_turns, cost_usd=rr.cost_usd, duration_ms=rr.duration_ms)
            builds = metrics._agent_builds(rec)
            if builds["agent_env_errors"] and not builds["agent_gradle_ok"]:
                # the agent's Gradle never succeeded and hit offline-resolution/cache-access errors: an
                # agent can cause that itself, two trials in a row is the environment (D-043)
                self.env_suspect_streak += 1
                self.event(event="env_suspect", arm=arm_name, task=tid, trial=k, streak=self.env_suspect_streak, **builds)
                if self.env_suspect_streak >= 2:
                    self.aborted = "env_suspect"
            else:
                self.env_suspect_streak = 0
            if rr.exit_reason == "usage_limited":
                n = 1
                while (self.root / "usage_limited" / arm_name / tid / f"t{k}-a{n}").exists():
                    n += 1
                dst = self.root / "usage_limited" / arm_name / tid / f"t{k}-a{n}"
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(rec), str(dst))
                pauses = json.loads((self.root / "manifest.json").read_text(encoding="utf-8")).get("usage_limited_pauses", {})
                pauses[arm_name] = pauses.get(arm_name, 0) + 1
                self.write_manifest(usage_limited_pauses=pauses)
                self.aborted = "usage_limit"
                return
        if self.grade and not (rec / "grade.json").exists():
            r = grading.grade(tid, rec / "diff.patch", out_dir=rec)
            metrics.build(rec, run_id=self.run_id, arm=arm_name, task_id=tid, trial=k)
            self.event(event="graded", arm=arm_name, task=tid, trial=k, resolved=r["resolved"], reason=r["reason"])


def new_run_id(label: str) -> str:
    return f"{datetime.now(timezone.utc):%Y%m%d-%H%M}-{label}"
