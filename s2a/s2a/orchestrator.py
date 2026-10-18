"""The S2A state machine (specs/s2a-orchestrator.md): load the pipeline and profile, run the stages in
order with their gates and budgets, keep resumable state under .s2a/runs/<run_id>/, end with the
spec's exit codes (0 ACCEPT · 2 REJECT after the fix loop · 3 gate · 4 budget/time · 5 paused ·
6 model service refused · 1 orchestrator error)."""
from __future__ import annotations

import json
import re
import threading
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

from s2a import gitutil, parse, render
from s2a.context import Ctx
from s2a.driver import Budget, Driver, DriverError, ServiceRefused, utcnow_iso
from s2a.gates import first_failure, run_gates
from s2a.platform import get_platform
from s2a.profile import detect_profile, load_pipeline, load_profile, prompt_text
from s2a.stages import fix, implement, intake, locate, map as map_stage, plan, report, reproduce, spec, verify
from s2a.stages.base import Stop
from s2a.state import RunState

ORDER = ["intake", "map", "locate", "reproduce", "spec", "plan", "implement", "verify", "fix", "report"]
SKIP_EFFECT = {"map": ["map"], "verify": ["verify", "fix"], "reproduce": ["reproduce"]}
EXIT_REASON = {0: "completed", 2: "completed", 3: "gate_failed", 5: "paused"}


def slug(text: str, n: int = 5) -> str:
    words = re.findall(r"[A-Za-z0-9]+", text.lower())[:n]
    return "-".join(words)[:40] or "run"


def run_dir(repo: Path, run_id: str) -> Path:
    return repo / ".s2a" / "runs" / run_id


def build_system(ctx_repo: Path, profile_name: str, mode: str, append_file: str | None) -> str:
    prof = load_profile(profile_name)
    pre, _ = render.render(prompt_text("preamble", profile_name), {
        "repo": str(ctx_repo), "profile_notes": prof.notes_for_prompts, **render.mode_values(mode)})
    head = Path(append_file).read_text(encoding="utf-8").strip() + "\n\n" if append_file else ""
    return head + pre


def _ctx(repo: Path, state: RunState, rd: Path, stop: threading.Event) -> Ctx:
    lim = state.limits
    budget = Budget(max_turns_total=lim["max_turns_total"], max_usd=lim["max_usd"],
                    timeout_minutes=lim["timeout_minutes"], max_interventions=lim.get("max_interventions", 2),
                    max_interventions_per_trial=lim.get("max_interventions_per_trial", 4),
                    turns_used=int(state.used.get("turns", 0)), usd_used=float(state.used.get("usd", 0.0)),
                    nudges_used=int(state.used.get("nudges", 0)), seconds_used_before=float(state.used.get("seconds", 0)))
    budget.start_clock()
    driver = Driver(run_dir=rd, cwd=repo, model=state.model, budget=budget, stop=stop)
    ctx = Ctx(repo=repo, run_dir=rd, state=state, pipeline=load_pipeline(), profile=load_profile(state.profile),
              driver=driver, plat=get_platform(), system=build_system(repo, state.profile, state.mode,
                                                                       state.append_system_prompt_file), stop=stop)
    if (repo / ".s2a" / "map.md").exists() and state.is_done("map") and "map" not in state.skip:
        map_stage.load(ctx)
    if ctx.art("plan.json").exists():
        ctx.tasks = parse.plan_tasks(json.loads(ctx.read("plan.json")))
    return ctx


def new_run(prompt: str, *, repo: Path, profile: str | None, mode: str, model: str, limits: dict, skip: list[str],
            run_id: str | None, branch: str | None, map_path: str | None, append_file: str | None) -> tuple[Ctx, float]:
    repo = repo.resolve()
    gitutil.exclude_s2a(repo)
    if gitutil.status_porcelain(repo):
        raise SystemExit("the working tree has uncommitted changes; commit or stash them first")
    prof = profile or detect_profile(repo)
    rid = run_id or f"{datetime.now(timezone.utc):%Y%m%d-%H%M}-{slug(prompt)}"
    rd = run_dir(repo, rid)
    if (rd / "state.json").exists():
        raise SystemExit(f"run {rid} exists; use `s2a resume {rid}`")
    rd.mkdir(parents=True, exist_ok=True)
    base = gitutil.head(repo)
    br = branch or f"s2a/{rid}"
    gitutil.ensure_branch(repo, br)
    state = RunState(run_id=rid, prompt=prompt, mode=mode, profile=prof, branch=br, base_commit=base, model=model,
                     limits=limits, repo=str(repo), skip=list(skip), map_path=map_path,
                     append_system_prompt_file=append_file, created_at=utcnow_iso())
    for s in skip:
        for st in SKIP_EFFECT.get(s, []):
            state.mark(st, "skipped")
    state.save(rd)
    return _ctx(repo, state, rd, threading.Event()), time.monotonic()


def load_run(run_id: str, repo: Path) -> tuple[Ctx, float]:
    repo = repo.resolve()
    rd = run_dir(repo, run_id)
    if not (rd / "state.json").exists():
        raise SystemExit(f"no run {run_id} under {repo / '.s2a' / 'runs'}")
    state = RunState.load(rd)
    state.exit_code, state.exit_reason = None, None
    gitutil.ensure_branch(repo, state.branch)
    ctx = _ctx(repo, state, rd, threading.Event())
    # interactive pause: the human may have edited the artifact; its gate runs again before continuing
    for name in ("spec", "plan"):
        s = state.stages.get(name) or {}
        if s.get("paused"):
            res = run_gates(ctx, ctx.pipeline.stage(name).gate, stage=name)
            bad = first_failure(res)
            if bad is not None:
                raise SystemExit(f"{name}.md does not pass {bad[0]}: {bad[1].message}")
            s.update({"paused": False, "approved": True})
            if name == "plan":
                ctx.state.stage("implement")["task_status"] = {t.id: "pending" for t in ctx.tasks}
    return ctx, time.monotonic()


def _verify_fix(ctx: Ctx) -> None:
    st_v, st_f = ctx.state.stage("verify"), ctx.state.stage("fix")
    rounds = len(st_v.get("rounds") or [])
    if rounds == 0 or st_v.get("status") != "done":
        verdict = verify.run(ctx, round_no=rounds + 1)
    else:
        verdict = ctx.state.verdict or "REJECT"
    loops = len(st_f.get("loops") or [])
    fcfg, vcfg = ctx.pipeline.stage("fix"), ctx.pipeline.stage("verify")
    while verdict == "REJECT" and loops < ctx.pipeline.fix_loops:
        if loops >= 1 and ctx.driver.budget.turns_left < fcfg.turns + vcfg.turns:
            ctx.state.notes.append("second fix loop skipped: not enough turns left")
            break
        if ctx.driver.budget.exhausted():
            break
        loops += 1
        if fix.run(ctx, loop_no=loops):
            verdict = verify.run(ctx, round_no=len(ctx.state.stage("verify").get("rounds") or []) + 1)
    ctx.state.mark("fix", "done" if loops else "skipped", loops=loops)
    ctx.save()


def _finish(ctx: Ctx, code: int, reason: str, t0: float) -> int:
    ctx.state.exit_code, ctx.state.exit_reason = code, reason
    ctx.save()
    with open(ctx.run_dir / "events.jsonl", "a", encoding="utf-8") as f:
        for ev in ctx.driver.events:
            f.write(json.dumps(ev) + "\n")
        f.write(json.dumps({"at": utcnow_iso(), "event": "exit", "code": code, "reason": reason}) + "\n")
    ctx.driver.events.clear()
    return code


def execute(ctx: Ctx, t0: float) -> int:
    before = float(ctx.state.used.get("seconds", 0))

    def tick() -> None:
        ctx.state.used["seconds"] = round(before + time.monotonic() - t0, 1)

    code, reason = 1, "harness_error"
    try:
        for name in ORDER:
            tick()
            if name == "fix":
                continue   # runs inside _verify_fix
            if name == "verify":
                v, f = ctx.state.stage("verify").get("status"), ctx.state.stage("fix").get("status")
                if v == "skipped" or (v == "done" and f in ("done", "skipped")):
                    continue
            elif ctx.state.is_done(name):
                continue
            ctx.save()
            {"intake": intake.run, "map": map_stage.run, "locate": locate.run, "reproduce": reproduce.run,
             "spec": spec.run, "plan": plan.run, "implement": implement.run, "verify": _verify_fix,
             "report": report.run}[name](ctx)
        tick()
        if "verify" in ctx.state.skip:
            ok = (ctx.state.stages.get("implement") or {}).get("all_green")
            code, reason = (0, "completed") if ok else (3, "gate_failed")
        else:
            code, reason = (0, "completed") if ctx.state.verdict == "ACCEPT" else (2, "completed")
    except Stop as e:
        tick()
        code, reason = e.code, e.reason
        ctx.state.notes.append(f"stopped: {e.reason} — {e.message[:300]}")
        if code in (3, 4):
            try:
                ctx.write("report.md", report.draft(ctx))
            except Exception:  # noqa: BLE001 - the report draft must never mask the real ending
                pass
    except KeyboardInterrupt:
        tick()
        code, reason = 4, "timeout"
        ctx.state.notes.append("interrupted (the running call was stopped)")
    except ServiceRefused as e:
        tick()
        code, reason = 6, e.reason
        ctx.state.notes.append(str(e)[:300])
    except (DriverError, gitutil.GitError, OSError, RuntimeError) as e:
        tick()
        code, reason = 1, "harness_error"
        ctx.state.notes.append(f"orchestrator error: {e!r}"[:500])
        (ctx.run_dir / "error.txt").write_text(traceback.format_exc(), encoding="utf-8")
    return _finish(ctx, code, reason, t0)
