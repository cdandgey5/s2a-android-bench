"""Path classification, excluded-path dropping, suspect build-config scan, diff stats."""
from __future__ import annotations

from abb.config import load_repo
from abb.harness import diffscope

REPO = load_repo("antennapod")


def test_classify_precedence() -> None:
    c = lambda p: diffscope.classify(p, REPO)  # noqa: E731
    assert c("app/src/test/java/X.java") == "test"
    assert c("app/src/testFree/java/X.java") == "test"
    assert c("gradlew") == "protected_build"
    assert c("gradle/wrapper/gradle-wrapper.properties") == "protected_build"
    assert c("buildSrc/src/main/kotlin/A.kt") == "protected_build"
    assert c("app/build.gradle") == "build_config"
    assert c("common.gradle") == "build_config"
    assert c("gradle.properties") == "build_config"
    assert c("app/src/main/java/X.java") == "source"
    assert c(".claude/settings.json") == "excluded"
    assert c("specs/001-feature/spec.md") == "excluded"
    assert c("app/build/outputs/x.apk") == "excluded"
    assert c("CLAUDE.md") == "excluded"


DIFF = """diff --git a/app/build.gradle b/app/build.gradle
--- a/app/build.gradle
+++ b/app/build.gradle
@@ -1,2 +1,4 @@
 android {
+    testOptions { unitTests.all { enabled = false } }
+    compileSdk 36
 }
diff --git a/.specify/memory/constitution.md b/.specify/memory/constitution.md
new file mode 100644
--- /dev/null
+++ b/.specify/memory/constitution.md
@@ -0,0 +1 @@
+rules
diff --git a/app/src/main/java/A.java b/app/src/main/java/A.java
--- a/app/src/main/java/A.java
+++ b/app/src/main/java/A.java
@@ -1,2 +1,2 @@
-class A {}
+class A { int x; }
"""


def test_drop_excluded() -> None:
    kept = diffscope.drop_excluded(DIFF, REPO)
    assert ".specify" not in kept and "app/build.gradle" in kept and "A.java" in kept


def test_suspect_test_config() -> None:
    hits = diffscope.suspect_test_config(DIFF, REPO)
    assert len(hits) == 1 and "testOptions" in hits[0]
    assert diffscope.suspect_test_config(DIFF, REPO, only_paths={"settings.gradle"}) == []


def test_diff_stats() -> None:
    s = diffscope.diff_stats(diffscope.drop_excluded(DIFF, REPO))
    assert s["files"] == 2 and s["insertions"] == 3 and s["deletions"] == 1
