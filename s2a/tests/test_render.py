from s2a import render

MAP = """# Map
## 1. Modules
- :app — the app
## 2. Commands
./gradlew :app:testDebugUnitTest
## 3. Test infrastructure
JUnit 4, Robolectric
## 4. Conventions
Hilt everywhere
## 6. Pitfalls
flavors
"""


def test_sections_by_heading() -> None:
    v = render.map_views(MAP)
    assert "testDebugUnitTest" in v["map_commands"] and "Robolectric" in v["map_commands"]
    assert "Modules" not in v["map_commands"]
    assert "Hilt" in v["map_conventions"] and "flavors" in v["map_conventions"] and "Robolectric" not in v["map_conventions"]


def test_extract_falls_back_to_whole_text() -> None:
    assert render.extract("no headings here", ["commands"]) == "no headings here"


def test_render_fills_and_reports_missing() -> None:
    out, missing = render.render("A {{x}} B {{y}}", {"x": "1"})
    assert out == "A 1 B " and missing == ["y"]


def test_caps() -> None:
    out, _ = render.render("{{map}}|{{other}}", {"map": "m" * 50_000, "other": "o" * 20_000})
    m, o = out.split("|", 1)
    assert len(m) < 41_000 and "truncated" in m and len(o) < 12_200 and "truncated" in o


def test_cap_diff_truncates_per_file_and_keeps_stat() -> None:
    d = "".join(f"diff --git a/f{i} b/f{i}\n" + "+x\n" * 20_000 for i in range(3))
    out = render.cap_diff(d, " f0 | 20000 +\n f1 | 20000 +")
    assert out.startswith("# git diff --stat") and len(out) <= 60_100 and out.count("diff --git") == 3
    assert "file diff truncated" in out


def test_mode_values() -> None:
    a, i = render.mode_values("autonomous"), render.mode_values("interactive")
    assert "Never ask" in a["question_policy"] and a["assumptions_or_questions_heading"] == "Assumptions"
    assert i["assumptions_or_questions_heading"] == "Open questions"
