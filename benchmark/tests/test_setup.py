"""One-time setup records: a retry after a failed attempt keeps the failed record (D-061)."""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from abb import paths
from abb.arms.base import Limits, PhaseCall
from abb.harness import setup


def _call(subtype: str, cost: float, turns: int) -> PhaseCall:
    return PhaseCall(name="map", session_id="s", cmd=["claude"], started_at="2026-11-01T00:00:00Z", duration_ms=1000,
                     num_turns=turns, tool_calls=turns, tool_errors=0, cost_usd=cost, cost_usd_imputed=cost,
                     input_tokens=1, output_tokens=1, cache_read_tokens=0, cache_write_tokens=0, subtype=subtype,
                     interventions=0, asked_question=False, rate_limit_retries=0, other_retries=0,
                     claude_code_version="x", model_drift=False, transcript_path="transcript/map.jsonl")


class FakeArm:
    setup_kind = "s2a-map"
    setup_dirs = [".s2a"]

    def __init__(self, outcomes: list[tuple[str, float, int]]) -> None:
        self.outcomes = outcomes

    def setup_prompt_hash(self) -> str:
        return "h"

    def one_time_setup(self, repo_key, ws, limits, *, ctx):
        subtype, cost, turns = self.outcomes.pop(0)
        (ws.dirs.work / ".s2a").mkdir(parents=True, exist_ok=True)
        (ws.dirs.work / ".s2a" / "map.md").write_text("# map\n", encoding="utf-8")
        (ctx.rec / "transcript").mkdir(parents=True, exist_ok=True)
        (ctx.rec / "transcript" / "map.jsonl").write_text(f'{{"turns": {turns}}}\n', encoding="utf-8")
        return [_call(subtype, cost, turns)]


def test_a_retry_keeps_the_failed_attempt(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(paths, "results_dir", lambda: tmp_path)
    monkeypatch.setattr(setup, "cache_key", lambda *a: "s2a-map-antennapod-k")
    monkeypatch.setattr(setup, "load_repo", lambda r: SimpleNamespace(build=SimpleNamespace(setup_commit="abc")))
    monkeypatch.setattr(setup, "load_env_lock", lambda: {})
    run_dir = tmp_path / "run"
    arm = FakeArm([("agent_error", 0.81, 26), ("success", 1.06, 29)])

    def make_context(arm, repo_key, rec_dir):
        ws = SimpleNamespace(dirs=SimpleNamespace(work=tmp_path / "ws"), cleanup=lambda: None)
        return ws, SimpleNamespace(rec=rec_dir, budget=SimpleNamespace(limits=Limits()))

    with pytest.raises(setup.SetupError):
        setup.ensure_setup(arm, "antennapod", run_dir, run_id="run", make_context=make_context, model="m")
    out = setup.ensure_setup(arm, "antennapod", run_dir, run_id="run", make_context=make_context, model="m")
    assert out["reused"] is False
    (failed,) = (run_dir / "setup_failed" / "s2a-map" / "antennapod").iterdir()
    assert json.loads((failed / "run.json").read_text(encoding="utf-8"))["num_turns"] == 26
    assert (failed / "transcript" / "map.jsonl").read_text(encoding="utf-8").strip() == '{"turns": 26}'
    rec = run_dir / "setup" / "s2a-map" / "antennapod"
    assert json.loads((rec / "run.json").read_text(encoding="utf-8"))["num_turns"] == 29
