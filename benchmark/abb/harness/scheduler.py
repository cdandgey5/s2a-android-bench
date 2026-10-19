"""Worker pool over trials (phases/phase-8-runner.md steps 3-6). Pure scheduling: the runner supplies
`run_job(job, slot) -> Outcome`, a probe, and the clock; this module decides what runs when.

- Order: trial-major, then task, then arm, so the trials of one task are a whole pass apart and the
  arms are interleaved (evens out API-side variance and rate limits).
- Workers: `workers` threads; worker k always runs as slot k (D-037: one sandbox user per slot).
- Stops launching (running jobs finish) on: the budget (`--max-usd` crossed -> "budget"), an abort
  file (`abb run abort` -> "abort"), an outcome that aborts (auth, model, env_suspect, setup), or a
  pause that lasted longer than `max_pause_s` ("usage_limit").
- Usage limits (D-028): a `usage_limited` outcome re-queues its job at the front and pauses every
  worker until the parsed reset (+2 min; 30 min if none was parsed); then one worker probes, every
  15 min, until the probe says ok. `pause_at` (D-028(c)): an outcome whose latest five-hour
  utilisation is at or above it pauses the same way *before* the window is spent, so running trials
  finish and no trial is cut.
"""
from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Literal


@dataclass(frozen=True, order=True)
class Job:
    arm: str
    task: str
    trial: int


@dataclass
class Outcome:
    status: Literal["done", "usage_limited", "abort"] = "done"
    cost_usd: float = 0.0
    reset_at: float | None = None        # epoch seconds: when the five-hour window resets (from rate_limit_event)
    utilization: float | None = None     # the latest five-hour utilisation the job's transcripts reported
    abort_reason: str | None = None


def order_jobs(arms: list[str], tasks: list[str], trials: int) -> list[Job]:
    return [Job(a, t, k) for k in range(1, trials + 1) for t in tasks for a in arms]


@dataclass
class Scheduler:
    jobs: list[Job]
    run_job: Callable[[Job, int], Outcome]
    workers: int = 1
    meter: object | None = None                       # CostMeter
    stop_file: Path | None = None
    probe: Callable[[], str] | None = None             # -> ok | usage_limited | auth | model | probe_failed
    pause_at: float | None = None
    max_pause_s: float = 48 * 3600
    clock: Callable[[], float] = time.time
    sleep: Callable[[float], None] = time.sleep
    on_event: Callable[..., None] = lambda **kw: None
    aborted: str | None = None
    pauses: int = 0
    _queue: deque = field(default_factory=deque)
    _lock: threading.Lock = field(default_factory=threading.Lock)
    _paused_until: float | None = None
    _pause_started: float | None = None
    _probing: bool = False
    _error: BaseException | None = None

    # ------------------------------------------------------------------ control
    def _stop_requested(self) -> bool:
        return bool(self.stop_file and self.stop_file.exists())

    def _pause(self, until: float, why: str) -> None:
        """Caller holds the lock."""
        now = self.clock()
        if self._paused_until is None:
            self._pause_started = now
            self.pauses += 1
            self.on_event(event="pause", why=why, until=until)
        self._paused_until = max(self._paused_until or 0, until)

    def _runnable(self) -> bool:
        """Wait until a job may start; False when the run must stop launching."""
        while True:
            do_probe, wait_s = False, 0.0
            with self._lock:
                if self.aborted or self._error:
                    return False
                if self._stop_requested():
                    self.aborted = "abort"
                    return False
                if self.meter is not None and self.meter.crossed():
                    self.aborted = "budget"
                    return False
                if self._paused_until is None:
                    return True
                now = self.clock()
                if self._pause_started is not None and now - self._pause_started > self.max_pause_s:
                    self.aborted = "usage_limit"
                    return False
                if now < self._paused_until:
                    wait_s = min(30.0, self._paused_until - now)
                elif self._probing:
                    wait_s = 5.0
                elif self.probe is None:
                    self._paused_until = self._pause_started = None
                    self.on_event(event="resume", probe=None)
                    return True
                else:
                    self._probing, do_probe = True, True
            if do_probe:
                outcome = self.probe()
                with self._lock:
                    self._probing = False
                    self.on_event(event="scheduler_probe", outcome=outcome)
                    if outcome == "ok":
                        self._paused_until = self._pause_started = None
                        self.on_event(event="resume", probe="ok")
                    elif outcome in ("auth", "model"):
                        self.aborted = outcome
                        return False
                    else:   # still limited, or the probe failed: try again in 15 min
                        self._paused_until = self.clock() + 15 * 60
                continue
            self.sleep(wait_s)

    def _take(self) -> Job | None:
        with self._lock:
            return self._queue.popleft() if self._queue else None

    def _handle(self, job: Job, out: Outcome) -> None:
        with self._lock:
            if self.meter is not None:
                self.meter.add(out.cost_usd)
            if out.status == "usage_limited":
                self._queue.appendleft(job)          # the same trial again, in a fresh t<k> (the runner moved the attempt)
                self._pause((out.reset_at + 120) if out.reset_at else self.clock() + 30 * 60, "usage_limited")
            elif out.status == "abort":
                self.aborted = self.aborted or out.abort_reason or "abort"
            elif self.pause_at is not None and out.utilization is not None and out.utilization >= self.pause_at:
                self._pause((out.reset_at + 120) if out.reset_at else self.clock() + 30 * 60,
                            f"five-hour utilisation {out.utilization} >= {self.pause_at}")

    # ------------------------------------------------------------------ run
    def _worker(self, slot: int) -> None:
        try:
            while self._runnable():
                job = self._take()
                if job is None:
                    return
                self._handle(job, self.run_job(job, slot))
        except BaseException as e:  # noqa: BLE001 - a crash must stop the other workers too
            with self._lock:
                self._error = self._error or e
                self.aborted = self.aborted or f"harness_crash: {type(e).__name__}: {str(e)[:200]}"

    def run(self) -> str | None:
        """Run every job (or stop early); returns the aborted reason (None when every job ran)."""
        self._queue.extend(self.jobs)
        threads = [threading.Thread(target=self._worker, args=(k,), name=f"slot-{k}", daemon=True)
                   for k in range(1, max(1, self.workers) + 1)]
        for t in threads:
            t.start()
            if len(threads) > 1:
                self.sleep(2)   # stagger the first launches (workspace snapshots and setup locks)
        try:
            while any(t.is_alive() for t in threads):
                for t in threads:
                    t.join(0.5)
        except KeyboardInterrupt:
            with self._lock:
                self.aborted = self.aborted or "interrupt"
            raise
        if self._error is not None:
            raise self._error
        return self.aborted
