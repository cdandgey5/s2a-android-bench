from pathlib import Path

from s2a.state import RunState


def _st() -> RunState:
    return RunState(run_id="r1", prompt="do x", mode="autonomous", profile="android", branch="s2a/r1", base_commit="abc",
                    model="claude-sonnet-5-5", limits={"max_turns_total": 200}, repo=".")


def test_save_load_roundtrip_and_progress(tmp_path: Path) -> None:
    s = _st()
    s.mark("intake", "done", type="bug")
    s.stage("implement")["task_status"] = {"T1": "done", "T2": "running"}
    s.learned.append("T1: the pref key lives in Prefs.kt")
    s.save(tmp_path)
    t = RunState.load(tmp_path)
    assert t.stages["intake"]["type"] == "bug" and t.stages["implement"]["task_status"]["T2"] == "running"
    md = (tmp_path / "progress.md").read_text(encoding="utf-8")
    assert "T2: running" in md and "Prefs.kt" in md and not (tmp_path / "state.json.tmp").exists()


def test_next_stage_skips_done_skipped_unavailable() -> None:
    s = _st()
    s.mark("intake", "done")
    s.mark("map", "skipped")
    s.mark("locate", "done")
    s.mark("reproduce", "unavailable")
    assert s.next_stage(["intake", "map", "locate", "reproduce", "spec"]) == "spec"
    s.mark("spec", "done_with_failures")
    assert s.next_stage(["intake", "spec", "plan"]) == "plan"
