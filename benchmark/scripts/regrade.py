"""Re-grade every trial of one task in a finished run after a logged task fix (tasks/CHANGELOG.md). The old
grade is kept as grade.before-<stamp>.json, the run's events.jsonl records each regrade with the reason, and
metrics.json is rebuilt. Transcripts, run.json and the diff are untouched (`abb audit` is unaffected).

    .venv\\Scripts\\python.exe scripts\\regrade.py <run_id> <task_id> --reason "tasks/CHANGELOG.md 2026-10-21"
"""
from __future__ import annotations

import argparse
import json
import shutil

from abb import paths
from abb.harness import grade as grading, metrics
from abb.util import stamp, utcnow_iso


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("run_id")
    ap.add_argument("task_id")
    ap.add_argument("--reason", required=True)
    a = ap.parse_args()
    root = paths.results_dir() / a.run_id
    ts = stamp()
    for rj in sorted(root.glob(f"*/{a.task_id}/t*/run.json")):
        rec = rj.parent
        if rec.parts[-4] in ("usage_limited", "setup", "salvaged"):
            continue
        arm, k = rec.parts[-3], int(rec.name[1:])
        old = json.loads((rec / "grade.json").read_text(encoding="utf-8")) if (rec / "grade.json").exists() else {}
        if (rec / "grade.json").exists():
            shutil.copyfile(rec / "grade.json", rec / f"grade.before-{ts}.json")
        r = grading.grade(a.task_id, rec / "diff.patch", out_dir=rec)
        metrics.build(rec, run_id=a.run_id, arm=arm, task_id=a.task_id, trial=k)
        ev = {"at": utcnow_iso(), "event": "regraded", "arm": arm, "task": a.task_id, "trial": k,
              "resolved_before": old.get("resolved"), "resolved": r["resolved"], "reason": a.reason}
        with open(root / "events.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(ev) + "\n")
        print(json.dumps(ev), flush=True)


if __name__ == "__main__":
    main()
