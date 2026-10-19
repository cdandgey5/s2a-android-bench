import pytest

from s2a import parse

PLAN = """# Plan: persist speed
## Tasks
### T1 Store speed  [approach: modify]  covers: AC1
- Files: playback/src/main/java/a/B.java (modify) · playback/src/main/java/a/C.java (new)
```json
{"tasks": [{"id": "T1", "title": "Store speed", "approach": "modify", "covers": ["AC1"],
            "files": ["playback/src/main/java/a/B.java (modify)", "playback/src/main/java/a/C.java (new)"],
            "module": ":playback", "task": "testDebugUnitTest", "tests": ["a.BTest.speed"], "fixes_repro": true}]}
```
"""


def test_plan_json_and_tasks() -> None:
    d = parse.plan_json(PLAN)
    (t,) = parse.plan_tasks(d)
    assert t.id == "T1" and t.module == ":playback" and t.fixes_repro and t.tests == ["a.BTest.speed"]
    assert parse.plan_file_path(t.files[1]) == ("playback/src/main/java/a/C.java", True)
    assert parse.plan_file_path(t.files[0]) == ("playback/src/main/java/a/B.java", False)


def test_plan_json_errors() -> None:
    with pytest.raises(ValueError):
        parse.plan_json("no json here")
    with pytest.raises(ValueError):
        parse.plan_json('```json\n{"nope": 1}\n```')


def test_ticket_and_criteria() -> None:
    t = "```\n# Speed resets\ntype: bug\nsize: M\n## Description\nx\n```"
    md = parse.strip_fence(t)
    assert parse.ticket_type(md) == "bug" and parse.ticket_size(md) == "M"
    spec = ("## Acceptance criteria\nAC1. WHEN x THE SYSTEM SHALL y. — verified by: a.BTest.speed\n"
            "AC2. WHEN z THE SYSTEM SHALL w.\n## Unchanged behaviour\nUB1. THE SYSTEM SHALL CONTINUE TO q. — verified by: obs\n")
    acs, ubs = parse.criteria(spec, "AC"), parse.criteria(spec, "UB")
    assert [c.id for c in acs] == ["AC1", "AC2"] and acs[0].verification == "a.BTest.speed" and acs[1].verification == ""
    assert [c.id for c in ubs] == ["UB1"]


WIN_PATH = r"C:\work\repo\app\src\main\java\X.kt"


def test_locate_candidates() -> None:
    md = ("## Candidates (ranked)\n1. playback/src/main/java/a/B.java — B.speed — reads the pref\n"
          f"2. `{WIN_PATH}` — X — evidence\n3. no path here\n## Call graph\n- x")
    assert parse.locate_candidates(md) == ["playback/src/main/java/a/B.java", WIN_PATH]


def test_new_test_methods_compare_whole_files_not_diff_lines() -> None:
    from s2a.stages.reproduce import new_test_methods

    before = "class SpeedTest {\n    @Test\n    void loads() { assertEquals(1, 1); }\n}\n"
    # a new test inserted above an existing one whose line was also touched: in the diff the existing signature is
    # an added line after an added @Test, and the new one may follow a context @Test
    now = ("class SpeedTest {\n    @Test\n    void speedPersists() { assertEquals(1.5f, new Speed().load()); }\n\n"
           "    @Test\n    void loads() { assertEquals(1, 1 ); }\n}\n")
    assert new_test_methods(now, before) == ["speedPersists"]
    kt = "class T {\n    @Test\n    fun `keeps speed`() {}\n    @Test fun other() {}\n}\n"
    assert new_test_methods(kt, "") == ["keeps speed", "other"]


def test_locate_candidates_skip_urls_elisions_and_files_to_create() -> None:
    md = ("## Candidates (ranked)\n"
          "1. `net/common/src/main/java/a/UrlChecker.java` — prepare() — handles https://subscribeonandroid.com/x\n"
          "2. https://subscribeonandroid.com/example.com/feed — the failing input\n"
          "3. `parser/media/.../MediaFormatDetector.java` — detection\n"
          "4. `parser/media/src/main/java/a/m4a/M4AReader.java` (new) — the reader to add\n")
    assert parse.locate_candidates(md) == ["net/common/src/main/java/a/UrlChecker.java",
                                           "parser/media/src/main/java/a/m4a/M4AReader.java"]
    assert parse.locate_candidates(md, include_new=False) == ["net/common/src/main/java/a/UrlChecker.java"]


def test_compile_task_follows_the_test_task() -> None:
    from s2a.gradle import compile_task_for

    assert compile_task_for("testFreeDebugUnitTest") == "compileFreeDebugUnitTestSources"
    assert compile_task_for("testDebugUnitTest") == "compileDebugUnitTestSources"
    assert compile_task_for("test") == "testClasses" and compile_task_for(None) is None
