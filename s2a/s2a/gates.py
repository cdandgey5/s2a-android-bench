"""Machine-checked gates. Each is `fn(ctx, *, stage, arg, task) -> GateResult`. Gates run commands
themselves (rendered from profile templates + map.json / plan.json fields) and never trust what the
agent says about tests; they never execute an agent-written command string."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from s2a import gitutil, gradle, parse
from s2a.context import Ctx
from s2a.parse import PlanTask


@dataclass
class GateResult:
    ok: bool
    message: str = ""
    data: dict = field(default_factory=dict)


def ok(msg: str = "", **data) -> GateResult:
    return GateResult(True, msg, data)


def fail(msg: str, **data) -> GateResult:
    return GateResult(False, msg, data)


ARTIFACT = {"intake": "ticket.md", "locate": "locate.md", "spec": "spec.md", "plan": "plan.md", "verify": "verify.md",
            "report": "report.md"}


def _rel(ctx: Ctx, p: str) -> str:
    q = p.replace("\\", "/").strip()
    root = str(ctx.repo).replace("\\", "/").rstrip("/")
    if q.lower().startswith(root.lower() + "/"):
        q = q[len(root) + 1:]
    return q.lstrip("./") if q.startswith("./") else q


# ---------------------------------------------------------------------------- artifacts
def artifact_exists(ctx: Ctx, *, stage: str, **_) -> GateResult:
    if stage == "map":
        missing = [n for n in ("map.md", "map.json") if not (ctx.s2a_dir / n).exists()]
        return fail(f"missing .s2a/{', .s2a/'.join(missing)}") if missing else ok()
    p = ctx.art(ARTIFACT[stage])
    return ok() if p.exists() and p.read_text(encoding="utf-8").strip() else fail(f"{p.name} is missing or empty")


def ticket_type_parses(ctx: Ctx, **_) -> GateResult:
    t = parse.ticket_type(ctx.read("ticket.md"))
    return ok(type=t) if t else fail("ticket.md has no `type: bug|feature|refactor|chore` line")


def ticket_size_parses(ctx: Ctx, **_) -> GateResult:
    s = parse.ticket_size(ctx.read("ticket.md"))
    return ok(size=s) if s else fail("ticket.md has no `size: S|M|L` line")


# ---------------------------------------------------------------------------- map
def map_json_valid(ctx: Ctx, **_) -> GateResult:
    try:
        d = json.loads((ctx.s2a_dir / "map.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        return fail(f"map.json does not parse: {e}")
    mods = d.get("modules")
    if not isinstance(mods, list) or not mods:
        return fail("map.json: `modules` must be a non-empty list")
    bad = [m for m in mods if not (isinstance(m, dict) and str(m.get("path", "")).startswith(":") and m.get("unit_test_task"))]
    if bad:
        return fail(f"map.json: modules need `path` (\":x\") and `unit_test_task`: {bad[:3]}")
    sm = d.get("smoke") or {}
    if not sm.get("module"):
        return fail("map.json: `smoke.module` missing")
    ctx.map_json = d
    return ok(modules=len(mods))


def map_test_command_runs(ctx: Ctx, **_) -> GateResult:
    d = ctx.map_json or json.loads((ctx.s2a_dir / "map.json").read_text(encoding="utf-8"))
    ctx.map_json = d
    mod = d["smoke"]["module"]
    r, res = gradle.run_tests(ctx, mod, label="smoke")
    if r.timed_out:
        return fail(f"the smoke test command for {mod} exceeded {ctx.pipeline.gate_timeout_s} s")
    if not res:
        tail = "\n".join(r.stdout().splitlines()[-25:])
        return fail(f"the smoke test command for {mod} produced no JUnit results (exit {r.exit_code}):\n{tail}")
    f = ctx.s2a_dir / "baseline" / f"{mod.strip(':').replace(':', '_')}.json"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps({"base_commit": ctx.state.base_commit, "module": mod, "exit_code": r.exit_code,
                             "in_place": True, "tests": {k: v.status for k, v in res.items()}}, indent=2),
                 encoding="utf-8")
    return ok(f"{len(res)} tests ran", tests=len(res), failed=sum(1 for v in res.values() if v.status != "passed"))


def map_lint_timed(ctx: Ctx, **_) -> GateResult:
    """SOFT: times the lint command once; failure or > 300 s disables the lint gate (never fails the stage)."""
    d = ctx.map_json or {}
    mod = (d.get("smoke") or {}).get("module")
    mt = gradle.module_tasks(ctx, mod) if mod else {}
    lint_s, reason = None, None
    if mod and mt.get("lint_task"):
        argv = gradle.render(ctx, ctx.profile.commands.lint, module=mod, lint_task=mt["lint_task"])
        r = gradle.run_logged(ctx, argv, "lint")
        if r.exit_code == 0 and not r.timed_out and r.duration_s <= 300:
            lint_s = r.duration_s
        else:
            reason = f"exit {r.exit_code}, {r.duration_s} s" + (" (timed out)" if r.timed_out else "")
    else:
        reason = "no lint task"
    d["lint_seconds"], d["lint_reason"] = lint_s, reason
    (ctx.s2a_dir / "map.json").write_text(json.dumps(d, indent=2), encoding="utf-8")
    ctx.map_json = d
    return ok(lint_seconds=lint_s, reason=reason)


# ---------------------------------------------------------------------------- locate
def listed_paths_exist(ctx: Ctx, **_) -> GateResult:
    paths = parse.locate_candidates(ctx.read("locate.md"))
    missing = [p for p in paths if not (ctx.repo / _rel(ctx, p)).exists()]
    return fail(f"listed paths do not exist: {missing[:8]}") if missing else ok(paths=len(paths))


def min_candidates(ctx: Ctx, *, arg: str | None = None, **_) -> GateResult:
    n = int(arg or 1)
    got = len(parse.locate_candidates(ctx.read("locate.md")))
    return ok(candidates=got) if got >= n else fail(f"{got} candidate path(s) found, at least {n} needed")


# ---------------------------------------------------------------------------- reproduce
def repro_manifest(ctx: Ctx) -> dict | None:
    p = ctx.art("repro/manifest.json")
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def _repro_selection(man: dict) -> dict[str, list[str]]:
    """module -> --tests filters (methods when known, else classes)."""
    out: dict[str, list[str]] = {}
    for t in man.get("tests") or []:
        out.setdefault(t["module"], []).append(t.get("id") or t["class"])
    return out


def _run_repro(ctx: Ctx, man: dict, tails: list[str] | None = None) -> dict[str, gradle.TestResult]:
    """Run the manifest's tests; `tails` collects the end of the Gradle output of every run without JUnit results
    (a compile error or an unknown test name), so the gate message says why (D-051)."""
    res: dict[str, gradle.TestResult] = {}
    for mod, sel in _repro_selection(man).items():
        proc, r = gradle.run_tests(ctx, mod, tests=sel, label="repro")
        res.update(r)
        if not r and tails is not None:
            out = (proc.stdout() + "\n" + proc.stderr()).strip().splitlines()
            keep = [ln for ln in out if re.search(r"error:|FAILED|No tests found|What went wrong|Could not|e: ", ln)]
            tails.append(f"{mod} (exit {proc.exit_code}):\n" + "\n".join((keep or out)[-25:]))
    return res


def _selected(results: dict[str, gradle.TestResult], man: dict) -> dict[str, gradle.TestResult]:
    keys = [t.get("id") or t["class"] for t in man.get("tests") or []]
    return {k: v for k, v in results.items() if any(k == s or k.startswith(s + ".") for s in keys)}


def repro_tests_behave(ctx: Ctx, **_) -> GateResult:
    man = repro_manifest(ctx)
    if not man or not man.get("tests"):
        return fail("no reproduction/characterization tests were written under a module's test source set")
    kind = ctx.ticket_type
    if kind == "feature" or kind == "chore":
        bad = []
        for mod in sorted({t["module"] for t in man["tests"]}):
            r = gradle.compile_module(ctx, mod, label="repro-compile")
            if r.exit_code != 0:
                bad.append(f"{mod}: exit {r.exit_code}\n" + "\n".join(r.stdout().splitlines()[-30:]))
        return fail("acceptance skeletons do not compile:\n" + "\n".join(bad)) if bad else ok("skeletons compile")
    tails: list[str] = []
    sel = _selected(_run_repro(ctx, man, tails), man)
    if not sel:
        return fail("the reproduction tests did not run (no JUnit results: compile error or wrong test names)"
                    + ("; Gradle said:\n" + "\n".join(tails) if tails else ""))
    if kind == "bug":
        wrong = {k: v.status for k, v in sel.items() if not (v.status == "failed" and v.kind == "assertion")}
        if wrong:
            return fail("bug reproduction tests must fail with an assertion now; these did not: "
                        + ", ".join(f"{k} ({s})" for k, s in list(wrong.items())[:10]))
        return ok(f"{len(sel)} test(s) fail with assertions", tests=sorted(sel))
    wrong = {k: v.status for k, v in sel.items() if v.status != "passed"}
    if wrong:
        return fail("characterization tests must pass now; these did not: " + ", ".join(list(wrong)[:10]))
    return ok(f"{len(sel)} characterization test(s) pass", tests=sorted(sel))


def _repro_pass(ctx: Ctx, label: str) -> GateResult:
    man = repro_manifest(ctx)
    if not man or not man.get("tests"):
        return ok("no reproduction tests (unavailable)")
    tails: list[str] = []
    sel = _selected(_run_repro(ctx, man, tails), man)
    if not sel:
        return fail(f"{label}: the reproduction tests did not run (compile error?)"
                    + ("; Gradle said:\n" + "\n".join(tails) if tails else ""))
    bad = [k for k, v in sel.items() if v.status != "passed"]
    return fail(f"{label}: these tests do not pass: {bad[:10]}") if bad else ok(f"{len(sel)} test(s) pass")


# ---------------------------------------------------------------------------- spec
def min_criteria(ctx: Ctx, *, arg: str | None = None, **_) -> GateResult:
    n = int(arg or 1)
    got = parse.criteria(ctx.read("spec.md"), "AC")
    return ok(criteria=len(got)) if len(got) >= n else fail(f"{len(got)} acceptance criteria (ACn.) found, {n} needed")


def every_criterion_has_verification(ctx: Ctx, **_) -> GateResult:
    md = ctx.read("spec.md")
    missing = [c.id for c in parse.criteria(md, "AC") + parse.criteria(md, "UB") if not c.verification]
    return fail(f"no `— verified by:` for {missing}") if missing else ok()


def criteria_ids_unique(ctx: Ctx, **_) -> GateResult:
    md = ctx.read("spec.md")
    ids = [c.id for c in parse.criteria(md, "AC") + parse.criteria(md, "UB")]
    dup = sorted({i for i in ids if ids.count(i) > 1})
    return fail(f"duplicate criterion ids {dup}") if dup else ok()


def unchanged_behaviour_present_for_bugs(ctx: Ctx, **_) -> GateResult:
    if ctx.ticket_type != "bug":
        return ok("not a bug")
    ub = parse.criteria(ctx.read("spec.md"), "UB")
    return ok(unchanged=len(ub)) if ub else fail("a bug spec needs at least one `UBn.` unchanged-behaviour item")


# ---------------------------------------------------------------------------- plan
def plan_json_valid(ctx: Ctx, **_) -> GateResult:
    try:
        d = parse.plan_json(ctx.read("plan.md"))
        tasks = parse.plan_tasks(d)
    except ValueError as e:
        return fail(f"plan JSON: {e}")
    if not tasks:
        return fail("plan JSON has no tasks")
    ids = [t.id for t in tasks]
    if len(set(ids)) != len(ids):
        return fail(f"duplicate task ids {ids}")
    for t in tasks:
        if not t.module.startswith(":"):
            return fail(f"{t.id}: `module` must be a Gradle path like :app, got {t.module!r}")
    ctx.tasks = tasks
    ctx.write_json("plan.json", d)
    return ok(tasks=len(tasks))


def every_criterion_covered(ctx: Ctx, **_) -> GateResult:
    acs = {c.id for c in parse.criteria(ctx.read("spec.md"), "AC")}
    covered = {c for t in ctx.tasks for c in t.covers}
    missing = sorted(acs - covered)
    return fail(f"criteria not covered by any task: {missing}") if missing else ok()


def modules_and_tasks_known(ctx: Ctx, **_) -> GateResult:
    bad = []
    for t in ctx.tasks:
        mt = gradle.module_tasks(ctx, t.module)
        if not mt.get("known"):
            bad.append(f"{t.id}: module {t.module} is unknown")
        elif t.task and mt.get("task") and t.task != mt["task"] and "skip_map" not in ctx.state.skip:
            bad.append(f"{t.id}: task {t.task!r} is not the unit-test task of {t.module} ({mt['task']})")
    return fail("; ".join(bad)) if bad else ok()


def paths_exist_or_new(ctx: Ctx, **_) -> GateResult:
    bad = []
    for t in ctx.tasks:
        for f in t.files:
            p, new = parse.plan_file_path(f)
            if not new and not (ctx.repo / _rel(ctx, p)).exists():
                bad.append(f"{t.id}: {p}")
    return fail(f"files neither existing nor marked (new): {bad[:8]}") if bad else ok()


def one_fixes_repro_task_for_bugs(ctx: Ctx, **_) -> GateResult:
    if ctx.ticket_type != "bug":
        return ok("not a bug")
    n = sum(1 for t in ctx.tasks if t.fixes_repro)
    return ok() if n == 1 else fail(f"a bug plan needs exactly one task with fixes_repro: true (found {n})")


# ---------------------------------------------------------------------------- implement (per task)
def _task_index(ctx: Ctx, task: PlanTask) -> int:
    return [t.id for t in ctx.tasks].index(task.id)


def compiles(ctx: Ctx, *, task: PlanTask | None = None, **_) -> GateResult:
    mods = [task.module] if task else affected_modules(ctx)
    bad = []
    for m in mods:
        r = gradle.compile_module(ctx, m)
        if r.exit_code != 0:
            bad.append(f"{m} (exit {r.exit_code}{', timed out' if r.timed_out else ''}):\n"
                       + "\n".join(r.stdout().splitlines()[-40:]))
    return fail("compile failed: " + "\n".join(bad)) if bad else ok()


def task_tests_pass(ctx: Ctx, *, task: PlanTask | None = None, **_) -> GateResult:
    assert task is not None
    base = gradle.baseline(ctx, task.module)
    _, res = gradle.run_tests(ctx, task.module, tests=task.tests or None, label=f"task-{task.id}-")
    if not res:
        return fail(f"no test results for {task.module} (compile error?)")
    named = []
    for t in task.tests:
        hits = {k: v for k, v in res.items() if k == t or k.startswith(t + ".")}
        if not hits:
            named.append(f"{t} did not run")
        named += [f"{k} {v.status}" for k, v in hits.items() if v.status != "passed"]
    regress = gradle.regressions(base, res, full=not task.tests)
    msgs = named + [f"{k} passed at base and fails now" for k in regress]
    return fail("; ".join(msgs[:15])) if msgs else ok(f"{len(res)} test(s) ran")


def repro_tests_pass_from_fixing_task(ctx: Ctx, *, task: PlanTask | None = None, **_) -> GateResult:
    if ctx.ticket_type != "bug" or task is None:
        return ok("not a bug")
    fix = next((i for i, t in enumerate(ctx.tasks) if t.fixes_repro), None)
    if fix is None or _task_index(ctx, task) < fix:
        return ok("before the fixing task")
    return _repro_pass(ctx, "reproduction")


def characterization_tests_pass_if_refactor(ctx: Ctx, **_) -> GateResult:
    return _repro_pass(ctx, "characterization") if ctx.ticket_type == "refactor" else ok("not a refactor")


def no_weakened_tests(ctx: Ctx, **_) -> GateResult:
    """Against base: removed @Test/assert lines or added weakening patterns in test files fail."""
    from fnmatch import fnmatch

    d = gitutil.diff(ctx.repo, ctx.state.base_commit)
    cur, bad = None, []
    pats = [re.compile(p) for p in ctx.profile.weakened_test_patterns]
    manifest = {t["path"] for t in (repro_manifest(ctx) or {}).get("tests") or []}
    for ln in d.splitlines():
        if ln.startswith("diff --git "):
            m = re.match(r"diff --git a/(.+?) b/(.+)$", ln)
            cur = m.group(2) if m else None
            continue
        if cur is None or not any(fnmatch(cur, g) for g in ctx.profile.test_dirs):
            continue
        if ln.startswith("-") and not ln.startswith("---"):
            if re.search(r"@Test\b|\bassert\w*\s*\(|\bassertThat\b|\bverify\s*\(", ln):
                bad.append(f"{cur}: removed `{ln[1:].strip()[:80]}`")
        elif ln.startswith("+") and not ln.startswith("+++"):
            if any(p.search(ln) for p in pats) and cur not in manifest:
                bad.append(f"{cur}: added `{ln[1:].strip()[:80]}`")
    return fail("existing tests weakened: " + "; ".join(bad[:10])) if bad else ok()


def lint_if_enabled(ctx: Ctx, *, task: PlanTask | None = None, **_) -> GateResult:
    s = (ctx.map_json or {}).get("lint_seconds")
    if not isinstance(s, (int, float)) or s >= 120 or task is None:
        return ok("lint gate off")
    mt = gradle.module_tasks(ctx, task.module)
    r = gradle.run_logged(ctx, gradle.render(ctx, ctx.profile.commands.lint, module=task.module,
                                             lint_task=mt["lint_task"]), f"lint-{task.id}-")
    return ok() if r.exit_code == 0 else fail("lint failed:\n" + "\n".join(r.stdout().splitlines()[-30:]))


# ---------------------------------------------------------------------------- after all tasks / fix
def affected_modules(ctx: Ctx) -> list[str]:
    mods = {t.module for t in ctx.tasks}
    for p in gitutil.changed_since(ctx.repo, ctx.state.base_commit):
        m = gradle.module_of_path(ctx, p)
        if m:
            mods.add(m)
    for p in parse.locate_candidates(ctx.read("locate.md")):
        m = gradle.module_of_path(ctx, _rel(ctx, p))
        if m:
            mods.add(m)
    return sorted(mods)


def affected_modules_tests_pass(ctx: Ctx, **_) -> GateResult:
    msgs = []
    for m in affected_modules(ctx):
        if not gradle.module_tasks(ctx, m).get("known"):
            continue
        base = gradle.baseline(ctx, m)
        r, res = gradle.run_tests(ctx, m, label="affected")
        if not res:
            msgs.append(f"{m}: no test results (exit {r.exit_code})")
            continue
        msgs += [f"{m}: {k} passed at base and fails now" for k in gradle.regressions(base, res)]
    return fail("; ".join(msgs[:15])) if msgs else ok()


def skeletons_enabled_and_pass_if_feature(ctx: Ctx, **_) -> GateResult:
    if ctx.ticket_type != "feature":
        return ok("not a feature")
    man = repro_manifest(ctx)
    if not man or not man.get("tests"):
        return ok("no acceptance skeletons (unavailable)")
    still_off = []
    for t in man["tests"]:
        p = ctx.repo / t["path"]
        if p.exists() and re.search(r"@(Ignore|Disabled)\b", p.read_text(encoding="utf-8", errors="replace")):
            still_off.append(t["path"])
    if still_off:
        return fail(f"acceptance skeletons are still disabled: {sorted(set(still_off))}")
    return _repro_pass(ctx, "acceptance")


def repro_tests_pass(ctx: Ctx, **_) -> GateResult:
    return _repro_pass(ctx, "reproduction") if ctx.ticket_type in ("bug", "refactor", "feature") else ok()


# ---------------------------------------------------------------------------- verify
def verdict_parses(ctx: Ctx, **_) -> GateResult:
    v = parse.verdict(ctx.read("verify.md"))
    return ok(stated=v.stated) if v.stated else fail("verify.md has no `VERDICT: ACCEPT|REJECT` line")


def verdict_consistent(ctx: Ctx, **_) -> GateResult:
    v = parse.verdict(ctx.read("verify.md"))
    return ok(verdict=v.derived, stated=v.stated, fails=[k for k, s in v.lines.items() if s == "FAIL"])


GATES = {f.__name__: f for f in (
    artifact_exists, ticket_type_parses, ticket_size_parses, map_json_valid, map_test_command_runs, map_lint_timed,
    listed_paths_exist, min_candidates, repro_tests_behave, min_criteria, every_criterion_has_verification,
    criteria_ids_unique, unchanged_behaviour_present_for_bugs, plan_json_valid, every_criterion_covered,
    modules_and_tasks_known, paths_exist_or_new, one_fixes_repro_task_for_bugs, compiles, task_tests_pass,
    repro_tests_pass_from_fixing_task, characterization_tests_pass_if_refactor, no_weakened_tests, lint_if_enabled,
    affected_modules_tests_pass, skeletons_enabled_and_pass_if_feature, repro_tests_pass, verdict_parses,
    verdict_consistent)}


def run_gates(ctx: Ctx, specs: list[str], *, stage: str, task: PlanTask | None = None) -> list[tuple[str, GateResult]]:
    """Run gates in order; stop at the first failure. Specs look like `name` or `name:arg`."""
    out = []
    for spec in specs:
        name, _, arg = spec.partition(":")
        res = GATES[name](ctx, stage=stage, arg=arg or None, task=task)
        out.append((spec, res))
        if not res.ok:
            break
    return out


def summarize(results: list[tuple[str, GateResult]]) -> dict:
    return {name: {"ok": r.ok, "message": r.message[:2000], **{k: v for k, v in r.data.items() if k != "tests"}}
            for name, r in results}


def first_failure(results: list[tuple[str, GateResult]]) -> tuple[str, GateResult] | None:
    return next(((n, r) for n, r in results if not r.ok), None)


__all__ = ["GATES", "GateResult", "affected_modules", "first_failure", "repro_manifest", "run_gates", "summarize",
           "Path"]
