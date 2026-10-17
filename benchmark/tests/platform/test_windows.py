"""Common platform-layer suite (specs/platform-layer.md rule 5), Windows implementation.

Sandbox-user cases (deny/grant round trip as abb-agent, profile hash) arrive with Phase 1.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from abb.harness.platform import ProcSpec, get_platform

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows implementation")
PLAT = get_platform() if sys.platform == "win32" else None


def _py() -> str:
    return str(PLAT.python())


def _spec(tmp_path: Path, code: str, **kw) -> ProcSpec:
    base = dict(argv=[_py(), "-I", "-c", code], cwd=tmp_path, env=PLAT.system_env(), stdin_text=None,
                timeout_s=60, memory_mb=None, as_user=None, out_dir=tmp_path / "out")
    base.update(kw)
    return ProcSpec(**base)


def test_exit_code_stdout_and_stdin(tmp_path: Path) -> None:
    code = "import sys; d = sys.stdin.read(); print('got:' + d.upper()); sys.exit(7)"
    r = PLAT.wait(PLAT.run(_spec(tmp_path, code, stdin_text="hello")))
    assert r.exit_code == 7 and not r.stopped_by_harness
    assert r.stdout().strip() == "got:HELLO"
    assert r.peak_memory_mb and r.peak_memory_mb > 0
    assert r.launcher["console_window_visible"] is False


def test_env_block_is_not_inherited(tmp_path: Path) -> None:
    os.environ["ABB_TEST_SHOULD_NOT_LEAK"] = "1"
    try:
        env = PLAT.system_env() | {"ABB_PROBE": "x"}
        r = PLAT.wait(PLAT.run(_spec(tmp_path, "import os; print(sorted(os.environ))", env=env)))
    finally:
        del os.environ["ABB_TEST_SHOULD_NOT_LEAK"]
    keys = r.stdout()
    assert "ABB_PROBE" in keys and "ABB_TEST_SHOULD_NOT_LEAK" not in keys and "CLAUDECODE" not in keys


def test_launch_json_carries_no_environment(tmp_path: Path) -> None:
    secret = "-".join(["sk", "ant", "oat99", "not", "a", "real", "token"])  # built at runtime: no token-shaped literal in git
    PLAT.wait(PLAT.run(_spec(tmp_path, "print(1)", env=PLAT.system_env() | {"CLAUDE_CODE_OAUTH_TOKEN": secret})))
    for f in (tmp_path / "out").iterdir():
        assert secret.encode() not in f.read_bytes(), f.name


def test_deadline_stops_sleeping_process(tmp_path: Path) -> None:
    t0 = time.monotonic()
    r = PLAT.wait(PLAT.run(_spec(tmp_path, "import time; time.sleep(600)", timeout_s=3, grace_s=2)))
    assert r.stopped_by_harness
    assert time.monotonic() - t0 < 20


@pytest.mark.parametrize("mode,sig", [("ctrl_break", "SIGBREAK"), ("ctrl_c", "SIGINT")])
def test_graceful_stop_delivers_interrupt(tmp_path: Path, mode: str, sig: str) -> None:
    code = (
        "import signal, sys, time\n"
        f"signal.signal(signal.{sig}, lambda *a: (print('GOT_{sig}', flush=True), sys.exit(3)))\n"
        "print('ready', flush=True)\n"
        "for _ in range(6000): time.sleep(0.1)\n"  # one long sleep is not woken by SIGBREAK on Windows
    )
    r = PLAT.wait(PLAT.run(_spec(tmp_path, code, timeout_s=4, grace_s=15, interrupt=mode)))
    assert r.stopped_by_harness
    assert f"GOT_{sig}" in r.stdout()
    assert r.launcher["interrupt_sent"] == mode and r.launcher["interrupt_ok"] is True
    assert r.exit_code == 3


def test_job_memory_limit_is_reported_not_raised(tmp_path: Path) -> None:
    code = "b = bytearray(600 * 1024 * 1024)\nprint(len(b))"
    r = PLAT.wait(PLAT.run(_spec(tmp_path, code, memory_mb=256)))
    assert r.job_memory_hit
    assert r.exit_code not in (0, None)
    assert "MemoryError" in r.stderr()


def test_tree_is_killed_with_the_job(tmp_path: Path) -> None:
    pidfile = tmp_path / "grandchild.pid"
    code = (
        "import subprocess, sys, time\n"
        f"p = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(600)'])\n"
        f"open(r'{pidfile}', 'w').write(str(p.pid))\n"
        "time.sleep(600)\n"
    )
    r = PLAT.wait(PLAT.run(_spec(tmp_path, code, timeout_s=4, grace_s=1)))
    assert r.stopped_by_harness
    gpid = int(pidfile.read_text())
    out = subprocess.run(["tasklist", "/FI", f"PID eq {gpid}", "/NH"], capture_output=True, text=True).stdout
    assert str(gpid) not in out


def test_robust_delete_readonly_and_locked(tmp_path: Path) -> None:
    root = tmp_path / "victim"
    (root / "sub").mkdir(parents=True)
    ro = root / "sub" / "ro.txt"
    ro.write_text("x")
    ro.chmod(0o444)
    locked = root / "locked.bin"
    locked.write_bytes(b"x")
    # a child holds the file open without FILE_SHARE_DELETE
    holder = subprocess.Popen([_py(), "-I", "-c", f"f = open(r'{locked}', 'rb'); import time; time.sleep(30)"])
    try:
        time.sleep(1.0)
        left = PLAT.rmtree_robust(root)
        assert locked in left
    finally:
        holder.kill()
        holder.wait()
    assert PLAT.rmtree_robust(root) == []
    assert not root.exists()


def test_gradlew_and_volume() -> None:
    assert PLAT.gradlew(Path("C:/x"))[0].endswith("gradlew.bat")
    assert PLAT.volume_filesystem(Path.home()).upper() in ("NTFS", "REFS")


@pytest.mark.skip(reason="Phase 1: needs the sandbox user abb-agent (deny/grant round trip, profile hash)")
def test_sandbox_user_access_round_trip() -> None:  # pragma: no cover
    pass
