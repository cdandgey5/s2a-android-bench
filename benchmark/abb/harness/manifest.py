"""`<run>/manifest.json` (specs/results-layout.md): written before the first trial, updated in place
(thread-safe) as the run goes: resumes, pauses, aborted_reason, audit_ok, finished_at."""
from __future__ import annotations

import json
import os
import platform as _pyplatform
import subprocess
import threading
from dataclasses import asdict
from pathlib import Path

from abb import paths
from abb.config import load_sandbox, load_task, load_toolchain
from abb.harness.agent_driver import write_json
from abb.harness.env import load_env_lock
from abb.harness.platform import get_platform
from abb.harness.tools import load_lock
from abb.util import sha256_file, utcnow_iso


def initial(runner) -> dict:
    from abb.harness.run import _split_sha, task_set_sha

    lock = load_env_lock()
    authrec = {}
    ap = paths.state_dir() / "auth.json"
    if ap.exists():
        authrec = json.loads(ap.read_text(encoding="utf-8"))
    sha = subprocess.run(["git", "-C", str(paths.repo_clone()), "rev-parse", "HEAD"], capture_output=True,
                         text=True).stdout.strip()
    tl = paths.config_dir() / "toolchain.lock.yaml"
    return {
        "run_id": runner.run_id, "created_at": utcnow_iso(), "label": runner.label, "prereg_sha256": None,
        "arms": runner.arms, "task_set": runner.task_set, "task_ids": runner.tasks,
        "task_set_sha256": task_set_sha(runner.tasks), "split_sha256": _split_sha(), "trials": runner.trials,
        "limits": asdict(runner.limits), "profile": runner.profile,
        "agent_version": load_toolchain().claude_code.version,
        "speckit_version": (load_lock().get("speckit") or {}).get("ref"),
        "s2a_git_sha": (load_env_lock().get("_s2a") or {}).get("s2a_git_sha"),
        "platform": get_platform().id,
        "env_fingerprints": {r: (lock.get(r) or {}).get("fingerprint")
                             for r in sorted({load_task(t).repo for t in runner.tasks})},
        "toolchain_lock_sha256": sha256_file(tl) if tl.exists() else None,
        "interrupt": load_sandbox().process.interrupt, "sandbox_mode": runner.sandbox,
        "parallel": runner.parallel, "slot_users": runner.slot_users() if runner.sandbox == "user" else [],
        "max_usd": runner.max_usd, "grade": runner.grade, "pause_at_utilization": runner.pause_at,
        "auth_mode": "subscription", "plan": authrec.get("subscriptionType") or "pro",
        "plan_source": authrec.get("plan_source") or "owner (reference/verified.md)",
        "usage_limited_pauses": {}, "scheduler_pauses": 0, "strip_agent_instructions": False,
        "allow_env_drift": runner.allow_env_drift, "allow_no_canary": runner.allow_no_canary,
        "harness_git_sha": sha, "split_file_sha256": None, "resumes": [], "aborted_reason": None,
        "audit_ok": None, "finished_at": None,
        "host": {"os": "windows", "release": f"{_pyplatform.release()} {_pyplatform.version()}",
                 "cpus": os.cpu_count(), "mem_gb": 32},
    }


class Manifest:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.RLock()

    def read(self) -> dict:
        with self._lock:
            return json.loads(self.path.read_text(encoding="utf-8")) if self.path.exists() else {}

    def update(self, runner=None, **updates) -> dict:
        """Create from `runner` if missing, then apply `updates`; one writer at a time."""
        with self._lock:
            m = self.read()
            if not m and runner is not None:
                m = initial(runner)
            m.update(updates)
            write_json(self.path, m)
            return m
