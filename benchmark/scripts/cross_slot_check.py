"""D-037 evidence during a parallel run: each slot user tries to read the OTHER slot's live trial (work tree,
agent-out, home). Every attempt must be denied. Real attempts through the launcher, as the user.

    .venv\\Scripts\\python.exe scripts\\cross_slot_check.py <run_id>
"""
from __future__ import annotations

import json
import sys

from abb import paths
from abb.harness.platform import get_platform


def main() -> None:
    run_id = sys.argv[1]
    root = paths.results_dir() / run_id
    events = [json.loads(x) for x in (root / "events.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    ended = {(e["arm"], e["task"], e["trial"]) for e in events if e.get("event") == "trial_end"}
    live = {}
    for e in events:
        if e.get("event") == "trial_start" and (e["arm"], e["task"], e["trial"]) not in ended:
            live[e["slot"]] = (e["user"], paths.work_dir() / run_id / e["arm"] / e["task"] / f"t{e['trial']}")
    if len(live) < 2:
        sys.exit(f"need two live trials, have {live}")
    plat, rows = get_platform(), []
    for slot, (user, _) in live.items():
        for other, (ouser, troot) in live.items():
            if other == slot:
                continue
            targets = [(troot / "work", "read"), (troot / "agent-out", "read"), (troot / "home", "read"),
                       (troot / "work", "create")]
            got = plat.check_paths(targets, as_user=user)
            for (p, op), g in zip(targets, got):
                rows.append({"as": user, "target_slot": other, "path": str(p), "op": op, "result": g,
                             "ok": g in ("denied", "missing")})
    for r in rows:
        print(f"{'OK  ' if r['ok'] else 'FAIL'} {r['as']:<11} {r['op']:<6} slot {r['target_slot']}: {r['path']} -> {r['result']}")
    out = root / "cross_slot_check.json"
    out.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    sys.exit(0 if all(r["ok"] for r in rows) else 1)


if __name__ == "__main__":
    main()
