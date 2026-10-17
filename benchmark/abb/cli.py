"""`abb` command line (Typer). Command groups arrive phase by phase; stubs say which phase."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer

app = typer.Typer(no_args_is_help=True, add_completion=False, help="Android Brownfield Bench (abb).")


def _stub(phase: int) -> None:
    typer.echo(f"not implemented in this phase (arrives in Phase {phase})")
    raise typer.Exit(2)


def _group(name: str, help_: str) -> typer.Typer:
    g = typer.Typer(no_args_is_help=True, add_completion=False, help=help_)
    app.add_typer(g, name=name)
    return g


tools_app = _group("tools", "Pinned toolchain under ABB_HOME/tools (Phase 0).")
env_app = _group("env", "Per-repo warm caches, fingerprints, verification (Phase 1).")
sandbox_app = _group("sandbox", "Sandbox user, firewall, proxy (Phase 1).")
auth_app = _group("auth", "Subscription token checks (Phase 0).")
tasks_app = _group("tasks", "Task authoring, lint, validation (Phase 2).")
repos_app = _group("repos", "Repository configs (Phase 0).")
labels_app = _group("labels", "Failure labelling (Phase 9).")
ws_app = _group("ws", "Workspaces and smoke tests (Phase 0/1).")
run_app = typer.Typer(add_completion=False, help="Run the benchmark matrix (Phase 4/8).", invoke_without_command=True)
app.add_typer(run_app, name="run")


# ---------------------------------------------------------------------------- tools
@tools_app.command("install")
def tools_install(only: Optional[list[str]] = typer.Option(None, help="jdk|python|launcher|claude|pwsh|android|speckit|git")) -> None:
    """Install the pinned toolchain (idempotent; verified against config/toolchain.lock.yaml)."""
    from abb.harness import tools

    try:
        tools.install(only)
    except tools.ToolError as e:
        typer.echo(f"ERROR: {e}", err=True)
        raise typer.Exit(1)
    typer.echo(f"toolchain installed; lock: {tools.lock_path()}")


@tools_app.command("check")
def tools_check() -> None:
    """Re-verify every installed component against the lock."""
    from abb.harness import tools

    rows = tools.check()
    for name, ok, detail in rows:
        typer.echo(f"{'OK  ' if ok else 'FAIL'} {name:<12} {detail}")
    if not all(ok for _, ok, _ in rows):
        raise typer.Exit(1)


# ---------------------------------------------------------------------------- auth
@auth_app.command("check")
def auth_check() -> None:
    """`claude.exe auth status` through the launcher with the mapped token and an empty CLAUDE_CONFIG_DIR."""
    from abb.harness import auth

    raise typer.Exit(auth.check_cli())


# ---------------------------------------------------------------------------- ws
@ws_app.command("smoke")
def ws_smoke(
    prompt: Optional[str] = typer.Argument(None, help="prompt sent on stdin (or --prompt-file)"),
    prompt_file: Optional[Path] = typer.Option(None, help="read the prompt from this file (relative to benchmark/)"),
    sandbox: str = typer.Option("none", help="user = run as the sandbox user (Phase 1)"),
    repo: Optional[str] = typer.Option(None, help="work dir = a history-free snapshot of this repo"),
    commit: Optional[str] = typer.Option(None, help="snapshot commit (default: cache_commit)"),
    model: str = typer.Option("claude-sonnet-5-5", help="full model id (never an alias)"),
    max_turns: int = typer.Option(3),
    max_usd: float = typer.Option(1.0, help="--max-budget-usd (estimate cap)"),
    deadline: Optional[int] = typer.Option(None, help="seconds; then STOP -> interrupt -> grace -> kill"),
    grace: int = typer.Option(30, help="seconds between the interrupt and killing the job"),
    interrupt: Optional[str] = typer.Option(None, help="ctrl_break | ctrl_c (default: sandbox.yaml)"),
    save: Optional[str] = typer.Option(None, help="fixture name: copy stdout to tests/fixtures/transcripts/<name>.jsonl"),
    tools: Optional[str] = typer.Option(None, help="pass --tools <value> (e.g. '' for none)"),
    proxy: bool = typer.Option(False, help="route through the harness proxy (started for the call)"),
    env: Optional[list[str]] = typer.Option(None, "--env", help="KEY=VALUE override of the agent block (experiments)"),
    allowed_tools: Optional[str] = typer.Option(None, help="pass --allowedTools <value>"),
    permission_mode: str = typer.Option("bypassPermissions"),
) -> None:
    """Run the pinned claude.exe headlessly through the platform layer with a trial-shaped env block."""
    from abb import paths
    from abb.harness import smoke

    if prompt_file is not None:
        pf = prompt_file if prompt_file.is_absolute() else paths.benchmark_dir() / prompt_file
        prompt = pf.read_text(encoding="utf-8")
    if not prompt:
        typer.echo("give a prompt or --prompt-file", err=True)
        raise typer.Exit(2)
    raise typer.Exit(smoke.smoke_cli(prompt, model=model, max_turns=max_turns, max_usd=max_usd, deadline=deadline,
                                     grace=grace, interrupt=interrupt, save=save, tools=tools, proxy=proxy,
                                     env_overrides=dict(e.split("=", 1) for e in (env or [])),
                                     allowed_tools=allowed_tools, permission_mode=permission_mode,
                                     sandbox=sandbox, repo=repo, commit=commit))


@ws_app.command("open")
def ws_open(repo: str, commit: Optional[str] = typer.Option(None, help="default: cache_commit"),
            as_agent: bool = typer.Option(False, "--as-agent", help="open the shell as the sandbox user")) -> None:
    """Debug helper: a fresh workspace and a visible PowerShell in it (agent env block, no token)."""
    from abb import paths
    from abb.config import load_repo, load_sandbox
    from abb.harness.platform import ProcSpec, get_platform
    from abb.harness.workspace import Workspace
    from abb.util import stamp

    rc = load_repo(repo)
    ws = Workspace(rc, paths.work_dir() / "ws-open" / f"{stamp()}-{repo}", "user" if as_agent else "none")
    ws.snapshot(commit or rc.build.cache_commit)
    typer.echo(f"workspace: {ws.dirs.root} (base {ws.base}); close the PowerShell window to finish")
    plat = get_platform()
    spec = ProcSpec(argv=[str(paths.tools_dir() / "pwsh" / "pwsh.exe"), "-NoExit", "-NoProfile"], cwd=ws.dirs.work,
                    env=ws.agent_env(None, proxy=True), stdin_text=None, timeout_s=8 * 3600, memory_mb=None,
                    as_user=load_sandbox().modes["user"].run_as if as_agent else None, out_dir=ws.dirs.root / "open-out",
                    hidden=False)
    plat.wait(plat.run(spec))


# ---------------------------------------------------------------------------- repos
@repos_app.command("check")
def repos_check(repo: str) -> None:
    """Strict check: real SHAs, task names filled, no case collisions, paths < 200 chars."""
    from abb.harness import repos

    raise typer.Exit(repos.check_cli(repo))


@repos_app.command("list")
def repos_list() -> None:
    from abb import paths

    for p in sorted(paths.repos_config_dir().glob("*.yaml")):
        typer.echo(p.stem)


# ---------------------------------------------------------------------------- env / sandbox
@env_app.command("warm")
def env_warm(repo: str, warm_commits: Optional[list[str]] = typer.Option(None, "--warm-commits"),
             keep_scratch: bool = typer.Option(False)) -> None:
    """Mirror + warm caches (gradle-ro, robolectric, gradle-pristine) + fingerprint in env.lock.json."""
    import json

    from abb.harness import env

    try:
        rec = env.warm(repo, warm_commits, keep_scratch=keep_scratch)
    except env.WarmError as e:
        typer.echo(f"ERROR: {e}", err=True)
        raise typer.Exit(1)
    typer.echo(json.dumps({k: rec[k] for k in ("fingerprint", "warm_commits", "warm_minutes", "robolectric_jars")}, indent=2))
    typer.echo(json.dumps(env.cache_sizes(env.load_repo(repo)), indent=2))


@env_app.command("verify")
def env_verify(repo: str, sandbox: str = typer.Option("user", help="user | none (dev only)"),
               transforms: str = typer.Option("both", help="seed_transforms off | on | both"),
               keep: bool = typer.Option(False, help="keep the verify workspaces")) -> None:
    """Fresh workspace, offline unit tests of verify_modules (< 10 min), seed task fail -> pass."""
    from abb.harness import verify

    rep = verify.verify(repo, sandbox=sandbox, transforms=transforms, keep=keep)
    ok, msgs = verify.verdict(rep)
    for m in msgs:
        typer.echo(m)
    typer.echo(f"report: {rep['report_file']}")
    if not ok:
        raise typer.Exit(1)


@env_app.command("fingerprint")
def env_fingerprint(repo: str) -> None:
    """Recompute the environment fingerprint and compare it with env.lock.json; print cache sizes."""
    import json

    from abb.harness import env

    r = env.current_fingerprint(repo)
    typer.echo(json.dumps(r, indent=2))
    if not r["match"]:
        raise typer.Exit(1)


@env_app.command("prune")
def env_prune(include_smoke: bool = typer.Option(False, help="also delete work/smoke (fixture evidence)")) -> None:
    """Delete scratch workspaces (warm, verify, probe, checks, debug); report cache sizes. Never touches caches."""
    import json

    from abb import paths
    from abb.config import load_repo
    from abb.harness import env
    from abb.harness.platform import get_platform

    plat = get_platform()
    kinds = ["warm", "verify", "probe", "sbcheck", "debug", "itest", "_cleanup", "auth", "ws-open"] + (["smoke"] if include_smoke else [])
    for k in kinds:
        d = paths.work_dir() / k
        if d.exists():
            left = plat.rmtree_robust(d)
            typer.echo(f"{'deleted' if not left else 'PARTIAL'} {d}" + (f" ({len(left)} leftovers)" if left else ""))
    sizes = {p.stem: env.cache_sizes(load_repo(p.stem)) for p in sorted(paths.repos_config_dir().glob("*.yaml"))
             if (paths.caches_dir() / "gradle-ro" / p.stem).exists()}
    typer.echo(json.dumps(sizes, indent=2))


@sandbox_app.command("setup")
def sandbox_setup(prepare_only: bool = typer.Option(False, help="only the non-elevated part (no UAC prompt)")) -> None:
    """Create/refresh the sandbox user, ACLs, firewall rule (ONE UAC prompt). Idempotent."""
    import json

    from abb.harness import sandbox

    if prepare_only:
        typer.echo(json.dumps(sandbox.prepare(list(sandbox.CHOSEN_REPOS)), indent=2))
        return
    res = sandbox.setup()
    typer.echo(json.dumps(res, indent=2))
    if res.get("exit_code") != 0:
        raise typer.Exit(1)


@sandbox_app.command("check")
def sandbox_check(smoke: bool = typer.Option(True, help="include the Claude smoke test as the sandbox user")) -> None:
    """Prove the boundary as the sandbox user: denied paths, firewall, proxy, tools, smoke test."""
    from abb.harness import sandbox

    rows = sandbox.check(smoke=smoke)
    for name, ok, detail in rows:
        typer.echo(f"{'OK  ' if ok else 'FAIL'} {name:<44} {detail}")
    if not all(ok for _, ok, _ in rows):
        raise typer.Exit(1)


@sandbox_app.command("install-s2a")
def sandbox_install_s2a() -> None:
    _stub(6)


# ---------------------------------------------------------------------------- tasks
@tasks_app.command("new")
def tasks_new(task_id: str) -> None:
    _stub(2)


@tasks_app.command("lint")
def tasks_lint(task_id: Optional[str] = typer.Argument(None), all_: bool = typer.Option(False, "--all")) -> None:
    _stub(2)


@tasks_app.command("validate")
def tasks_validate(task_id: Optional[str] = typer.Argument(None)) -> None:
    _stub(2)


@tasks_app.command("mine")
def tasks_mine(repo: str) -> None:
    _stub(2)


@tasks_app.command("list")
def tasks_list() -> None:
    _stub(2)


# ---------------------------------------------------------------------------- run, grading, analysis
@run_app.callback()
def run_main(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand is None:
        _stub(4)


@run_app.command("status")
def run_status(run_id: Optional[str] = typer.Argument(None)) -> None:
    _stub(8)


@app.command("grade")
def grade(run_id: str) -> None:
    """Grade a run's trials with the hidden tests (Phase 3)."""
    _stub(3)


@app.command("grade-patch")
def grade_patch(task_id: str, patch: Path) -> None:
    """Grade one patch against one task (Phase 3)."""
    _stub(3)


@app.command("report")
def report(run_id: str) -> None:
    """Tables, CIs and charts (Phase 4/9)."""
    _stub(4)


@app.command("split")
def split() -> None:
    """Freeze the dev/test split (Phase 7)."""
    _stub(7)


@labels_app.command("prepare")
def labels_prepare(run_id: str) -> None:
    _stub(9)


@labels_app.command("agreement")
def labels_agreement(run_id: str) -> None:
    _stub(9)


@app.command("audit")
def audit(run_id: str) -> None:
    """Recompute run.json/calls.jsonl totals from the verbatim transcripts (Phase 4)."""
    _stub(4)


@app.command("repro")
def repro(run_id: str) -> None:
    """Reproduce a published report from its transcripts (Phase 10)."""
    _stub(10)


if __name__ == "__main__":
    app()
