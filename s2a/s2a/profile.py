"""Pipeline and profile loading. Data files ship inside the package (importlib.resources);
S2A_PIPELINE, S2A_PROFILE_DIR and S2A_PROMPT_DIR override them for experiments."""
from __future__ import annotations

import os
from importlib import resources
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field


class _M(BaseModel):
    model_config = ConfigDict(extra="forbid")


class StageCfg(_M):
    name: str
    session: Literal["fresh", "per_task"] = "fresh"
    turns: int
    tools: Literal["read_only", "full"]
    gate: list[str] = Field(default_factory=list)
    gate_per_task: list[str] = Field(default_factory=list)
    gate_after_all: list[str] = Field(default_factory=list)
    post: list[str] = Field(default_factory=list)
    retry: int = 0
    on_gate_failure: Literal["stop", "record_and_continue"] = "stop"
    commit_after: bool = False
    commit_per_task: bool = False
    skippable: bool = False
    pause_in_interactive: bool = False
    optional: bool = False
    runs_when: str | None = None
    then: str | None = None
    cache: dict | None = None
    isolate: dict | None = None


class Pipeline(_M):
    version: int
    total_turns_default: int = 200
    fix_loops: int = 2
    implement_task_retries: int = 2
    implement_task_turn_cap: int = 35
    on_task_exhausted: str = "stop_implement_then_verify"
    small_change_skips: list[str] = Field(default_factory=list)
    lint_gate: str = "if_fast"
    gate_timeout_s: int = 900
    read_only_post: list[str] = Field(default_factory=list)
    test_gates_relative_to_baseline: bool = True
    gates_render_commands: bool = True
    stages: list[StageCfg]

    def stage(self, name: str) -> StageCfg:
        for s in self.stages:
            if s.name == name:
                return s
        raise KeyError(name)


class Detect(_M):
    any_of_files: list[str] = Field(default_factory=list)
    and_any_of_globs: list[str] = Field(default_factory=list)


class Commands(_M):
    offline_flag: str = "--offline"
    common_flags: str = ""
    build: str
    test_module: str
    test_class: str
    test_method: str
    lint: str
    test_smoke: str
    junit_results: str
    defaults: dict[str, str] = Field(default_factory=dict)


class Profile(_M):
    name: str
    detect: Detect
    commands: Commands
    test_dirs: list[str]
    weakened_test_patterns: list[str] = Field(default_factory=list)
    conventions_checklist: list[str] = Field(default_factory=list)
    notes_for_prompts: str = ""


def _data(rel: str) -> str:
    return resources.files("s2a").joinpath(rel).read_text(encoding="utf-8")


def load_pipeline() -> Pipeline:
    p = os.environ.get("S2A_PIPELINE")
    text = Path(p).read_text(encoding="utf-8") if p else _data("pipeline.yaml")
    return Pipeline.model_validate(yaml.safe_load(text))


def load_profile(name: str) -> Profile:
    d = os.environ.get("S2A_PROFILE_DIR")
    text = (Path(d) / f"{name}.yaml").read_text(encoding="utf-8") if d else _data(f"profiles/{name}.yaml")
    return Profile.model_validate(yaml.safe_load(text))


def detect_profile(repo: Path) -> str:
    """android when a settings.gradle* exists and some module has a main AndroidManifest.xml."""
    prof = load_profile("android")
    if any((repo / f).exists() for f in prof.detect.any_of_files):
        for pat in prof.detect.and_any_of_globs:
            if next(iter(repo.glob(pat)), None) is not None:
                return "android"
    raise SystemExit("no profile matches this repository (only `android` exists in v1); pass --profile")


def prompt_text(stage: str, profile: str) -> str:
    """prompts/<profile>/<stage>.md wins over prompts/<stage>.md (S2A_PROMPT_DIR overrides both)."""
    d = os.environ.get("S2A_PROMPT_DIR")
    if d:
        for p in (Path(d) / profile / f"{stage}.md", Path(d) / f"{stage}.md"):
            if p.exists():
                return p.read_text(encoding="utf-8")
    base = resources.files("s2a").joinpath("prompts")
    for rel in (f"{profile}/{stage}.md", f"{stage}.md"):
        f = base.joinpath(rel)
        if f.is_file():
            return f.read_text(encoding="utf-8")
    raise FileNotFoundError(f"no prompt for stage {stage!r}")
