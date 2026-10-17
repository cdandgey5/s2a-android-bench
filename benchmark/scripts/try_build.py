"""Repo-selection experiment (phases/phase-0-foundations.md step 6).

    uv run python scripts/try_build.py <repo_url> <ref> <jdk> [--key K]
        [--lib-module :m --lib-task t] [--app-module :app --app-task t]

Works in ABB_HOME/work/experiments/<key>/ (src/, gradle-home/, home/) with the installed JDK, a
scratch GRADLE_USER_HOME and JAVA_TOOL_OPTIONS=-Duser.home=<exp>/home, every process through the
platform layer inside an 8 GB Job Object. Without module arguments: `gradlew.bat tasks --all` and
the *UnitTest task names. With them: cold / warm (offline, cleanTest) / warm-clean (offline,
`clean` first, i.e. what a fresh workspace recompiles) timings, peak job memory, JUnit counts, plus
LOC, Robolectric usage, SDK levels, case collisions, longest path and the linked-PR count.
Results accumulate in <exp>/results.json.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import xml.etree.ElementTree as ET
from datetime import date, timedelta
from pathlib import Path

from abb import paths
from abb.config import load_repo
from abb.harness.platform import ProcSpec, get_platform, run_capture
from abb.util import utcnow_iso

PLAT = get_platform()
SKIP_DIRS = {"build", ".gradle", ".git", ".idea", "node_modules"}


def log(msg: str) -> None:
    print(f"{utcnow_iso()} {msg}", flush=True)


def git(args: list[str], cwd: Path, timeout_s: int = 3600) -> str:
    r = run_capture(PLAT, ["git", *args], cwd=cwd, timeout_s=timeout_s)
    if r.exit_code != 0:
        raise SystemExit(f"git {' '.join(args)} failed: {r.stderr()[-1500:]}")
    return r.stdout()


def gradle_env(exp: Path, jdk: int) -> dict[str, str]:
    jh = paths.tools_dir() / f"jdk{jdk}"
    return PLAT.harness_env({
        "JAVA_HOME": str(jh),
        "ANDROID_HOME": str(paths.tools_dir() / "android-sdk"),
        "ANDROID_SDK_ROOT": str(paths.tools_dir() / "android-sdk"),
        "GRADLE_USER_HOME": str(exp / "gradle-home"),
        "JAVA_TOOL_OPTIONS": f"-Duser.home={exp / 'home'} -Dfile.encoding=UTF-8",
        "ANDROID_USER_HOME": str(exp / "home" / ".android"),
        "PATH": str(jh / "bin") + os.pathsep + PLAT.harness_env().get("PATH", ""),
    })


def gradle(exp: Path, src: Path, jdk: int, args: list[str], label: str, timeout_s: int = 7200) -> dict:
    out = exp / "logs" / f"{time.strftime('%Y%m%d-%H%M%S')}-{label}"
    out.mkdir(parents=True, exist_ok=True)
    argv = PLAT.gradlew(src) + ["--console=plain", "--no-daemon", *args]
    log(f"[{label}] {' '.join(argv[1:])}")
    spec = ProcSpec(argv=argv, cwd=src, env=gradle_env(exp, jdk), stdin_text=None, timeout_s=timeout_s,
                    memory_mb=8192, as_user=None, out_dir=out)
    r = PLAT.wait(PLAT.run(spec))
    text = r.stdout() + "\n" + r.stderr()
    res = {"label": label, "args": args, "exit_code": r.exit_code, "duration_s": r.duration_s,
           "peak_memory_mb": r.peak_memory_mb, "job_memory_hit": r.job_memory_hit,
           "stopped_by_harness": r.stopped_by_harness, "log": str(out),
           "build_successful": "BUILD SUCCESSFUL" in text,
           "could_not_resolve": len(re.findall(r"Could not resolve", text)),
           "downloads": len(re.findall(r"^Download ", text, flags=re.M))}
    m = re.search(r"BUILD (SUCCESSFUL|FAILED) in (.+)", text)
    res["gradle_reported"] = m.group(0) if m else None
    log(f"[{label}] exit {r.exit_code} in {r.duration_s:.0f}s, peak {r.peak_memory_mb} MB, {res['gradle_reported']}")
    return res


def module_dir(src: Path, module: str) -> Path:
    return src.joinpath(*[p for p in module.split(":") if p])


def junit_counts(src: Path, module: str, task: str) -> dict:
    d = module_dir(src, module) / "build" / "test-results" / task
    c = {"files": 0, "tests": 0, "failures": 0, "errors": 0, "skipped": 0, "dir": str(d), "failed_tests": []}
    for f in sorted(d.glob("TEST-*.xml")):
        c["files"] += 1
        root = ET.parse(f).getroot()
        for k in ("tests", "failures", "errors", "skipped"):
            c[k] += int(root.get(k, 0))
        for tc in root.iter("testcase"):
            if tc.find("failure") is not None or tc.find("error") is not None:
                c["failed_tests"].append(f"{tc.get('classname')}.{tc.get('name')}")
    c["failed_tests"] = c["failed_tests"][:50]
    return c


def walk_sources(src: Path):
    for dirpath, dirnames, filenames in os.walk(src):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            yield Path(dirpath) / fn


def static_facts(src: Path, repo_url: str) -> dict:
    loc = {"java": 0, "kotlin": 0}
    test_loc = 0
    robo_files: list[str] = []
    sdk_levels: set[str] = set()
    modules_with_tests: set[str] = set()
    compile_sdk: set[str] = set()
    for p in walk_sources(src):
        suf = p.suffix
        rel = p.relative_to(src).as_posix()
        if suf in (".java", ".kt"):
            try:
                text = p.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            n = text.count("\n")
            loc["java" if suf == ".java" else "kotlin"] += n
            if "/src/test/" in rel:
                test_loc += n
                modules_with_tests.add(rel.split("/src/test/")[0])
                if "robolectric" in text.lower():
                    robo_files.append(rel)
                for m in re.finditer(r"@Config\s*\(([^)]*)\)", text):
                    for s in re.findall(r"sdk\s*=\s*\[?\{?\s*([0-9A-Za-z_., ]+)", m.group(1)):
                        sdk_levels.add(s.strip())
        elif p.name in ("build.gradle", "build.gradle.kts", "libs.versions.toml") or p.suffix in (".gradle", ".kts"):
            text = p.read_text(encoding="utf-8", errors="replace")
            for m in re.finditer(r"compileSdk(?:Version)?\s*[=(]?\s*([0-9A-Za-z_.\"']+)", text):
                compile_sdk.add(m.group(1).strip("\"'"))
            for m in re.finditer(r'^\s*compileSdk\w*\s*=\s*"?(\d+)"?', text, flags=re.M):
                compile_sdk.add(m.group(1))
        elif p.name == "robolectric.properties":
            sdk_levels.add("properties:" + p.read_text(encoding="utf-8", errors="replace").strip().replace("\n", "; "))
    files = git(["ls-files", "-z"], src).split("\0")
    files = [f for f in files if f]
    longest = max(files, key=len)
    folded: dict[str, list[str]] = {}
    for f in files:
        folded.setdefault(f.casefold(), []).append(f)
    collisions = [v for v in folded.values() if len(v) > 1]
    jdk_hints = {}
    jv = src / ".java-version"
    if jv.exists():
        jdk_hints[".java-version"] = jv.read_text(encoding="utf-8").strip()
    for wf in sorted((src / ".github" / "workflows").glob("*.y*ml")):
        t = wf.read_text(encoding="utf-8", errors="replace")
        jv_ = sorted(set(re.findall(r"java-version:\s*['\"]?(\d+)", t)))
        if jv_:
            jdk_hints[f"workflows/{wf.name}"] = jv_
        tasks_ = sorted(set(re.findall(r"\b(\w*[Tt]est\w*UnitTest|testDebugUnitTest|test\w+UnitTest)\b", t)))
        if tasks_:
            jdk_hints[f"workflows/{wf.name}:test_tasks"] = tasks_
    for bf in list(src.glob("*.gradle*")) + list(src.glob("**/build.gradle*")):
        if not bf.is_file() or "build" in bf.relative_to(src).parts[:-1]:
            continue
        t = bf.read_text(encoding="utf-8", errors="replace")
        for m in re.finditer(r"(jvmToolchain\s*\(\s*\d+\s*\)|JavaVersion\.VERSION_\w+|jvmTarget\s*=\s*\S+)", t):
            jdk_hints.setdefault("build_files", set()).add(m.group(1))
    if "build_files" in jdk_hints:
        jdk_hints["build_files"] = sorted(jdk_hints["build_files"])
    secrets = [f for f in files if re.search(r"google-services\.json|\.keystore$|\.jks$|secrets?\.properties|local\.properties", f)]
    return {
        "loc": loc, "loc_total": loc["java"] + loc["kotlin"], "test_loc": test_loc,
        "modules_with_unit_tests": sorted(modules_with_tests),
        "robolectric_test_files": len(robo_files), "robolectric_sdk_config": sorted(sdk_levels),
        "compile_sdk": sorted(compile_sdk), "tracked_files": len(files),
        "longest_path": {"len": len(longest), "path": longest}, "case_collisions": collisions,
        "jdk_hints": jdk_hints, "secret_like_files": secrets,
    }


def linked_pr_count(repo_url: str) -> dict:
    owner_repo = repo_url.rstrip("/").removeprefix("https://github.com/").removesuffix(".git")
    since = (date.today() - timedelta(days=730)).isoformat()
    r = run_capture(PLAT, ["gh", "pr", "list", "-R", owner_repo, "--state", "merged", "--search",
                           f"fixes OR closes OR resolves merged:>={since}", "--limit", "500", "--json", "number"],
                    cwd=paths.abb_home(), timeout_s=300)
    if r.exit_code != 0:
        return {"error": r.stderr()[-500:]}
    return {"since": since, "count": len(json.loads(r.stdout())), "limit": 500}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("repo_url")
    ap.add_argument("ref")
    ap.add_argument("jdk", type=int)
    ap.add_argument("--key")
    ap.add_argument("--lib-module")
    ap.add_argument("--lib-task")
    ap.add_argument("--app-module")
    ap.add_argument("--app-task")
    ap.add_argument("--skip-cold", action="store_true")
    a = ap.parse_args()
    key = a.key or a.repo_url.rstrip("/").split("/")[-1].lower()
    exp = paths.work_dir() / "experiments" / key
    src = exp / "src"
    for d in (exp / "gradle-home", exp / "home" / ".android"):
        d.mkdir(parents=True, exist_ok=True)
    try:
        props = load_repo(key).toolchain.gradle_user_home_props
    except FileNotFoundError:
        props = ""
    (exp / "gradle-home" / "gradle.properties").write_text(
        "\n".join(ln.split("#")[0].rstrip() for ln in props.splitlines() if ln.split("#")[0].strip()) + "\n",
        encoding="utf-8")
    if not (src / ".git").exists():
        log(f"cloning {a.repo_url}")
        git(["clone", "--no-checkout", a.repo_url, str(src)], exp)
    git(["fetch", "origin", "--prune"], src)
    sha = git(["rev-parse", f"origin/{a.ref}" if not re.fullmatch(r"[0-9a-f]{40}", a.ref) else a.ref], src).strip()
    git(["checkout", "-q", "--force", sha], src)
    git(["submodule", "deinit", "--all", "-f"], src) if (src / ".gitmodules").exists() else None
    head_branch = git(["symbolic-ref", "refs/remotes/origin/HEAD"], src).strip().rsplit("/", 1)[-1]
    rf = exp / "results.json"
    results = json.loads(rf.read_text(encoding="utf-8")) if rf.exists() else {"runs": []}
    results.update({"repo_url": a.repo_url, "key": key, "ref": a.ref, "commit": sha, "default_branch": head_branch,
                    "jdk": a.jdk, "updated_at": utcnow_iso()})
    if not a.lib_module and not a.app_module:
        r = gradle(exp, src, a.jdk, ["tasks", "--all"], "tasks-all")
        text = (Path(r["log"]) / "stdout.txt").read_text(encoding="utf-8", errors="replace")
        names = sorted(set(re.findall(r"^(\S*?(?:[Tt]est\w*UnitTest))\b", text, flags=re.M)))
        r["unit_test_tasks"] = names
        results["tasks_all"] = r
        results["static"] = static_facts(src, a.repo_url)
        results["linked_prs"] = linked_pr_count(a.repo_url)
        print(json.dumps({"unit_test_tasks": names, **{k: results["static"][k] for k in
                          ("loc_total", "modules_with_unit_tests", "compile_sdk", "longest_path", "case_collisions")}},
                         indent=2))
    else:
        for role, mod, task in (("lib", a.lib_module, a.lib_task), ("app", a.app_module, a.app_task)):
            if not mod:
                continue
            run = {"role": role, "module": mod, "task": task, "at": utcnow_iso()}
            if not a.skip_cold:
                run["cold"] = gradle(exp, src, a.jdk, ["--continue", f"{mod}:{task}"], f"{role}-cold")
                run["cold"]["junit"] = junit_counts(src, mod, task)
            run["warm"] = gradle(exp, src, a.jdk, ["--offline", "--continue", f"{mod}:cleanTest", f"{mod}:{task}"],
                                 f"{role}-warm")
            run["warm"]["junit"] = junit_counts(src, mod, task)
            run["warm_clean"] = gradle(exp, src, a.jdk, ["--offline", "--continue", "clean", f"{mod}:{task}"],
                                       f"{role}-warm-clean")
            run["warm_clean"]["junit"] = junit_counts(src, mod, task)
            results["runs"].append(run)
            rf.write_text(json.dumps(results, indent=2), encoding="utf-8")
    rf.write_text(json.dumps(results, indent=2), encoding="utf-8")
    log(f"results: {rf}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
