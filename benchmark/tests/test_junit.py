"""JUnit XML parsing: passed / failed / error / skipped / parameterized, class-level status."""
from __future__ import annotations

from pathlib import Path

from abb.harness.junit import parse_dir

XML = """<?xml version="1.0" encoding="UTF-8"?>
<testsuite name="com.ex.FooTest" tests="6" skipped="1" failures="1" errors="1" time="0.4">
  <testcase name="passes" classname="com.ex.FooTest" time="0.01"/>
  <testcase name="fails" classname="com.ex.FooTest" time="0.02"><failure message="boom">x</failure></testcase>
  <testcase name="errors" classname="com.ex.FooTest" time="0.03"><error message="npe">y</error></testcase>
  <testcase name="skips" classname="com.ex.FooTest" time="0"><skipped/></testcase>
  <testcase name="param[0]" classname="com.ex.FooTest" time="0.01"/>
  <testcase name="param[1]" classname="com.ex.FooTest" time="0.01"><failure>z</failure></testcase>
</testsuite>
"""
XML2 = """<?xml version="1.0" encoding="UTF-8"?>
<testsuite name="com.ex.BarTest" tests="1"><testcase name="ok" classname="com.ex.BarTest"/></testsuite>
"""


def test_statuses_and_counts(tmp_path: Path) -> None:
    (tmp_path / "TEST-com.ex.FooTest.xml").write_text(XML, encoding="utf-8")
    (tmp_path / "TEST-com.ex.BarTest.xml").write_text(XML2, encoding="utf-8")
    (tmp_path / "other.xml").write_text("<not-junit/>", encoding="utf-8")
    r = parse_dir(tmp_path)
    assert r.tests["com.ex.FooTest.passes"] == "passed"
    assert r.tests["com.ex.FooTest.fails"] == "failed"
    assert r.tests["com.ex.FooTest.errors"] == "error"
    assert r.tests["com.ex.FooTest.skips"] == "skipped"
    assert r.counts() == {"passed": 3, "failed": 2, "error": 1, "skipped": 1, "total": 7}
    assert r.times_ok is False  # BarTest has no time attribute (grading requires fresh XML with times)
    assert len(r.files) == 2


def test_method_and_class_status(tmp_path: Path) -> None:
    (tmp_path / "TEST-com.ex.FooTest.xml").write_text(XML, encoding="utf-8")
    r = parse_dir(tmp_path)
    assert r.status_of("com.ex.FooTest", "passes") == "passed"
    assert r.status_of("com.ex.FooTest", "param") == "failed"      # worst of the parameterized cases
    assert r.status_of("com.ex.FooTest") == "error"                 # worst over the class
    assert r.status_of("com.ex.Missing") is None


def test_empty_dir(tmp_path: Path) -> None:
    r = parse_dir(tmp_path / "nope")
    assert r.counts()["total"] == 0
