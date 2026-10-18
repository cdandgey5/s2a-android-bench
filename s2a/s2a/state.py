"""`.s2a/runs/<run_id>/state.json` (atomic writes) and its human-readable mirror `progress.md`."""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path

EXIT_REASONS = ("completed", "max_turns", "timeout", "budget", "agent_error", "harness_error", "gate_failed",
                "paused", "usage_limited", "auth_failed")


@dataclass
class RunState:
    run_id: str
    prompt: str
    mode: str
    profile: str
    branch: str
    base_commit: str
    model: str
    limits: dict
    repo: str
    skip: list[str] = field(default_factory=list)
    map_path: str | None = None
    append_system_prompt_file: str | None = None
    used: dict = field(default_factory=lambda: {"turns": 0, "usd": 0.0, "seconds": 0.0, "nudges": 0})
    stages: dict = field(default_factory=dict)
    assumptions: list[str] = field(default_factory=list)
    learned: list[str] = field(default_factory=list)
    ticket_type: str | None = None
    verdict: str | None = None
    exit_code: int | None = None
    exit_reason: str | None = None
    notes: list[str] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""

    # ------------------------------------------------------------------ persistence
    @staticmethod
    def path(run_dir: Path) -> Path:
        return run_dir / "state.json"

    def save(self, run_dir: Path) -> None:
        from s2a.driver import utcnow_iso

        self.updated_at = utcnow_iso()
        p = self.path(run_dir)
        tmp = p.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(asdict(self), indent=2, default=str), encoding="utf-8")
        os.replace(tmp, p)
        (run_dir / "progress.md").write_text(self.progress_md(), encoding="utf-8", newline="\n")

    @classmethod
    def load(cls, run_dir: Path) -> "RunState":
        data = json.loads(cls.path(run_dir).read_text(encoding="utf-8"))
        return cls(**data)

    # ------------------------------------------------------------------ stage bookkeeping
    def stage(self, name: str) -> dict:
        return self.stages.setdefault(name, {"status": "pending"})

    def mark(self, name: str, status: str, **kw) -> None:
        s = self.stage(name)
        s["status"] = status
        s.update(kw)

    def is_done(self, name: str) -> bool:
        return self.stage(name).get("status") in ("done", "done_with_failures", "skipped", "unavailable")

    def next_stage(self, order: list[str]) -> str | None:
        for n in order:
            if not self.is_done(n):
                return n
        return None

    # ------------------------------------------------------------------ progress.md
    def progress_md(self) -> str:
        lines = [f"# s2a run {self.run_id}", "", f"- Prompt: {self.prompt.strip().splitlines()[0][:200] if self.prompt.strip() else ''}",
                 f"- Mode: {self.mode} · profile: {self.profile} · model: {self.model} · base: {self.base_commit[:12]}",
                 f"- Used: {self.used.get('turns', 0)} turns, est. ${self.used.get('usd', 0):.4f}, "
                 f"{int(self.used.get('seconds', 0))} s", ""]
        lines += ["## Stages", "", "| stage | status | detail |", "|---|---|---|"]
        for name, s in self.stages.items():
            detail = {k: v for k, v in s.items() if k not in ("status", "calls", "task_status", "gates")}
            lines.append(f"| {name} | {s.get('status')} | {json.dumps(detail, default=str)[:160]} |")
        impl = self.stages.get("implement") or {}
        if impl.get("task_status"):
            lines += ["", "## Tasks", ""] + [f"- {k}: {v}" for k, v in impl["task_status"].items()]
        if self.learned:
            lines += ["", "## Learned (from implement sessions)", ""] + [f"- {x}" for x in self.learned[-30:]]
        if self.assumptions:
            lines += ["", "## Assumptions", ""] + [f"- {x}" for x in self.assumptions[-30:]]
        if self.notes:
            lines += ["", "## Notes", ""] + [f"- {x}" for x in self.notes[-30:]]
        if self.exit_reason:
            lines += ["", f"**Ended:** {self.exit_reason} (exit {self.exit_code}); verdict: {self.verdict}"]
        return "\n".join(lines) + "\n"
