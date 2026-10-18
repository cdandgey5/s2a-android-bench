"""Test doubles: a platform whose `gradlew` writes JUnit XML from a scenario function, a driver whose agent
is a Python callback, and a tiny Android-shaped git repository."""
from __future__ import annotations

import json
import re
import subprocess
import threading
from pathlib import Path
from typing import Callable

from s2a.driver import Budget, CallResult, Driver, PhaseCall, utcnow_iso
from s2a.platform.base import ProcResult

# scenario(repo, module, task, kind) -> {test id: (status, kind)}; kind in tasks|test|compile|lint
Scenario = Callable[[Path, str, str, str], dict]


def junit_xml(results: dict[str, tuple[str, str | None]]) -> dict[str, str]:
    """{class: xml} for results {"a.B.m": ("passed"|"failed"|"error"|"skipped", kind)}."""
    by: dict[str, list[str]] = {}
    for tid, (status, kind) in results.items():
        cls, _, m = tid.rpartition(".")
        body = ""
        if status == "failed":
            typ = "java.lang.AssertionError" if kind == "assertion" else "java.lang.IllegalStateException"
            body = f'<failure message="boom" type="{typ}">boom</failure>'
        elif status == "error":
            body = '<error message="boom" type="java.lang.RuntimeException">boom</error>'
        elif status == "skipped":
            body = "<skipped/>"
        by.setdefault(cls, []).append(f'<testcase name="{m}" classname="{cls}" time="0.01">{body}</testcase>')
    return {c: f'<?xml version="1.0"?><testsuite name="{c}">{"".join(v)}</testsuite>' for c, v in by.items()}


class FakePlatform:
    id = "fake"

    def __init__(self, scenario: Scenario) -> None:
        self.scenario = scenario
        self.runs: list[list[str]] = []

    def gradlew(self, repo: Path) -> list[str]:
        return [str(Path(repo) / "gradlew")]

    def run(self, argv, *, cwd, out_dir, timeout_s, env=None, stdin_text=None) -> ProcResult:
        self.runs.append(list(argv))
        out_dir.mkdir(parents=True, exist_ok=True)
        so, se = out_dir / "stdout.txt", out_dir / "stderr.txt"
        target = next((a for a in argv[1:] if re.match(r"^:[\w:-]*:\w+$", a)), "")
        module, _, task = target.rpartition(":")
        if task == "tasks":
            so.write_text("testDebugUnitTest - Runs unit tests.\ncompileDebugUnitTestSources - x\nlintDebug - lint\n",
                          encoding="utf-8")
            se.write_text("", encoding="utf-8")
            return ProcResult(0, so, se, 0.1)
        kind = "test" if "UnitTest" in task and not task.startswith("compile") else (
            "lint" if task.startswith("lint") else "compile")
        res = self.scenario(Path(cwd), module, task, kind)
        filters = [argv[i + 1] for i, a in enumerate(argv) if a == "--tests"]
        if kind == "test":
            if res.get("__compile_error__"):
                so.write_text("e: compilation error\nBUILD FAILED\n", encoding="utf-8")
                se.write_text("", encoding="utf-8")
                return ProcResult(1, so, se, 0.1)
            sel = {k: v for k, v in res.items() if not filters or any(k == f or k.startswith(f + ".") for f in filters)}
            d = Path(cwd) / module.strip(":").replace(":", "/") / "build" / "test-results" / task
            d.mkdir(parents=True, exist_ok=True)
            for cls, xml in junit_xml(sel).items():
                (d / f"TEST-{cls}.xml").write_text(xml, encoding="utf-8")
            failed = any(s in ("failed", "error") for s, _ in sel.values())
            so.write_text("BUILD FAILED\n" if failed else "BUILD SUCCESSFUL\n", encoding="utf-8")
            se.write_text("", encoding="utf-8")
            return ProcResult(1 if failed else 0, so, se, 0.1)
        bad = bool(res.get("__compile_error__"))
        so.write_text("BUILD FAILED\n" if bad else "BUILD SUCCESSFUL\n", encoding="utf-8")
        se.write_text("", encoding="utf-8")
        return ProcResult(1 if bad else 0, so, se, 0.1)

    def run_agent(self, *a, **k):  # the fake driver never starts a process
        raise AssertionError("run_agent must not be called with the fake driver")


Agent = Callable[[str, str, str, Path], str]   # (stage, call name, prompt, repo) -> final message


class FakeDriver(Driver):
    """Driver whose agent is a callback; records the calls like the real one (calls.jsonl)."""
    agent: Agent | None = None
    log: list[tuple[str, str]] = []

    def __init__(self, *, run_dir: Path, cwd: Path, model: str, budget: Budget, stop: threading.Event | None = None,
                 **_) -> None:
        self.run_dir, self.cwd, self.model, self.budget, self.stop = run_dir, cwd, model, budget, stop
        self.history, self.events, self.probes = [], [], 0
        for d in ("prompts", "transcripts"):
            (run_dir / d).mkdir(parents=True, exist_ok=True)

    def call(self, stage, prompt, *, name, system, turn_cap, read_only, session_id=None, structured=False,
             implementing=False, diff_empty=None) -> CallResult:
        assert FakeDriver.agent is not None
        (self.run_dir / "prompts" / f"{name}.md").write_text(prompt, encoding="utf-8")
        FakeDriver.log.append((stage, name))
        text = FakeDriver.agent(stage, name, prompt, self.cwd)
        turns = min(2, turn_cap)
        call = PhaseCall(name=name, session_id="s", cmd=["claude"], started_at=utcnow_iso(), duration_ms=1,
                         num_turns=turns, tool_calls=1, tool_errors=0, cost_usd=0.01, cost_usd_imputed=None,
                         input_tokens=1, output_tokens=1, cache_read_tokens=0, cache_write_tokens=0, subtype="success",
                         interventions=0, asked_question=False, rate_limit_retries=0, other_retries=0,
                         claude_code_version="test", model_drift=False, transcript_path="")
        self.budget.charge(turns, 0.01)
        with open(self.run_dir / "calls.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(call.__dict__) + "\n")
        return CallResult(call=call, texts=[text], last_text=text, transcripts=[])


def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=True).stdout


def make_repo(root: Path) -> Path:
    """settings.gradle + :app with a 'bug' (speed is never persisted) and one passing test."""
    repo = root / "repo"
    (repo / "app/src/main/java/a").mkdir(parents=True)
    (repo / "app/src/test/java/a").mkdir(parents=True)
    (repo / "settings.gradle").write_text("include ':app'\n", encoding="utf-8")
    (repo / "gradlew").write_text("#!/bin/sh\n", encoding="utf-8")
    (repo / "app/src/main/AndroidManifest.xml").write_text("<manifest/>\n", encoding="utf-8")
    (repo / "app/src/main/java/a/Speed.java").write_text(
        "package a;\nclass Speed {\n    float load() { return 1.0f; }\n}\n", encoding="utf-8")
    (repo / "app/src/test/java/a/SpeedTest.java").write_text(
        "package a;\nclass SpeedTest {\n    @Test\n    void loads() { assertEquals(1, 1); }\n}\n", encoding="utf-8")
    git(repo, "init", "-q")
    git(repo, "-c", "user.name=t", "-c", "user.email=t@t", "add", "-A")
    git(repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "base")
    return repo
