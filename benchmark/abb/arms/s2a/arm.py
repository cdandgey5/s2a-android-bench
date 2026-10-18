"""Arm C — the S2A orchestrator (phases/phase-6-s2a-orchestrator.md step 15), driven only through the
`s2a` CLI (AGENTS.md rule 13: the benchmark never imports s2a).

s2a           every stage; the map comes from the one-time setup (`s2a map`, setup kind s2a-map)
s2a-nomap     `--skip map`, no setup
s2a-noverify  `--skip verify` (verify + fix), the trial's turn budget minus their caps
s2a-norepro   `--skip reproduce`, the trial's turn budget minus its cap

`s2a.exe` runs as the sandbox user with the trial's environment block plus S2A_AUTONOMOUS=1,
S2A_CLAUDE_EXE (the pinned claude.exe) and S2A_EXPECT_CLAUDE_VERSION; it makes its own headless
calls (same nudge protocol, probe and budgets as the harness driver) and keeps its state under
<workspace>/.s2a/runs/<id>/. This wrapper turns that run's calls.jsonl into PhaseCalls, copies the
transcripts and prompts into the trial record verbatim, and maps state.json to an exit reason.
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import shutil
from pathlib import Path

import yaml

from abb.arms.base import Limits, PhaseCall, RunResult
from abb.arms.plain.arm import COMMON
from abb.config import TaskConfig, load_toolchain
from abb.harness import transcript as tx
from abb.harness.agent_driver import AbortRun, DriverContext, HarnessError
from abb.harness.platform import get_platform, run_capture
from abb.harness.tools import s2a_exe
from abb.harness.workspace import Workspace

HERE = Path(__file__).parent
RUN_ID = "trial"           # the s2a run id inside the workspace (neutral: the product never sees a task id)
SETUP_DIRS = (".s2a",)      # what one_time_setup leaves in the workspace (pruned to setup.keep) and the runner caches
FIELDS = {f.name for f in dataclasses.fields(PhaseCall)}
EXIT_4 = {"timeout": "timeout", "max_turns": "max_turns", "budget": "budget"}
HARNESS_NOTES = ("claude_code_version", "init.model", "foreign model", "transcript unparsable")  # our env, not the agent
KEEP_RUN_FILES = ("state.json", "progress.md", "events.jsonl", "error.txt")


def load_config() -> dict:
    return yaml.safe_load((HERE / "config.yaml").read_text(encoding="utf-8"))


def exe() -> Path:
    return s2a_exe(load_toolchain())


def environment_prompt() -> str:
    return COMMON.read_text(encoding="utf-8")


def s2a_env(ctx: DriverContext) -> dict[str, str]:
    env = ctx.ws.agent_env(ctx.token, proxy=ctx.proxy)
    env.update({"S2A_AUTONOMOUS": "1", "S2A_CLAUDE_EXE": str(get_platform().claude_exe()),
                "S2A_EXPECT_CLAUDE_VERSION": load_toolchain().claude_code.version,
                "PYTHONUTF8": "1", "PYTHONDONTWRITEBYTECODE": "1"})
    return env


def write_inputs(ctx: DriverContext, ticket: str | None) -> dict[str, Path]:
    """problem.md and environment.md where the sandbox user can read them (never in the work tree:
    s2a refuses a dirty tree, and nothing the harness adds may reach the diff)."""
    d = ctx.ws.dirs.agent_out / "s2a-in"
    d.mkdir(parents=True, exist_ok=True)
    out = {"environment": d / "environment.md"}
    out["environment"].write_text(environment_prompt(), encoding="utf-8", newline="\n")
    if ticket is not None:
        out["problem"] = d / "problem.md"
        out["problem"].write_text(ticket.strip() + "\n", encoding="utf-8", newline="\n")
    (ctx.record_dir / "prompts").mkdir(parents=True, exist_ok=True)
    for k, p in out.items():
        shutil.copyfile(p, ctx.record_dir / "prompts" / f"s2a-{k}.md")
    return out


def invoke(ctx: DriverContext, argv: list[str], name: str, timeout_s: int):
    r = ctx.ws.exec(argv, env=s2a_env(ctx), timeout_s=timeout_s, out_dir=ctx.ws.dirs.agent_out / name,
                    as_agent=ctx.as_agent)
    (ctx.record_dir / f"{name}.log").write_text(
        f"$ {' '.join(argv)}\nexit {r.exit_code} stopped_by_harness={r.stopped_by_harness} memory_hit={r.job_memory_hit}\n\n--- stdout\n{r.stdout()}"
        f"\n--- stderr\n{r.stderr()}\n", encoding="utf-8")
    return r


def _copy_dir(src: Path, dst: Path) -> None:
    dst.mkdir(parents=True, exist_ok=True)
    if src.exists():
        for f in src.iterdir():
            if f.is_file():
                shutil.copyfile(f, dst / f.name)


def collect_calls(rd: Path, rec: Path, model: str) -> list[PhaseCall]:
    """<run>/calls.jsonl -> PhaseCalls in execution order, transcript paths rewritten into the trial
    record; transcripts and prompts copied verbatim. A process that left a stream but no record (s2a
    itself was killed after the grace period) becomes a `timeout` call derived from its stream."""
    tdir = rec / "transcript"
    _copy_dir(rd / "transcripts", tdir)
    _copy_dir(rd / "prompts", rec / "prompts")
    calls: list[PhaseCall] = []
    named: set[str] = set()
    f = rd / "calls.jsonl"
    for ln in (f.read_text(encoding="utf-8").splitlines() if f.exists() else []):
        if not ln.strip():
            continue
        d = {k: v for k, v in json.loads(ln).items() if k in FIELDS}
        d["transcript_path"] = str(tdir / f"{d['name']}.jsonl")
        d["nudge_transcript_paths"] = [str(tdir / Path(p).name) for p in d.get("nudge_transcript_paths") or []]
        calls.append(PhaseCall(**d))
        named.add(d["name"])
        named.update(Path(p).stem for p in d["nudge_transcript_paths"])
    out_dirs = sorted((p for p in (rd / "agent-out").glob("*") if p.is_dir()), key=lambda p: p.stat().st_mtime) \
        if (rd / "agent-out").exists() else []
    for od in out_dirs:
        if od.name in named or od.name.startswith("probe-") or not (od / "stdout.txt").exists():
            continue
        dst = tdir / f"{od.name}.jsonl"
        shutil.copyfile(od / "stdout.txt", dst)
        calls.append(orphan_call(od.name, dst, calls, model))
    return calls


def orphan_call(name: str, path: Path, prior: list[PhaseCall], model: str) -> PhaseCall:
    history = []
    for c in prior:
        for p in [c.transcript_path, *c.nudge_transcript_paths]:
            if Path(p).exists():
                history.append(tx.parse_file(Path(p)))
    t = tx.parse_file(path)
    own = tx.invocation_cost(t, history)
    u = t.usage_totals()
    return PhaseCall(name=name, session_id=t.session_id, cmd=["(recorded by the arm: s2a was killed)"],
                     started_at="", duration_ms=0, num_turns=t.num_turns, tool_calls=t.tool_calls,
                     tool_errors=t.tool_errors, cost_usd=own, cost_usd_imputed=None if own is not None else
                     tx.impute_cost(t, model), subtype="timeout", interventions=0, asked_question=t.asked_question,
                     rate_limit_retries=t.rate_limit_retries, other_retries=t.other_retries,
                     claude_code_version=(t.init or {}).get("claude_code_version") or "", model_drift=False,
                     transcript_path=str(path), **u)


def check_calls(calls: list[PhaseCall], model: str) -> None:
    """The same init/model assertions the harness driver makes on its own calls (HarnessError: re-queued once)."""
    pin = load_toolchain().claude_code.version
    for c in calls:
        for p in [c.transcript_path, *c.nudge_transcript_paths]:
            t = tx.parse_file(Path(p))
            if not t.init:
                continue
            if not str(t.init.get("model") or "").startswith(model):
                raise HarnessError(f"{c.name}: init.model {t.init.get('model')!r} is not the pinned {model!r}")
            if t.init.get("claude_code_version") != pin:
                raise HarnessError(f"{c.name}: claude_code_version {t.init.get('claude_code_version')!r} != {pin}")
            if t.init.get("permissionMode") != "bypassPermissions":
                raise HarnessError(f"{c.name}: permissionMode {t.init.get('permissionMode')!r}")
        if c.model_drift:
            raise HarnessError(f"{c.name}: modelUsage has a foreign model")


def read_state(rd: Path) -> dict | None:
    f = rd / "state.json"
    try:
        return json.loads(f.read_text(encoding="utf-8")) if f.exists() else None
    except (OSError, json.JSONDecodeError):
        return None


def outcome(state: dict | None, proc_exit: int, timed_out: bool) -> tuple[str, list[str]]:
    """state.json -> (benchmark exit reason, notes). Raises AbortRun on auth, HarnessError on our env."""
    if state is None or state.get("exit_code") is None:
        if timed_out:
            return "timeout", ["s2a stopped by the harness deadline before it saved an ending"]
        return "agent_error", [f"s2a exited {proc_exit} without an ending in state.json"]
    code, reason = int(state["exit_code"]), str(state.get("exit_reason") or "")
    notes = [f"s2a exit {code} ({reason}); verdict {state.get('verdict')}"]
    last = " ".join(state.get("notes") or [])[-600:]
    if code in (0, 2):
        return "completed", notes
    if code == 4:
        return EXIT_4.get(reason, "timeout"), notes
    if code == 6:
        if reason == "usage_limited":
            return "usage_limited", notes
        raise AbortRun("auth", f"s2a: {reason}: {last[:300]}")
    if code in (3, 5):
        return "agent_error", notes + [f"{reason}: {last[:300]}"]
    if any(h in last for h in HARNESS_NOTES):
        raise HarnessError(f"s2a: {last[:400]}")
    return "agent_error", notes + [f"orchestrator error: {last[:300]}"]


def gate_runs(rd: Path) -> tuple[int, float]:
    n, secs = 0, 0.0
    for f in (rd / "gates").glob("*/argv.json") if (rd / "gates").exists() else []:
        try:
            secs += float(json.loads(f.read_text(encoding="utf-8")).get("seconds") or 0)
        except (OSError, json.JSONDecodeError):
            pass
        n += 1
    return n, round(secs, 1)


def copy_artifacts(rd: Path, dst: Path) -> list[str]:
    """The run's artifacts (*.md, *.json, repro/, the gates' argv.json) -> <trial>/artifacts (never graded)."""
    out = []
    for f in rd.rglob("*"):
        rel = f.relative_to(rd).as_posix()
        top = rel.split("/")[0]
        if not f.is_file() or top in ("transcripts", "prompts", "agent-out"):
            continue
        if top == "gates" and f.name != "argv.json":
            continue
        if f.suffix not in (".md", ".json", ".jsonl", ".txt") and top != "repro":
            continue
        (dst / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, dst / rel)
        out.append(rel)
    return out


class S2AArm:
    setup_dirs = SETUP_DIRS

    def __init__(self, name: str = "s2a") -> None:
        self.name = name
        self.cfg = load_config()
        self.variant = self.cfg["variants"][name]
        self.setup_kind = "s2a-map" if self.variant["map"] else None
        self.setup_subtype: str | None = None   # read by abb/harness/setup.py: the setup's real ending

    # ------------------------------------------------------------------ one-time setup (s2a map)
    def setup_prompt_hash(self) -> str:
        r = run_capture(get_platform(), [str(exe()), "map", "--print-key", "--profile", self.cfg["profile"]],
                        cwd=HERE, timeout_s=120)
        if r.exit_code != 0:
            raise HarnessError(f"s2a map --print-key failed (exit {r.exit_code}): {r.stderr()[-300:]}")
        material = {"s2a": json.loads(r.stdout().strip().splitlines()[-1]), "environment": environment_prompt(),
                    "setup": self.cfg["setup"]}
        return hashlib.sha256(json.dumps(material, sort_keys=True).encode()).hexdigest()[:16]

    def setup_limits(self) -> dict:
        return dict(self.cfg["setup"]["limits"])

    def one_time_setup(self, repo_key: str, ws: Workspace, limits: Limits, *, ctx: DriverContext) -> list[PhaseCall]:
        self.setup_subtype = None
        (ctx.record_dir / "prompts").mkdir(parents=True, exist_ok=True)
        inp = write_inputs(ctx, None)
        lim = ctx.budget.limits
        secs = ctx.budget.seconds_left()
        argv = [str(exe()), "map", "--repo", str(ws.dirs.work), "--profile", self.cfg["profile"], "--model", lim.model,
                "--max-turns", str(lim.max_turns_total), "--max-usd", f"{lim.max_usd:.4f}",
                "--timeout-min", str(lim.timeout_minutes), "--append-system-prompt-file", str(inp["environment"])]
        r = invoke(ctx, argv, "s2a-map", secs + int(self.cfg["harness_margin_s"]))
        s2a_dir = ws.dirs.work / ".s2a"
        runs = sorted((s2a_dir / "runs").glob("map-*"), key=lambda p: p.stat().st_mtime) if (s2a_dir / "runs").exists() else []
        if not runs:
            self.setup_subtype = "agent_error"
            return []
        rd = runs[-1]
        calls = collect_calls(rd, ctx.record_dir, lim.model)
        check_calls(calls, lim.model)
        for c in calls:
            ctx.budget.charge(c.num_turns, c.cost_usd if c.cost_usd is not None else c.cost_usd_imputed)
        for fname in KEEP_RUN_FILES:
            if (rd / fname).exists():
                (ctx.record_dir / "s2a-run").mkdir(exist_ok=True)
                shutil.copyfile(rd / fname, ctx.record_dir / "s2a-run" / fname)
        state = read_state(rd)
        try:
            reason, _ = outcome(state, r.exit_code, r.stopped_by_harness)
        except AbortRun as e:
            reason = f"auth_failed: {e.detail[:100]}"
        if reason != "completed":
            self.setup_subtype = reason
        keep = set(self.cfg["setup"]["keep"])
        for p in s2a_dir.iterdir():        # baselines and runs belong to setup_commit, not to any task's base
            if p.name not in keep:
                get_platform().rmtree_robust(p) if p.is_dir() else p.unlink()
        ws.git("worktree", "prune", check=False)
        return calls

    def install_setup(self, ws: Workspace, artifacts: Path) -> None:
        """The cached map (map.md, map.json, ...) into <workspace>/.s2a/ before run()."""
        if (artifacts / ".s2a").exists():
            shutil.copytree(artifacts / ".s2a", ws.dirs.work / ".s2a", dirs_exist_ok=True)

    # ------------------------------------------------------------------ per task
    def run(self, task: TaskConfig, ws: Workspace, limits: Limits, *, ctx: DriverContext, ticket: str,
            trial: int) -> RunResult:
        assert task.test_patch is None and task.gold_patch is None, "arms never see hidden tests or the fix"
        v, work, b, rec = self.variant, ws.dirs.work, ctx.budget, ctx.record_dir
        map_md = work / ".s2a" / "map.md"
        if v["map"] and not map_md.exists():
            raise HarnessError("s2a map setup artifacts missing in the workspace (install_setup not called)")
        (rec / "prompts").mkdir(parents=True, exist_ok=True)
        inp = write_inputs(ctx, ticket)
        secs = b.seconds_left()
        turns = max(1, b.turns_left - int(v["turns_off"]))
        argv = [str(exe()), "run", "--prompt-file", str(inp["problem"]), "--repo", str(work),
                "--profile", self.cfg["profile"], "--model", b.limits.model, "--max-turns", str(turns),
                "--max-usd", f"{b.usd_left:.4f}", "--timeout-min", f"{secs / 60:.2f}", "--run-id", RUN_ID,
                "--append-system-prompt-file", str(inp["environment"])]
        if v["map"]:
            argv += ["--map", str(map_md)]
        if v["skip"]:
            argv += ["--skip", ",".join(v["skip"])]
        r = invoke(ctx, argv, "s2a-run", secs + int(self.cfg["harness_margin_s"]))
        rd = work / ".s2a" / "runs" / RUN_ID
        calls = collect_calls(rd, rec, b.limits.model) if rd.exists() else []
        for c in calls:
            b.charge(c.num_turns, c.cost_usd if c.cost_usd is not None else c.cost_usd_imputed)
        self._events(ctx, rd)
        check_calls(calls, b.limits.model)
        state = read_state(rd) if rd.exists() else None
        reason, notes = outcome(state, r.exit_code, r.stopped_by_harness)
        if r.job_memory_hit:
            notes.append("the job memory limit was hit")
        arts = copy_artifacts(rd, rec / "artifacts") if rd.exists() else []
        runs, gate_s = gate_runs(rd)
        notes += [f"{len(calls)} call(s)", f"{runs} gate Gradle run(s)", f"{len(arts)} artifact file(s)"]
        diff = ws.diff()
        (rec / "diff.patch").write_bytes(diff.encode("utf-8"))
        (rec / "diff.full.patch").write_bytes(ws.git("diff", "--binary", "base").stdout().encode("utf-8"))
        st = state or {}
        rr = RunResult(arm=self.name, task_id=task.id, trial=trial, exit_reason=reason,  # type: ignore[arg-type]
                       diff_path=rec / "diff.patch", transcript_dir=rec / "transcript", workspace_base=ws.base or "",
                       calls=calls, gate_gradle_runs=runs, gate_seconds=gate_s,
                       artifacts={"s2a_exit_code": str(st.get("exit_code")), "s2a_exit_reason": str(st.get("exit_reason")),
                                  "verdict": str(st.get("verdict")), "files": str(len(arts))},
                       model=b.limits.model, agent_version=calls[-1].claude_code_version if calls else "",
                       notes="; ".join(notes))
        return rr.fill_totals()

    def _events(self, ctx: DriverContext, rd: Path) -> None:
        """s2a's usage-limit and probe events -> the run's events.jsonl; probe streams -> <run>/probes/."""
        f = rd / "events.jsonl"
        for ln in (f.read_text(encoding="utf-8").splitlines() if f.exists() else []):
            if ln.strip():
                ev = json.loads(ln)
                ev.pop("at", None)
                ctx.events.append({"source": "s2a", **ev, "event": f"s2a_{ev.get('event')}", "tag": ctx.tag})
        pdir = ctx.run_dir / "probes"
        for p in (rd / "transcripts").glob("probe-*.jsonl") if (rd / "transcripts").exists() else []:
            pdir.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(p, pdir / f"{ctx.tag}-{p.name}")
