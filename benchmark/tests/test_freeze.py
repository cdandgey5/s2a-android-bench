"""A held-out run starts only from the S5 freeze (run.freeze_record, Phase 10 step 1)."""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from abb import paths
from abb.harness import run as runmod

SHA = "5ca7283a1a63170d9070a2a0e54e3f5fd179729c"


def git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path: Path, monkeypatch) -> Path:
    root = tmp_path / "abb-src"
    (root / "docs").mkdir(parents=True)
    (root / "benchmark" / "tasks" / "t-0001").mkdir(parents=True)
    (root / "docs" / "PREREG.md").write_text(f"# PREREG\n\nStatus: **DRAFT**\n\ns2a {SHA}\n", encoding="utf-8")
    (root / "benchmark" / "tasks" / "t-0001" / "task.yaml").write_text("id: t-0001\n", encoding="utf-8")
    git(root, "init", "-q")
    git(root, "-c", "user.name=t", "-c", "user.email=t@t", "add", "-A")
    git(root, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "draft")
    monkeypatch.setattr(paths, "repo_clone", lambda: root)
    monkeypatch.setattr(runmod, "load_env_lock", lambda: {"_s2a": {"s2a_git_sha": SHA}})
    return root


def commit(root: Path, msg: str) -> None:
    git(root, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-am", msg)


def test_freeze_gate(repo: Path) -> None:
    with pytest.raises(SystemExit, match="not marked FROZEN"):
        runmod.freeze_record()
    p = repo / "docs" / "PREREG.md"
    p.write_text(p.read_text(encoding="utf-8").replace("DRAFT", "FROZEN"), encoding="utf-8")
    with pytest.raises(SystemExit, match="uncommitted"):
        runmod.freeze_record()
    commit(repo, "freeze")
    with pytest.raises(SystemExit, match="does not exist"):
        runmod.freeze_record()
    git(repo, "tag", runmod.FREEZE_TAG)
    rec = runmod.freeze_record()
    assert rec["freeze_tag"] == runmod.FREEZE_TAG and len(rec["prereg_sha256"]) == 64
    t = repo / "benchmark" / "tasks" / "t-0001" / "task.yaml"
    t.write_text("id: t-0001\nsplit: test\n", encoding="utf-8")
    commit(repo, "edit a task after the freeze")
    with pytest.raises(SystemExit, match="changed after"):
        runmod.freeze_record()


def test_freeze_needs_the_named_s2a(repo: Path, monkeypatch) -> None:
    p = repo / "docs" / "PREREG.md"
    p.write_text(p.read_text(encoding="utf-8").replace("DRAFT", "FROZEN"), encoding="utf-8")
    commit(repo, "freeze")
    git(repo, "tag", runmod.FREEZE_TAG)
    monkeypatch.setattr(runmod, "load_env_lock", lambda: {"_s2a": {"s2a_git_sha": "0" * 40}})
    with pytest.raises(SystemExit, match="installed s2a"):
        runmod.freeze_record()
