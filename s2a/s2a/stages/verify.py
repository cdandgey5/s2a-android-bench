"""Stage 7 — verify (independent, read-only, fresh context): commit before, review the diff against the
spec, then reset the tree to the pre-verify commit. The orchestrator derives the verdict itself:
any AC/UB line marked FAIL ⇒ REJECT, whatever the agent's VERDICT line says."""
from __future__ import annotations

from s2a import gitutil, parse, render
from s2a.context import Ctx
from s2a.stages.base import artifact_stage


def run(ctx: Ctx, *, round_no: int = 1) -> str:
    gitutil.commit_all(ctx.repo, "s2a: pre-verify")
    pre = gitutil.head(ctx.repo)
    diff = gitutil.diff(ctx.repo, ctx.state.base_commit)
    stat = gitutil.diff(ctx.repo, ctx.state.base_commit, stat=True)
    st = ctx.state.stage("verify")
    try:
        artifact_stage(ctx, "verify", values={"diff": render.cap_diff(diff, stat)})
    finally:
        modified = bool(gitutil.status_porcelain(ctx.repo)) or gitutil.head(ctx.repo) != pre
        gitutil.reset_hard_clean(ctx.repo, pre)
        st["verifier_modified_tree"] = st.get("verifier_modified_tree", False) or modified
    v = parse.verdict(ctx.read("verify.md"))
    verdict = v.derived or "REJECT"
    ctx.write(f"verify-{round_no}.md", ctx.read("verify.md"))
    st.setdefault("rounds", []).append({"round": round_no, "stated": v.stated, "verdict": verdict,
                                        "fails": [k for k, s in v.lines.items() if s == "FAIL"],
                                        "defects": len(v.defects)})
    ctx.state.verdict = verdict
    ctx.state.mark("verify", "done", verdict=verdict, stated=v.stated, pre_verify_commit=pre)
    ctx.save()
    return verdict
