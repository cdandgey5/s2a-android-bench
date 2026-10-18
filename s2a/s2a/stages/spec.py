"""Stage 4 — spec: EARS acceptance criteria with verifications, unchanged behaviour, assumptions (read-only)."""
from __future__ import annotations

from s2a import parse
from s2a.context import Ctx
from s2a.stages.base import Stop, artifact_stage


def run(ctx: Ctx) -> None:
    md, _ = artifact_stage(ctx, "spec")
    heading = "Assumptions" if ctx.state.mode == "autonomous" else "Open questions"
    ctx.state.assumptions += [f"spec: {a}" for a in parse.notes(md, heading)]
    ctx.state.mark("spec", "done", criteria=len(parse.criteria(md, "AC")), unchanged=len(parse.criteria(md, "UB")),
                   approved=None)
    ctx.save()
    if ctx.state.mode == "interactive" and ctx.pipeline.stage("spec").pause_in_interactive:
        ctx.state.mark("spec", "done", approved=False, paused=True)
        raise Stop(5, "paused", f"review {ctx.art('spec.md')} then run `s2a resume {ctx.state.run_id}`")
