"""`abb sandbox setup|check` (specs/environments.md §5, phases/phase-1-environments.md step 6).

setup: non-elevated preparation (password -> Credential Manager, directories, the Claude config
template under ABB_HOME, a params file without secrets) + ONE elevated step
(scripts/sandbox-setup.ps1 through a UAC prompt). check: proves the boundary with real attempts
made AS the sandbox user through the launcher.
"""
from __future__ import annotations

import hashlib
import json
import secrets
import shutil
import string
import sys
from pathlib import Path

from abb import paths
from abb.config import load_repo, load_sandbox
from abb.harness.agent_env import TrialDirs, build_agent_env, preflight
from abb.harness.platform import ProcSpec, get_platform
from abb.log import get_logger
from abb.util import stamp, utcnow_iso

log = get_logger("abb.sandbox")
CHOSEN_REPOS = ("antennapod", "wikipedia")


def _expand(p: str, repo_key: str | None = None) -> Path:
    s = p.replace("$ABB_HOME", str(paths.abb_home())).replace("$REPO_CLONE", str(paths.repo_clone()))
    if repo_key:
        s = s.replace("$REPO", repo_key)
    q = Path(s)
    return q if q.is_absolute() else paths.abb_home() / q


def template_dir() -> Path:
    return paths.abb_home() / "sandbox" / "claude-config.template"


def _new_password() -> str:
    alphabet = string.ascii_letters + string.digits + "-_.!#%+"
    while True:
        pw = "".join(secrets.choice(alphabet) for _ in range(28))
        if any(c.islower() for c in pw) and any(c.isupper() for c in pw) and any(c.isdigit() for c in pw):
            return pw


def setup_params(repos: list[str]) -> dict:
    sb = load_sandbox()
    m = sb.modes["user"]
    acl = m.acl
    plat = get_platform()
    deny, rx = [], []
    for d in acl.deny:
        if "$TRIAL" in d:
            continue
        if "$REPO" in d and "$REPO_CLONE" not in d:
            deny += [str(_expand(d, r)) for r in repos]
        else:
            deny.append(str(_expand(d)))
    for d in acl.rx:
        if "$TRIAL" in d:
            continue
        if "$REPO" in d:
            rx += [str(_expand(d, r)) for r in repos]
        else:
            rx.append(str(_expand(d)))
    return {
        "user": m.run_as,
        "harness_user": plat.harness_principal(),
        "venv_python": sys.executable,
        "reset_inheritance": [str(_expand(d)) for d in acl.reset_inheritance],
        "deny": deny,
        "rx": rx,
        "deny_write_dirs": [str(Path(d)) for d in acl.deny_write_dirs],
        "firewall_rule": m.firewall_rule,
        "result_path": str(paths.state_dir() / "sandbox-setup-result.json"),
    }


def apply_list_grants() -> list[str]:
    """D-036: list + traverse (this folder only) on ABB_HOME, caches, work for the sandbox user."""
    sb = load_sandbox()
    m = sb.modes["user"]
    plat = get_platform()
    home = paths.abb_home().resolve()
    targets: list[Path] = [_expand(d) for d in m.acl.list_dirs]
    # ... plus every ancestor (below ABB_HOME) of each read+execute grant, e.g. caches/gradle-ro
    for rx in setup_params(list(CHOSEN_REPOS))["rx"]:
        a = Path(rx).resolve().parent
        while a != home and home in a.parents:
            targets.append(a)
            a = a.parent
    done = []
    for p in dict.fromkeys(targets):
        p.mkdir(parents=True, exist_ok=True)
        plat.grant(p, m.run_as, "list")
        done.append(str(p))
    return done


def prepare(repos: list[str]) -> dict:
    """Everything that needs no admin rights. Idempotent."""
    import keyring

    sb = load_sandbox()
    user = sb.modes["user"].run_as
    if not keyring.get_password("abb", user):
        keyring.set_password("abb", user, _new_password())
        log.info("generated a password for %s and stored it in Credential Manager (service 'abb')", user)
    for d in (paths.results_dir(), paths.work_dir(), paths.state_dir(), paths.caches_dir() / "repos"):
        d.mkdir(parents=True, exist_ok=True)
    src = paths.benchmark_dir() / "sandbox" / "claude-config.template"
    dst = template_dir()
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    if not (paths.abb_home() / "env.lock.json").exists():
        (paths.abb_home() / "env.lock.json").write_text("{}\n", encoding="utf-8")
    apply_list_grants()
    params = setup_params(repos)
    pf = paths.state_dir() / "sandbox-setup-params.json"
    pf.write_text(json.dumps(params, indent=2), encoding="utf-8")
    return {"params_file": str(pf), **params}


def setup(repos: list[str] | None = None) -> dict:
    repos = list(repos or CHOSEN_REPOS)
    params = prepare(repos)
    plat = get_platform()
    script = paths.benchmark_dir() / "scripts" / "sandbox-setup.ps1"
    pwsh = paths.tools_dir() / "pwsh" / "pwsh.exe"
    rp = Path(params["result_path"])
    if rp.exists():
        rp.unlink()
    log.info("starting the elevated step: accept the UAC prompt")
    code = plat.run_elevated(pwsh, ["-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script),
                                    "-ParamsFile", params["params_file"]])
    result = json.loads(rp.read_text(encoding="utf-8-sig")) if rp.exists() else {"steps": {}, "error": "no result file"}
    result["exit_code"] = code
    return result


# ---------------------------------------------------------------------------- check
def _profile_hash(user: str) -> str:
    root = Path("C:/Users") / user
    h = hashlib.sha256()
    if root.exists():
        for f in sorted(root.rglob("*")):
            try:
                st = f.stat()
            except OSError:
                h.update(f"{f}:unreadable".encode())
                continue
            h.update(f"{f.relative_to(root).as_posix()}:{st.st_size}:{int(st.st_mtime)}\n".encode())
    return h.hexdigest()


def _as_user_run(argv: list[str], *, user: str, cwd: Path, env: dict, out: Path, timeout_s: int = 120, stdin: str | None = None):
    plat = get_platform()
    spec = ProcSpec(argv=argv, cwd=cwd, env=env, stdin_text=stdin, timeout_s=timeout_s, memory_mb=None, as_user=user,
                    out_dir=out)
    return plat.wait(plat.run(spec))


def check(*, smoke: bool = True) -> list[tuple[str, bool, str]]:
    from abb.harness.proxy import from_sandbox_config
    from abb.harness.smoke import run_smoke

    rows: list[tuple[str, bool, str]] = []

    def row(name: str, ok: bool, detail: str) -> None:
        rows.append((name, ok, detail))
        log.info("%s %s: %s", "OK" if ok else "FAIL", name, detail)

    plat = get_platform()
    sb = load_sandbox()
    user = sb.modes["user"].run_as
    row("user exists + password", plat.as_user_available(user), user)
    if not plat.as_user_available(user):
        return rows
    row("firewall rule", plat.firewall_rule_present(sb.modes["user"].firewall_rule), sb.modes["user"].firewall_rule)
    before = _profile_hash(user)
    # ---- filesystem (real attempts as the user)
    items: list[tuple[str, Path, str, str]] = []  # (label, path, op, expected)
    for key in CHOSEN_REPOS:
        r = load_repo(key)
        items += [
            (f"mirror {key}", paths.caches_dir() / "repos" / f"{r.key}.git", "read", "denied"),
            (f"pristine {key}", paths.caches_dir() / "gradle-pristine" / r.key, "read", "denied"),
            (f"gradle-ro {key} read", paths.caches_dir() / "gradle-ro" / r.key, "read", "ok"),
            (f"gradle-ro {key} create", paths.caches_dir() / "gradle-ro" / r.key, "create", "denied"),
            (f"robolectric {key} read", paths.caches_dir() / "robolectric" / r.key, "read", "ok"),
        ]
    items += [
        ("results", paths.results_dir(), "read", "denied"),
        ("results create", paths.results_dir(), "create", "denied"),
        ("env.lock.json", paths.abb_home() / "env.lock.json", "read", "denied"),
        ("code checkout", paths.repo_clone(), "read", "denied"),
        ("tasks (hidden tests)", paths.tasks_dir(), "read", "denied"),
        ("ABB_HOME list (names only, D-036)", paths.abb_home(), "read", "ok"),
        ("caches list (names only, D-036)", paths.caches_dir(), "read", "ok"),
        ("ABB_HOME create", paths.abb_home(), "create", "denied"),
        ("work create", paths.work_dir(), "create", "denied"),
        ("tools read", paths.tools_dir(), "read", "ok"),
        ("tools create", paths.tools_dir(), "create", "denied"),
        ("claude template read", template_dir() / "settings.json", "read", "ok"),
        (f"C:/Users/{user} create", Path("C:/Users") / user, "create", "denied"),
    ]
    res = plat.check_paths([(p, op) for _, p, op, _ in items], as_user=user)
    for (label, p, op, want), got in zip(items, res):
        ok = got == want or (want == "denied" and got == "missing" and op == "read" and not p.exists())
        row(f"fs: {label}", ok, f"{op} {p} -> {got} (want {want})")
    # ---- network as the user, then as the harness user
    work = paths.work_dir() / "sbcheck" / stamp()
    work.mkdir(parents=True)
    plat.grant(work, user, "modify")
    curl = Path(plat.system_env().get("SystemRoot", r"C:\Windows")) / "System32" / "curl.exe"
    base_env = {**plat.system_env(), "USERPROFILE": str(work), "TEMP": str(work), "TMP": str(work)}
    r = _as_user_run([str(curl), "-sS", "-o", "NUL", "-w", "%{http_code}", "--max-time", "15", "https://github.com"],
                     user=user, cwd=work, env=base_env, out=work / "curl-gh")
    row("net: github.com as sandbox user fails", r.exit_code not in (0, None), f"curl exit {r.exit_code}: {r.stderr().strip()[-120:]}")
    from abb.harness.platform.base import run_capture

    r2 = run_capture(plat, [str(curl), "-sS", "-o", "NUL", "-w", "%{http_code}", "--max-time", "15", "https://github.com"],
                     cwd=work, timeout_s=60)
    row("net: github.com as harness user works", r2.exit_code == 0, f"HTTP {r2.stdout().strip()}")
    plog = paths.results_dir() / "_sandbox-check" / f"{stamp()}-proxy.log"
    with from_sandbox_config("user", plog) as _proxy:
        r3 = _as_user_run([str(curl), "-sS", "-o", "NUL", "-w", "%{http_code}", "--max-time", "20", "-x",
                           f"http://{sb.modes['user'].proxy.listen}", "https://api.anthropic.com/v1/models"],
                          user=user, cwd=work, env=base_env, out=work / "curl-api")
        ok3 = r3.exit_code == 0 and r3.stdout().strip().isdigit() and r3.stdout().strip() != "000"
        row("net: api.anthropic.com via proxy as sandbox user", ok3,
            f"HTTP {r3.stdout().strip()} (401 is fine: no key)" + ("" if ok3 else f"; curl exit {r3.exit_code}: {r3.stderr().strip()[-200:]}"))
        r4 = _as_user_run([str(curl), "-sS", "-o", "NUL", "-w", "%{http_code}", "--max-time", "20", "-x",
                           f"http://{sb.modes['user'].proxy.listen}", "https://github.com"],
                          user=user, cwd=work, env=base_env, out=work / "curl-gh-proxy")
        row("net: github.com via proxy refused", r4.exit_code != 0, f"curl exit {r4.exit_code}")
        # ---- tools without a loaded profile
        for name, argv in (("git", ["git", "--version"]),
                           ("pwsh", [str(paths.tools_dir() / "pwsh" / "pwsh.exe"), "-NoProfile", "-Command", "$PSVersionTable.PSVersion.ToString()"]),
                           ("claude.exe", [str(plat.claude_exe()), "--version"])):
            env = {**base_env, "PATH": ";".join([str(paths.tools_dir() / "pwsh"), str(Path(plat.find_exe("git")).parent),
                                                 str(Path(base_env.get("SystemRoot", r"C:\Windows")) / "System32")]),
                   "DISABLE_AUTOUPDATER": "1", "DISABLE_UPDATES": "1"}
            rr = _as_user_run(argv if name != "git" else [str(plat.find_exe("git")), "--version"], user=user, cwd=work,
                              env=env, out=work / f"tool-{name}")
            row(f"tool without profile: {name}", rr.exit_code == 0, rr.stdout().strip()[:80] or rr.stderr().strip()[-120:])
        # ---- the Claude smoke test as the sandbox user through the proxy
        if smoke:
            s = run_smoke("Print the current directory and exit.", model="claude-sonnet-5-5", max_turns=3, max_usd=1.0,
                          deadline=None, grace=30, interrupt=None, tools=None, proxy=True, label="sbcheck",
                          as_user=user, proxy_running=True)
            res_ = (s["parsed"].get("result") or {})
            row("smoke as sandbox user via proxy", res_.get("subtype") == "success" and not s["token_leak_files"],
                f"subtype {res_.get('subtype')}, permissionMode {(s['parsed'].get('init') or {}).get('permissionMode')}, "
                f"retries {len(s['parsed']['api_retries'])}, trial {s['trial_dir']}")
    after = _profile_hash(user)
    row(f"C:/Users/{user} unchanged", before == after, f"{before[:12]} == {after[:12]}")
    (paths.state_dir() / "sandbox-check.json").write_text(json.dumps(
        {"checked_at": utcnow_iso(), "rows": [{"name": n, "ok": o, "detail": d} for n, o, d in rows]}, indent=2),
        encoding="utf-8")
    plat.rmtree_robust(work)
    return rows


def preflight_token() -> str:
    return preflight()


__all__ = ["build_agent_env", "check", "prepare", "setup", "TrialDirs"]
