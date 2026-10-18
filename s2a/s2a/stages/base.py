"""Shared stage machinery: prompt values, read-only artifact stages, clean-tree post-check, control flow."""
from __future__ import annotations

from s2a import gitutil, parse, render
from s2a.context import Ctx
from s2a.driver import CallResult
from s2a.gates import GateResult, first_failure, run_gates, summarize
from s2a.profile import StageCfg, prompt_text


class Stop(Exception):
    """End the run now: exit code + exit_reason (budget, usage limit, gate failure, pause)."""

    def __init__(self, code: int, reason: str, message: str = "") -> None:
        super().__init__(f"{reason}: {message}")
        self.code, self.reason, self.message = code, reason, message


SUBTYPE_STOP = {"usage_limited": (6, "usage_limited"), "timeout": (4, "timeout"), "error_max_budget_usd": (4, "budget")}


def check_budget(ctx: Ctx, before: str) -> None:
    why = ctx.driver.budget.exhausted()
    if why:
        raise Stop(4, why, f"budget exhausted before {before}")


def after_call(ctx: Ctx, res: CallResult) -> None:
    """A usage limit, a timeout or the USD cap ends the run (state is saved by the orchestrator)."""
    ctx.save()
    st = res.call.subtype
    if st in SUBTYPE_STOP:
        code, reason = SUBTYPE_STOP[st]
        if st == "timeout" and ctx.driver.budget.seconds_left() > 30 and not ctx.stop.is_set():
            return  # a per-call deadline inside a still-open budget is the stage's own failure
        raise Stop(code, reason, f"{res.call.name} ended {st}")
    if ctx.driver.budget.turns_left <= 0:
        raise Stop(4, "max_turns", f"turn budget used up during {res.call.name}")


def stage_turns(ctx: Ctx, cfg: StageCfg, used_in_stage: int = 0) -> int:
    return max(1, min(cfg.turns - used_in_stage, ctx.driver.budget.turns_left))


def base_values(ctx: Ctx) -> dict[str, str]:
    v = {"repo": str(ctx.repo), "prompt": ctx.state.prompt, "profile_notes": ctx.profile.notes_for_prompts,
         "ticket": ctx.read("ticket.md"), "locate": ctx.read("locate.md"), "spec": ctx.read("spec.md"),
         "plan": ctx.read("plan.md"), "repro": repro_text(ctx),
         "conventions_checklist": "\n".join(f"- {c}" for c in ctx.profile.conventions_checklist),
         "progress": ctx.read("progress.md")}
    v.update(render.mode_values(ctx.state.mode))
    if ctx.map_md:
        v.update(render.map_views(ctx.map_md))
    else:
        nomap = ("No codebase map is available: discover the build, test and module layout yourself (read the Gradle "
                 "settings and build files; `./gradlew <module>:tasks --all` lists task names).")
        v.update({"map": nomap, "map_commands": nomap, "map_conventions": nomap})
    return v


def repro_text(ctx: Ctx) -> str:
    rs = ctx.state.stages.get("reproduce") or {}
    if rs.get("status") == "skipped":
        return "Reproduction stage skipped."
    if rs.get("status") == "unavailable":
        return f"repro: unavailable — {rs.get('reason', 'the reproduction gate did not pass')}"
    man = ctx.art("repro/manifest.json")
    if not man.exists():
        return "No reproduction tests yet."
    import json

    m = json.loads(man.read_text(encoding="utf-8"))
    lines = [f"Result: {m.get('result')}"] + [f"- {t['path']} — {t.get('id') or t['class']}" for t in m.get("tests") or []]
    return "\n".join(lines)


def system_prompt(ctx: Ctx) -> str:
    return ctx.system


def call_name(ctx: Ctx, stage: str) -> str:
    """intake, then intake-2, intake-3 … (one file per call under prompts/ and transcripts/)."""
    s = ctx.state.stage(stage)
    s["calls_n"] = s.get("calls_n", 0) + 1
    return stage if s["calls_n"] == 1 else f"{stage}-{s['calls_n']}"


def clean_tree(ctx: Ctx, stage: str) -> list[str]:
    stray = gitutil.status_porcelain(ctx.repo)
    if stray:
        gitutil.checkout_clean(ctx.repo)
        ctx.state.stage(stage)["stray_edits"] = stray[:50]
    return stray


def artifact_stage(ctx: Ctx, stage: str, *, values: dict[str, str] | None = None, artifact: str | None = None,
                   gates: list[str] | None = None, template: str | None = None) -> tuple[str, list]:
    """Run a read-only stage: the artifact is the last assistant message that passes the stage's gates.
    Retries (fresh sessions, the failure appended) per `retry` in pipeline.yaml."""
    from s2a.gates import ARTIFACT

    cfg = ctx.pipeline.stage(stage)
    name_file = artifact or ARTIFACT[stage]
    gates = gates if gates is not None else cfg.gate
    vals = {**base_values(ctx), **(values or {})}
    tpl = template if template is not None else prompt_text(stage, ctx.state.profile)
    prompt, _ = render.render(tpl, vals)
    last_fail: tuple[str, GateResult] | None = None
    st = ctx.state.stage(stage)
    used = st.get("turns_used", 0)
    for attempt in range(1 + cfg.retry):
        check_budget(ctx, stage)
        p = prompt if attempt == 0 else (prompt + "\n\n## Previous attempt\nYour previous answer did not pass the check "
                                         f"`{last_fail[0]}`: {last_fail[1].message}\nReturn the artifact again, fixed, "
                                         "in exactly the requested format.")
        ctx.state.mark(stage, "running", attempts=attempt + 1)
        res = ctx.driver.call(stage, p, name=call_name(ctx, stage), system=ctx.system,
                              turn_cap=stage_turns(ctx, cfg, used), read_only=cfg.tools == "read_only", structured=True)
        used += res.call.num_turns
        st["turns_used"] = used
        st.setdefault("calls", []).append(res.call.name)
        if cfg.tools == "read_only" and "clean_tree" in ctx.pipeline.read_only_post:
            clean_tree(ctx, stage)
        after_call(ctx, res)
        results: list = []
        for text in reversed([t for t in res.texts if t.strip()]):
            ctx.write(name_file, parse.strip_fence(text))
            results = run_gates(ctx, gates, stage=stage)
            if first_failure(results) is None:
                st["gates"] = summarize(results)
                return ctx.read(name_file), results
        if not res.texts:
            results = [("artifact_exists", GateResult(False, "the call returned no message"))]
        last_fail = first_failure(results)
        st["gates"] = summarize(results)
        ctx.save()
    assert last_fail is not None
    raise Stop(3, "gate_failed", f"{stage}: {last_fail[0]} — {last_fail[1].message}")
