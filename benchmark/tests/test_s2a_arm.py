"""S2A arm (phases/phase-6 step 15-16): calls.jsonl -> PhaseCall mapping (paths rewritten, orphan
streams recorded), the s2a ending -> exit reason table, ablation flags and budgets, artifact capture,
and that a trial record built this way passes `abb audit`."""
from __future__ import annotations

import json
import shutil
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace

import pytest

from abb.arms.base import Limits
from abb.arms.registry import get_arm
from abb.arms.s2a import arm as s2
from abb.harness import audit
from abb.harness import transcript as tx
from abb.harness.agent_driver import AbortRun, HarnessError, TrialBudget, phasecall_dict

FIX = Path(__file__).parent / "fixtures" / "transcripts"


def s2a_record(name: str, src: Path, **over) -> dict:
    """A calls.jsonl line as s2a's driver writes it (absolute paths inside the workspace)."""
    t = tx.parse_file(src)
    rec = {"name": name, "session_id": t.session_id, "cmd": ["claude", "-p"], "started_at": "2026-10-18T00:00:00Z",
           "duration_ms": 10, "num_turns": t.num_turns, "tool_calls": t.tool_calls, "tool_errors": t.tool_errors,
           "cost_usd": tx.invocation_cost(t, []), "cost_usd_imputed": None, **t.usage_totals(), "subtype": "success",
           "interventions": 0, "asked_question": False, "rate_limit_retries": t.rate_limit_retries,
           "other_retries": t.other_retries, "claude_code_version": (t.init or {}).get("claude_code_version"),
           "model_drift": False, "transcript_path": f"C:/ws/work/.s2a/runs/trial/transcripts/{name}.jsonl",
           "interventions_log": [], "background_models": [], "nudge_transcript_paths": [], "prompt_sha256": "x",
           "system_prompt_sha256": "y", "some_future_field": 1}
    rec.update(over)
    return rec


def fake_run_dir(root: Path, *, orphan: bool = False) -> Path:
    rd = root / ".s2a" / "runs" / "trial"
    for d in ("transcripts", "prompts", "agent-out/intake", "gates/001-test_app", "repro"):
        (rd / d).mkdir(parents=True, exist_ok=True)
    shutil.copyfile(FIX / "smoke-success.jsonl", rd / "transcripts" / "intake.jsonl")
    (rd / "transcripts" / "intake.stderr.txt").write_text("", encoding="utf-8")
    (rd / "agent-out/intake/stdout.txt").write_text("x", encoding="utf-8")
    (rd / "prompts" / "intake.md").write_text("PROMPT", encoding="utf-8")
    (rd / "calls.jsonl").write_text(json.dumps(s2a_record("intake", FIX / "smoke-success.jsonl")) + "\n", encoding="utf-8")
    (rd / "gates/001-test_app/argv.json").write_text(json.dumps({"argv": ["gradlew"], "exit_code": 0, "seconds": 12.5}),
                                                     encoding="utf-8")
    (rd / "gates/001-test_app/stdout.txt").write_text("BUILD SUCCESSFUL", encoding="utf-8")
    for f in ("ticket.md", "spec.md", "plan.md", "verify.md", "report.md", "progress.md"):
        (rd / f).write_text(f"# {f}\n", encoding="utf-8")
    (rd / "plan.json").write_text("{}", encoding="utf-8")
    (rd / "repro" / "manifest.json").write_text("{}", encoding="utf-8")
    if orphan:  # s2a was killed while implement-T1 ran: a stream, no record
        (rd / "agent-out/implement-T1").mkdir()
        shutil.copyfile(FIX / "smoke-interrupt.jsonl", rd / "agent-out/implement-T1/stdout.txt")
    return rd


def test_calls_are_lifted_with_paths_rewritten(tmp_path: Path) -> None:
    rd, rec = fake_run_dir(tmp_path / "ws"), tmp_path / "rec"
    (c,) = s2.collect_calls(rd, rec, "claude-sonnet-5-5")
    assert c.name == "intake" and Path(c.transcript_path) == rec / "transcript" / "intake.jsonl"
    assert (rec / "transcript" / "intake.jsonl").read_bytes() == (FIX / "smoke-success.jsonl").read_bytes()
    assert (rec / "prompts" / "intake.md").read_text(encoding="utf-8") == "PROMPT"
    assert not hasattr(c, "some_future_field")


def test_a_killed_call_becomes_a_timeout_call_from_its_stream(tmp_path: Path) -> None:
    rd, rec = fake_run_dir(tmp_path / "ws", orphan=True), tmp_path / "rec"
    calls = s2.collect_calls(rd, rec, "claude-sonnet-5-5")
    assert [c.name for c in calls] == ["intake", "implement-T1"]
    o = calls[1]
    t = tx.parse_file(FIX / "smoke-interrupt.jsonl")
    assert o.subtype == "timeout" and o.num_turns == t.num_turns and o.output_tokens == t.usage_totals()["output_tokens"]
    assert (rec / "transcript" / "implement-T1.jsonl").exists()


@pytest.mark.parametrize("state,expected", [
    ({"exit_code": 0, "exit_reason": "completed", "verdict": "ACCEPT"}, "completed"),
    ({"exit_code": 2, "exit_reason": "completed", "verdict": "REJECT"}, "completed"),
    ({"exit_code": 4, "exit_reason": "max_turns"}, "max_turns"),
    ({"exit_code": 4, "exit_reason": "budget"}, "budget"),
    ({"exit_code": 4, "exit_reason": "timeout"}, "timeout"),
    ({"exit_code": 6, "exit_reason": "usage_limited"}, "usage_limited"),
    ({"exit_code": 3, "exit_reason": "gate_failed", "notes": ["stopped: gate_failed — plan_valid"]}, "agent_error"),
    ({"exit_code": 5, "exit_reason": "paused"}, "agent_error"),
    ({"exit_code": 1, "exit_reason": "harness_error", "notes": ["orchestrator error: KeyError('x')"]}, "agent_error"),
])
def test_exit_mapping(state: dict, expected: str) -> None:
    assert s2.outcome(state, 0, False)[0] == expected


def test_exit_mapping_special_cases() -> None:
    assert s2.outcome(None, 1, False)[0] == "agent_error"          # the product crashed: never re-run
    assert s2.outcome(None, None, True)[0] == "timeout"            # the harness stopped it before it saved
    with pytest.raises(AbortRun):
        s2.outcome({"exit_code": 6, "exit_reason": "auth_failed", "notes": ["401"]}, 6, False)
    with pytest.raises(HarnessError):                              # our environment, not the agent: re-queued once
        s2.outcome({"exit_code": 1, "exit_reason": "harness_error",
                    "notes": ["orchestrator error: DriverError(\"claude_code_version '2.0' != 2.1\")"]}, 1, False)


def test_variants_and_setup_kind() -> None:
    arms = {n: get_arm(n) for n in ("s2a", "s2a-nomap", "s2a-noverify", "s2a-norepro")}
    assert {n: a.setup_kind for n, a in arms.items()} == {"s2a": "s2a-map", "s2a-nomap": None,
                                                          "s2a-noverify": "s2a-map", "s2a-norepro": "s2a-map"}
    assert {n: (a.variant["skip"], a.variant["turns_off"]) for n, a in arms.items()} == {
        "s2a": ([], 0), "s2a-nomap": (["map"], 0), "s2a-noverify": (["verify"], 30), "s2a-norepro": (["reproduce"], 15)}


def test_artifacts_skip_streams_and_gate_output(tmp_path: Path) -> None:
    rd = fake_run_dir(tmp_path / "ws")
    got = set(s2.copy_artifacts(rd, tmp_path / "art"))
    assert {"ticket.md", "plan.json", "verify.md", "report.md", "repro/manifest.json", "gates/001-test_app/argv.json",
            "calls.jsonl"} <= got
    assert not any(g.startswith(("transcripts/", "prompts/", "agent-out/")) for g in got)
    assert "gates/001-test_app/stdout.txt" not in got
    assert s2.gate_runs(rd) == (1, 12.5)


class FakeWS:
    def __init__(self, root: Path) -> None:
        self.dirs = SimpleNamespace(work=root / "work", agent_out=root / "agent-out")
        self.dirs.work.mkdir(parents=True)
        self.dirs.agent_out.mkdir(parents=True)
        self.base = "abc"

    def diff(self) -> str:
        return "diff --git a/x b/x\n"

    def git(self, *a, **k):
        return SimpleNamespace(stdout=lambda: "full\n")


@pytest.mark.parametrize("name,flags,turns", [
    ("s2a", ["--map"], 200), ("s2a-nomap", ["--skip", "map"], 200), ("s2a-noverify", ["--map", "--skip", "verify"], 170),
    ("s2a-norepro", ["--map", "--skip", "reproduce"], 185)])
def test_run_argv_budget_and_record(tmp_path: Path, monkeypatch, name: str, flags: list[str], turns: int) -> None:
    ws = FakeWS(tmp_path)
    (ws.dirs.work / ".s2a").mkdir()
    (ws.dirs.work / ".s2a" / "map.md").write_text("# Map", encoding="utf-8")
    rec = tmp_path / "rec"
    rec.mkdir()
    ctx = SimpleNamespace(ws=ws, record_dir=rec, run_dir=tmp_path / "run", tag="s2a-x-t1", token="",
                          budget=TrialBudget.start(Limits()), as_agent=True, proxy=True, events=[])
    seen = {}

    def fake_invoke(c, argv, out_name, timeout_s):
        seen["argv"], seen["timeout"] = argv, timeout_s
        rd = fake_run_dir(ws.dirs.work)
        (rd / "state.json").write_text(json.dumps({"exit_code": 0, "exit_reason": "completed", "verdict": "ACCEPT"}),
                                       encoding="utf-8")
        (rd / "events.jsonl").write_text(json.dumps({"at": "t", "event": "exit", "code": 0}) + "\n", encoding="utf-8")
        return SimpleNamespace(exit_code=0, stopped_by_harness=False, job_memory_hit=False)

    monkeypatch.setattr(s2, "invoke", fake_invoke)
    monkeypatch.setattr(s2, "exe", lambda: Path("s2a.exe"))
    monkeypatch.setattr(s2, "check_calls", lambda calls, model: None)
    task = SimpleNamespace(id="antennapod-0000", test_patch=None, gold_patch=None)
    rr = get_arm(name).run(task, ws, Limits(), ctx=ctx, ticket="Speed resets.", trial=1)
    a = seen["argv"]
    assert a[1] == "run" and a[a.index("--max-turns") + 1] == str(turns) and a[a.index("--run-id") + 1] == "trial"
    assert ("--map" in a) == ("--map" in flags) and (a[a.index("--skip") + 1] if "--skip" in a else None) == (
        flags[flags.index("--skip") + 1] if "--skip" in flags else None)
    assert (ws.dirs.agent_out / "s2a-in" / "problem.md").read_text(encoding="utf-8") == "Speed resets.\n"
    assert not any("antennapod-0000" in x for x in a)               # the product never sees a task id
    assert rr.exit_reason == "completed" and rr.gate_gradle_runs == 1 and rr.gate_seconds == 12.5
    assert rr.artifacts["verdict"] == "ACCEPT" and (rec / "artifacts" / "report.md").exists()
    assert (rec / "diff.patch").read_text(encoding="utf-8").startswith("diff --git")
    assert rr.num_turns == rr.calls[0].num_turns and ctx.budget.turns_used == rr.num_turns
    assert ctx.events and ctx.events[0]["event"] == "s2a_exit"


def test_record_passes_the_audit(tmp_path: Path) -> None:
    rd, rec = fake_run_dir(tmp_path / "ws", orphan=True), tmp_path / "rec"
    calls = s2.collect_calls(rd, rec, "claude-sonnet-5-5")
    from abb.arms.base import RunResult

    rr = RunResult(arm="s2a", task_id="x", trial=1, exit_reason="timeout", diff_path=rec / "diff.patch",
                   transcript_dir=rec / "transcript", workspace_base="", calls=calls).fill_totals()
    data = asdict(rr)
    data["calls"] = [phasecall_dict(c) for c in calls]
    data["limits"] = asdict(Limits())
    (rec / "run.json").write_text(json.dumps(data, default=str), encoding="utf-8")
    (rec / "calls.jsonl").write_text("".join(json.dumps(c, default=str) + "\n" for c in data["calls"]), encoding="utf-8")
    pin = tx.parse_file(FIX / "smoke-success.jsonl").init["claude_code_version"]
    assert audit.audit_trial(rec, pin) == []
