"""`abb` command line (Typer). Command groups arrive phase by phase; stubs say which phase."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import typer

for _s in (sys.stdout, sys.stderr):  # tables and reports are UTF-8 (the Windows console default is cp1252)
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

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
    until_limit: bool = typer.Option(False, "--until-limit", help="usage-limit canary: repeat the probe prompt as the "
                                     "sandbox user until a limit answers (costs the rest of the window)"),
    max_calls: int = typer.Option(200, help="cap for --until-limit"),
) -> None:
    """Run the pinned claude.exe headlessly through the platform layer with a trial-shaped env block."""
    from abb import paths
    from abb.harness import smoke

    if until_limit:
        raise typer.Exit(smoke.until_limit(max_calls=max_calls, model=model))
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
             warm_commits_from_tasks: bool = typer.Option(True, "--warm-commits-from-tasks/--no-warm-commits-from-tasks",
                                                          help="also warm every task's base commit and the setup_commit"),
             keep_scratch: bool = typer.Option(False)) -> None:
    """Mirror + warm caches (gradle-ro, robolectric, gradle-pristine) + fingerprint in env.lock.json."""
    import json

    from abb.harness import env

    try:
        rec = env.warm(repo, warm_commits, keep_scratch=keep_scratch, include_tasks=warm_commits_from_tasks)
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
    """uv tool install <repo>/s2a for the sandbox user (tools/bin/s2a.exe); records s2a_git_sha in env.lock.json."""
    import json

    from abb.harness import tools

    typer.echo(json.dumps(tools.install_s2a(), indent=2))


# ---------------------------------------------------------------------------- tasks
@tasks_app.command("new")
def tasks_new(task_id: str, repo: str = typer.Option(...), base_commit: str = typer.Option(...),
              source: str = typer.Option("authored")) -> None:
    """Create tasks/<id>/ from the template."""
    from abb.harness import tasks

    typer.echo(tasks.new_task(task_id, repo, base_commit, source=source))


@tasks_app.command("coverage")
def tasks_coverage(set_setup: bool = typer.Option(True, "--set-setup/--no-set-setup",
                                                  help="write each repo's octopus merge-base into repos/<repo>.yaml")) -> None:
    """Coverage vs the (MVP-scaled) targets -> tasks/COVERAGE.md; sets build.setup_commit per repo."""
    from abb.harness import taskset

    out = taskset.coverage(set_setup=set_setup)
    for r in out["rows"]:
        typer.echo(f"{'ok ' if r['ok'] else 'NO '} {r['dimension']:<13} {str(r['value'])[:48]:<48} have {str(r['have']):<14} target {r['target']}")
    typer.echo(taskset.summary_json(out["setup_commits"]))


@tasks_app.command("hash")
def tasks_hash() -> None:
    """sha256 over every task's task.yaml, problem.md, test.patch, gold.patch -> tasks/TASKSET.sha256."""
    from abb.harness import taskset

    p = taskset.write_hash()
    typer.echo(p.read_text(encoding="utf-8").splitlines()[0])


@tasks_app.command("lint")
def tasks_lint(task_id: Optional[str] = typer.Argument(None), all_: bool = typer.Option(False, "--all"),
               offline_only: bool = typer.Option(False, "--offline-only", help="skip checks that need the repo"),
               setup_leak: bool = typer.Option(False, "--setup-leak",
                                               help="only check cached setup artifacts against every gold.patch")) -> None:
    """Named lint checks (specs/task-format.md rules 1-8, D-020); exit 1 on any error."""
    from abb.harness import tasks

    if setup_leak:
        from abb.harness import taskset

        hits = taskset.setup_leaks()
        for h in hits:
            typer.echo(f"ERROR setup-leak {h}")
        typer.echo(f"{len(hits)} leak(s)")
        raise typer.Exit(1 if hits else 0)

    ids = tasks.task_ids() if all_ else [task_id] if task_id else []
    if not ids:
        typer.echo("give a task id or --all", err=True)
        raise typer.Exit(2)
    errors = 0
    for tid in ids:
        fs = tasks.lint(tid, offline_only=offline_only)
        errors += sum(f.level == "error" for f in fs)
        for f in fs:
            typer.echo(str(f))
        if not fs:
            typer.echo(f"OK    {tid}")
    typer.echo(f"{len(ids)} task(s), {errors} error(s)")
    if errors:
        raise typer.Exit(1)


@tasks_app.command("tag")
def tasks_tag(task_id: str) -> None:
    """Compute tags (files, modules, lang, ui, test kind) and write them into task.yaml."""
    import json

    from abb.harness import tasks

    typer.echo(json.dumps(tasks.tag(task_id), indent=2))


@tasks_app.command("validate")
def tasks_validate(task_id: Optional[str] = typer.Argument(None), all_: bool = typer.Option(False, "--all"),
                   runs: int = typer.Option(3), keep_going: bool = typer.Option(False, "--keep-going")) -> None:
    """V0/V1/V2 x runs in fresh offline workspaces; writes the validation block and status."""
    from abb.harness import tasks, validate

    ids = tasks.task_ids() if all_ else [task_id] if task_id else []
    raise typer.Exit(validate.validate_cli(ids, runs=runs, keep_going=keep_going))


@tasks_app.command("mine")
def tasks_mine(repo: str, since: str = typer.Option("2026-07-01"), max_files: int = typer.Option(8),
               limit: int = typer.Option(200), allow_pre_cutoff: bool = typer.Option(False),
               promote: Optional[list[int]] = typer.Option(None, help="PR numbers to copy into tasks/<repo>-<NNNN>")) -> None:
    """Mine merged PRs that close an issue and touch tests -> ABB_HOME/state/candidates/<repo>/ (ranked)."""
    from abb.harness import mine

    if promote:
        for n in promote:
            typer.echo(f"PR #{n} -> {mine.promote(repo, n)}")
        return
    rows = mine.mine(repo, since, max_files=max_files, limit=limit, allow_pre_cutoff=allow_pre_cutoff)
    keep = sorted([r for r in rows if "dir" in r], key=lambda r: (r["non_test"], -min(r["issue_len"], 1500)))
    for r in keep:
        typer.echo(f"#{r['pr']:<6} non-test {r['non_test']:<2} tests {r['tests']:<2} issue #{r['issue']:<6} "
                   f"{r['category']:<8} {r['title'][:70]}")
    skipped = [r for r in rows if "skip" in r]
    typer.echo(f"{len(keep)} candidate(s), {len(skipped)} skipped (reasons in TRIAGE.json)")


@tasks_app.command("list")
def tasks_list() -> None:
    """Table of tasks: id, repo, category, source, tags, status."""
    from abb.config import load_task
    from abb.harness import tasks

    typer.echo(f"{'id':<17} {'category':<12} {'source':<9} {'files':<5} {'mods':<4} {'lang':<7} {'kind':<11} {'split':<5} status")
    for tid in tasks.task_ids():
        t = load_task(tid)
        typer.echo(f"{tid:<17} {t.category:<12} {t.source:<9} {t.tags.files_touched:<5} {t.tags.modules:<4} "
                   f"{t.tags.lang:<7} {t.tags.test_kind:<11} {str(t.split):<5} {t.status}")


@tasks_app.command("show")
def tasks_show(task_id: str) -> None:
    """task.yaml and problem.md of one task (refused for held-out tasks under ABB_TUNING=1)."""
    from abb.config import load_task
    from abb.harness import tasks

    tasks.refuse_held_out_while_tuning([task_id])
    d = tasks.task_dir(task_id)
    typer.echo((d / "task.yaml").read_text(encoding="utf-8"))
    typer.echo("---- " + load_task(task_id).problem_statement)
    typer.echo((d / load_task(task_id).problem_statement).read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------- run, grading, analysis
@run_app.callback()
def run_main(ctx: typer.Context,
             arm: Optional[list[str]] = typer.Option(None, "--arm", help="plain | plain-guided | plain-gate | speckit | speckit-sdd (repeatable)"),
             tasks: str = typer.Option("dev5", help="dev5 | dev | test | comma-separated ids"),
             trials: int = typer.Option(1), model: str = typer.Option("claude-sonnet-5-5"),
             label: str = typer.Option("run"), grade: bool = typer.Option(True, "--grade/--no-grade"),
             sandbox: str = typer.Option("user", help="user | none (dev only; refused for test tasks)"),
             resume: Optional[str] = typer.Option(None, help="run_id to continue"),
             allow_env_drift: bool = typer.Option(False), profile: Optional[str] = typer.Option(None)) -> None:
    """Run arms x tasks x trials sequentially (Phase 4 minimal runner); results under ABB_RESULTS_DIR/<run_id>."""
    if ctx.invoked_subcommand is not None:
        return
    import json

    from abb import paths
    from abb.config import load_task
    from abb.harness import run as runmod

    if resume:
        m = json.loads((paths.results_dir() / resume / "manifest.json").read_text(encoding="utf-8"))
        arms, ids, trials, model = m["arms"], m["task_ids"], m["trials"], m["limits"]["model"]
        label, run_id, task_set = m["label"], resume, m["task_set"]
    else:
        if not arm:
            typer.echo("give at least one --arm", err=True)
            raise typer.Exit(2)
        arms, ids, run_id, task_set = list(arm), runmod.resolve_tasks(tasks), runmod.new_run_id(label), tasks
    if sandbox == "none" and any(load_task(t).split == "test" for t in ids):
        typer.echo("--sandbox none is refused for split: test tasks (D-009)", err=True)
        raise typer.Exit(2)
    r = runmod.Runner(run_id=run_id, label=label, arms=arms, tasks=ids, trials=trials, model=model, grade=grade,
                      sandbox=sandbox, allow_env_drift=allow_env_drift, profile=profile, task_set=task_set)
    out = r.run()
    typer.echo(f"run {out['run_id']} finished; aborted_reason={out['aborted_reason']}")
    typer.echo(f"results: {paths.results_dir() / out['run_id']}")


@run_app.command("status")
def run_status(run_id: Optional[str] = typer.Argument(None)) -> None:
    _stub(8)


@app.command("grade")
def grade(run_id: str, arm: Optional[str] = typer.Option(None), task: Optional[str] = typer.Option(None),
          trial: Optional[int] = typer.Option(None), parallel: int = typer.Option(1),
          regrade: bool = typer.Option(False, help="re-grade trials that already have grade.json")) -> None:
    """Grade every <arm>/<task>/t<k>/diff.patch of a run that lacks grade.json; write metrics.json."""
    import json
    from concurrent.futures import ThreadPoolExecutor

    from abb import paths
    from abb.harness import grade as g
    from abb.harness import metrics

    root = paths.results_dir() / run_id
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8")) if (root / "manifest.json").exists() else {}
    todo = []
    for dp in sorted(root.glob("*/*/t*/diff.patch")):
        tdir = dp.parent
        a, tid, k = tdir.parent.parent.name, tdir.parent.name, int(tdir.name[1:])
        if a in ("setup", "usage_limited", "probes") or (arm and a != arm) or (task and tid != task) or (trial and k != trial):
            continue
        if (tdir / "grade.json").exists() and not regrade:
            continue
        todo.append((tdir, a, tid, k))

    def one(item):
        tdir, a, tid, k = item
        r = g.grade(tid, tdir / "diff.patch", out_dir=tdir)
        metrics.build(tdir, run_id=run_id, arm=a, task_id=tid, trial=k, manifest=manifest)
        return a, tid, k, r

    with ThreadPoolExecutor(max_workers=max(1, parallel)) as ex:
        for a, tid, k, r in ex.map(one, todo):
            typer.echo(f"{a:<14} {tid:<17} t{k}  resolved={r['resolved']!s:<5} build_ok={r['build_ok']!s:<5} "
                       f"reason={r['reason']} regressions={len(r['regressions'])}")
    typer.echo(f"graded {len(todo)} trial(s)")


@app.command("grade-patch")
def grade_patch(task_id: str, patch: Path, out: Optional[Path] = typer.Option(None)) -> None:
    """Grade one patch against one task (fresh offline workspace, hidden tests); prints grade.json."""
    import json

    from abb import paths
    from abb.harness import grade as g

    pp = patch if patch.is_absolute() else paths.benchmark_dir() / patch
    r = g.grade(task_id, pp, out_dir=out)
    typer.echo(json.dumps({k: r[k] for k in ("task_id", "resolved", "build_ok", "reason", "f2p", "p2p", "regressions",
                                             "flaky_p2p", "flags", "diff_stats", "scope_creep", "interface_candidate",
                                             "grade_duration_s")}, indent=2))


@app.command("report")
def report(run_id: str) -> None:
    """Minimal results table (Phase 4; Phase 9 adds CIs and charts) -> <run>/report/summary.md."""
    from abb.harness import report as rep

    typer.echo(rep.render(run_id))


@app.command("split")
def split(seed: int = typer.Option(20261101), dev_frac: float = typer.Option(0.30),
          pin_dev: Optional[list[str]] = typer.Option(None, "--pin-dev",
                                                      help="task ids forced into dev (default: every task with a trial under results/)")) -> None:
    """Freeze the dev/test split (Phase 7): stratified on repo x category -> tasks/split.yaml + task.yaml split fields."""
    from abb.harness import taskset

    doc = taskset.make_split(seed, dev_frac, list(pin_dev) if pin_dev else None)
    typer.echo(taskset.summary_json({k: doc[k] for k in ("seed", "dev_frac", "pinned_dev", "counts", "task_ids_sha256")}))
    typer.echo(f"dev {len(doc['dev'])} / test {len(doc['test'])}; wrote tasks/split.yaml")


@labels_app.command("prepare")
def labels_prepare(run_id: str) -> None:
    _stub(9)


@labels_app.command("agreement")
def labels_agreement(run_id: str) -> None:
    _stub(9)


@app.command("audit")
def audit(run_id: str,
          rederive: bool = typer.Option(False, help="first rewrite run.json/calls.jsonl/metrics.json from the transcripts "
                                        "(after a parser fix; every change is logged in events.jsonl and run.json)"),
          reason: str = typer.Option("", help="why (required with --rederive), e.g. a D-number")) -> None:
    """Recompute run.json/calls.jsonl totals from the verbatim transcripts; fail on mismatch or any token in the run."""
    import json

    from abb.harness import audit as aud

    if rederive:
        if not reason:
            typer.echo("--rederive needs --reason", err=True)
            raise typer.Exit(2)
        typer.echo(json.dumps({"rederived": aud.rederive(run_id, reason)}, indent=2, default=str))
    r = aud.audit(run_id)
    typer.echo(json.dumps(r, indent=2))
    if not r["ok"]:
        raise typer.Exit(1)


@app.command("repro")
def repro(run_id: str) -> None:
    """Reproduce a published report from its transcripts (Phase 10)."""
    _stub(10)


if __name__ == "__main__":
    app()
