"""Every seed/config YAML loads into its pydantic model (extra="forbid")."""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from abb import paths
from abb.arms.base import Limits
from abb.config import (
    LimitsConfig, RepoConfig, SandboxConfig, TaskConfig, ToolchainConfig, is_real_sha, load_dotenv,
    load_limits, load_repo, load_sandbox, load_task, load_toolchain,
)

REPOS = sorted(p.stem for p in paths.repos_config_dir().glob("*.yaml"))
TASKS = sorted(p.parent.name for p in paths.tasks_dir().glob("*/task.yaml") if p.parent.name != "_template")


def _yaml(p: Path) -> dict:
    return yaml.safe_load(p.read_text(encoding="utf-8"))


@pytest.mark.parametrize("key", REPOS)
def test_repo_configs_load(key: str) -> None:
    r = load_repo(key)
    assert r.key == key
    assert r.tests.task_for(":nonexistent") == r.tests.test_task_for_module["default"]


def test_chosen_repos_have_real_shas() -> None:
    for key in ("antennapod", "wikipedia"):
        r = load_repo(key)
        assert is_real_sha(r.build.cache_commit) and is_real_sha(r.build.setup_commit)


def test_template_task_loads() -> None:
    t = TaskConfig.model_validate(_yaml(paths.tasks_dir() / "_template" / "task.yaml"))
    assert t.status == "draft"


@pytest.mark.parametrize("task_id", TASKS)
def test_tasks_load(task_id: str) -> None:
    t = load_task(task_id)
    assert t.id == task_id
    assert t.repo in REPOS
    d = paths.tasks_dir() / task_id
    for f in (t.problem_statement, t.test_patch, t.gold_patch):
        assert (d / f).exists(), f
    assert all(e.test for e in t.fail_to_pass), "F2P entries must name at least a class (task-format rule 4)"


def test_patches_are_lf_only() -> None:
    for p in paths.tasks_dir().glob("*/*.patch"):
        assert b"\r" not in p.read_bytes(), p


def test_config_files_load() -> None:
    assert isinstance(load_sandbox(), SandboxConfig)
    assert isinstance(load_toolchain(), ToolchainConfig)
    lc = load_limits()
    assert isinstance(lc, LimitsConfig)
    dev = lc.resolve("dev")
    assert isinstance(dev, Limits) and dev.model == "claude-sonnet-5-5" and dev.max_usd == 5.0
    assert lc.resolve("final").model == "claude-opus-5-5"


def test_limits_dataclass_matches_yaml() -> None:
    yaml_fields = set(_yaml(paths.config_dir() / "limits.yaml")["default"])
    dc_fields = set(Limits.__dataclass_fields__)
    assert yaml_fields <= dc_fields and dc_fields - yaml_fields == {"model"}


def test_extra_fields_rejected() -> None:
    raw = _yaml(paths.repos_config_dir() / "antennapod.yaml")
    raw["unexpected"] = 1
    with pytest.raises(ValidationError):
        RepoConfig.model_validate(raw)


@pytest.mark.parametrize("bad", ["abc", "TODO", "todo_x", "3D105D598DFA582C6CB22BA40B56D11780366890"])
def test_sha_fields_strict_shape(bad: str) -> None:
    raw = _yaml(paths.tasks_dir() / "_template" / "task.yaml")
    raw["base_commit"] = bad
    with pytest.raises(ValidationError):
        TaskConfig.model_validate(raw)


def test_sha_fields_accept_todo_placeholder() -> None:
    raw = _yaml(paths.tasks_dir() / "_template" / "task.yaml")
    raw["base_commit"] = "TODO_40_CHAR_SHA"
    assert TaskConfig.model_validate(raw).base_commit == "TODO_40_CHAR_SHA"


def test_dotenv_parser(tmp_path: Path) -> None:
    p = tmp_path / ".env"
    p.write_text("# comment\nABB_OAUTH_TOKEN='x-y'\n\nOTHER = 2\nnoequals\n", encoding="utf-8")
    assert load_dotenv(p) == {"ABB_OAUTH_TOKEN": "x-y", "OTHER": "2"}


def test_sandbox_env_has_no_credentials() -> None:
    env = load_sandbox().process.env
    for k in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "CLAUDE_CODE_OAUTH_TOKEN"):
        assert k not in env
