"""Arm A — the plain agent, and its two controls (specs/adapter-interface.md).

plain         one headless call with the ticket; the whole turn budget (D-014)
plain-guided  the same, with the S2A workflow described in prose appended to the system prompt
plain-gate    the same as plain, then ONE harness-side unit-test run of the modules the diff touches;
              on failure the session is resumed once with the failing tests (gate_gradle_runs /
              gate_seconds, not an intervention)
"""
from __future__ import annotations

import time
from pathlib import Path

from abb.arms.base import Limits, PhaseCall, RunResult
from abb.config import TaskConfig
from abb.harness import gradle, junit
from abb.harness.agent_driver import DriverContext, run_headless
from abb.harness.diffscope import classify
from abb.harness.tasks import module_of
from abb.harness.workspace import Workspace

HERE = Path(__file__).parent
COMMON = HERE.parent / "common" / "environment.md"
EXIT = {"success": "completed", "error_max_turns": "max_turns", "error_max_budget_usd": "budget", "timeout": "timeout",
        "usage_limited": "usage_limited"}


def exit_reason(subtype: str) -> str:
    return EXIT.get(subtype, "agent_error")


def system_prompt(*, guided: bool) -> str:
    parts = [COMMON.read_text(encoding="utf-8"), (HERE / "prompts" / "system.md").read_text(encoding="utf-8")]
    if guided:
        parts.append((HERE / "prompts" / "guided.md").read_text(encoding="utf-8"))
    return "\n".join(p.rstrip("\n") for p in parts) + "\n"


def render_task(ticket: str) -> str:
    return (HERE / "prompts" / "task.md").read_text(encoding="utf-8").replace("{{ticket}}", ticket.strip())


class PlainArm:
    setup_kind = None

    def __init__(self, name: str = "plain", *, guided: bool = False, gate: bool = False) -> None:
        self.name, self.guided, self.gate = name, guided, gate

    def one_time_setup(self, repo_key: str, ws: Workspace, limits: Limits) -> list[PhaseCall]:
        return []

    def run(self, task: TaskConfig, ws: Workspace, limits: Limits, *, ctx: DriverContext, ticket: str,
            trial: int) -> RunResult:
        assert task.test_patch is None and task.gold_patch is None, "arms never see hidden tests or the fix"
        system = system_prompt(guided=self.guided)
        call = run_headless(ctx, render_task(ticket), call_name="plain", append_system_prompt=system,
                            turn_cap=None, is_implementing_call=True)
        calls = [call]
        gate_runs, gate_s = 0, 0.0
        if self.gate and call.subtype == "success" and not ctx.budget.exhausted():
            t0 = time.monotonic()
            failed, report = self._gate(ws, ctx)
            gate_runs, gate_s = 1, round(time.monotonic() - t0, 1)
            if failed and not ctx.budget.exhausted():
                fix = run_headless(ctx, report, call_name="plain.gate1", append_system_prompt=system,
                                   session_id=call.session_id, is_implementing_call=True)
                calls.append(fix)
        final = calls[-1]
        rec = ctx.record_dir
        diff = ws.diff()
        (rec / "diff.patch").write_bytes(diff.encode("utf-8"))
        full = ws.git("diff", "--binary", "base").stdout()
        (rec / "diff.full.patch").write_bytes(full.encode("utf-8"))
        rr = RunResult(arm=self.name, task_id=task.id, trial=trial, exit_reason=exit_reason(final.subtype),
                       diff_path=rec / "diff.patch", transcript_dir=rec / "transcript", workspace_base=ws.base or "",
                       calls=calls, gate_gradle_runs=gate_runs, gate_seconds=gate_s, model=ctx.budget.limits.model,
                       agent_version=final.claude_code_version)
        return rr.fill_totals()

    def _gate(self, ws: Workspace, ctx: DriverContext) -> tuple[bool, str]:
        """Run the unit tests of the modules the diff touches, as the sandbox user, offline."""
        repo = ws.repo
        files = set(ws.git("ls-files").stdout().splitlines())
        mods = sorted({module_of(p, files) for p in ws.changed_paths() if classify(p, repo) == "source"})
        if not mods:
            return False, ""
        env = ws.agent_env(None, proxy=True)
        args = ["--offline", "--console=plain", "--continue"] + [f"{m}:{repo.tests.task_for(m)}" for m in mods]
        r = ws.exec(gradle.expand_cmd("{gradlew}", ws.dirs.work) + args, env=env,
                    timeout_s=max(60, ctx.budget.seconds_left()), out_dir=ws.dirs.agent_out / "gate", as_agent=True)
        if r.exit_code == 0:
            return False, ""
        failed = []
        for m in mods:
            jr = junit.parse_dir(gradle.junit_dir(repo, ws.dirs.work, m))
            failed += [k for k, v in jr.tests.items() if v in ("failed", "error")]
        tail = "\n".join((r.stdout() + "\n" + r.stderr()).splitlines()[-60:])
        report = ("The harness ran the unit tests of the modules you changed (" + ", ".join(mods) + ") and they did "
                  "not pass.\n\nFailing tests:\n" + ("\n".join(f"- {f}" for f in failed[:40]) or "- (build failed)")
                  + "\n\nEnd of the Gradle output:\n```\n" + tail + "\n```\n\nFix the problem so that these tests pass.")
        return True, report
