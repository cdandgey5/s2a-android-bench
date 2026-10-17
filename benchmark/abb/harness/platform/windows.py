"""Windows implementation of the platform layer (specs/platform-layer.md).

The only module (with abb_launch.py) allowed to touch pywin32, ctypes-for-Win32, icacls or the
registry. Every process goes: harness -> launcher (suspended, in a Job Object, resumed) -> command.
"""
from __future__ import annotations

import ctypes
import json
import os
import platform as _pyplatform
import shutil
import stat
import subprocess
import sys
import time
from ctypes import wintypes
from pathlib import Path
from typing import Literal

import pywintypes
import win32api
import win32con
import win32event
import win32job
import win32process

from abb import paths
from abb.harness.platform.base import Proc, ProcResult, ProcSpec

JOB_OBJECT_MSG_END_OF_JOB_TIME = 1
JOB_OBJECT_MSG_ACTIVE_PROCESS_ZERO = 4
JOB_OBJECT_MSG_PROCESS_MEMORY_LIMIT = 9
JOB_OBJECT_MSG_JOB_MEMORY_LIMIT = 10
CREATE_NO_WINDOW = 0x08000000
INFINITE = 0xFFFFFFFF

_k32 = ctypes.WinDLL("kernel32", use_last_error=True)
_k32.CreateIoCompletionPort.argtypes = [wintypes.HANDLE, wintypes.HANDLE, ctypes.c_size_t, wintypes.DWORD]
_k32.CreateIoCompletionPort.restype = wintypes.HANDLE
_k32.GetQueuedCompletionStatus.argtypes = [
    wintypes.HANDLE,
    ctypes.POINTER(wintypes.DWORD),
    ctypes.POINTER(ctypes.c_size_t),
    ctypes.POINTER(ctypes.c_void_p),
    wintypes.DWORD,
]
_k32.GetQueuedCompletionStatus.restype = wintypes.BOOL
_k32.CloseHandle.argtypes = [wintypes.HANDLE]
_k32.GetVolumePathNameW.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.DWORD]
_k32.GetVolumeInformationW.argtypes = [
    wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD),
    ctypes.POINTER(wintypes.DWORD), ctypes.POINTER(wintypes.DWORD), wintypes.LPWSTR, wintypes.DWORD,
]


class _JOBOBJECT_ASSOCIATE_COMPLETION_PORT(ctypes.Structure):
    _fields_ = [("CompletionKey", ctypes.c_void_p), ("CompletionPort", wintypes.HANDLE)]


_k32.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
_k32.SetInformationJobObject.restype = wintypes.BOOL
_JobObjectAssociateCompletionPortInformation = 7

# Variables a process needs to function on Windows; everything else in an agent block is explicit.
SYSTEM_VARS = [
    "SystemRoot", "windir", "SystemDrive", "ComSpec", "PATHEXT", "OS",
    "PROCESSOR_ARCHITECTURE", "PROCESSOR_IDENTIFIER", "PROCESSOR_LEVEL", "PROCESSOR_REVISION",
    "NUMBER_OF_PROCESSORS", "ProgramFiles", "ProgramFiles(x86)", "ProgramW6432",
    "CommonProgramFiles", "CommonProgramFiles(x86)", "CommonProgramW6432", "ProgramData",
    "ALLUSERSPROFILE", "PUBLIC", "COMPUTERNAME", "DriverData",
]
# Never passed to a harness subprocess: credentials and the desktop app's session variables.
_HARNESS_SCRUB_PREFIXES = ("CLAUDE", "ANTHROPIC", "ABB_OAUTH_TOKEN", "MCP_", "ENABLE_IDE_INTEGRATION")


def _env_get(name: str) -> str | None:
    for k, v in os.environ.items():
        if k.upper() == name.upper():
            return v
    return None


def _sorted_block(env: dict[str, str]) -> dict[str, str]:
    seen: dict[str, str] = {}
    for k in sorted(env, key=str.upper):
        if k.upper() in (s.upper() for s in seen):
            raise ValueError(f"duplicate environment variable (case-insensitive): {k}")
        seen[k] = str(env[k])
    return seen


class WindowsPlatform:
    id = "windows"

    # ------------------------------------------------------------------ paths and tools
    def gradlew(self, repo_dir: Path) -> list[str]:
        return [str(Path(repo_dir) / "gradlew.bat")]

    def python(self) -> Path:
        """The shared tools interpreter (ABB_HOME/tools/python/...); before `abb tools install`
        the base interpreter of the harness venv (never the venv trampoline)."""
        cands = sorted(paths.tools_dir().glob("python/cpython-3.12*-windows-x86_64-none/python.exe"))
        if cands:
            return cands[-1]
        return Path(getattr(sys, "_base_executable", sys.executable))

    def claude_exe(self) -> Path:
        from abb.config import load_toolchain

        return paths.tools_dir() / "claude" / load_toolchain().claude_code.version / "claude.exe"

    def launcher_path(self) -> Path:
        """ABB_HOME/tools/abb_launch.py, refreshed from the package source when it differs."""
        src = Path(__file__).with_name("abb_launch.py")
        dst = paths.tools_dir() / "abb_launch.py"
        if not dst.exists() or dst.read_bytes() != src.read_bytes():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dst)
        return dst

    def find_exe(self, name: str) -> Path | None:
        p = shutil.which(name)
        return Path(p) if p else None

    # ------------------------------------------------------------------ environment blocks
    def system_env(self) -> dict[str, str]:
        env = {}
        for name in SYSTEM_VARS:
            v = _env_get(name)
            if v is not None:
                env[name] = v
        return env

    def harness_env(self, extra: dict[str, str] | None = None) -> dict[str, str]:
        """The harness user's own environment for harness-side tools (git, Gradle, sdkmanager),
        minus credentials and the desktop app's CLAUDE_*/ANTHROPIC_* session variables."""
        env = {k: v for k, v in os.environ.items() if not k.upper().startswith(_HARNESS_SCRUB_PREFIXES)}
        for k, v in (extra or {}).items():
            for existing in [e for e in env if e.upper() == k.upper()]:
                del env[existing]
            env[k] = v
        return env

    # ------------------------------------------------------------------ processes
    def run(self, spec: ProcSpec) -> Proc:
        if spec.as_user:
            raise NotImplementedError("launch as the sandbox user arrives in Phase 1 (CreateProcessWithLogonW)")
        out_dir = Path(spec.out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        stop_file = Path(spec.stop_file) if spec.stop_file else out_dir / "STOP"
        if stop_file.exists():
            stop_file.unlink()
        status_file = out_dir / "launcher.json"
        if status_file.exists():
            status_file.unlink()
        launch = {
            "argv": [str(a) for a in spec.argv],
            "cwd": str(spec.cwd),
            "stdout": str(out_dir / "stdout.txt"),
            "stderr": str(out_dir / "stderr.txt"),
            "stdin_text": spec.stdin_text,
            "stop_file": str(stop_file),
            "interrupt": spec.interrupt,
            "status_file": str(status_file),
            "poll_s": 0.2,
        }
        launch_json = out_dir / "launch.json"
        launch_json.write_text(json.dumps(launch, indent=2), encoding="utf-8")
        cmdline = subprocess.list2cmdline([str(self.python()), "-I", str(self.launcher_path()), str(launch_json)])

        job = win32job.CreateJobObject(None, "")
        info = win32job.QueryInformationJobObject(job, win32job.JobObjectExtendedLimitInformation)
        flags = win32job.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if spec.memory_mb:
            flags |= win32job.JOB_OBJECT_LIMIT_JOB_MEMORY
            info["JobMemoryLimit"] = int(spec.memory_mb) * 1024 * 1024
        info["BasicLimitInformation"]["LimitFlags"] = flags  # no BREAKAWAY_OK: children cannot leave
        win32job.SetInformationJobObject(job, win32job.JobObjectExtendedLimitInformation, info)
        port = _k32.CreateIoCompletionPort(wintypes.HANDLE(-1), None, 0, 1)
        assoc = _JOBOBJECT_ASSOCIATE_COMPLETION_PORT(1, port)
        if not _k32.SetInformationJobObject(
            int(job), _JobObjectAssociateCompletionPortInformation, ctypes.byref(assoc), ctypes.sizeof(assoc)
        ):
            raise OSError(ctypes.get_last_error(), "SetInformationJobObject(completion port) failed")

        si = win32process.STARTUPINFO()
        if spec.hidden:
            si.dwFlags = win32con.STARTF_USESHOWWINDOW
            si.wShowWindow = win32con.SW_HIDE
        cflags = win32process.CREATE_NEW_CONSOLE | win32process.CREATE_SUSPENDED | win32process.CREATE_UNICODE_ENVIRONMENT
        try:
            h_proc, h_thread, pid, _tid = win32process.CreateProcess(
                None, cmdline, None, None, False, cflags, _sorted_block(spec.env), str(spec.cwd), si
            )
        except pywintypes.error as e:
            win32api.CloseHandle(job)
            _k32.CloseHandle(port)
            raise OSError(e.winerror, f"CreateProcess failed for the launcher: {e.strerror}") from e
        try:
            win32job.AssignProcessToJobObject(job, h_proc)
        except pywintypes.error:
            win32process.TerminateProcess(h_proc, 1)
            raise
        win32process.ResumeThread(h_thread)
        win32api.CloseHandle(h_thread)
        return Proc(
            pid=pid,
            spec=spec,
            started_monotonic=time.monotonic(),
            stop_file=stop_file,
            handle={"proc": h_proc, "job": job, "port": port, "status_file": status_file},
        )

    def _launcher_exited(self, proc: Proc, wait_ms: int) -> bool:
        return win32event.WaitForSingleObject(proc.handle["proc"], wait_ms) == win32event.WAIT_OBJECT_0

    def stop_gracefully(self, proc: Proc, grace_s: int = 30) -> None:
        """STOP file -> the launcher sends the configured interrupt to the child -> wait -> kill the job."""
        proc.stop_file.parent.mkdir(parents=True, exist_ok=True)
        proc.stop_file.write_text("stop\n", encoding="utf-8")
        if not self._launcher_exited(proc, int(grace_s * 1000)):
            win32job.TerminateJobObject(proc.handle["job"], 1)
            self._launcher_exited(proc, 10_000)

    def wait(self, proc: Proc, timeout_s: int | None = None) -> ProcResult:
        h = proc.handle
        limit = proc.spec.timeout_s if timeout_s is None else timeout_s
        deadline = proc.started_monotonic + limit
        stopped = False
        while not self._launcher_exited(proc, 200):
            if time.monotonic() >= deadline:
                stopped = True
                self.stop_gracefully(proc, proc.spec.grace_s)
                break
        launcher_rc = win32process.GetExitCodeProcess(h["proc"])
        status = {}
        try:
            status = json.loads(Path(h["status_file"]).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            pass
        info = win32job.QueryInformationJobObject(h["job"], win32job.JobObjectExtendedLimitInformation)
        peak = int(info["PeakJobMemoryUsed"]) // (1024 * 1024)
        # stragglers (daemons, shells) die with the job; the launcher is already gone
        try:
            win32job.TerminateJobObject(h["job"], 1)
        except pywintypes.error:
            pass
        mem_hit = False
        n_bytes, key, ov = wintypes.DWORD(), ctypes.c_size_t(), ctypes.c_void_p()
        while _k32.GetQueuedCompletionStatus(h["port"], ctypes.byref(n_bytes), ctypes.byref(key), ctypes.byref(ov), 0):
            if n_bytes.value in (JOB_OBJECT_MSG_JOB_MEMORY_LIMIT, JOB_OBJECT_MSG_PROCESS_MEMORY_LIMIT):
                mem_hit = True
        win32api.CloseHandle(h["job"])
        _k32.CloseHandle(h["port"])
        win32api.CloseHandle(h["proc"])
        if status.get("child_exit_code") is not None:
            exit_code: int | None = int(status["child_exit_code"])
        elif stopped:
            exit_code = None  # killed by the harness before the child ended
        else:
            exit_code = int(launcher_rc)
        if status.get("error"):
            raise RuntimeError(f"launcher failed: {status['error']}")
        out_dir = Path(proc.spec.out_dir)
        return ProcResult(
            exit_code=exit_code,
            stopped_by_harness=stopped,
            duration_s=round(time.monotonic() - proc.started_monotonic, 3),
            peak_memory_mb=peak,
            job_memory_hit=mem_hit,
            stdout_path=out_dir / "stdout.txt",
            stderr_path=out_dir / "stderr.txt",
            launcher=status,
        )

    # ------------------------------------------------------------------ ACLs (applied in Phase 1)
    def _icacls(self, *args: str) -> None:
        from abb.harness.platform.base import run_capture

        icacls = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "icacls.exe"
        r = run_capture(self, [str(icacls), *args], cwd=Path.cwd(), timeout_s=600)
        if r.exit_code != 0:
            raise OSError(f"icacls {' '.join(args)} failed ({r.exit_code}): {r.stdout()} {r.stderr()}")

    def grant(self, path: Path, principal: str, rights: Literal["rx", "modify", "deny"], *, inherit: bool = True) -> None:
        inh = "(OI)(CI)" if inherit and Path(path).is_dir() else ""
        if rights == "rx":
            self._icacls(str(path), "/grant:r", f"{principal}:{inh}RX")
        elif rights == "modify":
            self._icacls(str(path), "/grant:r", f"{principal}:{inh}M")
        elif rights == "deny":
            self._icacls(str(path), "/deny", f"{principal}:{inh}F")
        else:
            raise ValueError(rights)

    def deny_write(self, path: Path, principal: str) -> None:
        if Path(path).is_dir():
            self._icacls(str(path), "/deny", f"{principal}:(OI)(CI)(W,WA,WD,AD,DC)")
        else:
            self._icacls(str(path), "/deny", f"{principal}:(W,WA,WD,DC)")

    def reset_inheritance(self, root: Path, owners: list[str]) -> None:
        grants: list[str] = []
        for o in owners:
            grants += ["/grant:r", f"{o}:(OI)(CI)F"]
        self._icacls(str(root), "/inheritance:r", *grants)

    def check_access(self, path: Path, *, as_user: str, op: Literal["read", "create"]) -> Literal["ok", "denied"]:
        raise NotImplementedError("check_access runs as the sandbox user: Phase 1")

    def as_user_available(self) -> bool:
        return False  # Phase 1: sandbox user + credential present

    # ------------------------------------------------------------------ misc
    def env_fingerprint_parts(self) -> dict:
        return {
            "platform": self.id,
            "os_release": _pyplatform.release(),
            "os_version": _pyplatform.version(),
            "arch": _pyplatform.machine(),
        }

    def enable_long_paths(self) -> None:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\FileSystem", 0, winreg.KEY_SET_VALUE
        ) as k:
            winreg.SetValueEx(k, "LongPathsEnabled", 0, winreg.REG_DWORD, 1)

    def long_paths_enabled(self) -> bool:
        import winreg

        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\FileSystem") as k:
                return winreg.QueryValueEx(k, "LongPathsEnabled")[0] == 1
        except OSError:
            return False

    def volume_filesystem(self, path: Path) -> str:
        p = Path(path)
        while not p.exists() and p != p.parent:
            p = p.parent
        vol = ctypes.create_unicode_buffer(260)
        if not _k32.GetVolumePathNameW(str(p), vol, 260):
            raise OSError(ctypes.get_last_error(), f"GetVolumePathNameW({p})")
        fs = ctypes.create_unicode_buffer(64)
        if not _k32.GetVolumeInformationW(vol.value, None, 0, None, None, None, fs, 64):
            raise OSError(ctypes.get_last_error(), f"GetVolumeInformationW({vol.value})")
        return fs.value

    def rmtree_robust(self, path: Path) -> list[Path]:
        path = Path(path)
        if not path.exists():
            return []

        def _onexc(func, p, _exc):  # read-only files (git objects) block deletion on Windows
            try:
                os.chmod(p, stat.S_IWRITE)
                func(p)
            except OSError:
                pass

        for _ in range(10):
            try:
                shutil.rmtree(path, onexc=_onexc)
            except OSError:
                pass
            if not path.exists():
                return []
            time.sleep(0.5)
        left = [p for p in path.rglob("*") if p.is_file()]
        return left or [path]
