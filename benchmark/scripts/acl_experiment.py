"""Parallel-slot ACL experiment (Phase 8 follow-up): does starting or cleaning up a trial of one slot user
change what another slot user can reach in its own live trial under a shared parent folder?
Java's toRealPath() lists every ancestor (D-036), so every ancestor must stay listable.

    .venv\\Scripts\\python.exe scripts\\acl_experiment.py
"""
from __future__ import annotations

from pathlib import Path

from abb import paths
from abb.harness.agent_env import TrialDirs, claude_template_dir
from abb.harness.platform import get_platform
from abb.harness.workspace import apply_trial_acls
from abb.util import stamp

U1, U2 = "abb-agent", "abb-agent2"


def trial(root: Path, user: str) -> TrialDirs:
    t = TrialDirs(root).create(claude_template=claude_template_dir())
    jar = t.gradle_home / "wrapper" / "dists" / "g" / "lib" / "a.jar"
    jar.parent.mkdir(parents=True, exist_ok=True)
    jar.write_bytes(b"PK\x05\x06" + b"\0" * 18)
    apply_trial_acls(t, user)
    return t


def probe(label: str, t: TrialDirs, user: str) -> bool:
    plat = get_platform()
    jar = t.gradle_home / "wrapper" / "dists" / "g" / "lib" / "a.jar"
    chain = [a for a in [*jar.parents][:: -1] if paths.work_dir() in a.parents or a == paths.work_dir()]
    items = [(a, "read") for a in chain] + [(jar, "read")]
    res = plat.check_paths(items, as_user=user)
    bad = [(str(p), r) for (p, _), r in zip(items, res) if r != "ok"]
    print(f"{'OK  ' if not bad else 'FAIL'} {label}: {user} reads {len(items)} paths" + (f"; denied: {bad}" if bad else ""))
    return not bad


def main() -> None:
    plat = get_platform()
    root = paths.work_dir() / "aclexp" / stamp()
    a = trial(root / "s2a" / "taskA" / "t2", U2)
    ok = probe("1 slot-2 trial alone", a, U2)
    b = trial(root / "s2a" / "taskB" / "t2", U1)
    ok &= probe("2 after slot 1 starts a trial under the same arm folder", a, U2)
    for d in (b.work, b.home, b.gradle_home, b.claude_config, b.agent_out, b.root):
        plat.revoke(d, U1)
    plat.rmtree_robust(b.root)
    ok &= probe("3 after slot 1's trial is revoked and deleted", a, U2)
    c = trial(root / "plain" / "taskC" / "t2", U1)
    ok &= probe("4 after slot 1 starts a trial under another arm folder", a, U2)
    for d in (a.work, a.home, a.gradle_home, a.claude_config, a.agent_out, a.root, c.work, c.home, c.gradle_home,
              c.claude_config, c.agent_out, c.root):
        plat.revoke(d, U2 if str(d).startswith(str(a.root)) else U1)
    plat.rmtree_robust(root)
    print("all OK" if ok else "SOME FAILED")


if __name__ == "__main__":
    main()
