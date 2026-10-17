"""`abb auth check` (specs/auth-and-usage.md §1): `claude.exe auth status` through the launcher with the
mapped token and an EMPTY CLAUDE_CONFIG_DIR; requires exit 0 and authMethod oauth_token; records
subscriptionType (the manifest's `plan`) in ABB_HOME/state/auth.json.
"""
from __future__ import annotations

import json

from abb import paths
from abb.harness.agent_env import AuthError, TrialDirs, build_agent_env, preflight
from abb.harness.platform import ProcSpec, get_platform
from abb.harness.smoke import leak_scan
from abb.util import stamp, utcnow_iso

RECORD_KEYS = ("loggedIn", "authMethod", "apiProvider", "subscriptionType")


def check() -> dict:
    token = preflight()
    plat = get_platform()
    claude = plat.claude_exe()
    if not claude.exists():
        raise FileNotFoundError(f"{claude} missing: run `abb tools install`")
    trial = TrialDirs(paths.work_dir() / "auth" / stamp()).create(claude_template=None)  # empty config dir
    env = build_agent_env(trial, token=token, proxy=False)
    spec = ProcSpec(argv=[str(claude), "auth", "status"], cwd=trial.work, env=env, stdin_text=None, timeout_s=120,
                    memory_mb=None, as_user=None, out_dir=trial.agent_out)
    r = plat.wait(plat.run(spec))
    rec: dict = {"checked_at": utcnow_iso(), "exit_code": r.exit_code, "claude_exe": str(claude)}
    try:
        data = json.loads(r.stdout())
        rec.update({k: data.get(k) for k in RECORD_KEYS})
        rec["fields"] = sorted(data.keys())
    except ValueError:
        rec["unparsable_stdout_tail"] = r.stdout()[-300:]
    rec["config_dir_empty_before"] = True
    rec["plan_source"] = "token session"
    if rec.get("subscriptionType") is None:
        # A token session does not report its plan (verified 2026-10-17, 2.1.302); the token was
        # created from the owner's login, so the plan is read from that login's `auth status`.
        login = plat.wait(plat.run(ProcSpec(
            argv=[str(claude), "auth", "status"], cwd=trial.work,
            env=plat.harness_env({"DISABLE_AUTOUPDATER": "1", "DISABLE_UPDATES": "1"}), stdin_text=None,
            timeout_s=120, memory_mb=None, as_user=None, out_dir=trial.root / "login-out")))
        try:
            ld = json.loads(login.stdout())
            rec["subscriptionType"] = ld.get("subscriptionType")
            rec["login_authMethod"] = ld.get("authMethod")
            rec["plan_source"] = ("harness user's login (token sessions do not report subscriptionType)"
                                  if ld.get("subscriptionType") else
                                  "not reported: token sessions omit it and the CLI login is "
                                  f"{ld.get('authMethod')!r}; see reference/verified.md (Day 0: pro)")
        except ValueError:
            rec["plan_source"] = "unknown"
    rec["token_leak_files"] = [str(p) for p in leak_scan([p for p in trial.root.rglob("*") if p.is_file()], token)]
    rec["ok"] = r.exit_code == 0 and rec.get("authMethod") == "oauth_token" and not rec["token_leak_files"]
    paths.state_dir().mkdir(parents=True, exist_ok=True)
    (paths.state_dir() / "auth.json").write_text(json.dumps(rec, indent=2), encoding="utf-8")
    plat.rmtree_robust(trial.root)
    return rec


def check_cli() -> int:
    try:
        rec = check()
    except (AuthError, FileNotFoundError) as e:
        print(f"ERROR: {e}")
        return 1
    print(json.dumps({k: rec.get(k) for k in ("ok", "exit_code", *RECORD_KEYS, "plan_source", "fields", "token_leak_files")}, indent=2))
    if not rec["ok"]:
        print("auth check FAILED: expected exit 0 and authMethod oauth_token (docs/DAY-0.md §3: re-create the token)")
        return 1
    return 0
