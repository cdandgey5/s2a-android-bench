"""abb report from fixture results (phases/phase-9-analysis.md): tables, withheld numbers on a failed audit,
setup rows kept apart, lost trials excluded, labels in the failure table, byte-identical reruns."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from abb import paths
from abb.harness import report

GRID = {"s2a": {"antennapod-0000": [1, 1], "antennapod-0001": [1, 0], "wikipedia-0002": [0, 0]},
        "plain": {"antennapod-0000": [1, 0], "antennapod-0001": [0, 0], "wikipedia-0002": [0, 0]}}


def _w(p: Path, d: dict) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(d), encoding="utf-8")


@pytest.fixture
def run(tmp_path, monkeypatch) -> str:
    monkeypatch.setattr(paths, "results_dir", lambda: tmp_path)
    rid = "20261101-0000-fixture"
    root = tmp_path / rid
    _w(root / "manifest.json", {"run_id": rid, "created_at": "2026-11-01T00:00:00Z", "label": "fixture",
                                "arms": ["s2a", "plain"], "task_ids": list(GRID["s2a"]), "trials": 2, "task_set": "dev",
                                "limits": {"model": "claude-sonnet-5-5"}, "audit_ok": True})
    _w(root / "audit.json", {"ok": True})
    for arm, tasks in GRID.items():
        for task, res in tasks.items():
            for k, r in enumerate(res, start=1):
                rec = root / arm / task / f"t{k}"
                cost = 1.0 if arm == "s2a" else 0.2
                exit_reason = "harness_error" if (arm, task, k) == ("plain", "wikipedia-0002", 2) else "completed"
                _w(rec / "run.json", {"arm": arm, "task_id": task, "trial": k, "exit_reason": exit_reason,
                                      "cost_usd": cost, "num_turns": 10, "tool_calls": 5, "interventions": 0,
                                      "duration_ms": 60000,
                                      "calls": [{"name": "implement-T1", "num_turns": 6}, {"name": "verify", "num_turns": 4}]})
                _w(rec / "grade.json", {"resolved": bool(r), "reason": None if r else "f2p_failed"})
                _w(rec / "metrics.json", {"repo": task.split("-")[0], "category": "bugfix", "source": "mined",
                                          "split": "dev", "build_ok": True, "regressions_n": 0, "output_tokens": 100})
    _w(root / "setup" / "s2a-map" / "antennapod" / "run.json", {"setup_kind": "s2a-map", "repo": "antennapod",
                                                                 "cost_usd": 0.45, "num_turns": 22})
    _w(root / "setup_failed" / "s2a-map" / "antennapod" / "20261101-000000" / "run.json",
       {"setup_kind": "s2a-map", "repo": "antennapod", "cost_usd": 0.81, "num_turns": 26})
    _w(root / "labels.json", {"items": {"Lx": {"arm": "plain", "task": "antennapod-0001", "trial": 1,
                                               "primary": "INCOMPLETE"}}})
    return rid


def test_rows_tables_and_exclusions(run, tmp_path) -> None:
    trials, setups, cuts, missing = report.load_rows(run)
    assert len(trials) == 12 and len(setups) == 1 and setups.iloc[0].cost_this_run == pytest.approx(0.45)
    assert setups.iloc[0].failed_attempts == 1 and setups.iloc[0].failed_cost == pytest.approx(0.81)
    rows, lost = report.counted(trials)
    assert len(lost) == 1 and len(rows) == 11 and missing == []
    report.render(run, n_boot=500)
    out = tmp_path / run / "report"
    h = pd.read_csv(out / "tables" / "headline.csv")
    s2a = h[h.arm == "s2a"].iloc[0]
    assert s2a["pass@1"] == pytest.approx(1.5 / 3, abs=1e-4) and s2a["pass^2"] == pytest.approx(1 / 3, abs=1e-4)
    plain = h[h.arm == "plain"].iloc[0]
    assert plain["pass@1"] == pytest.approx(0.5 / 3, abs=1e-4)      # the lost trial is out of the denominator
    assert (out / "tables" / "pairs.csv").exists() and (out / "tables" / "by_repo.csv").exists()
    f = pd.read_csv(out / "tables" / "failures.csv")
    assert int(f[(f.arm == "plain") & (f.label == "INCOMPLETE")].trials.iloc[0]) == 1
    st = pd.read_csv(out / "tables" / "stage_turns.csv")
    assert set(st.stage) == {"implement", "verify"}
    text = (out / "summary.md").read_text(encoding="utf-8")
    assert "Primary comparison (exploratory: no PREREG for this run)" in text and "Trials lost" in text
    assert "s2a-map" in text and (out / "charts" / "pass_at_1.png").exists()


def test_deterministic(run, tmp_path) -> None:
    a, b = tmp_path / "r1", tmp_path / "r2"
    report.render(run, out=a, n_boot=500)
    report.render(run, out=b, n_boot=500)
    assert report.diff_dirs(a, b) == []


def test_failed_audit_withholds_the_headline(run, tmp_path) -> None:
    _w(tmp_path / run / "audit.json", {"ok": False})
    text = report.render(run, n_boot=200)
    assert "Withheld" in text and "## Headline" not in text


def test_repro_checks_regrade_audit_and_report(run, tmp_path, monkeypatch) -> None:
    from abb.harness import audit as auditmod, grade as grading, repro

    monkeypatch.setattr(paths, "work_dir", lambda: tmp_path / "work")
    monkeypatch.setattr(auditmod, "audit", lambda rid: {"ok": True})
    report.render(run, n_boot=10_000)
    stored = lambda task, diff, out_dir: json.loads((diff.parent / "grade.json").read_text(encoding="utf-8"))
    monkeypatch.setattr(grading, "grade", stored)
    out = repro.repro(run, k=3, seed=0)
    assert out["ok"] and len(out["regraded"]) == 3 and out["report_identical"]
    assert (tmp_path / run / "repro.json").exists()
    monkeypatch.setattr(grading, "grade", lambda task, diff, out_dir: {**stored(task, diff, out_dir), "resolved": None})
    out = repro.repro(run, k=3, seed=0)
    assert not out["ok"] and all("resolved" in r["differences"] for r in out["regraded"])
