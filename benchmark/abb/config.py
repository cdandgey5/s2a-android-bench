"""Config models (pydantic, extra="forbid") for repos/*.yaml, tasks/*/task.yaml and config/*.yaml.

SHA fields accept 40 hex characters or a literal `TODO_*` placeholder; `abb repos check` is the
strict check. `Limits` lives in abb/arms/base.py and is re-exported here.
"""
from __future__ import annotations

import os
import re
from datetime import date, datetime
from pathlib import Path
from typing import Annotated, Literal

import yaml
from pydantic import AfterValidator, BaseModel, ConfigDict, Field

from abb import paths
from abb.arms.base import Limits

__all__ = [
    "Limits", "LimitsConfig", "RepoConfig", "SandboxConfig", "TaskConfig", "ToolchainConfig",
    "is_real_sha", "load_dotenv", "load_limits", "load_repo", "load_sandbox", "load_task",
    "load_toolchain", "oauth_token",
]

_SHA = re.compile(r"^[0-9a-f]{40}$")
_TODO = re.compile(r"^TODO_[A-Z0-9_]*$")


def _sha_or_todo(v: str) -> str:
    if not (_SHA.match(v) or _TODO.match(v)):
        raise ValueError(f"expected a 40-char lowercase hex SHA or TODO_*, got {v!r}")
    return v


Sha = Annotated[str, AfterValidator(_sha_or_todo)]


def is_real_sha(v: str | None) -> bool:
    return bool(v and _SHA.match(v))


class _M(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------------------- repos/<repo>.yaml
class AndroidPkgs(_M):
    packages: list[str] = Field(default_factory=list)


class RepoToolchain(_M):
    jdk: int
    android: AndroidPkgs = Field(default_factory=AndroidPkgs)
    gradle_user_home_props: str = ""


class WarmCommand(_M):
    cmd: str
    allow_failure: bool = False


class Stub(_M):
    path: str
    content_from: str


class RepoBuild(_M):
    cache_commit: Sha
    setup_commit: Sha
    warm_commands: list[WarmCommand]
    stubs: list[Stub] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)


class RepoTests(_M):
    test_task_for_module: dict[str, str]
    junit_dir: str = "build/test-results"
    verify_modules: list[str]
    test_dirs: list[str]
    protected_build_paths: list[str]
    build_config_files: list[str]

    def task_for(self, module: str) -> str:
        return self.test_task_for_module.get(module, self.test_task_for_module["default"])


class RepoWorkspace(_M):
    exclude_from_snapshot: list[str] = Field(default_factory=list)
    strip_agent_instructions: bool = False
    diff_exclude: list[str] = Field(default_factory=list)


class RepoLint(_M):
    command: str | None = None
    report_glob: str | None = None


class RepoConfig(_M):
    key: str
    display_name: str
    url: str
    license: str
    default_branch: str
    language: Literal["java", "kotlin", "mixed"]
    ui: Literal["xml", "compose", "mixed"]
    structure: Literal["single_module", "multi_module"]
    toolchain: RepoToolchain
    build: RepoBuild
    tests: RepoTests
    workspace: RepoWorkspace
    lint: RepoLint = Field(default_factory=RepoLint)

    @property
    def owner_repo(self) -> str:
        return self.url.rstrip("/").removeprefix("https://github.com/")


# ---------------------------------------------------------------------------- tasks/<id>/task.yaml
class Upstream(_M):
    issue_url: str | None = None
    pr_url: str | None = None
    fix_commit: str | None = None
    fix_date: date | None = None
    issue_created: date | None = None


class TaskTags(_M):
    files_touched: int = 0
    files_bucket: Literal["1", "2-5", "6+"] = "1"
    modules: int = 1
    lang: Literal["java", "kotlin", "mixed"] = "java"
    ui: Literal["none", "xml", "compose"] = "none"
    test_kind: Literal["junit", "robolectric", "compose", "screenshot"] = "junit"
    needs_test_hook: bool = False
    new_surface: bool = False
    ticket_mentions_code: bool = False


class TestRef(_M):
    module: str
    test: str | None = None
    method: str | None = None


class TaskLimits(_M):
    timeout_minutes: int | None = None
    max_turns_total: int | None = None
    max_usd: float | None = None


class Validation(_M):
    runs: int
    last_validated: datetime | None = None
    env_fingerprint: str | None = None
    p2p_stable: list[str] = Field(default_factory=list)
    screenshot_tolerance: float | None = None
    v1_test_compile: str | None = None
    flaky_tests: list[str] = Field(default_factory=list)


class TaskConfig(_M):
    id: str
    repo: str
    base_commit: Sha
    source: Literal["mined", "reverted", "authored"]
    category: Literal["bugfix", "feature", "refactor", "cross_module"]
    upstream: Upstream | None = None
    tags: TaskTags = Field(default_factory=TaskTags)
    problem_statement: str = "problem.md"
    test_patch: str | None = "test.patch"
    gold_patch: str | None = "gold.patch"
    fail_to_pass: list[TestRef]
    pass_to_pass: list[TestRef]
    limits: TaskLimits = Field(default_factory=TaskLimits)
    needs_emulator: bool = False
    split: Literal["dev", "test"] | None = None
    status: Literal["draft", "validated", "flaky", "dropped"] = "draft"
    created_with_s2a_sha: str | None = None
    drafted_by: Literal["agent", "human"] | None = None
    drafted_with_model: str | None = None
    validation: Validation | None = None


# ---------------------------------------------------------------------------- config/sandbox.yaml
class ProxyCfg(_M):
    listen: str = "127.0.0.1:8888"
    allow_hosts: list[str] = Field(default_factory=lambda: ["api.anthropic.com"])
    resolve_dns: bool = True
    log: str | None = None


class AclCfg(_M):
    reset_inheritance: list[str] = Field(default_factory=list)
    list_dirs: list[str] = Field(default_factory=list, alias="list")  # sandbox.yaml key `list` (D-036)
    deny: list[str] = Field(default_factory=list)
    rx: list[str] = Field(default_factory=list)
    modify: list[str] = Field(default_factory=list)
    deny_write_files: list[str] = Field(default_factory=list)
    deny_write_dirs: list[str] = Field(default_factory=list)


class SandboxMode(_M):
    run_as: str | None = None
    credential: str | None = None
    logon_flags: int | None = None
    firewall_rule: str | None = None
    proxy: ProxyCfg = Field(default_factory=ProxyCfg)
    acl: AclCfg | None = None


class ProcessCfg(_M):
    memory_mb: int = 8192
    grace_s: int = 30
    interrupt: Literal["ctrl_break", "ctrl_c"] = "ctrl_break"
    launcher: str = "tools/abb_launch.py"
    per_trial_dirs: list[str] = Field(default_factory=list)
    seed_gradle_home: list[str] = Field(default_factory=list)
    seed_transforms: bool = False
    auth: Literal["oauth_token"] = "oauth_token"
    env: dict[str, str] = Field(default_factory=dict)
    disallowed_tools: list[str] = Field(default_factory=list)


class SandboxConfig(_M):
    modes: dict[Literal["user", "none"], SandboxMode]
    process: ProcessCfg


# ---------------------------------------------------------------------------- config/toolchain.yaml
class JdkCfg(_M):
    source: Literal["adoptium"] = "adoptium"
    majors: list[int]
    image_type: str = "jdk"


class AndroidCfg(_M):
    cmdline_tools_zip: str
    cmdline_tools_sha256: str
    base_url: str
    packages: list[str]


class PythonCfg(_M):
    version: str
    uv_python_install_dir: str
    uv_tool_dir: str
    uv_tool_bin_dir: str


class ClaudeCodeCfg(_M):
    installer: str
    version: str
    exe_copy: str


class PowershellCfg(_M):
    version: str
    zip_url: str
    sha256: str


class SpeckitCfg(_M):
    ref: str
    script_flavor: Literal["ps", "sh"] = "ps"


class GitCfg(_M):
    global_config: dict[str, str]


class ToolchainConfig(_M):
    platform: str
    jdk: JdkCfg
    android: AndroidCfg
    python: PythonCfg
    claude_code: ClaudeCodeCfg
    powershell: PowershellCfg
    speckit: SpeckitCfg
    git: GitCfg


# ---------------------------------------------------------------------------- config/limits.yaml
class LimitsDefault(_M):
    timeout_minutes: int = 45
    max_turns_total: int = 200
    max_usd: float = 15.0
    max_interventions: int = 2
    max_interventions_per_trial: int = 4
    grade_timeout_minutes: int = 30


class LimitsProfile(_M):
    model: str | None = None
    timeout_minutes: int | None = None
    max_turns_total: int | None = None
    max_usd: float | None = None


class LimitsConfig(_M):
    default: LimitsDefault
    profiles: dict[str, LimitsProfile] = Field(default_factory=dict)

    def resolve(self, profile: str | None = None, **overrides) -> Limits:
        vals = self.default.model_dump()
        if profile:
            vals.update({k: v for k, v in self.profiles[profile].model_dump().items() if v is not None})
        vals.update({k: v for k, v in overrides.items() if v is not None})
        return Limits(**vals)


# ---------------------------------------------------------------------------- loaders
def _yaml(p: Path) -> dict:
    with open(p, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_repo(key: str) -> RepoConfig:
    return RepoConfig.model_validate(_yaml(paths.repos_config_dir() / f"{key}.yaml"))


def load_task(task_id: str) -> TaskConfig:
    return TaskConfig.model_validate(_yaml(paths.tasks_dir() / task_id / "task.yaml"))


def load_sandbox() -> SandboxConfig:
    return SandboxConfig.model_validate(_yaml(paths.config_dir() / "sandbox.yaml"))


def load_toolchain() -> ToolchainConfig:
    return ToolchainConfig.model_validate(_yaml(paths.config_dir() / "toolchain.yaml"))


def load_limits() -> LimitsConfig:
    return LimitsConfig.model_validate(_yaml(paths.config_dir() / "limits.yaml"))


def load_dotenv(path: Path | None = None) -> dict[str, str]:
    """The five-line .env parser (AGENTS.md rule 6): KEY=VALUE lines, # comments, no expansion."""
    p = path or paths.benchmark_dir() / ".env"
    if not p.exists():
        return {}
    lines = (ln.strip() for ln in p.read_text(encoding="utf-8").splitlines())
    pairs = (ln.split("=", 1) for ln in lines if ln and not ln.startswith("#") and "=" in ln)
    return {k.strip(): v.strip().strip('"').strip("'") for k, v in pairs}


def oauth_token() -> str | None:
    """ABB_OAUTH_TOKEN from the environment, else from the git-ignored benchmark/.env. Never logged."""
    return os.environ.get("ABB_OAUTH_TOKEN") or load_dotenv().get("ABB_OAUTH_TOKEN") or None
