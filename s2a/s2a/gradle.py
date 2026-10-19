"""Gradle as the gates run it: commands rendered from profile templates and map.json fields (never an
agent-written string), JUnit XML parsed from the module's results directory, per-module baselines."""
from __future__ import annotations

import json
import re
import shutil
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

from s2a import gitutil
from s2a.context import Ctx

ASSERTION_TYPES = re.compile(r"AssertionError|AssertionFailedError|ComparisonFailure|AssertionFailure|"
                             r"MultipleFailuresError|TruthFailureSubject|AssertionsKt", re.I)


@dataclass
class TestResult:
    status: str            # passed | failed | error | skipped
    kind: str | None       # assertion | error | None
    message: str = ""


def parse_junit_dir(d: Path) -> dict[str, TestResult]:
    """`TEST-*.xml` -> {"pkg.Class.method": TestResult}."""
    out: dict[str, TestResult] = {}
    for f in sorted(d.glob("TEST-*.xml")) if d.exists() else []:
        try:
            root = ET.parse(f).getroot()
        except ET.ParseError:
            continue
        for tc in root.iter("testcase"):
            key = f"{tc.get('classname', '')}.{tc.get('name', '')}"
            fail, err, skip = tc.find("failure"), tc.find("error"), tc.find("skipped")
            if fail is not None or err is not None:
                el = fail if fail is not None else err
                typ = (el.get("type") or "") + " " + (el.get("message") or "")[:200]
                kind = "assertion" if (fail is not None and ASSERTION_TYPES.search(typ)) else "error"
                out[key] = TestResult("failed" if fail is not None else "error", kind, (el.get("message") or "")[:300])
            elif skip is not None:
                out[key] = TestResult("skipped", None)
            else:
                out[key] = TestResult("passed", None)
    return out


# ---------------------------------------------------------------------------- modules
def _map_module(ctx: Ctx, module: str) -> dict | None:
    for m in (ctx.map_json or {}).get("modules") or []:
        if m.get("path") == module:
            return m
    return None


def module_dir(ctx: Ctx, module: str, root: Path | None = None) -> Path:
    m = _map_module(ctx, module)
    rel = (m or {}).get("dir") or module.strip(":").replace(":", "/")
    return (root or ctx.repo) / rel


def module_of_path(ctx: Ctx, rel_path: str) -> str | None:
    """The Gradle project that owns a repository path (longest map.json dir prefix, else the path before /src/)."""
    rel = rel_path.replace("\\", "/")
    best = None
    for m in (ctx.map_json or {}).get("modules") or []:
        d = (m.get("dir") or "").strip("/")
        if d and (rel == d or rel.startswith(d + "/")) and (best is None or len(d) > len(best[1])):
            best = (m["path"], d)
    if best:
        return best[0]
    if "/src/" in rel:
        return ":" + rel.split("/src/", 1)[0].replace("/", ":")
    return None


def discover_tasks(ctx: Ctx, module: str) -> dict:
    """`gradlew <module>:tasks --all` once per module (cached in state): the unit-test, compile and lint
    task names. Used when the map is skipped or lacks the module (`--skip map` keeps every gate on)."""
    cache = ctx.state.stages.setdefault("_modules", {})
    if module in cache:
        return cache[module]
    d = ctx.profile.commands.defaults
    argv = ctx.plat.gradlew(ctx.repo) + flags(ctx) + [f"{module}:tasks", "--all"]
    r = run_logged(ctx, argv, f"tasks{module.replace(':', '_')}")
    names = set(re.findall(r"(?m)^(\w+)\s+-\s", r.stdout()))
    def pick(default: str, pattern: str) -> str | None:
        if default in names:
            return default
        cands = sorted(n for n in names if re.fullmatch(pattern, n))
        pref = [n for n in cands if "Debug" in n]
        return (pref or cands or [None])[0]
    info = {"task": pick(d.get("task", "testDebugUnitTest"), r"test\w*UnitTest") or ("test" if "test" in names else None),
            "compile_task": pick(d.get("compile_task", "compileDebugUnitTestSources"), r"compile\w*UnitTestSources")
            or ("testClasses" if "testClasses" in names else None),
            "lint_task": pick(d.get("lint_task", "lintDebug"), r"lint\w*") , "known": bool(names),
            "exit_code": r.exit_code}
    cache[module] = info
    ctx.save()
    return info


def module_tasks(ctx: Ctx, module: str) -> dict:
    m = _map_module(ctx, module)
    if m and m.get("unit_test_task"):
        d = ctx.profile.commands.defaults
        return {"task": m["unit_test_task"], "compile_task": m.get("compile_task") or d.get("compile_task"),
                "lint_task": m.get("lint_task") or d.get("lint_task"), "known": True}
    return discover_tasks(ctx, module)


# ---------------------------------------------------------------------------- running
def flags(ctx: Ctx) -> list[str]:
    c = ctx.profile.commands
    return c.common_flags.split() + ([c.offline_flag] if c.offline_flag else [])


def render(ctx: Ctx, template: str, **kw: str) -> list[str]:
    """Profile template -> argv. {gradlew} and {flags} expand to several tokens; the others to one each."""
    argv: list[str] = []
    for tok in template.split():
        if tok == "{gradlew}":
            argv += ctx.plat.gradlew(kw.get("root") or ctx.repo)  # type: ignore[arg-type]
        elif tok == "{flags}":
            argv += flags(ctx)
        else:
            argv.append(re.sub(r"\{(\w+)\}", lambda m: str(kw.get(m.group(1), m.group(0))), tok))
    return argv


def run_logged(ctx: Ctx, argv: list[str], label: str, *, cwd: Path | None = None):
    if ctx.gate_seq == 0 and (ctx.run_dir / "gates").exists():  # a resumed run continues the numbering
        ctx.gate_seq = max((int(p.name[:3]) for p in (ctx.run_dir / "gates").iterdir() if p.name[:3].isdigit()),
                           default=0)
    ctx.gate_seq += 1
    out = ctx.run_dir / "gates" / f"{ctx.gate_seq:03d}-{label}"
    r = ctx.plat.run(argv, cwd=cwd or ctx.repo, out_dir=out, timeout_s=ctx.pipeline.gate_timeout_s)
    (out / "argv.json").write_text(json.dumps({"argv": argv, "exit_code": r.exit_code, "seconds": r.duration_s,
                                               "timed_out": r.timed_out}), encoding="utf-8")
    return r


def junit_dir(ctx: Ctx, module: str, task: str, root: Path | None = None) -> Path:
    tpl = ctx.profile.commands.junit_results            # "{module_dir}/build/test-results/{task}/TEST-*.xml"
    rel = tpl.replace("{module_dir}/", "").replace("{task}", task)
    return module_dir(ctx, module, root) / Path(rel).parent


def run_tests(ctx: Ctx, module: str, *, tests: list[str] | None = None, label: str = "test",
              root: Path | None = None) -> tuple[object, dict[str, TestResult]]:
    """The module's unit tests, or only `tests` (classes `a.b.C` or methods `a.b.C.m`), with fresh JUnit XML."""
    mt = module_tasks(ctx, module)
    task = mt["task"]
    jd = junit_dir(ctx, module, task, root)
    shutil.rmtree(jd, ignore_errors=True)
    argv = render(ctx, ctx.profile.commands.test_module, module=module, task=task, root=root or ctx.repo)
    for t in tests or []:
        argv += ["--tests", t]
    r = run_logged(ctx, argv, f"{label}{module.replace(':', '_')}", cwd=root or ctx.repo)
    return r, parse_junit_dir(jd)


def compile_module(ctx: Ctx, module: str, label: str = "compile"):
    mt = module_tasks(ctx, module)
    argv = render(ctx, ctx.profile.commands.build, module=module, compile_task=mt["compile_task"])
    return run_logged(ctx, argv, f"{label}{module.replace(':', '_')}")


# ---------------------------------------------------------------------------- baselines
def baseline(ctx: Ctx, module: str) -> dict[str, str]:
    """{test id: status} of the module's unit tests at base_commit, cached in .s2a/baseline/<module>.json.
    Run in place while the tree has no production change yet (before implement), else in a git worktree
    of base_commit under .s2a/."""
    f = ctx.s2a_dir / "baseline" / f"{module.strip(':').replace(':', '_') or 'root'}.json"
    if f.exists():
        data = json.loads(f.read_text(encoding="utf-8"))
        if data.get("base_commit") == ctx.state.base_commit:
            return data["tests"]
    impl = ctx.state.stages.get("implement") or {}
    in_place = impl.get("status") in (None, "pending") and not (impl.get("task_status") or {})
    root = ctx.repo
    if not in_place:
        root = ctx.s2a_dir / "wt-base"
        if not root.exists():
            gitutil.git(ctx.repo, "worktree", "add", "--detach", str(root), ctx.state.base_commit)
    r, res = run_tests(ctx, module, label="baseline", root=root)
    data = {"base_commit": ctx.state.base_commit, "module": module, "exit_code": r.exit_code, "in_place": in_place,
            "tests": {k: v.status for k, v in res.items()}}
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return data["tests"]


def regressions(base: dict[str, str], now: dict[str, TestResult], *, full: bool = True) -> list[str]:
    """Tests that passed at baseline and do not pass now. On a full-module run (`full`) a test that
    passed at baseline and is missing from the results counts too (deleted or no longer compiled)."""
    out = [k for k, st in base.items() if st == "passed" and k in now and now[k].status in ("failed", "error")]
    if full and now:
        out += [k for k, st in base.items() if st == "passed" and k not in now]
    return sorted(set(out))
