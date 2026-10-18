"""Stage 0 — intake: the prompt becomes a normalized ticket (type, size, done-when, constraints, unknowns)."""
from __future__ import annotations

from s2a import parse
from s2a.context import Ctx
from s2a.stages.base import artifact_stage


def run(ctx: Ctx) -> None:
    md, _ = artifact_stage(ctx, "intake")
    ctx.state.ticket_type = parse.ticket_type(md)
    ctx.state.mark("intake", "done", type=ctx.state.ticket_type, size=parse.ticket_size(md))
    for u in parse.notes(md, "Unknowns"):
        ctx.state.notes.append(f"unknown: {u}")
    ctx.save()
