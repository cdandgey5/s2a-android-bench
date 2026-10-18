"""Stage 8 — fix: address exactly the verifier's defects, with the same gates as a task; a failed gate
reverts the fix and counts as the loop's attempt. The orchestrator commits `s2a: fix <k>`."""
from __future__ import annotations

from s2a import gitutil, parse, render
from s2a.context import Ctx
from s2a.gates import first_failure, run_gates, summarize
from s2a.profile import prompt_text
from s2a.stages.base import after_call, base_values, call_name, check_budget, stage_turns


def run(ctx: Ctx, *, loop_no: int) -> bool:
    """One fix attempt. True when its gates passed and it was committed."""
    cfg = ctx.pipeline.stage("fix")
    check_budget(ctx, f"fix {loop_no}")
    v = parse.verdict(ctx.read("verify.md"))
    defects = v.defects or [f"{k} — FAIL (see the verification report)" for k, s in v.lines.items() if s == "FAIL"]
    vals = {**base_values(ctx), "defects": "\n".join(f"{i}. {d}" for i, d in enumerate(defects, 1)) or "(see verify)",
            "criteria": "\n".join(f"{c.id}. {c.text}" for c in parse.criteria(ctx.read("spec.md"), "AC"))}
    prompt, _ = render.render(prompt_text("fix", ctx.state.profile), vals)
    start = gitutil.head(ctx.repo)
    st = ctx.state.stage("fix")
    res = ctx.driver.call("fix", prompt, name=call_name(ctx, "fix"), system=ctx.system,
                          turn_cap=stage_turns(ctx, cfg), read_only=False, implementing=True,
                          diff_empty=lambda: not gitutil.changed_since(ctx.repo, start))
    st.setdefault("calls", []).append(res.call.name)
    st["turns_used"] = st.get("turns_used", 0) + res.call.num_turns
    after_call(ctx, res)
    results = run_gates(ctx, cfg.gate, stage="fix")
    st.setdefault("loops", []).append({"loop": loop_no, "gates": summarize(results)})
    bad = first_failure(results)
    if bad is not None:
        gitutil.reset_hard_clean(ctx.repo, start)
        ctx.state.notes.append(f"fix {loop_no}: gate {bad[0]} failed; fix reverted")
        st["status"] = "running"
        ctx.save()
        return False
    gitutil.commit_all(ctx.repo, f"s2a: fix {loop_no}")
    ctx.state.assumptions += [f"fix {loop_no}: {x}" for x in parse.notes(res.last_text, "Disputed")]
    st["status"] = "running"
    ctx.save()
    return True
