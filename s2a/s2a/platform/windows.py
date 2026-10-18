"""Windows implementation. Gradle/git run in their own process group (a Ctrl+C aimed at s2a does not
reach them; s2a stops them itself); `claude` runs under launch.py in a private hidden console so
the interrupt can be Ctrl+C (D-032 in the benchmark: Ctrl+C yields a `result` line, Ctrl+Break
does not)."""
from __future__ import annotations

import json
import subprocess
import sys
import threading
import time
from pathlib import Path

from s2a.platform.base import ProcResult

CREATE_NEW_PROCESS_GROUP = 0x00000200
CREATE_NEW_CONSOLE = 0x00000010
LAUNCHER = Path(__file__).with_name("launch.py")


def _kill_tree(pid: int) -> None:
    subprocess.run(["taskkill", "/T", "/F", "/PID", str(pid)], capture_output=True, timeout=60)


class WindowsPlatform:
    id = "windows"

    def gradlew(self, repo: Path) -> list[str]:
        return [str(repo / "gradlew.bat")]

    def run(self, argv: list[str], *, cwd: Path, out_dir: Path, timeout_s: float,
            env: dict[str, str] | None = None, stdin_text: str | None = None) -> ProcResult:
        out_dir.mkdir(parents=True, exist_ok=True)
        so, se = out_dir / "stdout.txt", out_dir / "stderr.txt"
        t0 = time.monotonic()
        with open(so, "wb") as out, open(se, "wb") as err:
            p = subprocess.Popen(argv, cwd=cwd, stdout=out, stderr=err, env=env,
                                 stdin=subprocess.PIPE if stdin_text is not None else subprocess.DEVNULL,
                                 creationflags=CREATE_NEW_PROCESS_GROUP)
            if stdin_text is not None:
                p.stdin.write(stdin_text.encode("utf-8"))
                p.stdin.close()
            timed_out = False
            try:
                while p.poll() is None:
                    if time.monotonic() - t0 > timeout_s:
                        timed_out = True
                        _kill_tree(p.pid)
                        p.wait(60)
                        break
                    time.sleep(0.2)
            except KeyboardInterrupt:
                _kill_tree(p.pid)
                raise
        return ProcResult(p.returncode, so, se, round(time.monotonic() - t0, 1), timed_out=timed_out)

    def run_agent(self, argv: list[str], *, cwd: Path, out_dir: Path, timeout_s: float, stdin_text: str,
                  grace_s: float = 30.0, stop: threading.Event | None = None,
                  env: dict[str, str] | None = None) -> ProcResult:
        out_dir.mkdir(parents=True, exist_ok=True)
        so, se = out_dir / "stdout.txt", out_dir / "stderr.txt"
        status, stop_file = out_dir / "launcher.json", out_dir / "STOP"
        for f in (status, stop_file):
            f.unlink(missing_ok=True)
        spec = {"argv": argv, "cwd": str(cwd), "stdout": str(so), "stderr": str(se), "stdin_text": stdin_text,
                "stop_file": str(stop_file), "status_file": str(status), "poll_s": 0.2}
        (out_dir / "launch.json").write_text(json.dumps(spec), encoding="utf-8")
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = 0  # SW_HIDE
        t0 = time.monotonic()
        p = subprocess.Popen([sys.executable, "-I", str(LAUNCHER), str(out_dir / "launch.json")], cwd=cwd, env=env,
                             creationflags=CREATE_NEW_CONSOLE, startupinfo=si,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL)
        timed_out = stopped = False
        interrupted_at: float | None = None
        interrupt = False
        try:
            while p.poll() is None:
                if interrupted_at is None:
                    if stop is not None and stop.is_set():
                        stopped = True
                    elif time.monotonic() - t0 > timeout_s:
                        timed_out = True
                    if stopped or timed_out:
                        stop_file.write_text("stop", encoding="utf-8")
                        interrupted_at = time.monotonic()
                elif time.monotonic() - interrupted_at > grace_s:
                    _kill_tree(p.pid)
                    p.wait(60)
                    break
                time.sleep(0.2)
        except KeyboardInterrupt:
            interrupt = True
            stopped = True
            stop_file.write_text("stop", encoding="utf-8")
            deadline = time.monotonic() + grace_s
            while p.poll() is None and time.monotonic() < deadline:
                time.sleep(0.2)
            if p.poll() is None:
                _kill_tree(p.pid)
        info = json.loads(status.read_text(encoding="utf-8")) if status.exists() else {}
        res = ProcResult(info.get("child_exit_code"), so, se, round(time.monotonic() - t0, 1), timed_out=timed_out,
                         stopped=stopped, info=info)
        if interrupt:
            raise KeyboardInterrupt
        if not info and not timed_out and not stopped:
            raise RuntimeError(f"launcher left no status file (exit {p.returncode}); see {out_dir}")
        if info.get("error"):
            raise RuntimeError(f"launcher failed: {info['error'][-400:]}")
        return res
