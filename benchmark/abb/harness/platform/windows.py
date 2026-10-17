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

_adv = ctypes.WinDLL("advapi32", use_last_error=True)


class _STARTUPINFOW(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD), ("lpReserved", wintypes.LPWSTR), ("lpDesktop", wintypes.LPWSTR),
        ("lpTitle", wintypes.LPWSTR), ("dwX", wintypes.DWORD), ("dwY", wintypes.DWORD), ("dwXSize", wintypes.DWORD),
        ("dwYSize", wintypes.DWORD), ("dwXCountChars", wintypes.DWORD), ("dwYCountChars", wintypes.DWORD),
        ("dwFillAttribute", wintypes.DWORD), ("dwFlags", wintypes.DWORD), ("wShowWindow", wintypes.WORD),
        ("cbReserved2", wintypes.WORD), ("lpReserved2", ctypes.c_void_p), ("hStdInput", wintypes.HANDLE),
        ("hStdOutput", wintypes.HANDLE), ("hStdError", wintypes.HANDLE),
    ]


class _PROCESS_INFORMATION(ctypes.Structure):
    _fields_ = [("hProcess", wintypes.HANDLE), ("hThread", wintypes.HANDLE),
                ("dwProcessId", wintypes.DWORD), ("dwThreadId", wintypes.DWORD)]


_adv.CreateProcessWithLogonW.argtypes = [
    wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPWSTR,
    wintypes.DWORD, ctypes.c_void_p, wintypes.LPCWSTR, ctypes.POINTER(_STARTUPINFOW), ctypes.POINTER(_PROCESS_INFORMATION),
]
_adv.CreateProcessWithLogonW.restype = wintypes.BOOL
LOGON_FLAGS_NO_PROFILE = 0  # sandbox.yaml: logon_flags (HKCU maps to HKU\.DEFAULT, nothing persists)

# A tiny probe run AS the sandbox user by check_access/check_paths: real open()/create attempts.
_PROBE = r"""
import json, os, sys, uuid
res = []
for path, op in json.load(open(sys.argv[1], encoding="utf-8")):
    try:
        if op == "read":
            if os.path.isdir(path):
                os.listdir(path)
            else:
                with open(path, "rb") as f:
                    f.read(1)
        else:
            target = os.path.join(path, "abb-probe-" + uuid.uuid4().hex) if os.path.isdir(path) else path
            with open(target, "xb") as f:
                f.write(b"x")
            os.remove(target)
        res.append("ok")
    except PermissionError:
        res.append("denied")
    except FileNotFoundError:
        res.append("missing")
    except OSError as e:
        res.append("error:" + type(e).__name__ + ":" + str(e.errno))
json.dump(res, open(sys.argv[2], "w", encoding="utf-8"))
"""


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

        cflags = win32process.CREATE_NEW_CONSOLE | win32process.CREATE_SUSPENDED | win32process.CREATE_UNICODE_ENVIRONMENT
        try:
            if spec.as_user:
                h_proc, h_thread, pid = self._create_as_user(spec.as_user, cmdline, cflags, spec)
            else:
                si = win32process.STARTUPINFO()
                if spec.hidden:
                    si.dwFlags = win32con.STARTF_USESHOWWINDOW
                    si.wShowWindow = win32con.SW_HIDE
                h_proc, h_thread, pid, _tid = win32process.CreateProcess(
                    None, cmdline, None, None, False, cflags, _sorted_block(spec.env), str(spec.cwd), si
                )
        except (pywintypes.error, OSError) as e:
            win32api.CloseHandle(job)
            _k32.CloseHandle(port)
            code = getattr(e, "winerror", None) or getattr(e, "errno", 0)
            who = f" as {spec.as_user}" if spec.as_user else ""
            raise OSError(code, f"starting the launcher failed{who}: {e}") from e
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

    # ------------------------------------------------------------------ the sandbox user
    @staticmethod
    def sandbox_password(user: str) -> str | None:
        import keyring

        return keyring.get_password("abb", user)

    def _create_as_user(self, user: str, cmdline: str, cflags: int, spec: ProcSpec):
        """CreateProcessWithLogonW without a profile, for the launcher only; returns pywin32 handles."""
        if len(cmdline) >= 1024:
            raise OSError(206, f"launcher command line is {len(cmdline)} chars; CreateProcessWithLogonW allows 1024")
        pw = self.sandbox_password(user)
        if not pw:
            raise OSError(1326, f"no password for {user} in Credential Manager (service 'abb'): run `abb sandbox setup`")
        env = _sorted_block(spec.env)
        block = "".join(f"{k}={v}\0" for k, v in env.items()) + "\0"
        env_buf = ctypes.create_unicode_buffer(block, len(block) + 1)
        cmd_buf = ctypes.create_unicode_buffer(cmdline, len(cmdline) + 1)
        si = _STARTUPINFOW()
        si.cb = ctypes.sizeof(si)
        if spec.hidden:
            si.dwFlags = win32con.STARTF_USESHOWWINDOW
            si.wShowWindow = win32con.SW_HIDE
        pi = _PROCESS_INFORMATION()
        ok = _adv.CreateProcessWithLogonW(user, ".", pw, LOGON_FLAGS_NO_PROFILE, None, cmd_buf, cflags,
                                          ctypes.cast(env_buf, ctypes.c_void_p), str(spec.cwd), ctypes.byref(si),
                                          ctypes.byref(pi))
        del pw
        if not ok:
            err = ctypes.get_last_error()
            raise OSError(err, f"CreateProcessWithLogonW failed: {ctypes.FormatError(err).strip()}")
        return pywintypes.HANDLE(pi.hProcess), pywintypes.HANDLE(pi.hThread), pi.dwProcessId

    def run_elevated(self, exe: Path, args: list[str], *, timeout_s: int = 1800) -> int:
        """ShellExecuteEx "runas": the UAC prompt the human accepts (abb sandbox setup only). Returns the exit code."""
        from win32com.shell import shell, shellcon

        info = shell.ShellExecuteEx(fMask=shellcon.SEE_MASK_NOCLOSEPROCESS, lpVerb="runas", lpFile=str(exe),
                                    lpParameters=subprocess.list2cmdline(args), nShow=win32con.SW_SHOWNORMAL)
        h = info["hProcess"]
        try:
            if win32event.WaitForSingleObject(h, timeout_s * 1000) != win32event.WAIT_OBJECT_0:
                raise TimeoutError(f"elevated {exe.name} did not finish within {timeout_s}s")
            return int(win32process.GetExitCodeProcess(h))
        finally:
            win32api.CloseHandle(h)

    def harness_principal(self) -> str:
        """DOMAIN\\user of the harness user, for ACL grants."""
        import win32api as _wa

        return _wa.GetUserNameEx(2)  # NameSamCompatible

    def firewall_rule_present(self, name: str) -> bool:
        pwsh = paths.tools_dir() / "pwsh" / "pwsh.exe"
        from abb.harness.platform.base import run_capture

        r = run_capture(self, [str(pwsh), "-NoProfile", "-NonInteractive", "-Command",
                               f"if (Get-NetFirewallRule -DisplayName '{name}' -ErrorAction SilentlyContinue) {{ 'yes' }} else {{ 'no' }}"],
                        cwd=Path.cwd(), timeout_s=120)
        return r.stdout().strip().endswith("yes")

    def user_exists(self, user: str) -> bool:
        import win32security

        try:
            win32security.LookupAccountName(None, user)
            return True
        except pywintypes.error:
            return False

    def user_sid(self, user: str) -> str:
        import win32security

        sid, _dom, _typ = win32security.LookupAccountName(None, user)
        return win32security.ConvertSidToStringSid(sid)

    def as_user_available(self, user: str = "abb-agent") -> bool:
        return self.user_exists(user) and bool(self.sandbox_password(user))

    def check_paths(self, items: list[tuple[Path, str]], *, as_user: str, env: dict[str, str] | None = None) -> list[str]:
        """One launch as `as_user`; per (path, "read"|"create") a REAL attempt -> ok | denied | missing | error:*."""
        from abb.util import stamp

        d = paths.work_dir() / "probe" / f"{stamp()}-{os.getpid()}"
        d.mkdir(parents=True)
        self.grant(d, as_user, "modify")
        (d / "probe.py").write_text(_PROBE, encoding="utf-8")
        (d / "items.json").write_text(json.dumps([[str(p), op] for p, op in items]), encoding="utf-8")
        block = env or {**self.system_env(), "USERPROFILE": str(d), "TEMP": str(d), "TMP": str(d)}
        spec = ProcSpec(argv=[str(self.python()), "-I", str(d / "probe.py"), str(d / "items.json"), str(d / "result.json")],
                        cwd=d, env=block, stdin_text=None, timeout_s=120, memory_mb=None, as_user=as_user,
                        out_dir=d / "out")
        r = self.wait(self.run(spec))
        try:
            res = json.loads((d / "result.json").read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            raise RuntimeError(f"probe as {as_user} failed (exit {r.exit_code}): {r.stderr()[-800:]}") from e
        self.rmtree_robust(d)
        return res

    def check_access(self, path: Path, *, as_user: str, op: Literal["read", "create"]) -> Literal["ok", "denied"]:
        res = self.check_paths([(path, op)], as_user=as_user)[0]
        return "ok" if res == "ok" else "denied"

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
