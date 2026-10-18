"""What every stage and gate receives."""
from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from pathlib import Path

from s2a.driver import Driver
from s2a.parse import PlanTask
from s2a.platform import Platform
from s2a.profile import Pipeline, Profile
from s2a.state import RunState


@dataclass
class Ctx:
    repo: Path
    run_dir: Path
    state: RunState
    pipeline: Pipeline
    profile: Profile
    driver: Driver
    plat: Platform
    system: str                                  # --append-system-prompt-file text + rendered preamble
    stop: threading.Event
    map_md: str | None = None
    map_json: dict | None = None
    tasks: list[PlanTask] = field(default_factory=list)
    gate_seq: int = 0

    @property
    def s2a_dir(self) -> Path:
        return self.repo / ".s2a"

    def art(self, name: str) -> Path:
        return self.run_dir / name

    def read(self, name: str) -> str:
        p = self.art(name)
        return p.read_text(encoding="utf-8") if p.exists() else ""

    def write(self, name: str, text: str) -> Path:
        p = self.art(name)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text if text.endswith("\n") else text + "\n", encoding="utf-8", newline="\n")
        return p

    def write_json(self, name: str, data) -> Path:
        return self.write(name, json.dumps(data, indent=2, default=str))

    @property
    def ticket_type(self) -> str:
        return self.state.ticket_type or "feature"

    def save(self) -> None:
        b = self.driver.budget
        self.state.used.update({"turns": b.turns_used, "usd": round(b.usd_used, 6), "nudges": b.nudges_used})
        self.state.save(self.run_dir)
