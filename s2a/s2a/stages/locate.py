"""Stage 2 — locate: ranked candidates, call graph, existing tests, blast radius (read-only)."""
from __future__ import annotations

from s2a import parse
from s2a.context import Ctx
from s2a.stages.base import artifact_stage


def run(ctx: Ctx) -> None:
    md, _ = artifact_stage(ctx, "locate")
    ctx.state.mark("locate", "done", candidates=len(parse.locate_candidates(md)))
    ctx.save()
