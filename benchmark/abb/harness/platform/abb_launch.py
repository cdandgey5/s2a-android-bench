"""abb launcher (stdlib + ctypes only). Copied to ABB_HOME/tools/abb_launch.py by `abb tools install`.

The harness starts THIS script (suspended, assigned to a Job Object, then resumed), either as the
harness user or - from Phase 1 - as the sandbox user through CreateProcessWithLogonW, whose
1024-character command line only has to carry:

    <tools python> -I <tools>/abb_launch.py <dir>/launch.json

launch.json (written by the harness): argv, cwd, stdout, stderr, stdin_text, stop_file,
interrupt ("ctrl_break" | "ctrl_c"), status_file, poll_s. It carries NO environment: the
environment block of this process (built from scratch by the harness) is handed to the child
unchanged, so no credential is ever written to disk (D-030).

The child is started with CreateProcess (32 K argv limit). For interrupt "ctrl_break" it gets its
own process group and, when <stop_file> appears, receives CTRL_BREAK_EVENT for that group only.
For "ctrl_c" it shares the launcher's group (Ctrl+C cannot be targeted at a group, and a new
group starts with Ctrl+C disabled); the launcher then ignores Ctrl+C itself and sends
CTRL_C_EVENT to every process on its own (hidden, private) console. The harness terminates the
whole job after its grace period; this script never kills anything.
"""
from __future__ import annotations

import ctypes
import json
import os
import signal
import subprocess
import sys
import threading
import time
import traceback
from ctypes import wintypes
from pathlib import Path

CTRL_C_EVENT = 0
CTRL_BREAK_EVENT = 1
CREATE_NEW_PROCESS_GROUP = 0x00000200

_k32 = ctypes.WinDLL("kernel32", use_last_error=True)
_u32 = ctypes.WinDLL("user32", use_last_error=True)
_k32.GetConsoleWindow.restype = wintypes.HWND
_k32.GenerateConsoleCtrlEvent.argtypes = [wintypes.DWORD, wintypes.DWORD]
_k32.GenerateConsoleCtrlEvent.restype = wintypes.BOOL
_k32.SetConsoleCtrlHandler.argtypes = [ctypes.c_void_p, wintypes.BOOL]
_k32.SetConsoleCtrlHandler.restype = wintypes.BOOL
_k32.ExitProcess.argtypes = [wintypes.UINT]
_u32.IsWindowVisible.argtypes = [wintypes.HWND]
_u32.IsWindowVisible.restype = wintypes.BOOL


def _utc() -> str:
    t = time.time()
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(t)) + f".{int((t % 1) * 1000):03d}Z"


def _write_status(path: Path, status: dict) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(status, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def _feed_stdin(child: subprocess.Popen, data: bytes, status: dict) -> None:
    try:
        child.stdin.write(data)
        child.stdin.close()
    except OSError as e:  # child exited before reading everything
        status["stdin_error"] = repr(e)


def main(argv: list[str]) -> int:
    spec_path = Path(argv[1])
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    status_file = Path(spec["status_file"])
    stop_file = Path(spec["stop_file"])
    interrupt = spec.get("interrupt", "ctrl_break")
    poll_s = float(spec.get("poll_s", 0.2))
    hwnd = _k32.GetConsoleWindow()
    status: dict = {
        "launcher_pid": os.getpid(),
        "started_at": _utc(),
        "interrupt_mode": interrupt,
        "interrupt_sent": None,
        "interrupt_sent_at": None,
        "interrupt_ok": None,
        "console_window": bool(hwnd),
        "console_window_visible": bool(hwnd) and bool(_u32.IsWindowVisible(hwnd)),
        "child_pid": None,
        "child_exit_code": None,
        "child_exited_at": None,
        "error": None,
    }
    try:
        flags = CREATE_NEW_PROCESS_GROUP if interrupt == "ctrl_break" else 0
        if interrupt == "ctrl_c":
            # "ignore Ctrl+C" is inherited from whoever started the harness (e.g. a shell spawned with
            # CREATE_NEW_PROCESS_GROUP); clear it so the child is created with Ctrl+C enabled
            _k32.SetConsoleCtrlHandler(None, False)
            signal.signal(signal.SIGINT, signal.SIG_IGN)  # the launcher itself still ignores it
        stdin_text = spec.get("stdin_text")
        with open(spec["stdout"], "wb") as out, open(spec["stderr"], "wb") as err:
            child = subprocess.Popen(
                spec["argv"],
                cwd=spec["cwd"],
                stdin=subprocess.PIPE if stdin_text is not None else subprocess.DEVNULL,
                stdout=out,
                stderr=err,
                creationflags=flags,
                env=None,  # this process's own block, unchanged
            )
            status["child_pid"] = child.pid
            if interrupt == "ctrl_c":
                # after the child exists, so it does not inherit "ignore Ctrl+C"
                _k32.SetConsoleCtrlHandler(None, True)
                signal.signal(signal.SIGINT, signal.SIG_IGN)
            _write_status(status_file, status)
            if stdin_text is not None:
                threading.Thread(
                    target=_feed_stdin, args=(child, stdin_text.encode("utf-8"), status), daemon=True
                ).start()
            while True:
                rc = child.poll()
                if rc is not None:
                    break
                if status["interrupt_sent"] is None and stop_file.exists():
                    if interrupt == "ctrl_break":
                        ok = _k32.GenerateConsoleCtrlEvent(CTRL_BREAK_EVENT, child.pid)
                    else:
                        ok = _k32.GenerateConsoleCtrlEvent(CTRL_C_EVENT, 0)
                    status["interrupt_sent"] = interrupt
                    status["interrupt_sent_at"] = _utc()
                    status["interrupt_ok"] = bool(ok)
                    if not ok:
                        status["interrupt_error"] = ctypes.get_last_error()
                    _write_status(status_file, status)
                time.sleep(poll_s)
        status["child_exit_code"] = rc
        status["child_exited_at"] = _utc()
        _write_status(status_file, status)
        return rc
    except BaseException:  # noqa: BLE001 - the status file is the only channel back
        status["error"] = traceback.format_exc()
        _write_status(status_file, status)
        return 125


if __name__ == "__main__":
    code = main(sys.argv)
    sys.stdout.flush()
    _k32.ExitProcess(code & 0xFFFFFFFF)
