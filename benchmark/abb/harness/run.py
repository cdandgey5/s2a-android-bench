"""The runner (phases/phase-8-runner.md): `abb run --arm A [--arm B] --tasks dev5|dev|test|all|<ids> --trials k
--parallel n [--max-usd X] [--grade] [--resume <run_id>]`.

Writes the results layout (specs/results-layout.md): manifest.json first, events.jsonl, proxy.log,
<arm>/<task>/t<k>/{run.json, calls.jsonl, transcript/, prompts/, diff.patch, diff.full.patch,
grade.json, metrics.json}, probes/, usage_limited/. A trial is complete iff run.json, diff.patch and
grade.json exist (or run.json + diff.patch without --grade); `--resume <run_id>` skips complete ones and
re-runs partial ones from scratch. Trials run on `--parallel` workers (abb/harness/scheduler.py); worker k
runs as sandbox slot user k (D-037). A usage-limited attempt is kept under usage_limited/, the trial is
re-queued and every worker pauses until the window resets and a probe succeeds (D-028).
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import threading
from dataclasses import asdict, replace
from datetime import datetime, timezone
from pathlib import Path

from abb import paths
from abb.arms.registry import get_arm
from abb.config import load_limits, load_repo, load_task
from abb.harness import auth, grade as grading, metrics
from abb.harness.agent_driver import AbortRun, DriverContext, HarnessError, TrialBudget, phasecall_dict, write_json
from abb.harness.agent_env import preflight
from abb.harness.costmeter import CostMeter
from abb.harness.env import load_env_lock
from abb.harness.manifest import Manifest, initial_shas
from abb.harness.platform import get_platform
from abb.harness.proxy import from_sandbox_config
from abb.harness.scheduler import Job, Outcome, Scheduler, order_jobs
from abb.harness.setup import SetupError, ensure_setup
from abb.harness.tasks import task_dir, task_ids
from abb.harness.workspace import Workspace
from abb.log import get_logger
from abb.util import stamp, utcnow_iso

log = get_logger("abb.run")
MATRIX_TRIALS = 30          # > this many trials (or any test task) is a "matrix" run: it needs the usage-limit canary
PAUSE_AT_UTILIZATION = 0.9  # D-028(c): stop launching once a trial reports this five-hour utilisation (None: off)
WINDOW = re.compile(rb'"five_hour":\{"utilization":([0-9.]+),"resetsAt":(\d+)')


def resolve_tasks(spec: str) -> list[str]:
    if spec == "dev5":
        ids = [t for t in task_ids("antennapod") if load_task(t).status == "validated"][:6]
        if len(ids) != 6:
            raise SystemExit(f"dev5 needs 6 validated antennapod tasks, found {ids}")
        return ids
    if spec in ("dev", "test"):
        return [t for t in task_ids() if load_task(t).split == spec and load_task(t).status == "validated"]
    if spec == "all":
        return [t for t in task_ids() if load_task(t).status == "validated"]
    return [s.strip() for s in spec.split(",") if s.strip()]


def _split_sha() -> str | None:
    from abb.harness.taskset import split_sha256

    return split_sha256()


FREEZE_TAG = "v1.0-frozen"


def freeze_record() -> dict:
    """A run with any split: test task starts only from the S5 freeze (Phase 10 step 1): docs/PREREG.md committed,
    unmodified and FROZEN; the freeze tag an ancestor of HEAD; PREREG and the tasks unchanged since the tag; the
    installed s2a the one PREREG names. Returns the manifest fields; raises SystemExit otherwise."""
    import subprocess

    root = paths.repo_clone()

    def git(*args: str) -> subprocess.CompletedProcess:
        return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True)

    prereg = root / "docs" / "PREREG.md"
    if not prereg.exists():
        raise SystemExit("held-out run refused: docs/PREREG.md is missing (S5, Phase 10 step 1)")
    text = prereg.read_text(encoding="utf-8")
    if not re.search(r"^Status: \*\*FROZEN", text, flags=re.M):
        raise SystemExit("held-out run refused: docs/PREREG.md is not marked FROZEN (S5, Phase 10 step 1)")
    if git("status", "--porcelain", "--", "docs/PREREG.md", "benchmark/tasks").stdout.strip():
        raise SystemExit("held-out run refused: docs/PREREG.md or benchmark/tasks has uncommitted changes")
    tag = git("rev-parse", "--verify", "--quiet", f"refs/tags/{FREEZE_TAG}^{{commit}}").stdout.strip()
    if not tag:
        raise SystemExit(f"held-out run refused: tag {FREEZE_TAG} does not exist (S5, Phase 10 step 1)")
    if git("merge-base", "--is-ancestor", tag, "HEAD").returncode != 0:
        raise SystemExit(f"held-out run refused: HEAD does not contain {FREEZE_TAG}")
    if git("diff", "--quiet", tag, "HEAD", "--", "docs/PREREG.md", "benchmark/tasks").returncode != 0:
        raise SystemExit(f"held-out run refused: docs/PREREG.md or benchmark/tasks changed after {FREEZE_TAG}")
    s2a = (load_env_lock().get("_s2a") or {}).get("s2a_git_sha")
    if not s2a or s2a not in text:
        raise SystemExit(f"held-out run refused: the installed s2a ({s2a}) is not the one docs/PREREG.md names")
    return {"prereg_sha256": hashlib.sha256(prereg.read_bytes()).hexdigest(), "freeze_tag": FREEZE_TAG,
            "freeze_commit": tag}


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


def window_state(rec: Path) -> tuple[float | None, float | None]:
    """(five-hour utilisation, resetsAt epoch) of the latest rate_limit_event in a trial's transcripts."""
    last = None
    for f in sorted(rec.glob("transcript/*.jsonl"), key=lambda p: p.stat().st_mtime):
        for m in WINDOW.finditer(f.read_bytes()):
            last = m
    return (float(last.group(1)), float(last.group(2))) if last else (None, None)


def has_canary() -> bool:
    p = paths.repo_clone() / "reference" / "verified.md"
    return p.exists() and "canary" in p.read_text(encoding="utf-8").lower()


class Runner:
    def __init__(self, *, run_id: str, label: str, arms: list[str], tasks: list[str], trials: int, model: str,
                 grade: bool, sandbox: str, allow_env_drift: bool, profile: str | None, task_set: str,
                 parallel: int = 1, max_usd: float | None = None, allow_no_canary: bool = False,
                 max_pause_h: float = 48.0, pause_at: float | None = PAUSE_AT_UTILIZATION,
                 through_trial: int | None = None):
        self.run_id, self.label, self.arms, self.tasks, self.trials = run_id, label, arms, tasks, trials
        self.through_trial = through_trial   # a batch (S6): launch only trial rounds <= this; resume for the rest
        self.model, self.grade, self.sandbox, self.allow_env_drift = model, grade, sandbox, allow_env_drift
        self.task_set, self.parallel, self.max_usd = task_set, max(1, parallel), max_usd
        self.allow_no_canary, self.max_pause_h, self.pause_at = allow_no_canary, max_pause_h, pause_at
        self.profile = profile or ("final" if model.startswith("claude-opus") else "dev")
        self.root = paths.results_dir() / run_id
        self.limits = load_limits().resolve(self.profile, model=model)
        self.token: str | None = None
        self.aborted: str | None = None
        self.manifest = Manifest(self.root / "manifest.json")
        self._lock = threading.RLock()                                # events.jsonl, counters
        self._setups: dict[tuple[str, str], dict | None] = {}         # (setup_kind, repo) -> ensure_setup() result
        self._setup_locks: dict[tuple[str, str], threading.Lock] = {}
        self.env_suspect_streak = 0                                   # D-043 circuit breaker
        self.probes = 0

    def slot_users(self) -> list[str]:
        from abb.harness.sandbox import slot_users

        return slot_users(self.parallel)

    def slot_user(self, slot: int) -> str | None:
        return self.slot_users()[slot - 1] if self.sandbox == "user" else None

    # ---------------------------------------------------------------- manifest / events
    def event(self, **kw) -> None:
        with self._lock:
            with open(self.root / "events.jsonl", "a", encoding="utf-8") as f:
                f.write(json.dumps({"at": utcnow_iso(), **kw}, default=str) + "\n")

    def write_manifest(self, **updates) -> None:
        self.manifest.update(self, **updates)

    # ---------------------------------------------------------------- checks
    def preflight(self) -> None:
        from abb.harness.tasks import refuse_held_out_while_tuning

        refuse_held_out_while_tuning(self.tasks)
        self.token = preflight()
        rec = auth.check()
        if not rec.get("ok"):
            raise SystemExit("abb auth check failed: the token is not accepted (docs/DAY-0.md §3)")
        if self.sandbox == "user":
            from abb.harness.sandbox import check_fs

            for user in self.slot_users():
                if not get_platform().as_user_available(user):
                    raise SystemExit(f"sandbox user {user} missing: `abb sandbox setup --slots {self.parallel}` "
                                     "(one UAC prompt; D-037)")
                bad = [f"{n}: {d}" for n, ok, d in check_fs(user) if not ok]  # D-043: real attempts as the user
                if bad:
                    raise SystemExit(f"sandbox filesystem check failed for {user} (see `abb sandbox check`; lost "
                                     "cache grants come back with `abb sandbox setup --prepare-only`):\n  "
                                     + "\n  ".join(bad))
        lock = load_env_lock()
        for tid in self.tasks:
            t = load_task(tid)
            if t.status != "validated":
                raise SystemExit(f"{tid} is {t.status}, not validated")
            cur = (lock.get(t.repo) or {}).get("fingerprint")
            if t.validation and t.validation.env_fingerprint != cur and not self.allow_env_drift:
                raise SystemExit(f"{tid} was validated against {t.validation.env_fingerprint}, environment is {cur}: "
                                 "re-validate or pass --allow-env-drift (recorded)")
        held_out = any(load_task(t).split == "test" for t in self.tasks)
        if held_out:
            self.write_manifest(**freeze_record())
        matrix = len(self.arms) * len(self.tasks) * self.trials > MATRIX_TRIALS or held_out
        if matrix and not has_canary() and not self.allow_no_canary:
            raise SystemExit("a matrix run needs the usage-limit canary in reference/verified.md (Phase 4 step 8), "
                             "or --allow-no-canary (recorded)")
        standby = get_platform().ac_standby_timeout_s()
        if standby:
            log.warning("AC standby timeout is %s s: the laptop may sleep during the run (docs/DAY-0.md §2)", standby)
            self.event(event="warning", what="ac_standby_timeout_s", value=standby)
        for a in self.arms:
            get_arm(a)

    # ---------------------------------------------------------------- run
    def run(self) -> dict:
        self.root.mkdir(parents=True, exist_ok=True)
        resumed = (self.root / "manifest.json").exists()
        self.write_manifest()
        if resumed:
            m = self.manifest.read()
            cur = initial_shas()  # trials after a resume run on these; the top-level shas stay the run start's
            self.write_manifest(resumes=m.get("resumes", []) + [{"at": utcnow_iso(), "reason": "--resume",
                                                                 "parallel": self.parallel, **cur}],
                                aborted_reason=None, finished_at=None, parallel=self.parallel,
                                slot_users=self.slot_users())
        self.preflight()
        stale = paths.work_dir() / self.run_id  # a killed harness leaves a live trial open to the sandbox user (D-037)
        if stale.exists():
            # keep the verbatim streams of the interrupted processes first: they exist only in the workspace —
            # agent-out/ (the harness's own calls) and work/.s2a/runs/*/agent-out/ (calls an orchestrator made).
            # They go to <run>/salvaged/<stamp>/..., outside the trial dir, which the re-run wipes.
            dst_root = self.root / "salvaged" / stamp()
            for so in [*stale.glob("*/*/t*/agent-out/*/stdout.txt"),
                       *stale.glob("*/*/t*/work/.s2a/runs/*/agent-out/*/stdout.txt")]:
                rel = so.relative_to(stale)
                dst = dst_root / rel.parent / "stdout.jsonl"
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(so, dst)
                self.event(event="stream_salvaged", file=str(dst.relative_to(self.root)), bytes=so.stat().st_size)
            left = get_platform().rmtree_robust(stale)
            self.event(event="stale_workspaces_removed", path=str(stale), leftovers=len(left))
            if left:
                raise SystemExit(f"could not delete stale workspaces under {stale} ({len(left)} leftovers)")
        stop = self.root / "STOP"
        stop.unlink(missing_ok=True)
        self.event(event="run_start", arms=self.arms, tasks=self.tasks, trials=self.trials, model=self.model,
                   parallel=self.parallel, max_usd=self.max_usd, through_trial=self.through_trial)
        if self.through_trial:
            m = self.manifest.read()
            self.write_manifest(batches=m.get("batches", []) + [{"at": utcnow_iso(), "through_trial": self.through_trial}])
        meter = CostMeter(self.max_usd, spent=self._spent_so_far())
        jobs = [j for j in order_jobs(self.arms, self.tasks, self.trials)
                if not self.through_trial or j.trial <= self.through_trial]
        sched = Scheduler(jobs, self._job, workers=self.parallel,
                          meter=meter, stop_file=stop, probe=self._scheduler_probe, pause_at=self.pause_at,
                          max_pause_s=self.max_pause_h * 3600, on_event=lambda **kw: self.event(**kw))
        proxy = from_sandbox_config("user", self.root / "proxy.log")
        proxy.start()
        try:
            self.aborted = sched.run()
        except BaseException as e:  # a harness crash must not end as a clean run (resume with --resume)
            self.aborted = self.aborted or sched.aborted or f"harness_crash: {type(e).__name__}: {str(e)[:200]}"
            raise
        finally:
            proxy.stop()
            self.write_manifest(finished_at=utcnow_iso(), aborted_reason=self.aborted,
                                scheduler_pauses=self.manifest.read().get("scheduler_pauses", 0) + sched.pauses,
                                spent_usd=meter.spent)
            self.event(event="run_end", aborted_reason=self.aborted, spent_usd=meter.spent)
        if self.grade and not self.aborted:   # phase 8 step 10: audit in the loop
            from abb.harness.audit import audit

            res = audit(self.run_id)
            self.write_manifest(audit_ok=res["ok"])
            self.event(event="audit", ok=res["ok"])
        return {"run_id": self.run_id, "aborted_reason": self.aborted, "spent_usd": meter.spent}

    def _spent_so_far(self) -> float:
        """est. USD of the trials already complete (a resumed run's budget counts them)."""
        total = 0.0
        for rj in list(self.root.glob("*/*/t*/run.json")) + list(self.root.glob("setup/*/*/run.json")):
            if rj.parts[-4] == "usage_limited":
                continue
            d = json.loads(rj.read_text(encoding="utf-8"))
            total += float(d.get("cost_usd") if d.get("cost_usd") is not None else (d.get("cost_usd_imputed") or 0))
        return total

    def _scheduler_probe(self) -> str:
        """After a usage-limit pause: `claude -p ping --tools "" --max-turns 1` as slot 1's user, through the
        launcher in a scratch dir; transcript kept under <run>/probes/. ok | usage_limited | auth | model | probe_failed."""
        from abb.harness import transcript as tx
        from abb.harness.agent_driver import AUTH_TEXT, MODEL_TEXT
        from abb.harness.smoke import run_smoke

        with self._lock:
            self.probes += 1
            n = self.probes
        s = run_smoke("ping", model=self.limits.model, max_turns=1, max_usd=0.5, deadline=120, grace=10,
                      interrupt=None, tools="", proxy=True, label="probe", as_user=self.slot_user(1),
                      proxy_running=True)
        out = Path(s["trial_dir"]) / "agent-out" / "stdout.txt"
        dst = self.root / "probes" / f"{stamp()}-scheduler-{n}.jsonl"
        dst.parent.mkdir(parents=True, exist_ok=True)
        if out.exists():
            shutil.copyfile(out, dst)
        t = tx.parse_file(dst) if dst.exists() else None
        text = "\n".join([(t.result_text() if t else ""), (t.last_text if t else "") or "", s.get("stderr_tail") or ""])
        if t and t.subtype == "success" and not (t.result or {}).get("is_error"):
            verdict = "ok"
        elif (t and t.usage_limited_text(s.get("stderr_tail") or "")) or re.search(r"\b429\b", text):
            verdict = "usage_limited"
        elif AUTH_TEXT.search(text):
            verdict = "auth"
        elif MODEL_TEXT.search(text):
            verdict = "model"
        else:
            verdict = "probe_failed"
        user = self.slot_user(1)
        if user:
            get_platform().revoke(Path(s["trial_dir"]), user)
        get_platform().rmtree_robust(Path(s["trial_dir"]))
        return verdict

    def setup_for(self, arm, repo_key: str, slot: int = 1) -> dict | None:
        """One-time setup per (setup kind, repo), cached across runs (abb/harness/setup.py); one worker runs
        it, the others wait for it."""
        key = (arm.setup_kind, repo_key)
        with self._lock:
            lk = self._setup_locks.setdefault(key, threading.Lock())
        with lk:
            if key in self._setups:
                return self._setups[key]
            self.event(event="setup_start", setup_kind=arm.setup_kind, repo=repo_key, slot=slot)
            holder: dict = {}

            def make_context(a, rk: str, rec_dir: Path):
                repo = load_repo(rk)
                root = paths.work_dir() / self.run_id / "_setup" / a.setup_kind / rk
                if root.exists():
                    get_platform().rmtree_robust(root)
                ws = Workspace(repo, root, self.sandbox, run_as=self.slot_user(slot))  # type: ignore[arg-type]
                ws.snapshot(repo.build.setup_commit)
                rec_dir.mkdir(parents=True, exist_ok=True)
                ctx = DriverContext(ws=ws, record_dir=rec_dir, run_dir=self.root, tag=f"setup-{a.setup_kind}-{rk}",
                                    token=self.token or "", budget=TrialBudget.start(replace(self.limits, **a.setup_limits())),
                                    as_agent=self.sandbox == "user")
                holder["ctx"] = ctx
                return ws, ctx

            try:
                res = ensure_setup(arm, repo_key, self.root, run_id=self.run_id, make_context=make_context,
                                   model=self.limits.model)
            finally:
                for ev in (holder["ctx"].events if "ctx" in holder else []):
                    self.event(**ev)
            self._setups[key] = res
            self.event(event="setup_end", setup_kind=arm.setup_kind, repo=repo_key, reused=res["reused"] if res else None,
                       cache_key=res["key"] if res else None)
            return res

    def _job(self, job: Job, slot: int) -> Outcome:
        return self.trial(job.arm, job.task, job.trial, slot=slot)

    def trial(self, arm_name: str, tid: str, k: int, attempt: int = 1, slot: int = 1) -> Outcome:
        rec = self.root / arm_name / tid / f"t{k}"
        if complete(rec, self.grade):
            self.event(event="trial_skip", arm=arm_name, task=tid, trial=k, reason="complete")
            return Outcome()
        if rec.exists() and not (rec / "run.json").exists():
            shutil.rmtree(rec)
        task = load_task(tid)
        repo = load_repo(task.repo)
        outcome = Outcome()
        if not (rec / "run.json").exists():
            rec.mkdir(parents=True, exist_ok=True)
            trial_root = paths.work_dir() / self.run_id / arm_name / tid / f"t{k}"
            if trial_root.exists():
                get_platform().rmtree_robust(trial_root)
            ws = Workspace(repo, trial_root, self.sandbox, run_as=self.slot_user(slot))  # type: ignore[arg-type]
            ws.snapshot(task.base_commit)
            arm = get_arm(arm_name)
            if getattr(arm, "setup_kind", None):
                try:
                    setup = self.setup_for(arm, task.repo, slot)
                except SetupError as e:
                    self.event(event="setup_failed", arm=arm_name, repo=task.repo, subtype=e.subtype, error=str(e)[:300])
                    ws.cleanup()
                    shutil.rmtree(rec, ignore_errors=True)
                    if e.subtype == "usage_limited":
                        util, reset = window_state(self.root / "setup" / arm.setup_kind / task.repo)
                        return Outcome("usage_limited", reset_at=reset, utilization=util)
                    return Outcome("abort", abort_reason="setup_failed")
                arm.install_setup(ws, setup["artifacts"])
            # the trial's clock starts once its one-time setup is in place: building it (or waiting for the other
            # slot to) is setup cost, never the trial's time (D-060)
            budget = TrialBudget.start(self.limits)
            ctx = DriverContext(ws=ws, record_dir=rec, run_dir=self.root, tag=f"{arm_name}-{tid}-t{k}",
                                token=self.token or "", budget=budget, as_agent=self.sandbox == "user")
            ticket = (task_dir(tid) / task.problem_statement).read_text(encoding="utf-8")
            arm_task = task.model_copy(update={"test_patch": None, "gold_patch": None})
            self.event(event="trial_start", arm=arm_name, task=tid, trial=k, attempt=attempt, slot=slot,
                       user=self.slot_user(slot))
            started = utcnow_iso()
            try:
                rr = arm.run(arm_task, ws, self.limits, ctx=ctx, ticket=ticket, trial=k)
            except HarnessError as e:
                self.event(event="harness_error", arm=arm_name, task=tid, trial=k, attempt=attempt, error=str(e)[:500])
                ws.cleanup()
                shutil.rmtree(rec, ignore_errors=True)
                if attempt == 1:
                    return self.trial(arm_name, tid, k, attempt=2, slot=slot)
                rec.mkdir(parents=True, exist_ok=True)
                write_json(rec / "run.json", {"arm": arm_name, "task_id": tid, "trial": k, "exit_reason": "harness_error",
                                             "error": str(e)[:2000], "calls": []})
                (rec / "diff.patch").write_bytes(b"")
                return Outcome()
            except AbortRun as e:
                self.event(event="abort", reason=e.reason, detail=e.detail[:500])
                ws.cleanup()
                shutil.rmtree(rec, ignore_errors=True)
                return Outcome("abort", abort_reason=e.reason)
            finally:
                for ev in ctx.events:
                    self.event(**ev)
            peak = ws.peak_memory_mb
            ws.cleanup()
            data = asdict(rr)
            data["calls"] = [phasecall_dict(c) for c in rr.calls]
            data.update(diff_path=str(rr.diff_path), transcript_dir=str(rr.transcript_dir), started_at=started,
                        finished_at=utcnow_iso(), limits=asdict(self.limits), attempt=attempt, slot=slot,
                        sandbox_user=self.slot_user(slot), peak_memory_mb=peak,
                        budget_left={"turns": budget.turns_left, "usd": round(budget.usd_left, 4),
                                     "seconds": budget.seconds_left()})
            write_json(rec / "run.json", data)
            with open(rec / "calls.jsonl", "w", encoding="utf-8") as f:
                for c in data["calls"]:
                    f.write(json.dumps(c, default=str) + "\n")
            cost = rr.cost_usd if rr.cost_usd is not None else rr.cost_usd_imputed
            util, reset = window_state(rec)
            outcome = Outcome(cost_usd=cost or 0.0, utilization=util, reset_at=reset)
            self.event(event="trial_end", arm=arm_name, task=tid, trial=k, exit_reason=rr.exit_reason,
                       turns=rr.num_turns, cost_usd=rr.cost_usd, duration_ms=rr.duration_ms, slot=slot,
                       peak_memory_mb=peak, five_hour=util)
            builds = metrics._agent_builds(rec)
            with self._lock:
                if builds["agent_env_errors"] and not builds["agent_gradle_ok"]:
                    # the agent's Gradle never succeeded and hit offline-resolution/cache-access errors: an
                    # agent can cause that itself, two trials in a row is the environment (D-043)
                    self.env_suspect_streak += 1
                    self.event(event="env_suspect", arm=arm_name, task=tid, trial=k, streak=self.env_suspect_streak,
                               **builds)
                    if self.env_suspect_streak >= 2:
                        outcome = Outcome("abort", cost_usd=outcome.cost_usd, abort_reason="env_suspect")
                else:
                    self.env_suspect_streak = 0
            if rr.exit_reason == "usage_limited":
                with self._lock:
                    n = 1
                    while (self.root / "usage_limited" / arm_name / tid / f"t{k}-a{n}").exists():
                        n += 1
                    dst = self.root / "usage_limited" / arm_name / tid / f"t{k}-a{n}"
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(rec), str(dst))
                    pauses = self.manifest.read().get("usage_limited_pauses", {})
                    pauses[arm_name] = pauses.get(arm_name, 0) + 1
                    self.write_manifest(usage_limited_pauses=pauses)
                return Outcome("usage_limited", cost_usd=outcome.cost_usd, utilization=util, reset_at=reset)
        if self.grade and not (rec / "grade.json").exists():
            r = grading.grade(tid, rec / "diff.patch", out_dir=rec)
            metrics.build(rec, run_id=self.run_id, arm=arm_name, task_id=tid, trial=k)
            self.event(event="graded", arm=arm_name, task=tid, trial=k, resolved=r["resolved"], reason=r["reason"])
        return outcome


def new_run_id(label: str) -> str:
    return f"{datetime.now(timezone.utc):%Y%m%d-%H%M}-{label}"


def status(run_id: str) -> dict:
    """`abb run status`: done / running / pending trials, est. USD so far, pause state, peak memory."""
    root = paths.results_dir() / run_id
    m = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    graded = bool(m.get("grade", True))
    jobs = order_jobs(m["arms"], m["task_ids"], m["trials"])
    done = [j for j in jobs if complete(root / j.arm / j.task / f"t{j.trial}", graded)]
    events = [json.loads(x) for x in (root / "events.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()] \
        if (root / "events.jsonl").exists() else []
    started = {(e["arm"], e["task"], e["trial"]) for e in events if e.get("event") == "trial_start"}
    ended = {(e["arm"], e["task"], e["trial"]) for e in events if e.get("event") in ("trial_end", "graded")}
    running = [j for j in jobs if (j.arm, j.task, j.trial) in started - ended and j not in done]
    spent, peak = 0.0, 0
    for rj in root.glob("*/*/t*/run.json"):
        d = json.loads(rj.read_text(encoding="utf-8"))
        spent += float(d.get("cost_usd") if d.get("cost_usd") is not None else (d.get("cost_usd_imputed") or 0))
        peak = max(peak, int(d.get("peak_memory_mb") or 0))
    pause = next((e for e in reversed(events) if e.get("event") in ("pause", "resume", "run_start")), None)
    return {"run_id": run_id, "total": len(jobs), "done": len(done), "running": [asdict(j) for j in running],
            "pending": len(jobs) - len(done) - len(running), "spent_usd": round(spent, 4),
            "paused_until": (datetime.fromtimestamp(pause["until"], timezone.utc).isoformat()
                             if pause and pause.get("event") == "pause" else None),
            "usage_limited_attempts": len(list(root.glob("usage_limited/*/*/t*"))), "peak_memory_mb": peak,
            "aborted_reason": m.get("aborted_reason"), "finished_at": m.get("finished_at"),
            "parallel": m.get("parallel"), "audit_ok": m.get("audit_ok")}


def invalidate(run_id: str, trial: str, reason: str) -> Path:
    """A trial a proven harness bug spoiled (PREREG harness-bug criteria): moved to <run>/invalidated/<arm>/<task>/
    t<k>-<stamp>/ with the reason, logged in events.jsonl; `abb run --resume` runs it again. Kept, never graded again."""
    root = paths.results_dir() / run_id
    arm, task, tk = trial.strip("/").split("/")
    src = root / arm / task / tk
    if not (src / "run.json").exists():
        raise SystemExit(f"{src} is not a finished trial")
    dst = root / "invalidated" / arm / task / f"{tk}-{stamp()}"
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dst))
    (dst / "INVALIDATED.txt").write_text(f"{utcnow_iso()}\n{reason}\n", encoding="utf-8")
    with open(root / "events.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps({"at": utcnow_iso(), "event": "invalidated", "arm": arm, "task": task,
                            "trial": int(tk[1:]), "moved_to": str(dst.relative_to(root)), "reason": reason}) + "\n")
    return dst


def abort(run_id: str) -> Path:
    """`abb run abort`: the scheduler stops launching trials; running ones finish (resumable)."""
    p = paths.results_dir() / run_id / "STOP"
    p.write_text(utcnow_iso() + "\n", encoding="utf-8")
    return p


def dry_run(arms: list[str], ids: list[str], trials: int, model: str) -> dict:
    """The matrix and its estimated cost from config/cost_estimates.yaml (mean est. USD per trial per arm, per model)."""
    import yaml

    p = paths.config_dir() / "cost_estimates.yaml"
    models = (yaml.safe_load(p.read_text(encoding="utf-8")) or {}).get("models", {}) if p.exists() else {}
    est = (models.get(model) or {}).get("per_trial_usd", {})
    jobs = order_jobs(arms, ids, trials)
    per_arm = {a: {"trials": sum(1 for j in jobs if j.arm == a), "usd_per_trial": est.get(a)} for a in arms}
    total = sum((v["usd_per_trial"] or 0) * v["trials"] for v in per_arm.values())
    return {"trials": len(jobs), "model": model, "order": [f"{j.arm}/{j.task}/t{j.trial}" for j in jobs[:12]]
            + (["…"] if len(jobs) > 12 else []), "per_arm": per_arm, "estimated_usd": round(total, 2),
            "unknown_arms": [a for a, v in per_arm.items() if v["usd_per_trial"] is None]}
