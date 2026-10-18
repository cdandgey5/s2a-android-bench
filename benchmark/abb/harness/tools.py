"""`abb tools install|check` (specs/environments.md §2).

Installs the pinned toolchain ONCE, as the harness user, into ABB_HOME/tools: Temurin JDK 17/21
(Adoptium API; first install records release_name + sha256 in config/toolchain.lock.yaml, later
installs fetch exactly that release), the Windows Android command-line tools (sha256 from
config/toolchain.yaml) + the pinned sdkmanager packages, CPython 3.12 (uv), a copy of the pinned
claude.exe, the launcher, Spec Kit's `specify` (uv tool), and the harness user's git config.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

import yaml

from abb import paths
from abb.config import ToolchainConfig, load_toolchain
from abb.harness.platform import get_platform, run_capture
from abb.log import get_logger
from abb.util import sha256_file, utcnow_iso

log = get_logger("abb.tools")
ADOPTIUM = "https://api.adoptium.net/v3"
UA = {"User-Agent": "abb-tools/0.1 (+https://github.com/cdandgey5/s2a-android-bench)"}


class ToolError(RuntimeError):
    pass


def lock_path() -> Path:
    return paths.config_dir() / "toolchain.lock.yaml"


def load_lock() -> dict:
    p = lock_path()
    if not p.exists():
        return {}
    return yaml.safe_load(p.read_text(encoding="utf-8")) or {}


def save_lock(lock: dict) -> None:
    header = "# Written by `abb tools install`; verified by `abb tools check`. Paths are relative to ABB_HOME.\n"
    lock_path().write_text(header + yaml.safe_dump(lock, sort_keys=True), encoding="utf-8", newline="\n")


def _rel(p: Path) -> str:
    return p.relative_to(paths.abb_home()).as_posix()


def _get_json(url: str):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def download(url: str, dest: Path, sha256: str | None) -> Path:
    """Download into its own directory; verify sha256 when given. Re-uses a matching file."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and sha256 and sha256_file(dest) == sha256:
        log.info("cached %s", dest.name)
        return dest
    tmp = dest.with_suffix(dest.suffix + ".part")
    log.info("downloading %s", url)
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=120) as r, open(tmp, "wb") as f:
        total = 0
        while chunk := r.read(1 << 20):
            f.write(chunk)
            total += len(chunk)
    got = sha256_file(tmp)
    if sha256 and got != sha256:
        tmp.unlink()
        raise ToolError(f"sha256 mismatch for {url}: expected {sha256}, got {got}")
    tmp.replace(dest)
    log.info("downloaded %s (%.1f MB)", dest.name, total / 1e6)
    return dest


def _extract_single_root(zip_path: Path, target: Path, staging_name: str) -> None:
    """Unzip into a fresh, empty staging dir; move its single top-level folder to `target`."""
    plat = get_platform()
    staging = paths.tools_dir() / "_staging" / staging_name
    if staging.exists():
        left = plat.rmtree_robust(staging)
        if left:
            raise ToolError(f"cannot clear {staging}: {left[:3]}")
    staging.mkdir(parents=True)
    with zipfile.ZipFile(zip_path) as z:
        z.extractall(staging)
    roots = [p for p in staging.iterdir()]
    if len(roots) != 1 or not roots[0].is_dir():
        raise ToolError(f"{zip_path.name}: expected one top-level directory, found {[r.name for r in roots]}")
    if target.exists():
        left = plat.rmtree_robust(target)
        if left:
            raise ToolError(f"cannot replace {target}: {left[:3]}")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(roots[0]), str(target))
    plat.rmtree_robust(staging)


def _run(argv: list, *, cwd: Path | None = None, extra_env: dict | None = None, stdin_text: str | None = None,
         timeout_s: int = 1800, check: bool = True):
    plat = get_platform()
    r = run_capture(
        plat, [str(a) for a in argv], cwd=cwd or paths.abb_home(), env=plat.harness_env(extra_env),
        timeout_s=timeout_s, stdin_text=stdin_text,
    )
    if check and r.exit_code != 0:
        raise ToolError(f"{Path(str(argv[0])).name} {' '.join(map(str, argv[1:]))[:200]} -> exit {r.exit_code}\n"
                        f"{r.stdout()[-2000:]}\n{r.stderr()[-2000:]}")
    return r


# ---------------------------------------------------------------------------- JDK
def _adoptium_pick(binaries: list[dict]) -> dict:
    for b in binaries:
        pkg = b.get("package") or {}
        if (b.get("os") == "windows" and b.get("architecture") == "x64" and b.get("image_type") == "jdk"
                and pkg.get("name", "").endswith(".zip")):
            return b
    raise ToolError("no windows-x64 jdk zip in the Adoptium answer")


def jdk_dir(major: int) -> Path:
    return paths.tools_dir() / f"jdk{major}"


def install_jdk(major: int, lock: dict) -> None:
    key = f"jdk{major}"
    locked = lock.get(key)
    q = "architecture=x64&image_type=jdk&os=windows&jvm_impl=hotspot&heap_size=normal&project=jdk"
    if locked:
        rel = urllib.parse.quote(locked["release_name"], safe="")
        release = _get_json(f"{ADOPTIUM}/assets/release_name/eclipse/{rel}?{q}")
        b = _adoptium_pick(release["binaries"])
        release_name = release["release_name"]
    else:
        items = _get_json(f"{ADOPTIUM}/assets/latest/{major}/hotspot?architecture=x64&image_type=jdk&os=windows&vendor=eclipse")
        b = _adoptium_pick([i["binary"] for i in items])
        release_name = next(i["release_name"] for i in items if i["binary"] is b)
    pkg = b["package"]
    sha = pkg["checksum"]
    if locked and locked["sha256"] != sha:
        raise ToolError(f"{key}: Adoptium now reports sha256 {sha} for {release_name}, lock has {locked['sha256']}")
    zp = download(pkg["link"], paths.tools_dir() / "_downloads" / key / pkg["name"], sha)
    target = jdk_dir(major)
    marker = target / ".abb-release"
    if not (marker.exists() and marker.read_text(encoding="utf-8").strip() == release_name):
        _extract_single_root(zp, target, key)
        marker.write_text(release_name + "\n", encoding="utf-8")
    lock[key] = {"release_name": release_name, "zip": pkg["name"], "sha256": sha, "url": pkg["link"],
                 "path": _rel(target)}
    log.info("%s = %s", key, release_name)


def java_version(major: int) -> str:
    r = _run([jdk_dir(major) / "bin" / "java.exe", "-version"])
    return (r.stderr() or r.stdout()).strip()


# ---------------------------------------------------------------------------- Python (uv)
def _uv() -> Path:
    uv = get_platform().find_exe("uv")
    if not uv:
        raise ToolError("uv not found on PATH (docs/DAY-0.md §1)")
    return uv


def _expand(tc_path: str) -> Path:
    return Path(tc_path.replace("$ABB_HOME", str(paths.abb_home())))


def install_python(tc: ToolchainConfig, lock: dict) -> Path:
    install_dir = _expand(tc.python.uv_python_install_dir)
    _run([_uv(), "python", "install", tc.python.version, "--no-bin"],
         extra_env={"UV_PYTHON_INSTALL_DIR": str(install_dir)})
    cands = sorted(install_dir.glob(f"cpython-{tc.python.version}.*-windows-x86_64-none/python.exe"))
    if not cands:
        raise ToolError(f"no CPython {tc.python.version} under {install_dir}")
    exe = cands[-1]
    ver = _run([exe, "-I", "-c", "import sys; print(sys.version.split()[0])"]).stdout().strip()
    lock["python"] = {"version": ver, "path": _rel(exe)}
    log.info("python = %s (%s)", ver, exe)
    return exe


# ---------------------------------------------------------------------------- Claude Code
def _claude_version(exe: Path) -> str:
    r = _run([exe, "--version"], extra_env={"DISABLE_AUTOUPDATER": "1", "DISABLE_UPDATES": "1"}, timeout_s=120)
    m = re.match(r"\s*(\d+\.\d+\.\d+)", r.stdout())
    if not m:
        raise ToolError(f"cannot parse `{exe} --version`: {r.stdout()!r}")
    return m.group(1)


def claude_copy_path(tc: ToolchainConfig) -> Path:
    return paths.tools_dir() / "claude" / tc.claude_code.version / "claude.exe"


def install_claude(tc: ToolchainConfig, lock: dict) -> None:
    pin = tc.claude_code.version
    dst = claude_copy_path(tc)
    locked = lock.get("claude_code")
    if dst.exists() and locked and locked.get("version") == pin and sha256_file(dst) == locked["sha256"]:
        log.info("claude.exe %s already in place", pin)
        return
    src = Path.home() / ".local" / "bin" / "claude.exe"
    if not src.exists():
        raise ToolError(f"{src} missing (docs/DAY-0.md §1)")
    have = _claude_version(src)
    if have != pin:
        raise ToolError(
            f"harness user's claude.exe is {have}, toolchain.yaml pins {pin}: reinstall the pin with "
            f"& ([scriptblock]::Create((irm https://claude.ai/install.ps1))) {pin}"
        )
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)
    if _claude_version(dst) != pin:
        raise ToolError(f"copied claude.exe does not report {pin}")
    lock["claude_code"] = {"version": pin, "sha256": sha256_file(dst), "path": _rel(dst)}
    log.info("claude.exe %s copied to %s", pin, dst)


# ---------------------------------------------------------------------------- Android SDK
def sdk_root() -> Path:
    return paths.tools_dir() / "android-sdk"


def sdkmanager() -> Path:
    return sdk_root() / "cmdline-tools" / "latest" / "bin" / "sdkmanager.bat"


def _sdk_env() -> dict:
    jh = jdk_dir(17)

    return {"JAVA_HOME": str(jh), "ANDROID_HOME": str(sdk_root()),
            "PATH": str(jh / "bin") + os.pathsep + get_platform().harness_env().get("PATH", "")}


def sdk_list_installed() -> dict[str, str]:
    r = _run([sdkmanager(), f"--sdk_root={sdk_root()}", "--list_installed"], extra_env=_sdk_env(), timeout_s=600)
    out: dict[str, str] = {}
    for line in r.stdout().splitlines():
        parts = [p.strip() for p in line.split("|")]
        if len(parts) >= 3 and parts[0] and parts[0] != "Path" and not parts[0].startswith("-"):
            out[parts[0]] = parts[1]
    return out


def install_android(tc: ToolchainConfig, lock: dict, extra_packages: list[str] | None = None) -> None:
    a = tc.android
    zp = download(a.base_url + a.cmdline_tools_zip, paths.tools_dir() / "_downloads" / "cmdline-tools" / a.cmdline_tools_zip,
                  a.cmdline_tools_sha256)
    latest = sdk_root() / "cmdline-tools" / "latest"
    marker = latest / ".abb-zip"
    if not (marker.exists() and marker.read_text(encoding="utf-8").strip() == a.cmdline_tools_zip):
        _extract_single_root(zp, latest, "cmdline-tools")
        marker.write_text(a.cmdline_tools_zip + "\n", encoding="utf-8")
    yes = "y\n" * 100
    _run([sdkmanager(), f"--sdk_root={sdk_root()}", "--licenses"], extra_env=_sdk_env(), stdin_text=yes, timeout_s=600)
    pkgs = list(dict.fromkeys(a.packages + (extra_packages or [])))
    _run([sdkmanager(), f"--sdk_root={sdk_root()}", *pkgs], extra_env=_sdk_env(), stdin_text=yes, timeout_s=3600)
    installed = sdk_list_installed()
    missing = [p for p in pkgs if p not in installed]
    if missing:
        raise ToolError(f"sdkmanager did not install {missing}")
    lock["android"] = {"cmdline_tools_zip": a.cmdline_tools_zip, "cmdline_tools_sha256": a.cmdline_tools_sha256,
                       "sdk_root": _rel(sdk_root()), "installed": installed}
    log.info("android sdk: %s", ", ".join(f"{k} {v}" for k, v in installed.items()))


# ---------------------------------------------------------------------------- PowerShell 7 (agent shell)
def pwsh_dir() -> Path:
    return paths.tools_dir() / "pwsh"


def install_pwsh(tc: ToolchainConfig, lock: dict) -> None:
    c = tc.powershell
    name = c.zip_url.rsplit("/", 1)[-1]
    zp = download(c.zip_url, paths.tools_dir() / "_downloads" / "pwsh" / name, c.sha256)
    marker = pwsh_dir() / ".abb-version"
    if not (marker.exists() and marker.read_text(encoding="utf-8").strip() == c.version):
        plat = get_platform()
        if pwsh_dir().exists() and plat.rmtree_robust(pwsh_dir()):
            raise ToolError(f"cannot replace {pwsh_dir()}")
        pwsh_dir().mkdir(parents=True)
        with zipfile.ZipFile(zp) as z:  # files at the archive root
            z.extractall(pwsh_dir())
        marker.write_text(c.version + "\n", encoding="utf-8")
    ver = _run([pwsh_dir() / "pwsh.exe", "-NoLogo", "-NoProfile", "-Command", "$PSVersionTable.PSVersion.ToString()"]).stdout().strip()
    if ver != c.version:
        raise ToolError(f"pinned pwsh reports {ver}, expected {c.version}")
    lock["powershell"] = {"version": ver, "zip": name, "sha256": c.sha256, "path": _rel(pwsh_dir() / "pwsh.exe")}
    log.info("pwsh %s", ver)


# ---------------------------------------------------------------------------- Spec Kit
def specify_exe(tc: ToolchainConfig) -> Path:
    return _expand(tc.python.uv_tool_bin_dir) / "specify.exe"


def install_speckit(tc: ToolchainConfig, lock: dict, py: Path) -> None:
    ref = tc.speckit.ref
    if ref.startswith("TODO"):
        raise ToolError("toolchain.yaml speckit.ref is not pinned")
    env = {"UV_TOOL_DIR": str(_expand(tc.python.uv_tool_dir)), "UV_TOOL_BIN_DIR": str(_expand(tc.python.uv_tool_bin_dir)),
           "UV_PYTHON_INSTALL_DIR": str(_expand(tc.python.uv_python_install_dir))}
    _run([_uv(), "tool", "install", "--force", "--python", py, "specify-cli", "--from",
          f"git+https://github.com/github/spec-kit.git@{ref}"], extra_env=env, timeout_s=1800)
    ver = _run([specify_exe(tc), "--version"], timeout_s=120).stdout().strip()
    lock["speckit"] = {"ref": ref, "version_output": ver[-300:], "path": _rel(specify_exe(tc))}
    log.info("specify %s", ver.splitlines()[-1] if ver else "?")


# ---------------------------------------------------------------------------- git
def git_exe() -> Path:
    g = get_platform().find_exe("git")
    if not g:
        raise ToolError("git not found on PATH")
    return g


def apply_git_config(tc: ToolchainConfig, lock: dict) -> None:
    for k, v in tc.git.global_config.items():
        _run([git_exe(), "config", "--global", k, v])
    ver = _run([git_exe(), "--version"]).stdout().strip()
    lock["git"] = {"version": ver, "global_config": dict(tc.git.global_config)}


# ---------------------------------------------------------------------------- entry points
def install(only: list[str] | None = None) -> dict:
    tc = load_toolchain()
    plat = get_platform()
    home = paths.abb_home()
    home.mkdir(parents=True, exist_ok=True)
    fs = plat.volume_filesystem(home)
    if fs.upper() not in ("NTFS", "REFS"):
        raise ToolError(f"ABB_HOME={home} is on {fs}: ACLs are required (NTFS or ReFS), see specs/environments.md §1")
    lock = load_lock()
    want = set(only or ["jdk", "python", "launcher", "claude", "pwsh", "android", "speckit", "git"])
    if "jdk" in want:
        for major in tc.jdk.majors:
            install_jdk(major, lock)
        save_lock(lock)
    py = None
    if "python" in want:
        py = install_python(tc, lock)
        save_lock(lock)
    if "launcher" in want:
        lp = plat.launcher_path()
        lock["launcher"] = {"sha256": sha256_file(lp), "path": _rel(lp)}
        save_lock(lock)
    if "claude" in want:
        install_claude(tc, lock)
        save_lock(lock)
    if "pwsh" in want:
        install_pwsh(tc, lock)
        save_lock(lock)
    if "android" in want:
        install_android(tc, lock)
        save_lock(lock)
    if "speckit" in want:
        install_speckit(tc, lock, py or plat.python())
        save_lock(lock)
    if "git" in want:
        apply_git_config(tc, lock)
    lock["platform"] = tc.platform
    lock["installed_at"] = utcnow_iso()
    save_lock(lock)
    return lock


def check() -> list[tuple[str, bool, str]]:
    """Re-verify every component against the lock. Returns (component, ok, detail) rows."""
    tc = load_toolchain()
    lock = load_lock()
    rows: list[tuple[str, bool, str]] = []

    def row(name: str, ok: bool, detail: str) -> None:
        rows.append((name, ok, detail))

    if not lock:
        return [("lock", False, f"{lock_path()} missing: run `abb tools install`")]
    for major in tc.jdk.majors:
        key = f"jdk{major}"
        L = lock.get(key)
        if not L:
            row(key, False, "not in lock")
            continue
        zp = paths.tools_dir() / "_downloads" / key / L["zip"]
        zip_ok = zp.exists() and sha256_file(zp) == L["sha256"]
        exe = jdk_dir(major) / "bin" / "java.exe"
        try:
            v = java_version(major) if exe.exists() else ""
        except ToolError as e:
            v = str(e)
        ver_ok = f'"{major}' in v
        row(key, zip_ok and ver_ok, f"{L['release_name']}; zip sha256 {'ok' if zip_ok else 'MISMATCH/missing'}; "
                                    f"{v.splitlines()[0] if v else 'java.exe missing'}")
    a = lock.get("android")
    if a:
        zp = paths.tools_dir() / "_downloads" / "cmdline-tools" / tc.android.cmdline_tools_zip
        zip_ok = zp.exists() and sha256_file(zp) == tc.android.cmdline_tools_sha256 == a["cmdline_tools_sha256"]
        try:
            inst = sdk_list_installed()
        except ToolError as e:
            inst = {}
            row("android-sdk", False, str(e)[:200])
        missing = [p for p in tc.android.packages if p not in inst]
        drift = {k: (v, inst.get(k)) for k, v in a["installed"].items() if inst.get(k) != v}
        row("android-sdk", zip_ok and not missing and not drift,
            f"cmdline-tools sha256 {'ok' if zip_ok else 'MISMATCH'}; installed {len(inst)} pkgs; "
            f"missing {missing or 'none'}; drift {drift or 'none'}")
    else:
        row("android-sdk", False, "not in lock")
    p = lock.get("python")
    if p:
        exe = paths.abb_home() / p["path"]
        row("python", exe.exists(), f"{p['version']} at {exe}")
    else:
        row("python", False, "not in lock")
    c = lock.get("claude_code")
    if c:
        exe = paths.abb_home() / c["path"]
        ok = exe.exists() and sha256_file(exe) == c["sha256"] and c["version"] == tc.claude_code.version
        v = _claude_version(exe) if exe.exists() else "missing"
        row("claude", ok and v == tc.claude_code.version, f"{exe} reports {v}; pin {tc.claude_code.version}; sha256 {'ok' if ok else 'MISMATCH'}")
    else:
        row("claude", False, "not in lock")
    w = lock.get("powershell")
    if w:
        zp = paths.tools_dir() / "_downloads" / "pwsh" / w["zip"]
        exe = paths.abb_home() / w["path"]
        ok = exe.exists() and zp.exists() and sha256_file(zp) == tc.powershell.sha256 == w["sha256"]
        row("pwsh", ok and w["version"] == tc.powershell.version, f"{w['version']} at {exe}; zip sha256 {'ok' if ok else 'MISMATCH'}")
    else:
        row("pwsh", False, "not in lock")
    lp = paths.tools_dir() / "abb_launch.py"
    src = Path(__file__).parent / "platform" / "abb_launch.py"
    row("launcher", lp.exists() and lp.read_bytes() == src.read_bytes(), str(lp))
    s = lock.get("speckit")
    if s:
        exe = specify_exe(tc)
        row("speckit", exe.exists() and s["ref"] == tc.speckit.ref, f"{s['ref']} at {exe}")
    else:
        row("speckit", False, "not in lock")
    g = lock.get("git")
    if g:
        bad = []
        for k, v in tc.git.global_config.items():
            r = _run([git_exe(), "config", "--global", "--get", k], check=False)
            if r.stdout().strip() != v:
                bad.append(f"{k}={r.stdout().strip() or '<unset>'}")
        row("git", not bad, f"{g['version']}; global config {'ok' if not bad else 'differs: ' + ', '.join(bad)}")
    else:
        row("git", False, "not in lock")
    return rows


# ---------------------------------------------------------------------------- s2a (Phase 6)
def s2a_exe(tc: ToolchainConfig) -> Path:
    return _expand(tc.python.uv_tool_bin_dir) / "s2a.exe"


def install_s2a() -> dict:
    """`abb sandbox install-s2a` (harness user): `uv tool install` of <repo>/s2a into ABB_HOME/tools/uvtools,
    s2a.exe in tools/bin (read/execute for the sandbox user); records s2a_git_sha in env.lock.json
    under `_s2a` (the run manifest copies it). Re-run after every prompt/pipeline change."""
    import json

    from abb.harness import env as envmod

    tc = load_toolchain()
    lock = load_lock()
    py = paths.abb_home() / (lock.get("python") or {}).get("path", "")
    if not py.exists():
        raise ToolError("the pinned CPython is missing: abb tools install")
    src = paths.repo_clone() / "s2a"
    sha = _run(["git", "log", "-1", "--format=%H", "--", "s2a"], cwd=paths.repo_clone(), timeout_s=60).stdout().strip()
    dirty = bool(_run(["git", "status", "--porcelain", "--", "s2a"], cwd=paths.repo_clone(), timeout_s=60).stdout().strip())
    env = {"UV_TOOL_DIR": str(_expand(tc.python.uv_tool_dir)), "UV_TOOL_BIN_DIR": str(_expand(tc.python.uv_tool_bin_dir)),
           "UV_PYTHON_INSTALL_DIR": str(_expand(tc.python.uv_python_install_dir))}
    _run([_uv(), "tool", "install", "--force", "--reinstall", "--python", py, str(src)], extra_env=env, timeout_s=1800)
    exe = s2a_exe(tc)
    help_out = _run([exe, "--help"], timeout_s=120).stdout()
    if "resume" not in help_out:
        raise ToolError(f"{exe} --help does not list `resume`")
    rec = {"s2a_git_sha": sha, "dirty": dirty, "path": _rel(exe), "installed_at": utcnow_iso()}
    elock = envmod.load_env_lock()
    elock["_s2a"] = rec
    envmod.lock_file().write_text(json.dumps(elock, indent=2) + "\n", encoding="utf-8", newline="\n")
    shutil.copyfile(envmod.lock_file(), paths.abb_home() / "env.lock.json")
    return rec
