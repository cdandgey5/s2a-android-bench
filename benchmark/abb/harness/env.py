"""`abb env warm|fingerprint|prune` (specs/environments.md §3): per-repo warm caches replace "the image".

warm: mirror -> scratch snapshot at cache_commit (+ every task base and setup_commit) -> run the
repo's warm_commands with a scratch GRADLE_USER_HOME and user.home -> split into
  caches/gradle-ro/<repo>/modules-2       read-only dependency cache (no *.lock, no gc.properties)
  caches/robolectric/<repo>/              flat android-all-instrumented jars
  caches/gradle-pristine/<repo>/          the whole Gradle home + init.d/abb.gradle, minus daemon/ (harness only)
-> fingerprint into benchmark/env.lock.json (and a copy at ABB_HOME/env.lock.json).
"""
from __future__ import annotations

import hashlib
import json
import shutil
import time
from pathlib import Path

from abb import paths
from abb.config import RepoConfig, load_repo, load_toolchain
from abb.harness import gradle
from abb.harness.platform import get_platform
from abb.harness.repos import ensure_mirror, extract_commit
from abb.harness.tools import load_lock
from abb.log import get_logger
from abb.util import sha256_file, stamp, utcnow_iso

log = get_logger("abb.env")


class WarmError(RuntimeError):
    pass


def lock_file() -> Path:
    return paths.benchmark_dir() / "env.lock.json"


def load_env_lock() -> dict:
    p = lock_file()
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def gradle_ro(repo: RepoConfig) -> Path:
    return paths.caches_dir() / "gradle-ro" / repo.key


def gradle_pristine(repo: RepoConfig) -> Path:
    return paths.caches_dir() / "gradle-pristine" / repo.key


def task_base_commits(repo: RepoConfig) -> list[str]:
    from abb.config import load_task

    out = []
    for p in sorted(paths.tasks_dir().glob("*/task.yaml")):
        if p.parent.name.startswith("_"):
            continue
        t = load_task(p.parent.name)
        if t.repo == repo.key and t.status != "dropped" and len(t.base_commit) == 40:
            out.append(t.base_commit)
    return out


def tree_hash(root: Path, pattern: str = "**/*") -> str:
    """sha256 over (relative path, file sha256) of every file: the content identity of a cache dir."""
    h = hashlib.sha256()
    for f in sorted(p for p in root.glob(pattern) if p.is_file()):
        h.update(f.relative_to(root).as_posix().encode())
        h.update(b"\0")
        h.update(sha256_file(f).encode())
        h.update(b"\n")
    return h.hexdigest()


def _replace_dir(new: Path, final: Path) -> None:
    plat = get_platform()
    if final.exists():
        old = final.with_name(final.name + f".old-{stamp()}")
        final.rename(old)
        left = plat.rmtree_robust(old)
        if left:
            log.warning("could not delete %s (%d leftovers)", old, len(left))
    final.parent.mkdir(parents=True, exist_ok=True)
    new.rename(final)


# D-044: test tasks run but match nothing, so every variant's classpaths resolve and compile
NO_TESTS_INIT = """// written by abb env warm (no_test_execution): resolve and compile, run no test
allprojects {
    tasks.withType(Test).configureEach {
        filter { includeTestsMatching "abb.warm.NoSuchTest"; failOnNoMatchingTests = false }
    }
}
"""


def _run_warm_commands(repo: RepoConfig, src: Path, guh: Path, home: Path, logs: Path, label: str) -> list[dict]:
    env = gradle.harness_gradle_env(repo, guh=guh, home=home)
    mem = 10240
    results = []
    for i, wc in enumerate(repo.build.warm_commands):
        argv = gradle.expand_cmd(wc.cmd, src)
        if wc.no_test_execution:
            init = logs / "abb-warm-no-tests.gradle"
            init.write_text(NO_TESTS_INIT, encoding="utf-8", newline="\n")
            argv = argv[:1] + ["--init-script", str(init)] + argv[1:]
        out = logs / f"{label}-{i}"
        log.info("[%s] %s", label, " ".join(argv[1:]))
        r = gradle.run(argv, src=src, env=env, out_dir=out, memory_mb=mem)
        rec = {"cmd": wc.cmd, "exit_code": r.exit_code, "duration_s": r.duration_s, "peak_memory_mb": r.peak_memory_mb,
               "job_memory_hit": r.job_memory_hit, "allow_failure": wc.allow_failure, "log": str(out)}
        results.append(rec)
        log.info("[%s] exit %s in %.0fs (peak %s MB)", label, r.exit_code, r.duration_s, r.peak_memory_mb)
        if r.exit_code != 0 and not wc.allow_failure:
            raise WarmError(f"{wc.cmd} failed at {label} (exit {r.exit_code}); log {out}")
    gradle.run(gradle.expand_cmd("{gradlew} --stop", src), src=src, env=env, out_dir=logs / f"{label}-stop", timeout_s=300)
    return results


def warm(key: str, extra_commits: list[str] | None = None, keep_scratch: bool = False, include_tasks: bool = True) -> dict:
    repo = load_repo(key)
    plat = get_platform()
    mirror = ensure_mirror(repo, fetch=True)
    commits = [repo.build.cache_commit]
    from_tasks = task_base_commits(repo) + [repo.build.setup_commit] if include_tasks else []
    for c in from_tasks + list(extra_commits or []):
        if c not in commits:
            commits.append(c)
    scratch = paths.work_dir() / "warm" / repo.key / stamp()
    guh, home, logs = scratch / "gradle-home", scratch / "home", scratch / "logs"
    gradle.write_gradle_home(repo, guh, with_init=False)  # warming must download Robolectric jars
    home.mkdir(parents=True)
    t0 = time.monotonic()
    runs, wrappers = [], {}
    for n, c in enumerate(commits):
        src = scratch / f"src-{n}"
        extract_commit(repo, c, src)
        wrappers[c] = gradle.wrapper_version(src)  # several versions share one cache (D-046; verify checks each)
        runs.append({"commit": c, "results": _run_warm_commands(repo, src, guh, home, logs, f"c{n}-{c[:8]}")})
        left = plat.rmtree_robust(src)
        if left:
            log.warning("scratch checkout leftovers: %d", len(left))
    # ---- split
    staging = paths.caches_dir() / "_staging" / f"{repo.key}-{stamp()}"
    ro_new = staging / "gradle-ro"
    (ro_new / "modules-2").parent.mkdir(parents=True, exist_ok=True)
    src_m2 = guh / "caches" / "modules-2"
    if not src_m2.exists():
        raise WarmError(f"{src_m2} missing: the warm resolved nothing")
    shutil.copytree(src_m2, ro_new / "modules-2", ignore=shutil.ignore_patterns("*.lock", "gc.properties"))
    robo_new = staging / "robolectric"
    robo_new.mkdir(parents=True)
    robo_src = home / ".m2" / "repository" / "org" / "robolectric" / "android-all-instrumented"
    jars = sorted(robo_src.glob("**/*.jar")) if robo_src.exists() else []
    for j in jars:
        shutil.copy2(j, robo_new / j.name)
    pristine_new = staging / "gradle-pristine"
    shutil.copytree(guh, pristine_new, ignore=shutil.ignore_patterns("daemon"))
    gradle.write_gradle_home(repo, pristine_new, with_init=True)
    _replace_dir(ro_new, gradle_ro(repo))
    _replace_dir(robo_new, gradle.robolectric_dir(repo))
    _replace_dir(pristine_new, gradle_pristine(repo))
    plat.rmtree_robust(staging)
    # D-043: the replacements carry staging's ACLs; take the new parents' (incl. the pristine deny)
    # and give the sandbox user its read grants back (abb sandbox setup set them on the old dirs)
    from abb.harness import sandbox

    for d in (gradle_ro(repo), gradle.robolectric_dir(repo), gradle_pristine(repo)):
        plat.inherit_acl(d)
    granted = sandbox.apply_cache_grants([repo.key])
    log.info("sandbox read grants re-applied: %s", granted)
    rec = fingerprint(repo, commits=commits, wrapper=",".join(sorted(set(wrappers.values()))))
    rec.update({"warm_runs": runs, "warm_minutes": round((time.monotonic() - t0) / 60, 1), "robolectric_jars": [j.name for j in jars],
                "mirror": str(mirror), "scratch": str(scratch)})
    lock = load_env_lock()
    lock[repo.key] = rec
    lock_file().write_text(json.dumps(lock, indent=2) + "\n", encoding="utf-8", newline="\n")
    shutil.copyfile(lock_file(), paths.abb_home() / "env.lock.json")
    if not keep_scratch:
        left = plat.rmtree_robust(scratch / "gradle-home")
        if left:
            log.warning("scratch Gradle home leftovers: %d", len(left))
    return rec


def fingerprint(repo: RepoConfig, *, commits: list[str], wrapper: str) -> dict:
    tl = load_lock()
    tc = load_toolchain()
    parts = {
        "jdk_release_names": {k: tl[k]["release_name"] for k in sorted(tl) if k.startswith("jdk")},
        "sdk_packages": tl.get("android", {}).get("installed", {}),
        "cache_commit": repo.build.cache_commit,
        "warm_commits": sorted(commits),
        "gradle_wrapper": wrapper,
        "gradle_user_home_props": gradle.render_props(repo),
        "claude_code_version": tc.claude_code.version,
        "platform": get_platform().id,
        "modules2_hash": tree_hash(gradle_ro(repo) / "modules-2"),
        "robolectric_hash": tree_hash(gradle.robolectric_dir(repo)),
    }
    fp = "sha256:" + hashlib.sha256(json.dumps(parts, sort_keys=True).encode()).hexdigest()
    return {"fingerprint": fp, "parts": parts, "built_at": utcnow_iso(), "cache_commit": repo.build.cache_commit,
            "setup_commit": repo.build.setup_commit, "warm_commits": commits, "jdk": repo.toolchain.jdk}


def current_fingerprint(key: str) -> dict:
    repo = load_repo(key)
    rec = load_env_lock().get(key)
    if not rec:
        raise WarmError(f"{key}: not warmed (abb env warm {key})")
    now = fingerprint(repo, commits=rec["warm_commits"], wrapper=rec["parts"]["gradle_wrapper"])
    return {"locked": rec["fingerprint"], "current": now["fingerprint"], "match": now["fingerprint"] == rec["fingerprint"],
            "sizes_gb": cache_sizes(repo)}


def _size_gb(p: Path) -> float:
    return round(sum(f.stat().st_size for f in p.rglob("*") if f.is_file()) / 1e9, 2) if p.exists() else 0.0


def cache_sizes(repo: RepoConfig) -> dict:
    return {"gradle-ro": _size_gb(gradle_ro(repo)), "robolectric": _size_gb(gradle.robolectric_dir(repo)),
            "gradle-pristine": _size_gb(gradle_pristine(repo)),
            "mirror": _size_gb(paths.caches_dir() / "repos" / f"{repo.key}.git")}
