"""Stage 3 — reproduce (bug: failing tests) / characterize (refactor: passing tests) / acceptance skeleton
(feature: compiling tests). The agent writes tests into the module's test source set; the
orchestrator derives the manifest from git (changed test files + new @Test methods), reverts any
production edit, runs `repro_tests_behave`, and on success commits exactly the listed files; after
one failed retry it reverts and records `repro: unavailable` (never silently)."""
from __future__ import annotations

import json
import re
import shutil
from fnmatch import fnmatch

from s2a import gitutil, gradle, render
from s2a.context import Ctx
from s2a.gates import first_failure, run_gates, summarize
from s2a.profile import prompt_text
from s2a.stages.base import after_call, base_values, call_name, can_retry, check_budget, stage_turns

RESULT = {"bug": "failing_test_written", "refactor": "characterization_written", "feature": "skeleton_written",
          "chore": "skeleton_written"}
TEST_FILE = re.compile(r"(?:^|/)src/test\w*/(?:java|kotlin)/(.+)\.(?:java|kt)$")


def test_methods(source: str) -> list[str]:
    """Names of the @Test functions in a Java/Kotlin test source (the first signature after each @Test)."""
    names, armed = [], False
    for body in source.splitlines():
        if re.search(r"@Test\b", body):
            armed = True
        m = re.search(r"\bfun\s+`([^`]+)`\s*\(|\bfun\s+(\w+)\s*\(|\bvoid\s+(\w+)\s*\(", body)
        if m and armed:
            names.append(next(g for g in m.groups() if g))
            armed = False
    return names


def new_test_methods(now: str, before: str) -> list[str]:
    """@Test functions the file has now and did not have at HEAD (D-051: compared by name over whole files, since a
    diff can show an existing method as added, or a new one as context, depending on how git aligns it)."""
    old = set(test_methods(before))
    return [n for n in test_methods(now) if n not in old]


def build_manifest(ctx: Ctx) -> tuple[dict, list[str]]:
    """(manifest, non-test paths the agent changed)."""
    changed = gitutil.changed_since(ctx.repo, "HEAD")
    tests, other = [], []
    for p in changed:
        if any(fnmatch(p, g) for g in ctx.profile.test_dirs) and (ctx.repo / p).exists():
            m = TEST_FILE.search(p)
            if not m:
                continue   # fixtures/resources: committed with the tests, not run as tests
            cls = m.group(1).replace("/", ".")
            module = gradle.module_of_path(ctx, p) or ":app"
            before = gitutil.git(ctx.repo, "show", f"HEAD:{p}", check=False)   # "" for a new file
            methods = new_test_methods((ctx.repo / p).read_text(encoding="utf-8", errors="replace"), before)
            if methods:
                tests += [{"path": p, "module": module, "class": cls, "id": f"{cls}.{n}"} for n in methods]
            else:
                tests.append({"path": p, "module": module, "class": cls})
        elif not any(fnmatch(p, g) for g in ctx.profile.test_dirs):
            other.append(p)
    files = sorted({p for p in changed if any(fnmatch(p, g) for g in ctx.profile.test_dirs)})
    return {"kind": ctx.ticket_type, "tests": tests, "files": files}, other


def run(ctx: Ctx) -> None:
    cfg = ctx.pipeline.stage("reproduce")
    vals = base_values(ctx)
    prompt, _ = render.render(prompt_text("reproduce", ctx.state.profile), vals)
    st = ctx.state.stage("reproduce")
    used, last = st.get("turns_used", 0), None
    for attempt in range(1 + cfg.retry):
        if attempt and not can_retry(ctx, cfg, used):
            break
        check_budget(ctx, "reproduce")
        p = prompt if attempt == 0 else (prompt + "\n\n## Previous attempt\nThe orchestrator ran your tests and the check "
                                         f"`{last[0]}` failed:\n{last[1].message}\nFix the tests (not production code).")
        ctx.state.mark("reproduce", "running", attempts=attempt + 1)
        res = ctx.driver.call("reproduce", p, name=call_name(ctx, "reproduce"), system=ctx.system,
                              turn_cap=stage_turns(ctx, cfg, used), read_only=False)
        used += res.call.num_turns
        st["turns_used"] = used
        st.setdefault("calls", []).append(res.call.name)
        after_call(ctx, res)
        man, other = build_manifest(ctx)
        if other:  # production code is out of bounds in this stage
            gitutil.git(ctx.repo, "checkout", "-q", "HEAD", "--", *[o for o in other if _tracked(ctx, o)], check=False)
            for o in other:
                if not _tracked(ctx, o):
                    (ctx.repo / o).unlink(missing_ok=True)
            st["stray_edits"] = other[:50]
        ctx.write_json("repro/manifest.json", man)
        results = run_gates(ctx, cfg.gate, stage="reproduce")
        st["gates"] = summarize(results)
        last = first_failure(results)
        if last is None:
            man["result"] = RESULT.get(ctx.ticket_type, "written")
            man["observed"] = results[-1][1].data.get("tests")
            ctx.write_json("repro/manifest.json", man)
            for f in man["files"]:
                dst = ctx.art("repro") / f
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ctx.repo / f, dst)
            sha = gitutil.commit_paths(ctx.repo, man["files"], "s2a: reproduction tests")
            ctx.state.mark("reproduce", "done", result=man["result"], tests=len(man["tests"]), commit=sha)
            ctx.save()
            return
        gitutil.checkout_clean(ctx.repo)   # next attempt (or give up) starts from the committed tree
        ctx.save()
    ctx.art("repro/manifest.json").unlink(missing_ok=True)
    ctx.state.mark("reproduce", "unavailable", reason=f"{last[0]}: {last[1].message[:1500]}")
    ctx.state.notes.append(f"repro: unavailable ({last[0]})")
    ctx.save()


def _tracked(ctx: Ctx, path: str) -> bool:
    return bool(gitutil.git(ctx.repo, "ls-files", "--", path, check=False).strip())


__all__ = ["build_manifest", "run", "json"]
