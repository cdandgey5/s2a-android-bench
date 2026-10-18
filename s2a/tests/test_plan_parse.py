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
