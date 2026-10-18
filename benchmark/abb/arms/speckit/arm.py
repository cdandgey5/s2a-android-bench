"""Arm B — GitHub Spec Kit, driven headlessly (specs/speckit-automation.md).

speckit      bug path (bug extension) for bugfix tasks, SDD path otherwise (`path_by_category`)
speckit-sdd  the SDD path for every task (optional ablation of the tool's routing)

One-time setup per repo (`speckit-constitution`, cached by abb/harness/setup.py): `specify init`
and `specify extension add bug` as the harness user (they download templates), then the
`/speckit-constitution` call as the sandbox user. Per task: the call table of the chosen path, one
Claude Code session across calls (`--resume`), the nudge protocol per call, continue after an
`error_max_turns` call (artifacts may be partial), and a second implement only if converge left
open tasks. `/speckit-clarify`, `/speckit-checklist` and `/speckit-analyze` expect a human and are
skipped (D-006).
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
from pathlib import Path

import yaml

from abb import paths
from abb.arms.base import Limits, PhaseCall, RunResult
from abb.arms.plain.arm import COMMON, exit_reason
from abb.config import TaskConfig
from abb.harness.agent_driver import DriverContext, HarnessError, run_headless
from abb.harness.platform import get_platform, run_capture
from abb.harness.tools import load_lock
from abb.harness.workspace import Workspace
from abb.util import glob_match

HERE = Path(__file__).parent
SETUP_DIRS = (".specify", ".claude")   # what one_time_setup leaves in the workspace and the runner copies back
OPEN_TASK = re.compile(r"^\s*[-*]\s*\[ \]", re.M)


def load_config() -> dict:
    return yaml.safe_load((HERE / "config.yaml").read_text(encoding="utf-8"))


def environment_prompt() -> str:
    return COMMON.read_text(encoding="utf-8")


def specify_exe() -> Path:
    rel = (load_lock().get("speckit") or {}).get("path") or "tools/bin/specify.exe"
    return paths.abb_home() / rel


def step_args(step: dict, ticket: str) -> str:
    if step.get("args_file"):
        return (HERE / step["args_file"]).read_text(encoding="utf-8").strip()
    return str(step.get("args") or "").replace("{{ticket}}", ticket.strip()).strip()


def skill_body(work: Path, command: str) -> str:
    """The SKILL.md that `specify init --integration claude` wrote, without its YAML front matter."""
    p = work / ".claude" / "skills" / command / "SKILL.md"
    text = p.read_text(encoding="utf-8")
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            text = text[end + 4:]
    return text.lstrip("\n")


def build_prompt(step: dict, ticket: str, *, work: Path, invocation: str) -> str:
    """native: `/speckit-<cmd> <args>` (Claude Code expands the skill); inline: the skill text with
    `$ARGUMENTS` replaced (the fallback when a CLI version stops expanding project skills in -p)."""
    args = step_args(step, ticket)
    if invocation == "native":
        return f"/{step['command']} {args}".rstrip()
    if invocation == "inline":
        return skill_body(work, step["command"]).replace("$ARGUMENTS", args)
    raise ValueError(f"unknown invocation {invocation!r}")


def call_table(category: str, *, path: str | None = None, cfg: dict | None = None) -> tuple[str, list[dict]]:
    cfg = cfg or load_config()
    chosen = path or cfg["path_by_category"][category]
    return chosen, list(cfg["paths"][chosen])


def open_tasks(work: Path) -> int:
    """Unchecked items (`- [ ]`) in every specs/**/tasks.md: converge left work for a second implement."""
    return sum(len(OPEN_TASK.findall(p.read_text(encoding="utf-8", errors="replace")))
               for p in (work / "specs").glob("**/tasks.md")) if (work / "specs").exists() else 0


def copy_artifacts(work: Path, dst: Path, cfg: dict) -> list[str]:
    """specs/** and .specify/** (minus templates/scripts) -> <trial>/artifacts (never graded: diff_exclude)."""
    keep, skip = cfg["artifacts"]["copy"], cfg["artifacts"]["skip"]
    out = []
    for top in ("specs", ".specify"):
        base = work / top
        if not base.exists():
            continue
        for f in base.rglob("*"):
            rel = f.relative_to(work).as_posix()
            if f.is_file() and glob_match(rel, keep) and not glob_match(rel, skip):
                (dst / rel).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(f, dst / rel)
                out.append(rel)
    return out


class SpecKitArm:
    setup_kind = "speckit-constitution"

    def __init__(self, name: str = "speckit", *, path: str | None = None) -> None:
        self.name, self.path = name, path
        self.cfg = load_config()

    # ------------------------------------------------------------------ one-time setup
    def setup_prompt_hash(self) -> str:
        s = self.cfg["setup"]
        material = {"prompt": step_args({"args_file": s["constitution_prompt_file"]}, ""), "init": s["init_args"],
                    "extensions": s["extensions"], "speckit": (load_lock().get("speckit") or {}).get("ref"),
                    "invocation": self.cfg["invocation"], "environment": environment_prompt()}
        return hashlib.sha256(json.dumps(material, sort_keys=True).encode()).hexdigest()[:16]

    def setup_limits(self) -> dict:
        return dict(self.cfg["setup"]["limits"])

    setup_dirs = SETUP_DIRS

    def one_time_setup(self, repo_key: str, ws: Workspace, limits: Limits, *, ctx: DriverContext) -> list[PhaseCall]:
        s = self.cfg["setup"]
        exe = specify_exe()
        plat = get_platform()
        for argv in [s["init_args"]] + [["extension", "add", e] for e in s["extensions"]]:
            r = run_capture(plat, [str(exe), *argv], cwd=ws.dirs.work, timeout_s=900)  # harness user: needs GitHub
            with open(ctx.record_dir / "specify.log", "a", encoding="utf-8") as f:
                f.write(f"$ specify {' '.join(argv)}\n{r.stdout()}\n{r.stderr()}\nexit {r.exit_code}\n\n")
            if r.exit_code != 0:
                raise HarnessError(f"specify {' '.join(argv)} failed (exit {r.exit_code}); see specify.log")
        prompt = build_prompt({"command": "speckit-constitution", "args_file": s["constitution_prompt_file"]}, "",
                              work=ws.dirs.work, invocation=self.cfg["invocation"])
        call = run_headless(ctx, prompt, call_name="speckit-constitution", append_system_prompt=environment_prompt(),
                            turn_cap=s["turn_cap"])
        return [call]

    def install_setup(self, ws: Workspace, artifacts: Path) -> None:
        """Copy the cached `.specify/` and `.claude/` into a task workspace (before run())."""
        for d in self.setup_dirs:
            if (artifacts / d).exists():
                shutil.copytree(artifacts / d, ws.dirs.work / d, dirs_exist_ok=True)

    # ------------------------------------------------------------------ per task
    def run(self, task: TaskConfig, ws: Workspace, limits: Limits, *, ctx: DriverContext, ticket: str,
            trial: int) -> RunResult:
        assert task.test_patch is None and task.gold_patch is None, "arms never see hidden tests or the fix"
        if not (ws.dirs.work / ".specify").exists():
            raise HarnessError("Spec Kit setup artifacts missing in the workspace (install_setup not called)")
        chosen, steps = call_table(task.category, path=self.path, cfg=self.cfg)
        notes = [f"path {chosen}", f"invocation {self.cfg['invocation']}"]
        calls: list[PhaseCall] = []
        session: str | None = None
        system = environment_prompt()
        for step in steps:
            if ctx.budget.exhausted():
                notes.append(f"budget exhausted before {step['name']}")
                break
            if step.get("only_if") == "open_tasks":
                n = open_tasks(ws.dirs.work)
                if n == 0:
                    continue
                notes.append(f"{n} open task(s) after converge: second implement")
            prompt = build_prompt(step, ticket, work=ws.dirs.work, invocation=self.cfg["invocation"])
            call = run_headless(ctx, prompt, call_name=step["name"], append_system_prompt=system,
                                turn_cap=step.get("turn_cap"), session_id=session,
                                is_implementing_call=bool(step.get("implementing")))
            calls.append(call)
            session = call.session_id or session
            if call.subtype == "error_max_turns":
                notes.append(f"{step['name']} hit its turn cap; continuing with partial artifacts")
                continue
            if call.subtype != "success":
                notes.append(f"{step['name']} ended {call.subtype}; sequence stopped")
                break
        rec = ctx.record_dir
        arts = copy_artifacts(ws.dirs.work, rec / "artifacts", self.cfg)
        notes.append(f"{len(arts)} artifact file(s)")
        diff = ws.diff()
        (rec / "diff.patch").write_bytes(diff.encode("utf-8"))
        (rec / "diff.full.patch").write_bytes(ws.git("diff", "--binary", "base").stdout().encode("utf-8"))
        subtypes = [c.subtype for c in calls]
        final = "usage_limited" if "usage_limited" in subtypes else "timeout" if "timeout" in subtypes else (
            subtypes[-1] if subtypes else "agent_error")
        last = calls[-1] if calls else None
        rr = RunResult(arm=self.name, task_id=task.id, trial=trial, exit_reason=exit_reason(final),
                       diff_path=rec / "diff.patch", transcript_dir=rec / "transcript", workspace_base=ws.base or "",
                       calls=calls, artifacts={"files": str(len(arts)), "path": chosen}, model=ctx.budget.limits.model,
                       agent_version=last.claude_code_version if last else "", notes="; ".join(notes))
        return rr.fill_totals()
