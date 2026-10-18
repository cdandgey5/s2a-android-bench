"""The real Driver over canned stream-json (fake run_agent): nudges, usage limit, probe, per-process cost."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from s2a import driver as drv
from s2a.platform.base import ProcResult

FIX = Path(__file__).parent / "fixtures" / "transcripts"


class CannedPlatform:
    id = "fake"

    def __init__(self, streams: list[str]) -> None:
        self.streams = list(streams)
        self.argv: list[list[str]] = []
        self.stdin: list[str] = []

    def run_agent(self, argv, *, cwd, out_dir, timeout_s, stdin_text, grace_s=30.0, stop=None, env=None):
        self.argv.append(list(argv))
        self.stdin.append(stdin_text)
        out_dir.mkdir(parents=True, exist_ok=True)
        so, se = out_dir / "stdout.txt", out_dir / "stderr.txt"
        src = self.streams.pop(0)
        if src.endswith(".jsonl"):
            shutil.copyfile(FIX / src, so)
        else:
            so.write_text(src, encoding="utf-8")
        se.write_text("", encoding="utf-8")
        return ProcResult(0, so, se, 0.1)


def _driver(tmp_path: Path, streams: list[str]) -> tuple[drv.Driver, CannedPlatform]:
    b = drv.Budget(max_turns_total=200, max_usd=15, timeout_minutes=45)
    b.start_clock()
    d = drv.Driver(run_dir=tmp_path / "run", cwd=tmp_path, model="claude-sonnet-5-5", budget=b, claude_exe="claude")
    plat = CannedPlatform(streams)
    d.plat = plat
    return d, plat


def _result_stream(text: str, *, session: str = "s1", cost: float = 0.01, out: int = 10) -> str:
    init = {"type": "system", "subtype": "init", "model": "claude-sonnet-5-5", "session_id": session,
            "permissionMode": "bypassPermissions", "claude_code_version": "2.1.302"}
    asst = {"type": "assistant", "message": {"id": f"m-{session}-{text[:5]}", "content": [{"type": "text", "text": text}],
                                             "usage": {"output_tokens": out}}}
    res = {"type": "result", "subtype": "success", "num_turns": 1, "total_cost_usd": cost, "session_id": session,
           "usage": {"input_tokens": 1, "output_tokens": out, "cache_read_input_tokens": 0,
                     "cache_creation_input_tokens": 0},
           "modelUsage": {"claude-sonnet-5-5": {"outputTokens": out, "costUSD": cost}}}
    return "\n".join(json.dumps(x) for x in (init, asst, res)) + "\n"


def test_flags_and_read_only_tools(tmp_path) -> None:
    d, plat = _driver(tmp_path, [_result_stream("done.")])
    r = d.call("intake", "PROMPT", name="intake", system="SYS", turn_cap=5, read_only=True, structured=True)
    a = plat.argv[0]
    assert a[a.index("--max-turns") + 1] == "5" and a[a.index("--permission-mode") + 1] == "bypassPermissions"
    assert a[a.index("--disallowedTools") + 1] == "WebFetch,WebSearch,Edit,Write,MultiEdit,NotebookEdit"
    assert a[a.index("--append-system-prompt") + 1] == "SYS" and plat.stdin[0] == "PROMPT"
    assert r.call.subtype == "success" and r.texts == ["done."]
    rec = json.loads((tmp_path / "run" / "calls.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert rec["name"] == "intake" and rec["prompt_sha256"] == drv.sha256_text("PROMPT")
    assert (tmp_path / "run" / "transcripts" / "intake.jsonl").exists() and (tmp_path / "run/prompts/intake.md").exists()


def test_question_nudges_once_and_resumes_the_session(tmp_path) -> None:
    d, plat = _driver(tmp_path, [_result_stream("Which option do you want?", cost=0.02, out=10),
                                 _result_stream("Assumed option A and finished.", cost=0.03, out=15)])
    r = d.call("implement", "P", name="implement-T1", system="S", turn_cap=35, read_only=False)
    assert r.call.interventions == 1 and r.call.interventions_log[0]["trigger"] == "b"
    assert plat.argv[1][plat.argv[1].index("--resume") + 1] == "s1" and plat.stdin[1] == drv.NUDGE_TEXT
    assert r.last_text.startswith("Assumed") and r.call.num_turns == 2
    # the resumed process reports the session's running cost (0.03 includes the first 0.02): own = 0.03 here
    # because the canned stream's modelUsage carries only its own output tokens (no restored base)
    assert r.call.cost_usd == pytest.approx(0.05)


def test_artifact_stages_do_not_nudge_on_question_marks(tmp_path) -> None:
    d, _ = _driver(tmp_path, [_result_stream("## Unknowns\n- what about tablets?")])
    r = d.call("intake", "P", name="intake", system="S", turn_cap=5, read_only=True, structured=True)
    assert r.call.interventions == 0


def test_usage_limit_canary_is_usage_limited(tmp_path) -> None:
    d, _ = _driver(tmp_path, ["usage-limited-canary.jsonl"])
    r = d.call("plan", "P", name="plan", system="S", turn_cap=15, read_only=True, structured=True)
    assert r.call.subtype == "usage_limited" and d.events[-1]["event"] == "usage_limited"
    assert d.events[-1]["resets_hint"] == "2am"


def test_unexplained_ending_runs_the_probe(tmp_path) -> None:
    d, plat = _driver(tmp_path, ["smoke-interrupt.jsonl", "probe-limited.jsonl"])
    r = d.call("map", "P", name="map", system="S", turn_cap=25, read_only=False)
    assert r.call.subtype == "usage_limited" and d.probes == 1
    assert plat.argv[1][plat.argv[1].index("--tools") + 1] == "" and plat.stdin[1] == "ping"
    assert (tmp_path / "run" / "transcripts" / "probe-map-1.jsonl").exists()


def test_auth_refusal_raises(tmp_path) -> None:
    bad = json.dumps({"type": "result", "subtype": "error_during_execution", "is_error": True, "num_turns": 0,
                      "result": "API Error: 401 authentication_error: invalid oauth token"}) + "\n"
    d, _ = _driver(tmp_path, [bad, bad])
    with pytest.raises(drv.ServiceRefused):
        d.call("intake", "P", name="intake", system="S", turn_cap=5, read_only=True, structured=True)


class InterruptingPlatform(CannedPlatform):
    """The second process is stopped from outside: it wrote part of its stream, then Ctrl+C arrives."""

    def run_agent(self, argv, *, cwd, out_dir, timeout_s, stdin_text, grace_s=30.0, stop=None, env=None):
        if len(self.argv) == 1:
            self.argv.append(list(argv))
            out_dir.mkdir(parents=True, exist_ok=True)
            partial = _result_stream("working", session="s2", cost=0.04, out=20).splitlines()[:2]
            (out_dir / "stdout.txt").write_text("\n".join(partial) + "\n", encoding="utf-8")
            raise KeyboardInterrupt
        return super().run_agent(argv, cwd=cwd, out_dir=out_dir, timeout_s=timeout_s, stdin_text=stdin_text,
                                 grace_s=grace_s, stop=stop, env=env)


def test_an_interrupted_call_is_recorded_before_the_interrupt_propagates(tmp_path) -> None:
    d, _ = _driver(tmp_path, [_result_stream("done.")])
    d.plat = InterruptingPlatform([_result_stream("done.")])
    d.call("intake", "P", name="intake", system="S", turn_cap=5, read_only=True, structured=True)
    with pytest.raises(KeyboardInterrupt):
        d.call("implement", "P", name="implement-T1", system="S", turn_cap=35, read_only=False)
    recs = [json.loads(x) for x in (tmp_path / "run" / "calls.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [r["name"] for r in recs] == ["intake", "implement-T1"]
    assert recs[1]["subtype"] == "timeout" and recs[1]["cost_usd"] is None and recs[1]["output_tokens"] == 20
    assert (tmp_path / "run" / "transcripts" / "implement-T1.jsonl").exists()
    assert d.budget.turns_used == 1   # the partial stream has no result line: no turns counted for it
