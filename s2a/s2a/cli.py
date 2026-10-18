"""s2a run | resume | status | map | show (specs/s2a-orchestrator.md §2)."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Optional

import typer

for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

app = typer.Typer(add_completion=False, help="S2A: drive a coding agent through a brownfield change end to end.")


def _limits(max_turns: int, max_usd: float, timeout_min: float, model: str) -> dict:
    return {"timeout_minutes": timeout_min, "max_turns_total": max_turns, "max_usd": max_usd, "max_interventions": 2,
            "max_interventions_per_trial": 4, "model": model}


def _mode(interactive: bool) -> str:
    return "interactive" if interactive and os.environ.get("S2A_AUTONOMOUS") != "1" else "autonomous"


@app.command()
def run(prompt: Optional[str] = typer.Argument(None, help="the change to make, in plain words"),
        prompt_file: Optional[Path] = typer.Option(None, help="read the prompt from this file instead"),
        repo: Path = typer.Option(Path("."), help="the repository"), profile: Optional[str] = typer.Option(None),
        interactive: bool = typer.Option(False, help="pause after spec and plan for approval (exit 5)"),
        model: str = typer.Option("claude-sonnet-5-5"), max_turns: int = typer.Option(200),
        max_usd: float = typer.Option(15.0), timeout_min: float = typer.Option(45, help="wall clock for the whole run"),
        skip: Optional[str] = typer.Option(None, help="comma-separated: map, verify, reproduce"),
        run_id: Optional[str] = typer.Option(None), branch: Optional[str] = typer.Option(None),
        map: Optional[Path] = typer.Option(None, "--map", help="use this map.md (+ map.json beside it) as-is"),
        append_system_prompt_file: Optional[Path] = typer.Option(None, help="text placed before s2a's preamble")) -> None:
    """Run every stage from the prompt to a verified change and a report."""
    from s2a import orchestrator

    if prompt_file is not None:
        prompt = prompt_file.read_text(encoding="utf-8")
    if not prompt or not prompt.strip():
        typer.echo("give a prompt or --prompt-file", err=True)
        raise typer.Exit(1)
    skips = [s.strip() for s in (skip or "").split(",") if s.strip()]
    bad = [s for s in skips if s not in orchestrator.SKIP_EFFECT]
    if bad:
        typer.echo(f"--skip accepts map, verify, reproduce (got {bad})", err=True)
        raise typer.Exit(1)
    ctx, t0 = orchestrator.new_run(prompt, repo=repo, profile=profile, mode=_mode(interactive), model=model,
                                   limits=_limits(max_turns, max_usd, timeout_min, model), skip=skips, run_id=run_id,
                                   branch=branch, map_path=str(map.resolve()) if map else None,
                                   append_file=str(append_system_prompt_file.resolve()) if append_system_prompt_file
                                   else None)
    typer.echo(f"s2a run {ctx.state.run_id} ({ctx.state.mode}); state: {ctx.run_dir / 'state.json'}")
    code = orchestrator.execute(ctx, t0)
    typer.echo(f"exit {code} ({ctx.state.exit_reason}); verdict {ctx.state.verdict}; report: {ctx.art('report.md')}")
    raise typer.Exit(code)


@app.command()
def resume(run_id: str, repo: Path = typer.Option(Path("."))) -> None:
    """Continue from the first stage that is not done (implement: the first task that is not done)."""
    from s2a import orchestrator

    ctx, t0 = orchestrator.load_run(run_id, repo)
    code = orchestrator.execute(ctx, t0)
    typer.echo(f"exit {code} ({ctx.state.exit_reason}); verdict {ctx.state.verdict}")
    raise typer.Exit(code)


@app.command()
def status(run_id: str, repo: Path = typer.Option(Path("."))) -> None:
    """Stage table, budgets used, tool-error counts, next action."""
    from s2a import orchestrator
    from s2a.state import RunState

    rd = orchestrator.run_dir(repo.resolve(), run_id)
    st = RunState.load(rd)
    errs: dict[str, int] = {}
    turns: dict[str, int] = {}
    if (rd / "calls.jsonl").exists():
        for ln in (rd / "calls.jsonl").read_text(encoding="utf-8").splitlines():
            if ln.strip():
                c = json.loads(ln)
                stage = c["name"].split("-")[0].split(".")[0]
                errs[stage] = errs.get(stage, 0) + int(c.get("tool_errors") or 0)
                turns[stage] = turns.get(stage, 0) + int(c.get("num_turns") or 0)
    typer.echo(f"run {st.run_id} · {st.mode} · model {st.model} · base {st.base_commit[:12]} · branch {st.branch}")
    typer.echo(f"used: {st.used.get('turns')} turns, est. ${float(st.used.get('usd') or 0):.4f}, "
               f"{int(st.used.get('seconds') or 0)} s; limits {st.limits}")
    typer.echo(f"{'stage':<11} {'status':<20} {'turns':>5} {'tool err':>8}")
    for name in orchestrator.ORDER:
        s = st.stages.get(name) or {"status": "pending"}
        typer.echo(f"{name:<11} {s.get('status', ''):<20} {turns.get(name, 0):>5} {errs.get(name, 0):>8}")
    tasks = (st.stages.get("implement") or {}).get("task_status") or {}
    if tasks:
        typer.echo("tasks: " + ", ".join(f"{k} {v}" for k, v in tasks.items()))
    nxt = st.next_stage([n for n in orchestrator.ORDER if n != "fix"])
    typer.echo(f"verdict: {st.verdict} · exit: {st.exit_code} ({st.exit_reason}) · next: "
               + (f"s2a resume {st.run_id}  (at {nxt})" if nxt and st.exit_code not in (0, 2) else "nothing"))


@app.command("map")
def map_cmd(refresh: bool = typer.Option(False), repo: Path = typer.Option(Path(".")),
            profile: Optional[str] = typer.Option(None), model: str = typer.Option("claude-sonnet-5-5"),
            append_system_prompt_file: Optional[Path] = typer.Option(None), max_turns: int = typer.Option(25),
            max_usd: float = typer.Option(15.0), timeout_min: int = typer.Option(20),
            print_key: bool = typer.Option(False, help="print what a map depends on (profile, prompt and stage "
                                                       "hashes) as JSON and exit; for caching maps across machines")
            ) -> None:
    """(Re)build the codebase map only; its calls go to .s2a/map.calls.jsonl."""
    import hashlib
    from datetime import datetime, timezone

    from s2a import orchestrator
    from s2a.stages import map as map_stage
    from s2a.stages.base import Stop

    repo = repo.resolve()
    if print_key:
        from s2a.profile import detect_profile, load_pipeline, load_profile, prompt_text

        def h(text: str) -> str:
            return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]

        prof = profile or detect_profile(repo)
        typer.echo(json.dumps({"profile": prof, "map_prompt": h(prompt_text("map", prof)),
                               "preamble": h(prompt_text("preamble", prof)),
                               "stage": h(load_pipeline().stage("map").model_dump_json()),
                               "profile_cfg": h(load_profile(prof).model_dump_json())}, sort_keys=True))
        raise typer.Exit(0)
    if refresh:
        (repo / ".s2a" / "map.key.json").unlink(missing_ok=True)
    from s2a import gitutil

    rid = f"map-{datetime.now(timezone.utc):%Y%m%d-%H%M%S}"
    current = gitutil.git(repo, "rev-parse", "--abbrev-ref", "HEAD").strip()
    ctx, t0 = orchestrator.new_run("(map only)", repo=repo, profile=profile, mode="autonomous", model=model,
                                   limits=_limits(max_turns, max_usd, timeout_min, model), skip=[], run_id=rid,
                                   branch=current, map_path=None,
                                   append_file=str(append_system_prompt_file.resolve()) if append_system_prompt_file
                                   else None)
    code = 0
    try:
        map_stage.run(ctx)
        ctx.state.exit_code, ctx.state.exit_reason = 0, "completed"
    except Stop as e:
        code = e.code
        ctx.state.exit_code, ctx.state.exit_reason = e.code, e.reason
        ctx.state.notes.append(e.message[:300])
    ctx.save()
    typer.echo(f"map: {ctx.state.stages.get('map')}; exit {code}")
    raise typer.Exit(code)


@app.command()
def show(run_id: str, artifact: str = typer.Argument(..., help="ticket | locate | spec | plan | verify | report"),
         repo: Path = typer.Option(Path("."))) -> None:
    """Print one artifact of a run."""
    from s2a import orchestrator

    p = orchestrator.run_dir(repo.resolve(), run_id) / f"{artifact}.md"
    if not p.exists():
        typer.echo(f"{p} does not exist", err=True)
        raise typer.Exit(1)
    typer.echo(p.read_text(encoding="utf-8"))


if __name__ == "__main__":
    app()
