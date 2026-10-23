"""`abb repro <run_id>` (Phase 10 step 7): re-grade k random trials from their stored diffs, re-run `abb audit`,
re-render the report into a scratch directory, and check all of it against the stored files.

Writes <run>/repro.json. Grading runs Gradle as the sandbox user, so it refuses while any run looks live.
"""
from __future__ import annotations

import json
import random
import time
from pathlib import Path

from abb import paths
from abb.harness import audit as auditmod, grade as grading, report as rep
from abb.harness.agent_driver import write_json
from abb.util import stamp, utcnow_iso

GRADE_KEYS = ("resolved", "build_ok", "reason", "f2p", "regressions")
LIVE_S = 600  # a run whose events.jsonl moved within this many seconds and has no finished_at is live


def live_runs() -> list[str]:
    out = []
    for mf in paths.results_dir().glob("*/manifest.json"):
        ev = mf.parent / "events.jsonl"
        m = json.loads(mf.read_text(encoding="utf-8"))
        if not m.get("finished_at") and ev.exists() and time.time() - ev.stat().st_mtime < LIVE_S:
            out.append(mf.parent.name)
    return sorted(out)


def pick(run_id: str, k: int, seed: int) -> list[Path]:
    """k graded trials of the run, chosen by `seed` (cut, setup, salvaged and invalidated records excluded)."""
    root = paths.results_dir() / run_id
    recs = sorted(rj.parent for rj in root.glob("*/*/t*/run.json")
                  if rj.parts[-4] not in ("usage_limited", "setup", "salvaged", "invalidated")
                  and (rj.parent / "grade.json").exists())
    return random.Random(seed).sample(recs, min(k, len(recs)))


def repro(run_id: str, k: int = 3, seed: int = 0, regrade: bool = True) -> dict:
    root = paths.results_dir() / run_id
    if regrade and (live := live_runs()):
        raise SystemExit(f"abb repro refused: run(s) {', '.join(live)} look live; grading would share their sandbox "
                         "users and CPU")
    scratch = paths.work_dir() / "repro" / f"{run_id}-{stamp()}"
    out: dict = {"run_id": run_id, "at": utcnow_iso(), "seed": seed, "k": k, "regraded": []}
    if regrade:
        for rec in pick(run_id, k, seed):
            rel = rec.relative_to(root).as_posix()
            old = json.loads((rec / "grade.json").read_text(encoding="utf-8"))
            new = grading.grade(rec.parent.name, rec / "diff.patch", out_dir=scratch / "grade" / rel)
            diffs = {key: [old.get(key), new.get(key)] for key in GRADE_KEYS if old.get(key) != new.get(key)}
            out["regraded"].append({"trial": rel, "resolved": new.get("resolved"), "matches": not diffs,
                                    "differences": diffs})
    out["audit_ok"] = bool(auditmod.audit(run_id)["ok"])
    rep.render(run_id, out=scratch / "report")
    d = rep.diff_dirs(root / "report", scratch / "report")
    out["report_identical"], out["report_differences"] = not d, d
    out["ok"] = all(r["matches"] for r in out["regraded"]) and out["audit_ok"] and not d
    write_json(root / "repro.json", out)
    return out
