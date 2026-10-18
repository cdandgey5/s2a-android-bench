"""s2a platform layer (same contract as the benchmark's specs/platform-layer.md, own copy; the only
place with OS-specific code). Two kinds of process:

- `run`: tools the orchestrator runs itself (Gradle, git) — output to files, a deadline, and the
  whole process tree killed when it passes;
- `run_agent`: the headless `claude` call — stdin prompt, stream-json to a file, and on the
  deadline (or when `stop` is set, e.g. the orchestrator itself was interrupted) the interrupt
  Claude Code answers with a `result` line (Ctrl+C), `grace_s` to finish, then a tree kill.
"""
from __future__ import annotations

import os
import subprocess
import sys
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol


@dataclass
class ProcResult:
    exit_code: int | None
    stdout_path: Path
    stderr_path: Path
    duration_s: float
    timed_out: bool = False           # the deadline passed (for run_agent: we interrupted it)
    stopped: bool = False             # run_agent: interrupted because `stop` was set
    info: dict = field(default_factory=dict)

    def stdout(self) -> str:
        return self.stdout_path.read_text(encoding="utf-8", errors="replace") if self.stdout_path.exists() else ""

    def stderr(self) -> str:
        return self.stderr_path.read_text(encoding="utf-8", errors="replace") if self.stderr_path.exists() else ""


class Platform(Protocol):
    id: str

    def gradlew(self, repo: Path) -> list[str]: ...
    def run(self, argv: list[str], *, cwd: Path, out_dir: Path, timeout_s: float,
            env: dict[str, str] | None = None, stdin_text: str | None = None) -> ProcResult: ...
    def run_agent(self, argv: list[str], *, cwd: Path, out_dir: Path, timeout_s: float, stdin_text: str,
                  grace_s: float = 30.0, stop: threading.Event | None = None,
                  env: dict[str, str] | None = None) -> ProcResult: ...


def get_platform() -> Platform:
    if sys.platform == "win32":
        from s2a.platform.windows import WindowsPlatform

        return WindowsPlatform()
    from s2a.platform.posix import PosixPlatform

    return PosixPlatform()


def run_text(argv: list[str], *, cwd: Path, timeout_s: float = 120) -> subprocess.CompletedProcess:
    """Short helper commands (git) whose output is small: captured in memory, never a tree kill."""
    return subprocess.run(argv, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                          timeout=timeout_s, env=os.environ.copy())
