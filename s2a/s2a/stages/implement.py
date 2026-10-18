"""Stage 6 — implement: one fresh session per plan task; per-task gates; reset + ≤ 2 retries (fresh
sessions, gate output appended); a task that still fails stops implement (fail fast); the
orchestrator commits each task; after the last task the affected modules' tests must pass relative
to baseline (and, for features, the acceptance skeletons are enabled and pass)."""
from __future__ import annotations

import re

from s2a import gitutil, gradle, parse, render
from s2a.context import Ctx
from s2a.gates import first_failure, run_gates, summarize
from s2a.parse import PlanTask
from s2a.profile import prompt_text
from s2a.stages.base import after_call, base_values, call_name, check_budget


def task_block(ctx: Ctx, task: PlanTask) -> str:
    """The plan's Markdown section for this task (### T1 …), plus its JSON fields."""
    md = ctx.read("plan.md")
    m = re.search(rf"(?ms)^###\s+{re.escape(task.id)}\b.*?(?=^###\s|^##\s|\Z)", md)
    js = (f"- id: {task.id}\n- module: {task.module} (unit-test task {task.task or '(from the map)'})\n"
          f"- files: {', '.join(task.files)}\n- tests: {', '.join(task.tests) or '(none named)'}\n"
          f"- approach: {task.approach}\n- covers: {', '.join(task.covers)}"
          + ("\n- this task fixes the reproduction: the reproduction tests must pass after it" if task.fixes_repro else ""))
    return ((m.group(0).strip() + "\n\n") if m else f"### {task.id} {task.title}\n\n") + js


def criteria_for(ctx: Ctx, task: PlanTask) -> str:
    acs = parse.criteria(ctx.read("spec.md"), "AC")
    picked = [c for c in acs if c.id in task.covers] or acs
    return "\n".join(f"{c.id}. {c.text}" for c in picked)


def _diff_empty_since(ctx: Ctx, rev: str):
    return lambda: not gitutil.changed_since(ctx.repo, rev)


def run(ctx: Ctx) -> None:
    cfg = ctx.pipeline.stage("implement")
    st = ctx.state.stage("implement")
    st["status"] = "running"
    ts: dict = st.setdefault("task_status", {t.id: "pending" for t in ctx.tasks})
    used = st.get("turns_used", 0)
    gitutil.checkout_clean(ctx.repo)          # resume: drop a half-done task's edits (done tasks are committed)
    # baselines for every module the plan touches, while the tree has no production change yet
    for m in sorted({t.module for t in ctx.tasks}):
        if gradle.module_tasks(ctx, m).get("known"):
            gradle.baseline(ctx, m)
    vals = base_values(ctx)
    tpl = prompt_text("implement", ctx.state.profile)
    failed_task = None
    for k, task in enumerate(ctx.tasks, 1):
        if ts.get(task.id) == "done":
            continue
        errors, ok_task = "", False
        for attempt in range(1 + ctx.pipeline.implement_task_retries):
            check_budget(ctx, f"implement {task.id}")
            stage_left = cfg.turns - used
            if stage_left <= 0:
                st["note"] = "implement stage turn cap reached"
                break
            ts[task.id] = "running"
            st["current_task"] = task.id
            ctx.save()
            prompt, _ = render.render(tpl, {**vals, "task_id": task.id, "task_count": str(len(ctx.tasks)),
                                            "task": task_block(ctx, task), "criteria": criteria_for(ctx, task),
                                            "progress": ctx.read("progress.md"),
                                            "diff_stat": gitutil.diff(ctx.repo, ctx.state.base_commit, stat=True)
                                            or "(no changes yet)",
                                            "previous_attempt_errors": errors})
            start = gitutil.head(ctx.repo)
            cap = max(1, min(ctx.pipeline.implement_task_turn_cap, stage_left, ctx.driver.budget.turns_left))
            res = ctx.driver.call("implement", prompt, name=call_name(ctx, f"implement-{task.id}"), system=ctx.system,
                                  turn_cap=cap, read_only=False, implementing=True,
                                  diff_empty=_diff_empty_since(ctx, start))
            used += res.call.num_turns
            st["turns_used"] = used
            st.setdefault("calls", []).append(res.call.name)
            after_call(ctx, res)
            results = run_gates(ctx, cfg.gate_per_task, stage="implement", task=task)
            st.setdefault("gates", {})[f"{task.id}-{attempt + 1}"] = summarize(results)
            bad = first_failure(results)
            if bad is None:
                gitutil.commit_all(ctx.repo, f"s2a: {task.id} - {task.title}"[:200])
                ts[task.id] = "done"
                ctx.state.learned += [f"{task.id}: {x}" for x in parse.notes(res.last_text, "Learned")]
                ctx.state.assumptions += [f"{task.id}: {x}" for x in parse.notes(res.last_text, "Assumptions")]
                ctx.save()
                ok_task = True
                break
            errors = (f"## Previous attempt failed\nThe orchestrator's check `{bad[0]}` failed after your last "
                      f"session (the working tree was reset to the last commit):\n```\n{bad[1].message[:4000]}\n```")
            gitutil.checkout_clean(ctx.repo)
            ts[task.id] = f"failed-attempt-{attempt + 1}"
            ctx.save()
        if not ok_task:
            ts[task.id] = "failed"
            failed_task = task.id
            for later in ctx.tasks[k:]:
                ts[later.id] = "skipped"
            ctx.state.notes.append(f"implement: task {task.id} failed its gates; remaining tasks skipped")
            break
    if failed_task is None and all(v == "done" for v in ts.values()):
        results = run_gates(ctx, cfg.gate_after_all, stage="implement")
        st["gates_after_all"] = summarize(results)
        bad = first_failure(results)
        st["status"] = "done" if bad is None else "done_with_failures"
        if bad is not None:
            ctx.state.notes.append(f"implement: after-all gate {bad[0]} failed: {bad[1].message[:300]}")
    else:
        st["status"] = "done_with_failures"
        st["failed_task"] = failed_task
    st["all_green"] = st["status"] == "done"
    ctx.save()
