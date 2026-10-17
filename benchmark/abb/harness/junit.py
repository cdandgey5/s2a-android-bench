"""JUnit XML -> {test_id: status} (xml.etree only)."""
from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

Status = Literal["passed", "failed", "error", "skipped"]
_RANK = {"passed": 0, "skipped": 1, "failed": 2, "error": 3}


@dataclass
class JUnitResult:
    tests: dict[str, Status] = field(default_factory=dict)   # "<classname>.<name>" -> status
    files: list[str] = field(default_factory=list)
    times_ok: bool = True                                    # every testcase carried a `time` attribute

    def counts(self) -> dict[str, int]:
        c = {"passed": 0, "failed": 0, "error": 0, "skipped": 0}
        for s in self.tests.values():
            c[s] += 1
        c["total"] = len(self.tests)
        return c

    def status_of(self, cls: str, method: str | None = None) -> Status | None:
        """A method's status, or the worst status over a whole class; None if nothing ran."""
        if method:
            hits = [s for k, s in self.tests.items() if k == f"{cls}.{method}" or k.startswith(f"{cls}.{method}[")]
        else:
            hits = [s for k, s in self.tests.items() if k.rsplit(".", 1)[0] == cls or k.startswith(cls + "$")
                    or (k.startswith(cls + ".") and "[" in k)]
        if not hits:
            return None
        return max(hits, key=lambda s: _RANK[s])


def _case_status(tc: ET.Element) -> Status:
    if tc.find("error") is not None:
        return "error"
    if tc.find("failure") is not None:
        return "failed"
    if tc.find("skipped") is not None:
        return "skipped"
    return "passed"


def parse_file(p: Path, into: JUnitResult) -> None:
    root = ET.parse(p).getroot()
    suites = [root] if root.tag == "testsuite" else list(root.iter("testsuite"))
    for suite in suites:
        for tc in suite.iter("testcase"):
            cls = tc.get("classname") or suite.get("name") or "?"
            name = tc.get("name") or "?"
            if tc.get("time") is None:
                into.times_ok = False
            key = f"{cls}.{name}"
            st = _case_status(tc)
            prev = into.tests.get(key)
            into.tests[key] = st if prev is None else max(prev, st, key=lambda s: _RANK[s])
    into.files.append(str(p))


def parse_dir(d: Path) -> JUnitResult:
    r = JUnitResult()
    for p in sorted(Path(d).glob("TEST-*.xml")):
        parse_file(p, r)
    return r
