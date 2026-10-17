# Spec: Arm adapter interface

Every arm (plain, controls, speckit, s2a and its ablations, future agents) implements one
class. The runner only ever talks to this interface. Seed file: `benchmark/abb/arms/base.py`
(keep it field-for-field identical to this spec and to `benchmark/config/limits.yaml`).

```python
# benchmark/abb/arms/base.py
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Protocol

ExitReason = Literal[
    "completed",          # agent ended its final turn normally
    "max_turns",          # hit the per-call or total turn budget
    "timeout",            # harness-initiated stop at the deadline (stopped_by_harness)
    "budget",             # --max-budget-usd tripped
    "agent_error",        # non-zero exit, error_during_execution, no result line (probe ok), orchestrator crash
    "usage_limited",      # model service refused (subscription window; probe failed): attempt kept under usage_limited/, trial re-queued, not counted in the primary metric (D-028)
    "harness_error",      # OUR bug (platform failure, transcript unparsable, model drift); trial is re-runnable
]

@dataclass
class Limits:
    timeout_minutes: int = 45              # whole trial, all phase calls and gates included
    max_turns_total: int = 200             # summed over all headless calls in the trial
    max_usd: float = 15.0                  # summed over all calls
    max_interventions: int = 2             # nudges per headless call
    max_interventions_per_trial: int = 4   # nudges per trial (comparable across arms)
    grade_timeout_minutes: int = 30        # used by the grader
    model: str = "claude-sonnet-5-5"       # pinned per run; final runs use claude-opus-5-5

@dataclass
class PhaseCall:
    """One headless invocation of the agent (an arm may make several)."""
    name: str                          # e.g. "plain", "speckit-specify", "s2a-implement-T2"
    session_id: str | None
    cmd: list[str]                     # argv actually executed (secrets redacted)
    started_at: str
    duration_ms: int
    num_turns: int
    tool_calls: int
    tool_errors: int                   # tool_result blocks with is_error
    cost_usd: float | None             # None when no result line was emitted
    cost_usd_imputed: float | None     # from per-message usage when cost_usd is None
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_write_tokens: int
    subtype: str                       # success | error_max_turns | error_max_budget_usd | ...
    interventions: int                 # nudges issued during this call
    interventions_log: list[dict]      # [{trigger: a|b|c|human, text, type?}]
    asked_question: bool
    rate_limit_retries: int            # api_retry events with error == rate_limit
    other_retries: int                 # other api_retry events
    claude_code_version: str           # from the init event
    background_models: list[str]       # modelUsage keys other than the pinned model (haiku only)
    model_drift: bool                  # any non-haiku foreign model in modelUsage → harness_error
    transcript_path: str               # transcript jsonl for this call (inside the trial dir)
    nudge_transcript_paths: list[str]
    prompt_sha256: str
    system_prompt_sha256: str          # environment.md + arm text, combined

@dataclass
class RunResult:
    arm: str
    task_id: str
    trial: int
    exit_reason: ExitReason
    diff_path: Path                    # scoped agent diff (input to grading)
    transcript_dir: Path
    workspace_base: str                # `git rev-parse HEAD` of the workspace after snapshot
    calls: list[PhaseCall] = field(default_factory=list)
    artifacts: dict[str, str] = field(default_factory=dict)
    # Harness-side verification the arm's own tooling performed (S2A gates; plain-gate hook):
    gate_gradle_runs: int = 0
    gate_seconds: float = 0.0
    # Derived totals (filled by the runner from calls):
    duration_ms: int = 0
    cost_usd: float | None = None      # None if any call lacks a result line
    cost_usd_imputed: float = 0.0      # always computable
    num_turns: int = 0
    tool_calls: int = 0
    interventions: int = 0
    asked_question: bool = False
    model: str = ""
    agent_version: str = ""
    notes: str = ""

class Arm(Protocol):
    name: str          # "plain" | "plain-guided" | "plain-gate" | "speckit" | "speckit-sdd" | "s2a" | "s2a-nomap" | "s2a-noverify" | "s2a-norepro"
    setup_kind: str | None   # None | "speckit-constitution" | "s2a-map"  (what one_time_setup produces; shared by arms with the same kind)

    def one_time_setup(self, repo_key: str, ws: "Workspace", limits: Limits) -> list[PhaseCall]:
        """Per-repo setup whose cost is reported separately. Idempotent; cached per
        (setup_kind, repo, setup_commit, environment fingerprint, prompt hash)."""

    def run(self, task: "Task", ws: "Workspace", limits: Limits) -> RunResult:
        """Attempt the task. Must respect Limits. Must never read task.test_patch or
        task.gold_patch. Must write diff.patch before returning, even on error."""
```

## Rules for all adapters

1. **Only `problem.md` reaches the agent.** The runner passes a `Task` whose `test_patch` /
   `gold_patch` attributes are `None` during `run()`.
2. **Same headless driver contract.** Adapters call `abb/harness/agent_driver.py:
   run_headless(...)`, or shell out to the `s2a` CLI whose `s2a/driver.py` implements the same
   contract and is tested on the same transcript fixtures. No adapter shells out to `claude`
   directly.
3. **Same environment preamble.** Every call of every arm gets `abb/arms/common/environment.md`
   as the first part of `--append-system-prompt`, byte-identical. An arm may append its own
   text after it; the s2a arm passes it with `--append-system-prompt-file`. The combined hash
   is recorded per call.
4. **Budget accounting.** The driver subtracts each call's turns/USD/time from the remaining
   `Limits`; when a limit is exhausted the adapter stops starting new calls and returns with
   the corresponding `exit_reason`. Gate/Gradle time run by the arm's own tooling counts against
   wall-clock and is reported as `gate_gradle_runs` / `gate_seconds`.
5. **Artifacts** go to `artifacts/` and are listed in `RunResult.artifacts`; artifact folders
   are excluded from the graded diff via `repos.workspace.diff_exclude`.
6. **Determinism of prompts.** Templates live in `abb/arms/<arm>/prompts/*.md` or in the `s2a`
   package (pinned by `s2a_git_sha`); every prompt's sha256 is recorded.
7. **No hidden retries, same policy for every arm.** The nudge protocol is the only retry and
   it is counted. A non-zero exit, a missing result line, or an orchestrator crash is
   `agent_error` — the product failed — and is **never re-run**. Only `harness_error` (our bug:
   platform failure, unparsable transcript, model drift) is re-queued once, identically for all arms.
   Retry counts are reported per arm.
8. **Transcripts are the source of truth.** `abb audit <run_id>` recomputes every `run.json`
   total from the verbatim transcripts and fails the run report on mismatch (see
   `headless-agent-driving.md`).
9. **Registration.** `abb/arms/registry.py` maps `name → class`. Adding an arm = one folder +
   one registry line.

## Arm list (v1)

| name | class | Description | setup_kind |
|---|---|---|---|
| `plain` | `arms.plain.PlainArm` | One headless call with the ticket and a short system prompt. | none |
| `plain-guided` (control) | `arms.plain.PlainArm(guided=True)` | Plain arm whose system prompt describes the S2A workflow in prose (map → locate → reproduce → spec → plan → small steps → self-review); no orchestrator, no gates. Separates "better instructions" from "harness". Same budget. | none |
| `plain-gate` (control, optional) | `arms.plain.PlainArm(gate=True)` | Plain arm plus **one harness-side check**: after the single call, the harness runs the unit tests of the modules the diff touches; on failure it resumes the session once with the failing test output (recorded as `gate_gradle_runs`, not as an intervention) and stops. Harness-side, not a Claude Code hook (hooks are stripped at snapshot, and arms never shell out to `claude`). Separates "orchestrator-run tests" from "workflow". | none |
| `speckit` | `arms.speckit.SpecKitArm` | `specify init` → bug path for bugfix tasks, SDD path otherwise → implement/converge loop. | `speckit-constitution` |
| `speckit-sdd` (optional) | `arms.speckit.SpecKitArm(path="sdd")` | Forces the SDD path for every task. | `speckit-constitution` |
| `s2a` | `arms.s2a.S2AArm` | Calls the orchestrator with `s2a` installed for the sandbox user: `s2a run … --map … --append-system-prompt-file …` with `S2A_AUTONOMOUS=1` in its environment; lifts `calls.jsonl` into `PhaseCall`s. See `specs/s2a-orchestrator.md` §9. | `s2a-map` (shared) |
| `s2a-nomap` | `arms.s2a.S2AArm(skip=["map"])` | `--skip map`; gates stay on. | none |
| `s2a-noverify` | `arms.s2a.S2AArm(skip=["verify"])` | `--skip verify` (also skips fix). | `s2a-map` (shared) |
| `s2a-norepro` (optional) | `arms.s2a.S2AArm(skip=["reproduce"])` | `--skip reproduce`. | `s2a-map` (shared) |

**Ablation budget rule.** An ablation arm passes `--max-turns 200 − <skipped stage cap>` so the
skipped stage's turns are not silently reallocated to the fix loop (`nomap` keeps 200: the map
is one-time setup). Per-stage turns are reported so the reader can see where budget went.

Which arms run in the final matrix is fixed in `docs/PREREG.md` before the freeze (default:
`plain`, `plain-guided`, `speckit`, `s2a`, `s2a-nomap`, `s2a-noverify`; the optional arms run if
budget allows, at 1 trial, and are labelled exploratory).
