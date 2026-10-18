"""Task tooling: lint rules (offline subset on synthetic tasks), patch splitting, tag computation."""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest
import yaml

from abb import paths
from abb.harness import tasks
from abb.util import glob_match

TEST_DIRS = ["**/src/test/**", "**/src/androidTest/**"]

GOLD = """diff --git a/lib/src/main/java/com/ex/Foo.java b/lib/src/main/java/com/ex/Foo.java
index 1111111..2222222 100644
--- a/lib/src/main/java/com/ex/Foo.java
+++ b/lib/src/main/java/com/ex/Foo.java
@@ -1,3 +1,4 @@
 class Foo {
+    int bar() { return 1; }
 }
"""
TEST = """diff --git a/lib/src/test/java/com/ex/FooTest.java b/lib/src/test/java/com/ex/FooTest.java
new file mode 100644
index 0000000..3333333
--- /dev/null
+++ b/lib/src/test/java/com/ex/FooTest.java
@@ -0,0 +1,3 @@
+import org.junit.Test;
+public class FooTest { @Test public void bar() { new Foo().bar(); } }
+
"""


@pytest.fixture()
def tasks_root(tmp_path: Path, monkeypatch) -> Path:
    root = tmp_path / "tasks"
    shutil.copytree(paths.tasks_dir() / "_template", root / "_template")
    monkeypatch.setattr(paths, "tasks_dir", lambda: root)
    return root


def _make(root: Path, tid: str = "antennapod-0099", **over) -> str:
    d = root / tid
    d.mkdir()
    (d / "gold.patch").write_bytes(over.pop("gold", GOLD).encode())
    (d / "test.patch").write_bytes(over.pop("test", TEST).encode())
    (d / "problem.md").write_text(over.pop("problem", "# Bar is wrong\n\nIt returns the wrong thing.\n"), encoding="utf-8")
    (d / "LICENSE-NOTE.md").write_text("GPL", encoding="utf-8")
    data = {
        "id": tid, "repo": "antennapod", "base_commit": "3d105d598dfa582c6cb22ba40b56d11780366890",
        "source": "authored", "category": "bugfix", "fail_to_pass": [{"module": ":lib", "test": "com.ex.FooTest"}],
        "pass_to_pass": [{"module": ":lib"}], "created_with_s2a_sha": "abc", "drafted_by": "agent",
        "drafted_with_model": "claude-opus-5-5", "split": "dev",
    }
    data.update(over)
    (d / "task.yaml").write_text(yaml.safe_dump(data), encoding="utf-8")
    return tid


def _rules(fs) -> set[str]:
    return {f.rule for f in fs if f.level == "error"}


def test_clean_task_passes_offline(tasks_root: Path) -> None:
    assert _rules(tasks.lint(_make(tasks_root), offline_only=True)) == set()


def test_id_must_match_dir(tasks_root: Path) -> None:
    tid = _make(tasks_root, "antennapod-0098")
    p = tasks_root / tid / "task.yaml"
    d = yaml.safe_load(p.read_text())
    d["id"] = "antennapod-0097"
    p.write_text(yaml.safe_dump(d))
    assert "id-matches-dir" in _rules(tasks.lint(tid, offline_only=True))


def test_test_patch_outside_test_dirs(tasks_root: Path) -> None:
    tid = _make(tasks_root, test=GOLD)
    assert "test-patch-in-test-dirs" in _rules(tasks.lint(tid, offline_only=True))


def test_gold_patch_touching_tests(tasks_root: Path) -> None:
    tid = _make(tasks_root, gold=GOLD + TEST)
    assert "gold-patch-no-tests" in _rules(tasks.lint(tid, offline_only=True))


def test_crlf_patch_rejected(tasks_root: Path) -> None:
    tid = _make(tasks_root, gold=GOLD.replace("\n", "\r\n"))
    assert "patch-lf" in _rules(tasks.lint(tid, offline_only=True))


def test_whole_module_f2p_rejected(tasks_root: Path) -> None:
    tid = _make(tasks_root, fail_to_pass=[{"module": ":lib"}])
    assert "f2p-names-class" in _rules(tasks.lint(tid, offline_only=True))


def test_drafted_by_and_model_required(tasks_root: Path) -> None:
    tid = _make(tasks_root, drafted_with_model=None)
    assert "drafted-by" in _rules(tasks.lint(tid, offline_only=True))


def test_problem_must_not_name_test_class(tasks_root: Path) -> None:
    tid = _make(tasks_root, problem="# Broken\n\nFooTest fails.\n")
    assert "problem-no-test-names" in _rules(tasks.lint(tid, offline_only=True))


def test_mined_needs_upstream_dates(tasks_root: Path) -> None:
    tid = _make(tasks_root, source="mined", upstream={"pr_url": "u", "fix_commit": "c"})
    assert "upstream" in _rules(tasks.lint(tid, offline_only=True))


def test_split_patch_by_test_dirs() -> None:
    test, gold = tasks.split_patch(GOLD + TEST, TEST_DIRS)
    assert tasks.patch_files(test) == ["lib/src/test/java/com/ex/FooTest.java"]
    assert tasks.patch_files(gold) == ["lib/src/main/java/com/ex/Foo.java"]
    assert test + gold != "" and test in (GOLD + TEST) and gold in (GOLD + TEST)


def test_module_of() -> None:
    files = {"build.gradle", "lib/build.gradle", "net/common/build.gradle.kts"}
    assert tasks.module_of("lib/src/main/java/A.java", files) == ":lib"
    assert tasks.module_of("net/common/src/main/x/B.kt", files) == ":net:common"
    assert tasks.module_of("README.md", files) == ":"


def test_compute_tags(tasks_root: Path, monkeypatch) -> None:
    tid = _make(tasks_root)
    monkeypatch.setattr(tasks, "tree", lambda repo, commit: ["lib/build.gradle", "lib/src/main/java/com/ex/Foo.java"])
    t = tasks.compute_tags(tid)
    assert t == {"files_touched": 1, "files_bucket": "1", "modules": 1, "lang": "java", "ui": "none", "test_kind": "junit"}


def test_glob_semantics() -> None:
    assert glob_match("app/src/test/java/X.java", TEST_DIRS)
    assert glob_match("src/androidTest/X.kt", TEST_DIRS)
    assert not glob_match("app/src/main/java/X.java", TEST_DIRS)
    assert glob_match("gradle/wrapper/gradle-wrapper.properties", ["gradle/**"])
    assert not glob_match("app/gradle.properties", ["gradle.properties"])


def test_post_cutoff() -> None:
    from abb.config import TaskConfig

    base = yaml.safe_load((paths.tasks_dir() / "_template" / "task.yaml").read_text(encoding="utf-8"))
    base.update(source="mined", upstream={"fix_date": "2026-07-02", "issue_created": "2026-06-30"})
    assert not tasks.is_post_cutoff(TaskConfig.model_validate(base))
    base["upstream"]["issue_created"] = "2026-07-01"
    assert tasks.is_post_cutoff(TaskConfig.model_validate(base))


def test_tuning_sessions_refuse_held_out_tasks(monkeypatch) -> None:
    import pytest

    from abb.harness.tasks import refuse_held_out_while_tuning

    monkeypatch.delenv("ABB_TUNING", raising=False)
    refuse_held_out_while_tuning(["antennapod-0000", "antennapod-0006"])      # not tuning: no effect
    monkeypatch.setenv("ABB_TUNING", "1")
    refuse_held_out_while_tuning(["antennapod-0000"])                          # dev (pinned dev5)
    with pytest.raises(SystemExit, match="antennapod-0006"):
        refuse_held_out_while_tuning(["antennapod-0000", "antennapod-0006"])  # split: test
