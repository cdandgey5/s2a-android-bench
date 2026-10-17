"""Arm adapter interface - the only contract the runner knows about.

Seed file: keep the dataclasses identical to specs/adapter-interface.md and the fields of
benchmark/config/limits.yaml. See specs/adapter-interface.md for the rules.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Literal, Protocol

if TYPE_CHECKING:  # pragma: no cover
    from abb.config import TaskConfig as Task
    from abb.harness.workspace import Workspace

ExitReason = Literal[
    "completed",      # agent ended its final turn normally
    "max_turns",      # hit the per-call or total turn budget
    "timeout",        # harness-initiated stop at the deadline (stopped_by_harness)
    "budget",         # --max-budget-usd tripped
    "agent_error",    # non-zero exit, no result line, orchestrator crash; never re-run
    "harness_error",  # our bug (platform failure, unparsable transcript, model drift); re-queued once
]


@dataclass
class Limits:
    """Budget for ONE trial, shared by every headless call the arm makes."""

    timeout_minutes: int = 45
    max_turns_total: int = 200
    max_usd: float = 15.0
    max_interventions: int = 2             # nudges per headless call
    max_interventions_per_trial: int = 4   # nudges per trial, all calls together
    grade_timeout_minutes: int = 30        # used by the grader only
    model: str = "claude-sonnet-5-5"       # dev default; final runs pin claude-opus-5-5


@dataclass
class PhaseCall:
    """One headless invocation of the agent. An arm may make several per trial."""

    name: str
    session_id: str | None
    cmd: list[str]                   # argv actually executed (secrets redacted)
    started_at: str                  # ISO 8601 UTC
    duration_ms: int
    num_turns: int
    tool_calls: int
    tool_errors: int                 # tool_result blocks with is_error
    cost_usd: float | None           # None when no result line was emitted
    cost_usd_imputed: float | None   # from per-message usage when cost_usd is None
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_write_tokens: int
    subtype: str                     # success | error_max_turns | error_max_budget_usd | ...
    interventions: int               # nudges issued during this call
    asked_question: bool
    rate_limit_retries: int          # api_retry events with error == rate_limit
    other_retries: int               # other api_retry events
    claude_code_version: str         # from the init event
    model_drift: bool                # a non-haiku foreign model appeared in modelUsage
    transcript_path: str
    interventions_log: list[dict] = field(default_factory=list)
    background_models: list[str] = field(default_factory=list)
    nudge_transcript_paths: list[str] = field(default_factory=list)
    prompt_sha256: str = ""
    system_prompt_sha256: str = ""


@dataclass
class RunResult:
    arm: str
    task_id: str
    trial: int
    exit_reason: ExitReason
    diff_path: Path                  # scoped diff (input to grading)
    transcript_dir: Path
    workspace_base: str              # `git rev-parse HEAD` of the workspace after snapshot
    calls: list[PhaseCall] = field(default_factory=list)
    artifacts: dict[str, str] = field(default_factory=dict)
    gate_gradle_runs: int = 0        # Gradle runs performed by the arm's own tooling (S2A gates, plain-gate hook)
    gate_seconds: float = 0.0
    # Totals, filled by the runner from `calls`:
    duration_ms: int = 0
    cost_usd: float | None = None    # None if any call lacks a result line
    cost_usd_imputed: float = 0.0    # always computable
    num_turns: int = 0
    tool_calls: int = 0
    interventions: int = 0
    asked_question: bool = False
    model: str = ""
    agent_version: str = ""
    notes: str = ""

    def fill_totals(self) -> "RunResult":
        self.duration_ms = sum(c.duration_ms for c in self.calls)
        if any(c.cost_usd is None for c in self.calls):
            self.cost_usd = None
        else:
            self.cost_usd = round(sum(c.cost_usd for c in self.calls), 4)
        self.cost_usd_imputed = round(
            sum((c.cost_usd if c.cost_usd is not None else (c.cost_usd_imputed or 0.0)) for c in self.calls), 4
        )
        self.num_turns = sum(c.num_turns for c in self.calls)
        self.tool_calls = sum(c.tool_calls for c in self.calls)
        self.interventions = sum(c.interventions for c in self.calls)
        self.asked_question = any(c.asked_question for c in self.calls)
        return self


class Arm(Protocol):
    """Implemented by arms.plain.PlainArm, arms.speckit.SpecKitArm, arms.s2a.S2AArm."""

    name: str
    setup_kind: str | None           # None | "speckit-constitution" | "s2a-map"

    def one_time_setup(self, repo_key: str, ws: "Workspace", limits: Limits) -> list[PhaseCall]:
        """Per-repo setup whose cost is reported separately. Idempotent; cached per
        (setup_kind, repo, setup_commit, environment fingerprint, prompt hash)."""
        ...

    def run(self, task: "Task", ws: "Workspace", limits: Limits) -> RunResult:
        """Attempt the task. Must respect `limits`, must never read task.test_patch or
        task.gold_patch (the runner sets them to None), and must write diff.patch before
        returning even on failure (an empty diff is valid)."""
        ...
