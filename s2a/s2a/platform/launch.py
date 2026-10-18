"""s2a launcher (stdlib + ctypes only), started by the Windows platform layer in a private, hidden console.

    <python> -I launch.py <dir>/launch.json

launch.json: argv, cwd, stdout, stderr, stdin_text, stop_file, status_file, poll_s. It carries no
environment: this process's own environment block is handed to the child unchanged, so no
credential is written to disk.

The child shares this console and process group, so when <stop_file> appears the launcher
ignores Ctrl+C itself and sends CTRL_C_EVENT to every process on its (private) console: Claude
Code then writes its `result` line and exits (Ctrl+Break would end it without one). The caller
kills the process tree after its grace period; this script never kills anything.
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

_k32 = ctypes.WinDLL("kernel32", use_last_error=True)
_k32.GenerateConsoleCtrlEvent.argtypes = [wintypes.DWORD, wintypes.DWORD]
_k32.GenerateConsoleCtrlEvent.restype = wintypes.BOOL
_k32.SetConsoleCtrlHandler.argtypes = [ctypes.c_void_p, wintypes.BOOL]
_k32.SetConsoleCtrlHandler.restype = wintypes.BOOL
_k32.ExitProcess.argtypes = [wintypes.UINT]


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
    except OSError as e:
        status["stdin_error"] = repr(e)


def main(argv: list[str]) -> int:
    spec = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
    status_file, stop_file = Path(spec["status_file"]), Path(spec["stop_file"])
    poll_s = float(spec.get("poll_s", 0.2))
    status: dict = {"launcher_pid": os.getpid(), "started_at": _utc(), "child_pid": None, "child_exit_code": None,
                    "interrupt_sent_at": None, "interrupt_ok": None, "error": None}
    try:
        # clear an inherited "ignore Ctrl+C" so the child is created with Ctrl+C enabled
        _k32.SetConsoleCtrlHandler(None, False)
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        stdin_text = spec.get("stdin_text")
        with open(spec["stdout"], "wb") as out, open(spec["stderr"], "wb") as err:
            child = subprocess.Popen(spec["argv"], cwd=spec["cwd"],
                                     stdin=subprocess.PIPE if stdin_text is not None else subprocess.DEVNULL,
                                     stdout=out, stderr=err, env=None)
            status["child_pid"] = child.pid
            _k32.SetConsoleCtrlHandler(None, True)  # the launcher ignores the Ctrl+C it sends
            _write_status(status_file, status)
            if stdin_text is not None:
                threading.Thread(target=_feed_stdin, args=(child, stdin_text.encode("utf-8"), status),
                                 daemon=True).start()
            while True:
                rc = child.poll()
                if rc is not None:
                    break
                if status["interrupt_sent_at"] is None and stop_file.exists():
                    status["interrupt_ok"] = bool(_k32.GenerateConsoleCtrlEvent(CTRL_C_EVENT, 0))
                    status["interrupt_sent_at"] = _utc()
                    _write_status(status_file, status)
                time.sleep(poll_s)
        status["child_exit_code"] = rc
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
