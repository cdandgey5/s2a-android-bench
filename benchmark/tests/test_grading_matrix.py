"""Grading sanity matrix (specs/grading-protocol.md, Phase 3 gate): 2 tasks x 7 patches.

Integration: real Gradle runs, offline, pristine cache. ABB_INTEGRATION=1.
antennapod-0000 is a plain bugfix (hidden test uses a base interface); antennapod-0005 is a
new-surface refactor (hidden tests use the API the ticket names).
"""
from __future__ import annotations

import os

import pytest

from abb import paths
from abb.config import load_task
from abb.harness.grade import grade

pytestmark = pytest.mark.skipif(not os.environ.get("ABB_INTEGRATION"), reason="integration: set ABB_INTEGRATION=1")
TASKS = ["antennapod-0000", "antennapod-0005"]
VARIANTS = ["gold", "empty", "gold_plus_delete_test", "compile_break", "regression", "gradlew_edit", "interface_mismatch"]


def _grade(task: str, variant: str, tmp_path) -> dict:
    return grade(task, paths.fixtures_dir() / "grading" / task / f"{variant}.patch", out_dir=tmp_path / "out")


@pytest.mark.parametrize("task", TASKS)
@pytest.mark.parametrize("variant", VARIANTS)
def test_matrix(task: str, variant: str, tmp_path) -> None:
    t = load_task(task)
    r = _grade(task, variant, tmp_path)
    f = r["flags"]
    assert (tmp_path / "out" / "grade.json").exists()
    if variant == "gold":
        assert r["resolved"] is True and r["build_ok"] is True and r["reason"] is None, r
        assert all(s == "passed" for s in r["f2p"].values()) and r["regressions"] == []
    elif variant == "empty":
        assert r["resolved"] is False
        if t.tags.new_surface:
            assert r["reason"] == "test_compile_failed" and r["interface_candidate"] is False, r
        else:
            assert r["build_ok"] is True and r["reason"] is None, r
            assert all(s in ("failed", "error") for s in r["f2p"].values()), r["f2p"]
    elif variant == "gold_plus_delete_test":
        assert f["agent_touched_tests"] is True and f["reverted_test_paths"], f
        assert r["resolved"] is True, r
    elif variant == "compile_break":
        assert r["build_ok"] is False and r["resolved"] is False, r
    elif variant == "regression":
        assert r["resolved"] is False and r["regressions"], r
        assert all(s == "passed" for s in r["f2p"].values()), r["f2p"]
    elif variant == "gradlew_edit":
        assert "gradlew" in f["build_config_reverted"] and f["build_config_changed"] is True, f
        assert r["resolved"] is True, r
    elif variant == "interface_mismatch":
        assert r["reason"] == "test_compile_failed" and r["resolved"] is False, r
        assert r["interface_candidate"] is True, r
