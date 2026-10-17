"""Per-trial directories and the agent environment block (specs/environments.md §5).

The block is built from scratch: system variables + `sandbox.yaml: process.env` with the per-trial
paths filled in + the subscription token (mapped from ABB_OAUTH_TOKEN to CLAUDE_CODE_OAUTH_TOKEN,
specs/auth-and-usage.md §1) + JAVA_HOME/ANDROID_HOME/PATH. The harness environment is never
inherited, and the block never carries an API key.
"""
from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from abb import paths
from abb.config import RepoConfig, load_sandbox, oauth_token
from abb.harness.platform import get_platform

FORBIDDEN_IN_BLOCK = (
    "ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "CLAUDE_CODE_USE_BEDROCK", "CLAUDE_CODE_USE_VERTEX",
    "CLAUDE_CODE_USE_FOUNDRY", "ANTHROPIC_MODEL", "ANTHROPIC_BASE_URL",
)
FORBIDDEN_IN_HARNESS = ("CLAUDE_CODE_OAUTH_TOKEN", "ANTHROPIC_API_KEY")
PROXY_VARS = ("HTTPS_PROXY", "HTTP_PROXY", "NO_PROXY", "CLAUDE_CODE_PROXY_RESOLVES_HOSTS")


class AuthError(RuntimeError):
    pass


def preflight() -> str:
    """Refuse to start if the harness's own env carries a global token or API key; return the token."""
    bad = [k for k in FORBIDDEN_IN_HARNESS if os.environ.get(k)]
    if bad:
        raise AuthError(
            f"{', '.join(bad)} is set in the harness environment; it must never be set globally "
            "(docs/DAY-0.md §3). Remove it and restart the shell."
        )
    tok = oauth_token()
    if not tok:
        raise AuthError("ABB_OAUTH_TOKEN is not set (user environment or benchmark/.env); see docs/DAY-0.md §3")
    return tok


@dataclass
class TrialDirs:
    root: Path

    @property
    def work(self) -> Path:
        return self.root / "work"

    @property
    def home(self) -> Path:
        return self.root / "home"

    @property
    def gradle_home(self) -> Path:
        return self.root / "gradle-home"

    @property
    def claude_config(self) -> Path:
        return self.root / "claude-config"

    @property
    def agent_out(self) -> Path:
        return self.root / "agent-out"

    @property
    def stop_file(self) -> Path:
        return self.root / "STOP"

    def create(self, *, claude_template: Path | None) -> "TrialDirs":
        for d in (self.work, self.home, self.gradle_home, self.claude_config, self.agent_out):
            d.mkdir(parents=True, exist_ok=False)
        (self.home / ".android").mkdir()
        if claude_template is not None:
            for f in claude_template.iterdir():
                if f.is_file():
                    shutil.copyfile(f, self.claude_config / f.name)
        return self


def claude_template_dir() -> Path:
    """ABB_HOME/sandbox/claude-config.template once Phase 1 installed it, else the repo's copy."""
    installed = paths.abb_home() / "sandbox" / "claude-config.template"
    return installed if installed.exists() else paths.benchmark_dir() / "sandbox" / "claude-config.template"


def agent_path_dirs(jdk_home: Path) -> list[Path]:
    plat = get_platform()
    sysroot = Path(plat.system_env().get("SystemRoot", r"C:\Windows"))
    dirs = [jdk_home / "bin", paths.tools_dir() / "bin", paths.tools_dir() / "android-sdk" / "platform-tools"]
    git = plat.find_exe("git")
    if git:
        dirs.append(git.parent)  # Git\cmd: Claude Code derives Git Bash from git.exe's location
    dirs.append(paths.tools_dir() / "pwsh")  # pinned pwsh (D-031), never the owner's per-user Store alias
    dirs += [sysroot / "System32", sysroot, sysroot / "System32" / "Wbem",
             sysroot / "System32" / "WindowsPowerShell" / "v1.0", sysroot / "System32" / "OpenSSH"]
    return dirs


def build_agent_env(
    trial: TrialDirs,
    *,
    token: str,
    repo: RepoConfig | None = None,
    proxy: bool = True,
    jdk: int | None = None,
) -> dict[str, str]:
    plat = get_platform()
    sb = load_sandbox()
    env = plat.system_env()
    subst = [
        ("$TRIAL/home/.android", str(trial.home / ".android")),
        ("$TRIAL/home", str(trial.home)),
        ("$TRIAL/gradle-home", str(trial.gradle_home)),
        ("$TRIAL/claude-config", str(trial.claude_config)),
        ("$TRIAL", str(trial.root)),
    ]
    for k, v in sb.process.env.items():
        if not proxy and k in PROXY_VARS:
            continue
        if "$REPO" in v:
            if repo is None:
                continue
            v = str(paths.abb_home() / Path(v.replace("$REPO", repo.key)))
        for a, b in subst:
            v = v.replace(a, b)
        env[k] = v
    for k in ("HOME", "TEMP", "TMP", "APPDATA", "LOCALAPPDATA"):
        env[k] = str(trial.home)
    major = jdk or (repo.toolchain.jdk if repo else 17)
    jdk_home = paths.tools_dir() / f"jdk{major}"
    env["JAVA_HOME"] = str(jdk_home)
    env["ANDROID_HOME"] = str(paths.tools_dir() / "android-sdk")
    env["PATH"] = os.pathsep.join(str(d) for d in agent_path_dirs(jdk_home))
    env["CLAUDE_CODE_OAUTH_TOKEN"] = token
    leaked = [k for k in env if k.upper() in FORBIDDEN_IN_BLOCK]
    if leaked:
        raise AuthError(f"agent environment block must not contain {leaked}")
    return env


def redact(argv: list[str], token: str | None) -> list[str]:
    return [a.replace(token, "<REDACTED>") if token else a for a in argv]
