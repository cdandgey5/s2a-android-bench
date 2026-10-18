"""Gate building blocks: JUnit parsing (assertion vs error), baseline-relative regressions, verdict derivation."""
from __future__ import annotations

from pathlib import Path

from s2a import gradle
from tests.fakes import junit_xml


def test_junit_kinds(tmp_path: Path) -> None:
    for cls, xml in junit_xml({"a.B.ok": ("passed", None), "a.B.assert": ("failed", "assertion"),
                               "a.B.crash": ("failed", "error"), "a.C.err": ("error", None),
                               "a.C.skip": ("skipped", None)}).items():
        (tmp_path / f"TEST-{cls}.xml").write_text(xml, encoding="utf-8")
    r = gradle.parse_junit_dir(tmp_path)
    assert r["a.B.ok"].status == "passed" and r["a.B.assert"].kind == "assertion"
    assert r["a.B.crash"].kind == "error" and r["a.C.err"].status == "error" and r["a.C.skip"].status == "skipped"
    assert gradle.parse_junit_dir(tmp_path / "missing") == {}


def test_regressions_ignore_tests_that_already_failed_at_baseline() -> None:
    base = {"a.T.x": "passed", "a.T.y": "failed", "a.T.z": "passed"}
    now = {"a.T.x": gradle.TestResult("failed", "assertion"), "a.T.y": gradle.TestResult("failed", "assertion")}
    assert gradle.regressions(base, now) == ["a.T.x", "a.T.z"]           # z vanished from a full run
    assert gradle.regressions(base, now, full=False) == ["a.T.x"]        # a filtered run says nothing about z
    assert gradle.regressions(base, {}) == []
