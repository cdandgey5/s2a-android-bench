"""Parsers for the stage artifacts (pure functions; unit-tested with sample artifacts)."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

TYPES = ("bug", "feature", "refactor", "chore")
SIZES = ("S", "M", "L")


def strip_fence(text: str) -> str:
    """An artifact returned inside one ``` fence (as the prompts show the format) -> its content."""
    t = text.strip()
    m = re.fullmatch(r"```[\w-]*\n(.*?)\n?```", t, flags=re.S)
    return m.group(1) if m else t


def section(md: str, title: str) -> str:
    """Body of the `## <title>` section (case-insensitive, up to the next heading of the same or higher level)."""
    lines = md.splitlines()
    out, inside, level = [], False, 0
    for ln in lines:
        m = re.match(r"^(#{1,6})\s+(.*)$", ln)
        if m:
            if inside and len(m.group(1)) <= level:
                break
            if m.group(2).strip().lower().startswith(title.lower()):
                inside, level = True, len(m.group(1))
                continue
        if inside:
            out.append(ln)
    return "\n".join(out).strip()


def bullets(text: str) -> list[str]:
    return [re.sub(r"^\s*(?:[-*]|\d+[.)])\s+", "", ln).strip() for ln in text.splitlines()
            if re.match(r"^\s*(?:[-*]|\d+[.)])\s+\S", ln)]


# ---------------------------------------------------------------------------- ticket
def ticket_field(md: str, name: str) -> str | None:
    m = re.search(rf"(?im)^\s*{name}\s*:\s*([A-Za-z]+)", md)
    return m.group(1) if m else None


def ticket_type(md: str) -> str | None:
    v = (ticket_field(md, "type") or "").lower()
    return v if v in TYPES else None


def ticket_size(md: str) -> str | None:
    v = (ticket_field(md, "size") or "").upper()
    return v if v in SIZES else None


# ---------------------------------------------------------------------------- locate
# a Windows drive path (not the "s://" inside a URL) or a relative path with a file extension
PATH_TOKEN = re.compile(r"`?((?<![\w/])[A-Za-z]:[\\/](?![\\/])[^\s`—|,]+|[\w.\-]+(?:[\\/][\w.\-@$]+)+\.\w+)`?")
NEW_MARK = re.compile(r"\((?:new|to (?:be )?create[d]?)\)|\bnew file\b|\bto be created\b|\bdoes not exist yet\b", re.I)


def locate_candidates(md: str, *, include_new: bool = True) -> list[str]:
    """Paths of the ranked candidates: the first path-like token of each bullet, skipping URLs and elided paths
    (`a/.../B.java`); with include_new=False, bullets marked as files to create are left out."""
    body = section(md, "Candidates") or md
    out = []
    for item in bullets(body):
        if not include_new and NEW_MARK.search(item):
            continue
        for m in PATH_TOKEN.finditer(item):
            tok, start = m.group(1).rstrip(".:;"), m.start(1)
            if "://" in item[max(0, start - 8):start + 3] or "..." in tok or "…" in tok:
                continue
            first = tok.replace("\\", "/").split("/")[0]
            if "." in first.strip(".") and not re.fullmatch(r"[A-Za-z]:", first):
                continue   # a host name (`www.itunes.com/...`, `example.com/feed`), not a repository path
            out.append(tok)
            break
    return out


# ---------------------------------------------------------------------------- spec
@dataclass
class Criterion:
    id: str
    text: str
    verification: str


def criteria(md: str, prefix: str) -> list[Criterion]:
    out = []
    for m in re.finditer(rf"(?m)^\s*(?:[-*]\s*)?\**({prefix}\d+)\**[.:)]?\s+(.*)$", md):
        text = m.group(2).strip()
        ver = ""
        vm = re.search(r"(?:—|--|-)\s*verified by\s*:?\s*(.+)$", text, flags=re.I)
        if vm:
            ver = vm.group(1).strip()
        out.append(Criterion(m.group(1), text, ver))
    return out


# ---------------------------------------------------------------------------- plan
@dataclass
class PlanTask:
    id: str
    title: str
    approach: str = "modify"
    covers: list[str] = field(default_factory=list)
    files: list[str] = field(default_factory=list)
    module: str = ""
    task: str = ""
    tests: list[str] = field(default_factory=list)
    fixes_repro: bool = False


def plan_json(md: str) -> dict:
    """The last fenced ```json block that has a `tasks` list."""
    blocks = re.findall(r"```json\s*\n(.*?)\n```", md, flags=re.S)
    for b in reversed(blocks):
        try:
            d = json.loads(b)
        except ValueError:
            continue
        if isinstance(d, dict) and isinstance(d.get("tasks"), list):
            return d
    raise ValueError("no fenced ```json block with a `tasks` list")


def plan_tasks(d: dict) -> list[PlanTask]:
    out = []
    for i, t in enumerate(d["tasks"], 1):
        if not isinstance(t, dict):
            raise ValueError(f"task {i} is not an object")
        out.append(PlanTask(id=str(t.get("id") or f"T{i}"), title=str(t.get("title") or ""),
                            approach=str(t.get("approach") or "modify"), covers=[str(c) for c in t.get("covers") or []],
                            files=[str(f) for f in t.get("files") or []], module=str(t.get("module") or ""),
                            task=str(t.get("task") or ""), tests=[str(x) for x in t.get("tests") or []],
                            fixes_repro=bool(t.get("fixes_repro"))))
    return out


def plan_file_path(entry: str) -> tuple[str, bool]:
    """'path (new)' / 'path (modify)' -> (path, is_new)."""
    m = re.match(r"^\s*`?([^`(]+?)`?\s*(?:\((new|modify|modified|delete)\))?\s*$", entry, flags=re.I)
    path = (m.group(1) if m else entry).strip()
    return path, bool(m and (m.group(2) or "").lower() == "new")


# ---------------------------------------------------------------------------- verify
@dataclass
class Verdict:
    stated: str | None                      # ACCEPT | REJECT | None
    lines: dict[str, str]                   # AC1/UB1 -> PASS|FAIL
    defects: list[str]

    @property
    def derived(self) -> str | None:
        if self.stated is None:
            return None
        return "REJECT" if self.stated == "REJECT" or any(v == "FAIL" for v in self.lines.values()) else "ACCEPT"


def verdict(md: str) -> Verdict:
    lines = {}
    for m in re.finditer(r"(?m)^\s*(?:[-*]\s*)?\**((?:AC|UB)\d+)\**\s*[—:-]+\s*\**(PASS|FAIL)\**", md):
        lines[m.group(1)] = m.group(2)
    vm = re.findall(r"(?im)^\s*\**VERDICT\**\s*:\s*\**(ACCEPT|REJECT)\**", md)
    defects = [d for d in bullets(section(md, "Defects")) if d and not re.match(r"(?i)^\(?none\)?\.?$", d)]
    return Verdict(vm[-1].upper() if vm else None, lines, defects)


# ---------------------------------------------------------------------------- implement / fix messages
def notes(md: str, title: str) -> list[str]:
    return [b for b in bullets(section(md, title)) if b and not re.match(r"(?i)^\(?none\)?\.?$", b)]
