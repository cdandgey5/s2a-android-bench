"""Stage 9 — report: the orchestrator always writes a draft from the artifacts; an optional 5-turn polish
call runs only when turns remain."""
from __future__ import annotations

from s2a import gitutil, parse
from s2a.context import Ctx
from s2a.stages.base import Stop, artifact_stage


def draft(ctx: Ctx) -> str:
    s = ctx.state
    title = (ctx.read("ticket.md").splitlines() or ["# change"])[0].lstrip("# ").strip() or "change"
    v = parse.verdict(ctx.read("verify.md")) if ctx.read("verify.md") else None
    rows = []
    for c in parse.criteria(ctx.read("spec.md"), "AC") + parse.criteria(ctx.read("spec.md"), "UB"):
        rows.append(f"| {c.id} | {(v.lines.get(c.id) if v else None) or 'not verified'} | {c.verification or '—'} |")
    impl = s.stages.get("implement") or {}
    lines = [f"# Change report: {title}", "", "## Summary", "",
             f"Ticket type: {s.ticket_type or '?'}. Tasks: "
             + ", ".join(f"{k} {v}" for k, v in (impl.get("task_status") or {}).items()) + ". "
             f"Verdict: {s.verdict or 'none (verification skipped)'}.", "",
             "## Acceptance criteria → evidence", "", "| Criterion | Result | Verification |", "|---|---|---|", *rows, "",
             "## Assumptions made", ""] + [f"- {a}" for a in s.assumptions] + [
             "", "## Residual risks", ""] + [f"- {d}" for d in (v.defects if v else [])] + [f"- {n}" for n in s.notes] + [
             "", "## Files changed", "", "```", gitutil.diff(ctx.repo, s.base_commit, stat=True).strip(), "```", "",
             "## How to verify", ""]
    for t in ctx.tasks:
        lines.append(f"- {t.module}:{t.task or '(unit tests)'}" + (f" --tests {' '.join(t.tests)}" if t.tests else ""))
    lines += ["", "## Suggested PR description", "", title]
    return "\n".join(lines) + "\n"


def run(ctx: Ctx) -> None:
    ctx.write("report.md", draft(ctx))
    st = ctx.state.stage("report")
    st["draft"] = True
    if ctx.driver.budget.turns_left >= 5 and not ctx.driver.budget.exhausted():
        try:
            artifact_stage(ctx, "report", values={"draft_report": ctx.read("report.md")})
            st["polished"] = True
        except Stop as e:
            if e.code == 6:
                raise
            ctx.write("report.md", draft(ctx))
            st["polished"] = False
    ctx.state.mark("report", "done")
    ctx.save()
