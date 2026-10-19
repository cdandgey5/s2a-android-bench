"""The whole pipeline with fakes (no Claude, no Gradle): stage order, gates, commits, verdict, exit codes,
resume after an interruption, the fix loop, and the reproduction gate failing then passing."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from s2a import orchestrator
from tests.fakes import FakeDriver, FakePlatform, git, make_repo

MAP_MD = "# Map\n## 1. Modules\n- :app\n## 2. Commands\ngradlew :app:testDebugUnitTest\n## 4. Conventions\nplain Java\n"
MAP_JSON = {"modules": [{"path": ":app", "dir": "app", "kind": "app", "unit_test_task": "testDebugUnitTest",
                         "compile_task": "compileDebugUnitTestSources", "lint_task": "lintDebug"}],
            "smoke": {"module": ":app", "task": "testDebugUnitTest"}, "test_frameworks": ["junit4"]}
REPRO = ("package a;\nclass SpeedReproTest {\n    @Test\n    void speedPersists() { assertEquals(1.5f, new Speed().load()); }\n"
         "}\n")
FIXED = "package a;\nclass Speed {\n    float saved = 1.5f;\n    float load() { return saved; }\n}\n"


def scenario(repo: Path, module: str, task: str, kind: str) -> dict:
    """SpeedTest always passes; SpeedReproTest fails (assertion) until Speed.java is fixed."""
    res = {"a.SpeedTest.loads": ("passed", None)}
    if (repo / "app/src/test/java/a/SpeedReproTest.java").exists():
        fixed = "return saved" in (repo / "app/src/main/java/a/Speed.java").read_text(encoding="utf-8")
        res["a.SpeedReproTest.speedPersists"] = ("passed", None) if fixed else ("failed", "assertion")
    return res


def plan_md(two_tasks: bool = False) -> str:
    tasks = [{"id": "T1", "title": "Persist the speed", "approach": "modify", "covers": ["AC1"],
              "files": ["app/src/main/java/a/Speed.java"], "module": ":app", "task": "testDebugUnitTest",
              "tests": ["a.SpeedReproTest"], "fixes_repro": True}]
    if two_tasks:
        tasks.append({"id": "T2", "title": "Tidy", "approach": "modify", "covers": ["AC1"],
                      "files": ["app/src/main/java/a/Speed.java"], "module": ":app", "task": "testDebugUnitTest",
                      "tests": [], "fixes_repro": False})
    return "# Plan: speed\n## Tasks\n### T1 Persist the speed\n- Files: x\n```json\n" + json.dumps({"tasks": tasks}) + "\n```\n"


def make_agent(*, verdicts: list[str] | None = None, two_tasks: bool = False, interrupt_on: str | None = None):
    verdicts = list(verdicts or ["ACCEPT"])

    def agent(stage: str, name: str, prompt: str, repo: Path) -> str:
        if interrupt_on and name == interrupt_on:
            raise KeyboardInterrupt
        if stage == "intake":
            return "```\n# Playback speed is not persisted\ntype: bug\nsize: S\n## Description\nx\n## Done when\n- y\n```"
        if stage == "map":
            (repo / ".s2a").mkdir(exist_ok=True)
            (repo / ".s2a/map.md").write_text(MAP_MD, encoding="utf-8")
            (repo / ".s2a/map.json").write_text(json.dumps(MAP_JSON), encoding="utf-8")
            return "map written"
        if stage == "locate":
            return "## Candidates (ranked)\n1. app/src/main/java/a/Speed.java — Speed.load — returns a constant\n"
        if stage == "reproduce":
            (repo / "app/src/test/java/a/SpeedReproTest.java").write_text(REPRO, encoding="utf-8")
            return "## Tests written\n- app/src/test/java/a/SpeedReproTest.java — speedPersists — FAILS as expected"
        if stage == "spec":
            return ("# Spec: speed\n## Acceptance criteria\nAC1. WHEN the app restarts THE SYSTEM SHALL keep the speed. "
                    "— verified by: a.SpeedReproTest.speedPersists\n## Unchanged behaviour\nUB1. THE SYSTEM SHALL CONTINUE "
                    "TO load. — verified by: a.SpeedTest.loads\n## Assumptions\n- per app, not per podcast\n")
        if stage == "plan":
            return plan_md(two_tasks)
        if stage == "implement":
            if "task T1" in prompt or "T1 Persist" in prompt:
                (repo / "app/src/main/java/a/Speed.java").write_text(FIXED, encoding="utf-8")
            else:
                (repo / "app/src/main/java/a/Speed.java").write_text(FIXED + "// tidy\n", encoding="utf-8")
            return "## Done\n- Speed.java\n## Learned\n- the speed lives in Speed.saved\n## Assumptions\n- none"
        if stage == "verify":
            v = verdicts.pop(0) if verdicts else "ACCEPT"
            line = "PASS" if v == "ACCEPT" else "FAIL"
            return (f"# Verification\n## Acceptance criteria\nAC1 — {line} — ran\n## Unchanged behaviour\nUB1 — PASS — ran\n"
                    f"## Defects\n{'(none)' if v == 'ACCEPT' else '1. Speed.java:3 tidy the field'}\nVERDICT: {v}\n")
        if stage == "fix":
            (repo / "app/src/main/java/a/Speed.java").write_text(FIXED + "// fixed per review\n", encoding="utf-8")
            return "## Fixed\n- 1 — tidied"
        if stage == "report":
            return "# Change report: speed\n## Summary\nDone."
        raise AssertionError(stage)

    return agent


@pytest.fixture
def env(monkeypatch, tmp_path):
    plat = FakePlatform(scenario)
    monkeypatch.setattr(orchestrator, "Driver", FakeDriver)
    monkeypatch.setattr(orchestrator, "get_platform", lambda: plat)
    FakeDriver.log = []
    return make_repo(tmp_path), plat


def _run(repo: Path, **kw):
    ctx, t0 = orchestrator.new_run("Playback speed resets after restart; it should persist.", repo=repo, profile="android",
                                   mode="autonomous", model="claude-sonnet-5-5",
                                   limits={"timeout_minutes": 45, "max_turns_total": 200, "max_usd": 15.0},
                                   skip=kw.get("skip", []), run_id="r1", branch=None, map_path=None, append_file=None)
    return ctx, orchestrator.execute(ctx, t0)


def test_happy_path_accept(env) -> None:
    repo, plat = env
    FakeDriver.agent = make_agent()
    ctx, code = _run(repo)
    assert code == 0 and ctx.state.verdict == "ACCEPT" and ctx.state.exit_reason == "completed"
    assert [s for s, _ in FakeDriver.log] == ["intake", "map", "locate", "reproduce", "spec", "plan", "implement",
                                               "verify", "report"]
    log = git(repo, "log", "--format=%s")
    assert "s2a: reproduction tests" in log and "s2a: T1 - Persist the speed" in log
    for f in ("ticket.md", "locate.md", "spec.md", "plan.md", "plan.json", "verify.md", "report.md", "progress.md",
              "state.json", "calls.jsonl", "repro/manifest.json"):
        assert (ctx.run_dir / f).exists(), f
    man = json.loads((ctx.run_dir / "repro/manifest.json").read_text(encoding="utf-8"))
    assert man["tests"][0]["id"] == "a.SpeedReproTest.speedPersists" and man["result"] == "failing_test_written"
    assert (repo / ".s2a/baseline/app.json").exists()
    assert ".s2a/" in (repo / ".git/info/exclude").read_text(encoding="utf-8")
    assert not git(repo, "status", "--porcelain").strip()
    assert "per app" in " ".join(ctx.state.assumptions) and "Speed.saved" in " ".join(ctx.state.learned)


def test_interrupt_then_resume_continues_at_the_unfinished_task(env) -> None:
    repo, _ = env
    FakeDriver.agent = make_agent(two_tasks=True, interrupt_on="implement-T2")
    ctx, code = _run(repo)
    assert code == 4 and ctx.state.exit_reason == "timeout"
    assert ctx.state.stages["implement"]["task_status"] == {"T1": "done", "T2": "running"}
    FakeDriver.log = []
    FakeDriver.agent = make_agent(two_tasks=True)
    ctx2, t0 = orchestrator.load_run("r1", repo)
    code2 = orchestrator.execute(ctx2, t0)
    assert code2 == 0 and [n for _, n in FakeDriver.log][0].startswith("implement-T2")
    assert "implement-T1" not in [n for _, n in FakeDriver.log]
    assert git(repo, "log", "--format=%s").count("s2a: T1 -") == 1


def test_reject_then_fix_then_accept(env) -> None:
    repo, _ = env
    FakeDriver.agent = make_agent(verdicts=["REJECT", "ACCEPT"])
    ctx, code = _run(repo)
    assert code == 0 and ctx.state.verdict == "ACCEPT"
    rounds = ctx.state.stages["verify"]["rounds"]
    assert [r["verdict"] for r in rounds] == ["REJECT", "ACCEPT"] and "s2a: fix 1" in git(repo, "log", "--format=%s")


def test_reject_twice_exits_2(env) -> None:
    repo, _ = env
    FakeDriver.agent = make_agent(verdicts=["REJECT", "REJECT", "REJECT"])
    ctx, code = _run(repo)
    assert code == 2 and ctx.state.verdict == "REJECT" and ctx.state.stages["fix"]["loops"] == 2


def test_skip_verify_exits_0_when_implement_is_green(env) -> None:
    repo, _ = env
    FakeDriver.agent = make_agent()
    ctx, code = _run(repo, skip=["verify"])
    assert code == 0 and ctx.state.verdict is None
    assert "verify" not in [s for s, _ in FakeDriver.log] and "fix" not in [s for s, _ in FakeDriver.log]


def test_repro_that_passes_at_base_is_retried_then_unavailable(env, monkeypatch) -> None:
    repo, _ = env
    base = make_agent()

    def agent(stage, name, prompt, r):
        if stage == "reproduce":  # a "reproduction" that does not reproduce: it passes now
            (r / "app/src/test/java/a/SpeedReproTest.java").write_text(REPRO.replace("1.5f", "1.0f"), encoding="utf-8")
            return "## Tests written"
        return base(stage, name, prompt, r)

    def scen(repo_, module, task, kind):
        res = {"a.SpeedTest.loads": ("passed", None)}
        if (repo_ / "app/src/test/java/a/SpeedReproTest.java").exists():
            res["a.SpeedReproTest.speedPersists"] = ("passed", None)
        return res

    FakeDriver.agent = agent
    _, plat = env
    plat.scenario = scen
    ctx, code = _run(repo)
    st = ctx.state.stages["reproduce"]
    assert st["status"] == "unavailable" and st["attempts"] == 2 and "fail with an assertion" in st["reason"]
    assert not (repo / "app/src/test/java/a/SpeedReproTest.java").exists()   # reverted, never committed


def test_weakened_test_fails_the_task(env) -> None:
    repo, _ = env
    base = make_agent()

    def agent(stage, name, prompt, r):
        if stage == "implement":
            (r / "app/src/main/java/a/Speed.java").write_text(FIXED, encoding="utf-8")
            t = r / "app/src/test/java/a/SpeedTest.java"
            t.write_text(t.read_text(encoding="utf-8").replace("    @Test\n", "    @Ignore\n"), encoding="utf-8")
            return "## Done"
        return base(stage, name, prompt, r)

    FakeDriver.agent = agent
    ctx, code = _run(repo)
    ts = ctx.state.stages["implement"]["task_status"]
    assert ts["T1"] == "failed" and ctx.state.stages["implement"]["status"] == "done_with_failures"
    gates = ctx.state.stages["implement"]["gates"]
    assert any("no_weakened_tests" in g and not g["no_weakened_tests"]["ok"] for g in gates.values())
    assert code == 0 or code == 2  # verify still runs (the fake verifier accepts); the task failure is in the report


def test_plan_gate_failure_gets_one_retry_with_the_failed_check(env) -> None:
    repo, _ = env
    base = make_agent()
    seen: list[str] = []

    def agent(stage, name, prompt, r):
        if stage == "plan":
            seen.append(prompt)
            text = plan_md()
            if len(seen) == 1:   # first answer names a file that neither exists nor is marked (new)
                text = text.replace('"files": ["app/src/main/java/a/Speed.java"]',
                                    '"files": ["app/src/main/java/a/Speed.java", "app/src/test/resources/speed.xml"]')
            return text
        return base(stage, name, prompt, r)

    FakeDriver.agent = agent
    ctx, code = _run(repo)
    assert code == 0 and ctx.state.stages["plan"]["attempts"] == 2
    assert "paths_exist_or_new" in seen[1] and "## Previous attempt" in seen[1]


def test_no_retry_when_the_stage_has_too_few_turns_left(env, monkeypatch) -> None:
    from s2a.stages import base as stage_base

    repo, _ = env
    monkeypatch.setattr(stage_base, "MIN_RETRY_TURNS", 100)   # nothing is ever "enough" for a retry
    good = make_agent()

    def agent(stage, name, prompt, r):
        if stage == "plan":
            return "no plan here"
        return good(stage, name, prompt, r)

    FakeDriver.agent = agent
    ctx, code = _run(repo)
    assert code == 3 and ctx.state.stages["plan"]["attempts"] == 1
    assert [n for s, n in FakeDriver.log if s == "plan"] == ["plan"]


def test_a_call_that_spends_the_last_turn_still_reaches_its_gate(env) -> None:
    repo, _ = env
    FakeDriver.agent = make_agent()
    ctx, t0 = orchestrator.new_run("Playback speed resets after restart; it should persist.", repo=repo, profile="android",
                                   mode="autonomous", model="claude-sonnet-5-5",
                                   limits={"timeout_minutes": 45, "max_turns_total": 4, "max_usd": 15.0}, skip=[],
                                   run_id="r1", branch=None, map_path=None, append_file=None)
    code = orchestrator.execute(ctx, t0)        # the fake spends 2 turns per call: intake + map use all 4
    assert code == 4 and ctx.state.exit_reason == "max_turns"
    assert ctx.state.stages["map"]["status"] == "done"   # the map's gate ran and passed on the last turns
