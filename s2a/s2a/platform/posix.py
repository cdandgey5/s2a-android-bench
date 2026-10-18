"""POSIX implementation (macOS later; kept minimal): process groups, SIGINT for the agent, SIGKILL after grace."""
from __future__ import annotations

import os
import signal
import subprocess
import threading
import time
from pathlib import Path

from s2a.platform.base import ProcResult


def _killpg(pid: int, sig: int) -> None:
    try:
        os.killpg(os.getpgid(pid), sig)
    except ProcessLookupError:
        pass


class PosixPlatform:
    id = "posix"

    def gradlew(self, repo: Path) -> list[str]:
        return [str(repo / "gradlew")]

    def run(self, argv: list[str], *, cwd: Path, out_dir: Path, timeout_s: float,
            env: dict[str, str] | None = None, stdin_text: str | None = None) -> ProcResult:
        out_dir.mkdir(parents=True, exist_ok=True)
        so, se = out_dir / "stdout.txt", out_dir / "stderr.txt"
        t0 = time.monotonic()
        with open(so, "wb") as out, open(se, "wb") as err:
            p = subprocess.Popen(argv, cwd=cwd, stdout=out, stderr=err, env=env, start_new_session=True,
                                 stdin=subprocess.PIPE if stdin_text is not None else subprocess.DEVNULL)
            if stdin_text is not None:
                p.stdin.write(stdin_text.encode("utf-8"))
                p.stdin.close()
            timed_out = False
            try:
                p.wait(timeout_s)
            except subprocess.TimeoutExpired:
                timed_out = True
                _killpg(p.pid, signal.SIGKILL)
                p.wait(60)
            except KeyboardInterrupt:
                _killpg(p.pid, signal.SIGKILL)
                raise
        return ProcResult(p.returncode, so, se, round(time.monotonic() - t0, 1), timed_out=timed_out)

    def run_agent(self, argv: list[str], *, cwd: Path, out_dir: Path, timeout_s: float, stdin_text: str,
                  grace_s: float = 30.0, stop: threading.Event | None = None,
                  env: dict[str, str] | None = None) -> ProcResult:
        out_dir.mkdir(parents=True, exist_ok=True)
        so, se = out_dir / "stdout.txt", out_dir / "stderr.txt"
        t0 = time.monotonic()
        with open(so, "wb") as out, open(se, "wb") as err:
            p = subprocess.Popen(argv, cwd=cwd, stdout=out, stderr=err, stdin=subprocess.PIPE, env=env,
                                 start_new_session=True)
            p.stdin.write(stdin_text.encode("utf-8"))
            p.stdin.close()
            timed_out = stopped = False
            sent: float | None = None
            try:
                while p.poll() is None:
                    if sent is None and ((stop is not None and stop.is_set()) or time.monotonic() - t0 > timeout_s):
                        stopped = stop is not None and stop.is_set()
                        timed_out = not stopped
                        _killpg(p.pid, signal.SIGINT)
                        sent = time.monotonic()
                    elif sent is not None and time.monotonic() - sent > grace_s:
                        _killpg(p.pid, signal.SIGKILL)
                        p.wait(60)
                        break
                    time.sleep(0.2)
            except KeyboardInterrupt:
                _killpg(p.pid, signal.SIGINT)
                try:
                    p.wait(grace_s)
                except subprocess.TimeoutExpired:
                    _killpg(p.pid, signal.SIGKILL)
                raise
        return ProcResult(p.returncode, so, se, round(time.monotonic() - t0, 1), timed_out=timed_out, stopped=stopped)
