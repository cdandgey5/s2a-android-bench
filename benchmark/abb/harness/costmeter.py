"""Running est. USD total of a run (thread-safe); `--max-usd` stops launching new trials once crossed
(phases/phase-8-runner.md step 6). The numbers are Claude Code's client-side estimates, never a bill."""
from __future__ import annotations

import threading


class CostMeter:
    def __init__(self, max_usd: float | None = None, spent: float = 0.0) -> None:
        self.max_usd = max_usd
        self._spent = float(spent)
        self._lock = threading.Lock()

    def add(self, usd: float | None) -> float:
        with self._lock:
            self._spent += float(usd or 0.0)
            return self._spent

    @property
    def spent(self) -> float:
        with self._lock:
            return round(self._spent, 4)

    def crossed(self) -> bool:
        return self.max_usd is not None and self.spent >= self.max_usd
