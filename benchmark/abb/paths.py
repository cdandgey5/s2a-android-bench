"""Filesystem roots (specs/environments.md §1). pathlib only; functions so tests can redirect ABB_HOME."""
from __future__ import annotations

import os
from pathlib import Path


def benchmark_dir() -> Path:
    """`benchmark/` in the code checkout; every config path is relative to it."""
    return Path(__file__).resolve().parents[1]


def repo_clone() -> Path:
    """The harness source checkout (`%USERPROFILE%\\abb-src`); denied to the sandbox user."""
    return benchmark_dir().parent


def abb_home() -> Path:
    v = os.environ.get("ABB_HOME")
    return Path(v) if v else Path.home() / "abb"


def tools_dir() -> Path:
    return abb_home() / "tools"


def caches_dir() -> Path:
    return abb_home() / "caches"


def work_dir() -> Path:
    return abb_home() / "work"


def state_dir() -> Path:
    """Harness-only state (auth check record, locks); denied to the sandbox user with ABB_HOME."""
    return abb_home() / "state"


def results_dir() -> Path:
    v = os.environ.get("ABB_RESULTS_DIR")
    return Path(v) if v else abb_home() / "results"


def config_dir() -> Path:
    return benchmark_dir() / "config"


def repos_config_dir() -> Path:
    return benchmark_dir() / "repos"


def tasks_dir() -> Path:
    return benchmark_dir() / "tasks"


def fixtures_dir() -> Path:
    return benchmark_dir() / "tests" / "fixtures"
