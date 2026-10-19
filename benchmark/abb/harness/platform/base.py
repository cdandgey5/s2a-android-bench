"""Platform contract (specs/platform-layer.md). The only OS-independent part of the platform layer.

Every subprocess the harness starts goes through `Platform.run`. Implementations live next to this
file: `windows.py` (v1) and `posix.py` (stub until macOS support).
"""
from __future__ import annotations

import sys
import tempfile
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Protocol

Interrupt = Literal["ctrl_break", "ctrl_c"]


@dataclass
class ProcSpec:
    argv: list[str]                  # the real command (claude.exe ..., gradlew.bat ..., git ...)
    cwd: Path
    env: dict[str, str]              # the FULL environment block (never inherit the harness env)
    stdin_text: str | None           # prompts go in on stdin (Claude Code >= 2.1.211)
    timeout_s: int
    memory_mb: int | None            # Job Object JOB memory limit (whole tree)
    as_user: str | None              # "abb-agent" or None
    out_dir: Path                    # stdout.txt / stderr.txt / launcher.json land here
    hidden: bool = True
    interrupt: Interrupt = "ctrl_break"   # sandbox.yaml: process.interrupt (both drivers use the same)
    stop_file: Path | None = None    # default: <out_dir>/STOP (trials pass <trial>/STOP)
    grace_s: int = 30                # STOP -> interrupt -> wait grace_s -> terminate the job


@dataclass
class Proc:
    pid: int                         # the launcher's pid
    spec: ProcSpec
    started_monotonic: float
    stop_file: Path
    handle: Any = None               # platform-private (process handle, job, completion port)


@dataclass
class ProcResult:
    exit_code: int | None            # None if killed by the harness
    stopped_by_harness: bool         # True when the deadline hit -> exit_reason "timeout" regardless of code
    duration_s: float
    peak_memory_mb: int | None       # from the Job Object
    job_memory_hit: bool             # a process inside the job hit the job limit -> agent_error, never harness_error
    stdout_path: Path | None = None
    stderr_path: Path | None = None
    launcher: dict = field(default_factory=dict)   # the launcher's status record (interrupt sent, child exit, console)

    def stdout(self) -> str:
        return _read(self.stdout_path)

    def stderr(self) -> str:
        return _read(self.stderr_path)


def _read(p: Path | None) -> str:
    if p is None or not p.exists():
        return ""
    return p.read_bytes().decode("utf-8", errors="replace")


class Platform(Protocol):
    id: str

    def gradlew(self, repo_dir: Path) -> list[str]: ...
    def python(self) -> Path: ...
    def claude_exe(self) -> Path: ...
    def run(self, spec: ProcSpec) -> Proc: ...
    def wait(self, proc: Proc, timeout_s: int | None = None) -> ProcResult: ...
    def stop_gracefully(self, proc: Proc, grace_s: int = 30) -> None: ...
    def grant(self, path: Path, principal: str, rights: Literal["rx", "modify", "deny"], *, inherit: bool = True) -> None: ...
    def deny_write(self, path: Path, principal: str) -> None: ...
    def reset_inheritance(self, root: Path, owners: list[str]) -> None: ...
    def inherit_acl(self, path: Path) -> None: ...   # a moved tree takes what its new parent passes down
    def check_access(self, path: Path, *, as_user: str, op: Literal["read", "create"]) -> Literal["ok", "denied"]: ...
    def as_user_available(self) -> bool: ...
    def env_fingerprint_parts(self) -> dict: ...
    def enable_long_paths(self) -> None: ...
    def rmtree_robust(self, path: Path) -> list[Path]: ...
    def system_env(self) -> dict[str, str]: ...
    def harness_env(self, extra: dict[str, str] | None = None) -> dict[str, str]: ...
    def volume_filesystem(self, path: Path) -> str: ...
    def find_exe(self, name: str) -> Path | None: ...
    def ac_standby_timeout_s(self) -> int | None: ...   # non-zero: the machine may sleep on AC during a run


def get_platform() -> Platform:
    if sys.platform == "win32":
        from abb.harness.platform.windows import WindowsPlatform

        return WindowsPlatform()
    from abb.harness.platform.posix import PosixPlatform

    return PosixPlatform()


def run_capture(
    platform: Platform,
    argv: list[str],
    *,
    cwd: Path,
    env: dict[str, str] | None = None,
    timeout_s: int = 600,
    memory_mb: int | None = None,
    stdin_text: str | None = None,
    out_dir: Path | None = None,
) -> ProcResult:
    """Run a short harness command through the platform layer and wait for it.

    Output files go to `out_dir` (default: a fresh directory under the system temp dir of the
    harness user). Use `result.stdout()` / `result.stderr()` to read them.
    """
    if out_dir is None:
        out_dir = Path(tempfile.gettempdir()) / "abb-run" / uuid.uuid4().hex[:12]
    out_dir.mkdir(parents=True, exist_ok=True)
    spec = ProcSpec(
        argv=[str(a) for a in argv],
        cwd=cwd,
        env=env if env is not None else platform.harness_env(),
        stdin_text=stdin_text,
        timeout_s=timeout_s,
        memory_mb=memory_mb,
        as_user=None,
        out_dir=out_dir,
    )
    proc = platform.run(spec)
    return platform.wait(proc, timeout_s)
