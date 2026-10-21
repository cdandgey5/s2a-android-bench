"""D-055 hypothesis: two threads granting different users RX on the SAME folder at the same moment (two trials'
snapshots under one shared parent) can lose one grant (icacls reads the DACL, adds its ACE, writes it back).

    .venv\\Scripts\\python.exe scripts\\acl_race_check.py [rounds]
"""
from __future__ import annotations

import subprocess
import sys
import threading

from abb import paths
from abb.harness.platform import get_platform
from abb.util import stamp

U1, U2 = "abb-agent", "abb-agent2"


def aces(path) -> str:
    return subprocess.run(["icacls", str(path)], capture_output=True, text=True).stdout


def main() -> None:
    rounds = int(sys.argv[1]) if len(sys.argv) > 1 else 40
    plat = get_platform()
    root = paths.work_dir() / "aclrace" / stamp()
    lost = 0
    for i in range(rounds):
        d = root / f"d{i}"
        d.mkdir(parents=True)
        barrier = threading.Barrier(2)

        def grant(user: str) -> None:
            barrier.wait()
            plat.grant(d, user, "list")

        ts = [threading.Thread(target=grant, args=(u,)) for u in (U1, U2)]
        for t in ts:
            t.start()
        for t in ts:
            t.join()
        a = aces(d)
        missing = [u for u in (U1, U2) if f"\\{u}:" not in a]
        if missing:
            lost += 1
            print(f"round {i}: lost {missing}")
    plat.rmtree_robust(root)
    print(f"{lost}/{rounds} rounds lost a grant")


if __name__ == "__main__":
    main()
