"""Workspace invariants (phases/phase-1-environments.md step 7). Integration: needs warm caches and the
sandbox user (ABB_INTEGRATION=1); every access check is a REAL attempt made as abb-agent through the
launcher, never Test-Path."""
from __future__ import annotations

import os
import re
import zipfile
from pathlib import Path

import pytest

from abb import paths
from abb.config import load_repo, load_sandbox, load_task
from abb.harness.platform import get_platform
from abb.harness.workspace import Workspace
from abb.util import stamp

pytestmark = pytest.mark.skipif(not os.environ.get("ABB_INTEGRATION"), reason="integration: set ABB_INTEGRATION=1")
PLAT = get_platform()
USER = load_sandbox().modes["user"].run_as
REPO = "antennapod"


@pytest.fixture(scope="module")
def two_ws():
    if not PLAT.as_user_available(USER):
        pytest.skip("sandbox user missing: abb sandbox setup")
    repo = load_repo(REPO)
    base = paths.work_dir() / "itest" / stamp()
    a, b = Workspace(repo, base / "a", "user"), Workspace(repo, base / "b", "user")
    a.snapshot(repo.build.cache_commit)
    b.snapshot(repo.build.cache_commit)
    # b plays a FINISHED trial of the same sandbox user: the harness revokes it at trial end (D-037).
    # Concurrent trials run as different slot users (abb-agent2, Phase 8); see test_concurrent_slots.
    _as_agent(b, [str(PLAT.find_exe("git")), "status"], "touch")   # files now owned by the sandbox user
    (b.dirs.work / "agent-made.txt").write_text("x")
    b.revoke()
    yield a, b
    a.cleanup()
    b.cleanup()
    PLAT.rmtree_robust(base)


def _as_agent(ws: Workspace, argv: list[str], name: str):
    env = ws.agent_env(None, proxy=True)
    return ws.exec(argv, env=env, timeout_s=300, out_dir=ws.dirs.agent_out / name, as_agent=True)


def test_history_free_no_remotes(two_ws) -> None:
    a, _ = two_ws
    git = str(PLAT.find_exe("git"))
    r = _as_agent(a, [git, "log", "--all", "--oneline"], "gitlog")
    assert r.exit_code == 0, r.stderr()
    assert len(r.stdout().strip().splitlines()) == 1
    r = _as_agent(a, [git, "remote", "-v"], "gitremote")
    assert r.exit_code == 0 and r.stdout().strip() == ""


def test_denied_and_readonly_paths(two_ws) -> None:
    a, b = two_ws
    k = REPO
    items = [
        (paths.caches_dir() / "repos" / f"{k}.git", "read", "denied"),
        (paths.caches_dir() / "gradle-pristine" / k, "read", "denied"),
        (paths.results_dir(), "read", "denied"),
        (paths.repo_clone(), "read", "denied"),
        (b.dirs.work, "read", "denied"),                     # another (finished, revoked) trial's directory
        (b.dirs.work / "build.gradle", "read", "denied"),
        (b.dirs.root, "create", "denied"),
        (paths.caches_dir() / "gradle-ro" / k, "create", "denied"),
        (paths.caches_dir() / "gradle-ro" / k, "read", "ok"),
        (paths.abb_home(), "create", "denied"),
        (paths.work_dir(), "create", "denied"),
        (a.dirs.claude_config / "settings.json", "create", "denied"),   # open("xb") on an existing file
        (a.dirs.work, "create", "ok"),
        (a.dirs.root, "create", "denied"),                   # cannot create siblings of its own dirs
    ]
    got = PLAT.check_paths([(p, op) for p, op, _ in items], as_user=USER)
    bad = [(str(p), op, want, g) for (p, op, want), g in zip(items, got) if g != want and not
           (want == "denied" and g == "error:FileExistsError:17")]
    assert not bad, bad


def test_revoked_trial_files_owned_by_agent_stay_closed(two_ws) -> None:
    """A file the agent itself created in a revoked trial: no implicit owner rights (OWNER RIGHTS entry)."""
    a, b = two_ws
    py = str(PLAT.python())
    target = b.dirs.agent_out / "touch" / "stdout.txt"   # written by the launcher AS the sandbox user
    assert target.exists()
    code = ("import subprocess,sys; r = subprocess.run([r'C:\\Windows\\System32\\icacls.exe', sys.argv[1], '/grant', "
            "'abb-agent:F'], capture_output=True); print(r.returncode)")
    r = _as_agent(a, [py, "-I", "-c", code, str(target)], "takeover")
    assert r.stdout().strip() != "0", "the sandbox user could rewrite the DACL of a revoked trial's file"
    assert PLAT.check_paths([(target, "read")], as_user=USER) == ["denied"]


def test_concurrent_slots() -> None:
    """Two live trials of DIFFERENT slot users cannot see each other (needs abb-agent2: abb sandbox setup --slots 2)."""
    if not PLAT.as_user_available("abb-agent2"):
        pytest.skip("single slot: concurrent trials start in Phase 8 with abb-agent2 (D-037)")
    pytest.fail("slot-2 isolation test is written with Phase 8's --slots support")


def test_settings_json_not_writable(two_ws) -> None:
    a, _ = two_ws
    py = str(PLAT.python())
    code = f"open(r'{a.dirs.claude_config / 'settings.json'}', 'ab').write(b' ')"
    r = _as_agent(a, [py, "-I", "-c", code], "settings-write")
    assert r.exit_code != 0 and "PermissionError" in r.stderr()


def test_snapshot_contents(two_ws) -> None:
    a, _ = two_ws
    w = a.dirs.work
    assert not (w / ".claude" / "settings.json").exists() and not (w / ".claude" / "hooks").exists()
    assert not (w / ".mcp.json").exists()
    assert (w / "CLAUDE.md").exists() and (w / "AGENTS.md").exists()   # instructions kept (D-004)
    assert not list(a.dirs.gradle_home.glob("daemon")) and not list(a.dirs.gradle_home.rglob("build-cache-1"))
    assert (a.dirs.gradle_home / "init.d" / "abb.gradle").exists()
    assert list((a.dirs.gradle_home / "wrapper" / "dists").iterdir())


def test_bytes_identical_to_mirror(two_ws) -> None:
    a, _ = two_ws
    repo = load_repo(REPO)
    mirror = paths.caches_dir() / "repos" / f"{REPO}.git"
    from abb.harness.platform import run_capture

    sample = ["gradlew.bat", "build.gradle", "parser/feed/src/main/java/de/danoeh/antennapod/parser/feed/util/DurationParser.java"]
    for rel in sample:
        r = run_capture(PLAT, ["git", "show", f"{repo.build.cache_commit}:{rel}"], cwd=mirror, timeout_s=60)
        assert r.stdout_path.read_bytes() == (a.dirs.work / rel).read_bytes(), rel


def test_registry_hkcu_write_fails(two_ws) -> None:
    a, _ = two_ws
    reg = str(Path(PLAT.system_env()["SystemRoot"]) / "System32" / "reg.exe")
    r = _as_agent(a, [reg, "add", r"HKCU\Software\abb", "/f"], "reg")
    assert r.exit_code != 0


def test_profile_unchanged_by_agent_activity(two_ws) -> None:
    from abb.harness.sandbox import _profile_hash

    a, _ = two_ws
    before = _profile_hash(USER)
    _as_agent(a, [str(paths.tools_dir() / "pwsh" / "pwsh.exe"), "-NoProfile", "-Command", "New-Item -Force $env:TEMP\\x.txt"], "pwsh")
    _as_agent(a, [str(PLAT.find_exe("git")), "status"], "gitstatus")
    assert _profile_hash(USER) == before


def _gold_added_classes() -> set[str]:
    names: set[str] = set()
    for p in sorted(paths.tasks_dir().glob("*/task.yaml")):
        if p.parent.name.startswith("_"):
            continue
        t = load_task(p.parent.name)
        gp = p.parent / (t.gold_patch or "gold.patch")
        if not gp.exists():
            continue
        for ln in gp.read_text(encoding="utf-8", errors="replace").splitlines():
            if ln.startswith("+") and not ln.startswith("+++"):
                names |= set(re.findall(r"\b(?:class|interface|object|enum)\s+([A-Z]\w+)", ln))
    return names


def test_caches_hold_no_gold_classes() -> None:
    names = _gold_added_classes()
    if not names:
        pytest.skip("no task's gold.patch adds a class (the seed changes one line)")
    hits = []
    for root in (paths.caches_dir() / "gradle-ro", paths.caches_dir() / "robolectric"):
        for jar in root.rglob("*.jar"):
            try:
                with zipfile.ZipFile(jar) as z:
                    for n in z.namelist():
                        if any(n.endswith(f"/{c}.class") for c in names):
                            hits.append(f"{jar}:{n}")
            except zipfile.BadZipFile:
                continue
    assert not hits, hits[:10]
