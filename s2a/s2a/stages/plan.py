"""Stage 5 — plan: small ordered tasks + a fenced JSON block (module/task/tests per task) (read-only)."""
from __future__ import annotations

from s2a.context import Ctx
from s2a.stages.base import Stop, artifact_stage


def run(ctx: Ctx) -> None:
    artifact_stage(ctx, "plan")   # plan_json_valid writes plan.json and fills ctx.tasks
    ctx.state.mark("plan", "done", tasks=len(ctx.tasks), approved=None)
    impl = ctx.state.stage("implement")
    impl["task_status"] = {t.id: "pending" for t in ctx.tasks}
    ctx.save()
    if ctx.state.mode == "interactive" and ctx.pipeline.stage("plan").pause_in_interactive:
        ctx.state.mark("plan", "done", approved=False, paused=True)
        raise Stop(5, "paused", f"review {ctx.art('plan.md')} then run `s2a resume {ctx.state.run_id}`")
