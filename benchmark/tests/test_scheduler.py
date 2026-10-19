"""Phase 8 runner (phases/phase-8-runner.md): job order, parallel slots, budget stop, abort file, usage-limit
pause -> probe -> resume, pre-emptive pause (D-028(c)); and through Runner.trial with a fake arm: the resume
rule, retry-once on harness_error, usage-limited attempts kept and re-queued."""
from __future__ import annotations

import json
import threading
from pathlib import Path

import pytest

from abb import paths
from abb.arms.base import RunResult
from abb.harness import run as runmod
from abb.harness.agent_driver import HarnessError
from abb.harness.costmeter import CostMeter
from abb.harness.scheduler import Job, Outcome, Scheduler, order_jobs


class Clock:
    def __init__(self) -> None:
        self.t = 1_000_000.0
        self.lock = threading.Lock()

    def now(self) -> float:
        with self.lock:
            return self.t

    def sleep(self, s: float) -> None:
        with self.lock:
            self.t += max(s, 0.01)


def sched(jobs, run_job, clock=None, **kw) -> Scheduler:
    clock = clock or Clock()
    return Scheduler(jobs, run_job, clock=clock.now, sleep=clock.sleep, **kw)


def test_order_spreads_trials_of_a_task_and_interleaves_arms() -> None:
    jobs = order_jobs(["plain", "s2a"], ["t1", "t2"], 2)
    assert [f"{j.arm}/{j.task}/{j.trial}" for j in jobs] == [
        "plain/t1/1", "s2a/t1/1", "plain/t2/1", "s2a/t2/1", "plain/t1/2", "s2a/t1/2", "plain/t2/2", "s2a/t2/2"]


def test_every_job_runs_once_on_both_slots() -> None:
    seen, lock = [], threading.Lock()

    def run_job(job, slot):
        with lock:
            seen.append((job, slot))
        return Outcome(cost_usd=0.1)

    jobs = order_jobs(["a", "b"], ["t1", "t2", "t3"], 1)
    s = sched(jobs, run_job, workers=2)
    assert s.run() is None
    assert sorted(j for j, _ in seen) == sorted(jobs) and {sl for _, sl in seen} <= {1, 2}


def test_budget_stops_launching_once_crossed() -> None:
    ran = []
    s = sched(order_jobs(["a"], ["t1", "t2", "t3", "t4"], 1), lambda j, sl: ran.append(j) or Outcome(cost_usd=0.3),
              meter=CostMeter(0.5))
    assert s.run() == "budget" and len(ran) == 2


def test_abort_file_stops_launching(tmp_path: Path) -> None:
    stop, ran = tmp_path / "STOP", []

    def run_job(job, slot):
        ran.append(job)
        stop.write_text("x")
        return Outcome()

    s = sched(order_jobs(["a"], ["t1", "t2"], 1), run_job, stop_file=stop)
    assert s.run() == "abort" and len(ran) == 1


def test_usage_limit_requeues_pauses_probes_then_resumes() -> None:
    clock, calls, probes = Clock(), [], []

    def run_job(job, slot):
        calls.append((job.task, clock.now()))
        if job.task == "t2" and sum(1 for t, _ in calls if t == "t2") == 1:
            return Outcome("usage_limited", cost_usd=0.05, reset_at=clock.now() + 3600)
        return Outcome(cost_usd=0.1)

    def probe():
        probes.append(clock.now())
        return "usage_limited" if len(probes) == 1 else "ok"

    s = sched(order_jobs(["a"], ["t1", "t2", "t3"], 1), run_job, clock, probe=probe)
    limited_at = None
    assert s.run() is None
    assert [t for t, _ in calls] == ["t1", "t2", "t2", "t3"] and s.pauses == 1
    limited_at = calls[1][1]
    assert probes[0] >= limited_at + 3600 + 120                       # first probe after the reset + 2 min
    assert probes[1] >= probes[0] + 15 * 60                           # then every 15 min
    assert calls[2][1] >= probes[1]                                   # the trial re-ran only after a good probe


def test_high_utilisation_pauses_before_the_window_is_spent() -> None:
    clock, calls = Clock(), []

    def run_job(job, slot):
        calls.append(clock.now())
        return Outcome(cost_usd=0.1, utilization=0.93 if len(calls) == 1 else 0.1, reset_at=clock.now() + 600)

    s = sched(order_jobs(["a"], ["t1", "t2"], 1), run_job, clock, probe=lambda: "ok", pause_at=0.9)
    assert s.run() is None and s.pauses == 1 and calls[1] >= calls[0] + 600 + 120


def test_auth_probe_and_endless_limit_abort() -> None:
    lim = lambda j, sl: Outcome("usage_limited", reset_at=None)   # noqa: E731
    assert sched([Job("a", "t1", 1)], lim, probe=lambda: "auth").run() == "auth"
    assert sched([Job("a", "t1", 1)], lim, probe=lambda: "usage_limited", max_pause_s=3 * 3600).run() == "usage_limit"


def test_an_aborting_outcome_stops_the_run() -> None:
    ran = []
    s = sched(order_jobs(["a"], ["t1", "t2"], 1),
              lambda j, sl: ran.append(j) or Outcome("abort", abort_reason="env_suspect"))
    assert s.run() == "env_suspect" and len(ran) == 1


def test_a_crashing_job_stops_every_worker_and_raises() -> None:
    def run_job(job, slot):
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        sched(order_jobs(["a"], ["t1", "t2", "t3"], 1), run_job, workers=2).run()


# ---------------------------------------------------------------------------- Runner.trial with a fake arm
class FakeWS:
    def __init__(self, repo, root, sandbox="none", run_as=None):
        self.dirs, self.base, self.peak_memory_mb = type("D", (), {"root": Path(root)})(), "base", 0

    def snapshot(self, commit):
        pass

    def cleanup(self):
        return []


class FakeArm:
    setup_kind = None

    def __init__(self, script):
        self.script = list(script)

    def run(self, task, ws, limits, *, ctx, ticket, trial):
        step = self.script.pop(0)
        if step == "harness_error":
            raise HarnessError("platform failure")
        rec = ctx.record_dir
        (rec / "diff.patch").write_bytes(b"")
        return RunResult(arm="fake", task_id=task.id, trial=trial, exit_reason=step, diff_path=rec / "diff.patch",
                         transcript_dir=rec / "transcript", workspace_base="base", cost_usd=0.2).fill_totals()


@pytest.fixture
def runner(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "results_dir", lambda: tmp_path / "results")
    monkeypatch.setattr(paths, "work_dir", lambda: tmp_path / "work")
    monkeypatch.setattr(runmod, "Workspace", FakeWS)
    monkeypatch.setattr(runmod.metrics, "_agent_builds", lambda rec: {"agent_env_errors": 0, "agent_gradle_ok": 1})
    r = runmod.Runner(run_id="r1", label="t", arms=["fake"], tasks=["antennapod-0000"], trials=1,
                      model="claude-sonnet-5-5", grade=False, sandbox="none", allow_env_drift=False, profile=None,
                      task_set="x")
    r.root.mkdir(parents=True)
    (r.root / "manifest.json").write_text(json.dumps({"run_id": "r1", "usage_limited_pauses": {}}), encoding="utf-8")
    return r


def _events(r) -> list[dict]:
    return [json.loads(x) for x in (r.root / "events.jsonl").read_text(encoding="utf-8").splitlines()]


def test_harness_error_is_retried_once(runner, monkeypatch) -> None:
    arm = FakeArm(["harness_error", "completed"])
    monkeypatch.setattr(runmod, "get_arm", lambda name: arm)
    out = runner.trial("fake", "antennapod-0000", 1)
    rj = json.loads((runner.root / "fake/antennapod-0000/t1/run.json").read_text(encoding="utf-8"))
    assert out.status == "done" and rj["exit_reason"] == "completed" and rj["attempt"] == 2
    assert [e["event"] for e in _events(runner)].count("harness_error") == 1


def test_harness_error_twice_is_a_lost_trial_not_a_third_try(runner, monkeypatch) -> None:
    arm = FakeArm(["harness_error", "harness_error"])
    monkeypatch.setattr(runmod, "get_arm", lambda name: arm)
    runner.trial("fake", "antennapod-0000", 1)
    rj = json.loads((runner.root / "fake/antennapod-0000/t1/run.json").read_text(encoding="utf-8"))
    assert rj["exit_reason"] == "harness_error" and arm.script == []


def test_resume_skips_complete_trials_and_reruns_partial_ones(runner, monkeypatch) -> None:
    arm = FakeArm(["completed", "completed"])
    monkeypatch.setattr(runmod, "get_arm", lambda name: arm)
    runner.trial("fake", "antennapod-0000", 1)
    runner.trial("fake", "antennapod-0000", 1)                       # complete: skipped
    assert arm.script == ["completed"]
    part = runner.root / "fake/antennapod-0000/t2"
    part.mkdir(parents=True)
    (part / "junk.txt").write_text("partial")                        # no run.json: wiped and re-run
    runner.trial("fake", "antennapod-0000", 2)
    assert arm.script == [] and not (part / "junk.txt").exists() and (part / "run.json").exists()


def test_a_usage_limited_attempt_is_kept_and_the_trial_requeued(runner, monkeypatch) -> None:
    arm = FakeArm(["usage_limited"])
    monkeypatch.setattr(runmod, "get_arm", lambda name: arm)
    out = runner.trial("fake", "antennapod-0000", 1)
    assert out.status == "usage_limited"
    assert (runner.root / "usage_limited/fake/antennapod-0000/t1-a1/run.json").exists()
    assert not (runner.root / "fake/antennapod-0000/t1").exists()
    assert json.loads((runner.root / "manifest.json").read_text(encoding="utf-8"))["usage_limited_pauses"] == {"fake": 1}
