"""Bare mirrors and `abb repos check <repo>` (the strict check; the schema accepts TODO_* placeholders).

The mirror lives at ABB_HOME/caches/repos/<repo>.git (denied to the sandbox user from Phase 1 on);
`ensure_mirror` creates it with `git clone --mirror` and Phase 1's `abb env warm` reuses it.
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

from abb import paths
from abb.config import RepoConfig, is_real_sha, load_repo, load_toolchain
from abb.harness.platform import get_platform, run_capture
from abb.log import get_logger

log = get_logger("abb.repos")
MAX_PATH_CHARS = 200


def mirror_path(repo: RepoConfig) -> Path:
    return paths.caches_dir() / "repos" / f"{repo.key}.git"


def git(args: list[str], cwd: Path, timeout_s: int = 3600, check: bool = True) -> str:
    r = run_capture(get_platform(), ["git", *args], cwd=cwd, timeout_s=timeout_s)
    if check and r.exit_code != 0:
        raise RuntimeError(f"git {' '.join(args)} failed ({r.exit_code}): {r.stderr()[-1500:]}")
    return r.stdout()


def ensure_mirror(repo: RepoConfig, *, fetch: bool = False) -> Path:
    m = mirror_path(repo)
    if not (m / "HEAD").exists():
        m.parent.mkdir(parents=True, exist_ok=True)
        log.info("cloning mirror %s -> %s", repo.url, m)
        git(["clone", "--mirror", repo.url, str(m)], m.parent)
    elif fetch:
        git(["remote", "update", "--prune"], m)
    return m


def _todo_strings(obj, where: str = "") -> list[str]:
    out: list[str] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            out += _todo_strings(v, f"{where}.{k}" if where else str(k))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            out += _todo_strings(v, f"{where}[{i}]")
    elif isinstance(obj, str) and "TODO" in obj:
        out.append(f"{where}={obj!r}")
    return out


def check(key: str) -> list[tuple[str, bool, str]]:
    rows: list[tuple[str, bool, str]] = []

    def row(name: str, ok: bool, detail: str) -> None:
        rows.append((name, ok, detail))

    raw = yaml.safe_load((paths.repos_config_dir() / f"{key}.yaml").read_text(encoding="utf-8"))
    repo = load_repo(key)
    row("schema", True, f"repos/{key}.yaml loads (extra=forbid)")
    todos = _todo_strings(raw)
    row("no TODO values", not todos, ", ".join(todos) or "none")
    for f in ("cache_commit", "setup_commit"):
        v = getattr(repo.build, f)
        row(f"{f} is a SHA", is_real_sha(v), v)
    tc = load_toolchain()
    row("jdk pinned", repo.toolchain.jdk in tc.jdk.majors, f"jdk {repo.toolchain.jdk}; toolchain majors {tc.jdk.majors}")
    missing_pkgs = [p for p in repo.toolchain.android.packages if p not in tc.android.packages]
    row("sdk packages pinned", not missing_pkgs, f"not in toolchain.yaml: {missing_pkgs}" if missing_pkgs else "all in toolchain.yaml")
    t = repo.tests
    row("test tasks named", "default" in t.test_task_for_module and all(v and "TODO" not in v for v in t.test_task_for_module.values()),
        str(t.test_task_for_module))
    row("verify_modules", len(t.verify_modules) >= 1 and all(m.startswith(":") and "TODO" not in m for m in t.verify_modules),
        str(t.verify_modules))
    row("warm commands", bool(repo.build.warm_commands) and all("{gradlew}" in w.cmd for w in repo.build.warm_commands),
        "; ".join(w.cmd for w in repo.build.warm_commands))
    if not all(is_real_sha(getattr(repo.build, f)) for f in ("cache_commit", "setup_commit")):
        return rows
    m = ensure_mirror(repo)
    head = git(["symbolic-ref", "HEAD"], m).strip().removeprefix("refs/heads/")
    row("default branch", head == repo.default_branch, f"mirror HEAD {head}; config {repo.default_branch}")
    for f in ("cache_commit", "setup_commit"):
        sha = getattr(repo.build, f)
        r = run_capture(get_platform(), ["git", "cat-file", "-e", f"{sha}^{{commit}}"], cwd=m, timeout_s=60)
        if r.exit_code != 0:
            git(["fetch", "origin", sha], m, check=False)
            r = run_capture(get_platform(), ["git", "cat-file", "-e", f"{sha}^{{commit}}"], cwd=m, timeout_s=60)
        row(f"{f} exists upstream", r.exit_code == 0, sha)
    files = [f for f in git(["ls-tree", "-r", "--name-only", "-z", repo.build.cache_commit], m).split("\0") if f]
    folded: dict[str, list[str]] = {}
    for f in files:
        folded.setdefault(f.casefold(), []).append(f)
    coll = [v for v in folded.values() if len(v) > 1]
    row("no case collisions", not coll, f"{len(files)} files; collisions: {coll[:5] or 'none'}")
    longest = max(files, key=len)
    row(f"paths < {MAX_PATH_CHARS} chars", len(longest) < MAX_PATH_CHARS, f"longest {len(longest)}: {longest}")
    links = [ln.split("\t", 1)[1] for ln in git(["ls-tree", "-r", repo.build.cache_commit], m).splitlines()
             if ln.startswith("120000 ")]
    row("symlinks (checked out as files)", True, f"{len(links)}: {links[:5]}" if links else "none")
    tree = set(files)
    for mod in t.verify_modules:
        d = "/".join(p for p in mod.split(":") if p)
        has = any(f.startswith(d + "/src/test/") for f in tree)
        row(f"{mod} has unit tests", has, f"{d}/src/test/ at cache_commit")
    wrapper = git(["show", f"{repo.build.cache_commit}:gradle/wrapper/gradle-wrapper.properties"], m)
    mm = re.search(r"distributionUrl=.*gradle-([0-9.]+)-", wrapper)
    row("gradle wrapper", bool(mm), mm.group(1) if mm else "no wrapper")
    return rows


def check_cli(key: str) -> int:
    try:
        rows = check(key)
    except FileNotFoundError as e:
        print(f"ERROR: {e}")
        return 1
    for name, ok, detail in rows:
        print(f"{'OK  ' if ok else 'FAIL'} {name:<28} {detail}")
    return 0 if all(ok for _, ok, _ in rows) else 1


def extract_commit(repo: RepoConfig, commit: str, dest: Path, *, exclude: list[str] | None = None) -> list[str]:
    """`git archive <commit>` from the mirror into an empty `dest` (no .git), as bytes: no CRLF conversion.

    Symlinks (git mode 120000) become plain files holding the link target, exactly what Git for
    Windows checks out with its default core.symlinks=false (e.g. Wikipedia's values-zh-rHK).
    Returns the materialized symlink paths.
    """
    import tarfile
    import tempfile

    m = ensure_mirror(repo)
    dest.mkdir(parents=True, exist_ok=False)
    out = Path(tempfile.mkdtemp(prefix="abb-archive-"))
    r = run_capture(get_platform(), ["git", "archive", "--format=tar", commit], cwd=m, timeout_s=1800, out_dir=out)
    if r.exit_code != 0:
        raise RuntimeError(f"git archive {commit} failed: {r.stderr()[-1000:]}")
    excl = [e.strip("/") for e in (exclude or [])]
    links: list[str] = []
    with tarfile.open(r.stdout_path) as tf:
        members = [mm for mm in tf.getmembers()
                   if not any(mm.name == e or mm.name.startswith(e + "/") for e in excl)]
        regular = [mm for mm in members if not (mm.issym() or mm.islnk())]
        tf.extractall(dest, members=regular, filter="data")
        for mm in members:
            if mm.issym() or mm.islnk():
                target = dest / mm.name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(mm.linkname.encode("utf-8"))
                links.append(mm.name)
    get_platform().rmtree_robust(out)
    return links
