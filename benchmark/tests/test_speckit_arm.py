"""Spec Kit arm (phases/phase-5 step 6): call sequence per category, prompt building (native and
template-inlining fallback), the converge -> second-implement rule, partial-artifact handling."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from abb.arms.base import Limits, PhaseCall
from abb.arms.speckit import arm as sk
from abb.config import load_task

SDD = ["speckit-specify", "speckit-plan", "speckit-tasks", "speckit-implement", "speckit-converge", "speckit-implement-2"]
BUG = ["speckit-bug-assess", "speckit-bug-fix", "speckit-bug-test"]


@pytest.mark.parametrize("category,path,names", [
    ("bugfix", "bug", BUG), ("feature", "sdd", SDD), ("refactor", "sdd", SDD), ("cross_module", "sdd", SDD)])
def test_call_table_by_category(category: str, path: str, names: list[str]) -> None:
    chosen, steps = sk.call_table(category)
    assert chosen == path and [s["name"] for s in steps] == names


def test_speckit_sdd_variant_forces_sdd() -> None:
    chosen, steps = sk.call_table("bugfix", path="sdd")
    assert chosen == "sdd" and [s["name"] for s in steps] == SDD


def test_turn_caps_match_the_spec() -> None:
    caps = {s["name"]: s.get("turn_cap") for s in sk.call_table("feature")[1]}
    assert caps == {"speckit-specify": 15, "speckit-plan": 15, "speckit-tasks": 15, "speckit-implement": 120,
                    "speckit-converge": 20, "speckit-implement-2": None}
    bug = {s["name"]: s.get("turn_cap") for s in sk.call_table("bugfix")[1]}
    assert bug == {"speckit-bug-assess": 20, "speckit-bug-fix": 120, "speckit-bug-test": 40}


def test_native_prompts(tmp_path: Path) -> None:
    steps = dict((s["name"], s) for s in sk.call_table("feature")[1])
    t = "Episodes are not marked as played\n\nSteps: ..."
    assert sk.build_prompt(steps["speckit-specify"], t, work=tmp_path, invocation="native") == f"/speckit-specify {t}"
    assert sk.build_prompt(steps["speckit-tasks"], t, work=tmp_path, invocation="native") == "/speckit-tasks"
    plan = sk.build_prompt(steps["speckit-plan"], t, work=tmp_path, invocation="native")
    assert plan.startswith("/speckit-plan Use the existing build, module layout and test conventions")


def test_inline_fallback_substitutes_arguments_and_drops_front_matter(tmp_path: Path) -> None:
    d = tmp_path / ".claude" / "skills" / "speckit-specify"
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text('---\nname: "speckit-specify"\nuser-invocable: true\n---\n\n## User Input\n\n'
                                "```text\n$ARGUMENTS\n```\n\nDo the thing with $ARGUMENTS.\n", encoding="utf-8")
    step = {"name": "speckit-specify", "command": "speckit-specify", "args": "{{ticket}}"}
    out = sk.build_prompt(step, "  Add a button  ", work=tmp_path, invocation="inline")
    assert out.startswith("## User Input") and "user-invocable" not in out
    assert "Add a button" in out and "$ARGUMENTS" not in out and out.count("Add a button") == 2


def test_open_tasks_counts_unchecked_items(tmp_path: Path) -> None:
    f = tmp_path / "specs" / "001-x" / "tasks.md"
    f.parent.mkdir(parents=True)
    f.write_text("- [X] T001 done\n- [ ] T002 open\n  - [ ] T003 open nested\n* [x] T004 done\n", encoding="utf-8")
    assert sk.open_tasks(tmp_path) == 2
    assert sk.open_tasks(tmp_path / "nowhere") == 0


def test_artifacts_skip_templates_and_scripts(tmp_path: Path) -> None:
    for rel in ("specs/001-x/spec.md", ".specify/memory/constitution.md", ".specify/templates/spec-template.md",
                ".specify/scripts/powershell/common.ps1", ".specify/bugs/b1/assessment.md", "app/src/Main.java"):
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text("x", encoding="utf-8")
    got = sorted(sk.copy_artifacts(tmp_path, tmp_path / "_out", sk.load_config()))
    assert got == [".specify/bugs/b1/assessment.md", ".specify/memory/constitution.md", "specs/001-x/spec.md"]


def test_setup_prompt_hash_is_stable() -> None:
    a, b = sk.SpecKitArm(), sk.SpecKitArm("speckit-sdd", path="sdd")
    assert a.setup_prompt_hash() == b.setup_prompt_hash()  # both arms share one constitution (same setup kind)
    assert a.setup_kind == b.setup_kind == "speckit-constitution"


# ---------------------------------------------------------------------------- run() with a fake driver
def _call(name: str, subtype: str) -> PhaseCall:
    return PhaseCall(name=name, session_id="sess-1", cmd=[], started_at="", duration_ms=10, num_turns=2, tool_calls=1,
                     tool_errors=0, cost_usd=0.01, cost_usd_imputed=None, input_tokens=1, output_tokens=1,
                     cache_read_tokens=0, cache_write_tokens=0, subtype=subtype, interventions=0, asked_question=False,
                     rate_limit_retries=0, other_retries=0, claude_code_version="2.1.302", model_drift=False,
                     transcript_path="")


class _FakeWs:
    def __init__(self, root: Path) -> None:
        self.dirs = SimpleNamespace(work=root / "work")
        (self.dirs.work / ".specify").mkdir(parents=True)
        self.base = "base-sha"

    def diff(self) -> str:
        return ""

    def git(self, *a):
        return SimpleNamespace(stdout=lambda: "")


def _run(monkeypatch, tmp_path: Path, category: str, outcomes: dict[str, str], *, open_after_converge: int = 0):
    seen: list[tuple[str, str | None, int | None]] = []

    def fake(ctx, prompt, *, call_name, append_system_prompt=None, turn_cap=None, session_id=None,
             is_implementing_call=False, **_):
        seen.append((call_name, session_id, turn_cap))
        if call_name == "speckit-converge" and open_after_converge:
            p = ws.dirs.work / "specs" / "001" / "tasks.md"
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("- [ ] T9 left\n" * open_after_converge, encoding="utf-8")
        return _call(call_name, outcomes.get(call_name, "success"))

    monkeypatch.setattr(sk, "run_headless", fake)
    ws = _FakeWs(tmp_path)
    budget = SimpleNamespace(exhausted=lambda: False, limits=Limits())
    ctx = SimpleNamespace(record_dir=tmp_path / "rec", budget=budget)
    (tmp_path / "rec").mkdir()
    task = load_task("antennapod-0003").model_copy(update={"test_patch": None, "gold_patch": None,
                                                            "category": category})
    rr = sk.SpecKitArm().run(task, ws, Limits(), ctx=ctx, ticket="T", trial=1)
    return rr, seen


def test_sdd_runs_in_one_session_and_skips_second_implement_without_open_tasks(monkeypatch, tmp_path) -> None:
    rr, seen = _run(monkeypatch, tmp_path, "feature", {})
    assert [s[0] for s in seen] == SDD[:-1]
    assert seen[0][1] is None and all(s[1] == "sess-1" for s in seen[1:])  # first call opens, the rest --resume
    assert rr.exit_reason == "completed" and "path sdd" in rr.notes


def test_second_implement_when_converge_leaves_open_tasks(monkeypatch, tmp_path) -> None:
    rr, seen = _run(monkeypatch, tmp_path, "refactor", {}, open_after_converge=2)
    assert [s[0] for s in seen] == SDD and seen[-1][2] is None  # remaining budget
    assert "2 open task(s)" in rr.notes


def test_max_turns_continues_but_usage_limit_stops(monkeypatch, tmp_path) -> None:
    rr, seen = _run(monkeypatch, tmp_path / "a", "feature", {"speckit-specify": "error_max_turns"})
    assert [s[0] for s in seen] == SDD[:-1] and "speckit-specify hit its turn cap" in rr.notes
    rr2, seen2 = _run(monkeypatch, tmp_path / "b", "bugfix", {"speckit-bug-fix": "usage_limited"})
    assert [s[0] for s in seen2] == BUG[:2] and rr2.exit_reason == "usage_limited"


def test_bug_path_for_bugfix(monkeypatch, tmp_path) -> None:
    rr, seen = _run(monkeypatch, tmp_path, "bugfix", {})
    assert [s[0] for s in seen] == BUG and rr.artifacts["path"] == "bug"
