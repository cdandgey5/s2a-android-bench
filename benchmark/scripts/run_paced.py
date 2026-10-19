"""Run `abb run …` and, whenever it stops on the subscription usage limit, wait for the five-hour window to reset
(the latest `rate_limit_event.resetsAt` in the run's transcripts, + 2 min) and `abb run --resume` it. A stopgap until
Phase 8's scheduler; the usage-limited attempts stay under <run>/usage_limited/ (D-028).

    .venv\\Scripts\\python.exe scripts\\run_paced.py --max-resumes 4 -- --arm s2a --tasks dev5 --trials 1 --label x --grade
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

from abb import paths

HERE = Path(__file__).resolve().parents[1]
ABB = HERE / ".venv" / "Scripts" / "abb.exe"


def latest_reset(root: Path) -> int | None:
    resets = []
    for f in sorted(root.rglob("transcript/*.jsonl"), key=lambda p: p.stat().st_mtime)[-20:]:
        resets += [int(x) for x in re.findall(r'"five_hour":\{"utilization":[0-9.]+,"resetsAt":(\d+)', f.read_text(
            encoding="utf-8", errors="replace"))]
    return max(resets) if resets else None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-resumes", type=int, default=4)
    ap.add_argument("rest", nargs=argparse.REMAINDER)
    a = ap.parse_args()
    args = [x for x in a.rest if x != "--"]
    out = subprocess.run([str(ABB), "run", *args], cwd=HERE, capture_output=True, text=True, encoding="utf-8",
                         errors="replace")
    print(out.stdout[-2000:], out.stderr[-2000:], flush=True)
    m = re.search(r"run (\S+) finished; aborted_reason=(\S+)", out.stdout)
    if not m:
        sys.exit(f"could not find the run id in the output (exit {out.returncode})")
    run_id = m.group(1)
    for n in range(a.max_resumes):
        man = json.loads((paths.results_dir() / run_id / "manifest.json").read_text(encoding="utf-8"))
        if man.get("aborted_reason") != "usage_limit":
            print(f"{run_id}: done, aborted_reason={man.get('aborted_reason')}", flush=True)
            return
        reset = latest_reset(paths.results_dir() / run_id) or int(time.time()) + 3600
        wait = max(60, reset + 120 - int(time.time()))
        print(f"{run_id}: usage limit; resuming in {wait} s (resetsAt {reset})", flush=True)
        time.sleep(wait)
        out = subprocess.run([str(ABB), "run", "--resume", run_id], cwd=HERE, capture_output=True, text=True,
                             encoding="utf-8", errors="replace")
        print(f"resume {n + 1}:", out.stdout[-1500:], out.stderr[-1500:], flush=True)
    print(f"{run_id}: stopped after {a.max_resumes} resumes", flush=True)


if __name__ == "__main__":
    main()
