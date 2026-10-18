"""Prompt rendering: `{{name}}` placeholders, map sections by heading, size caps (the map 40 kB, the diff
60 kB with per-file truncation and a --stat header, everything else 12 kB)."""
from __future__ import annotations

import re

CAPS = {"map": 40_000, "diff": 60_000}
DEFAULT_CAP = 12_000
PLACEHOLDER = re.compile(r"\{\{(\w+)\}\}")

QUESTION_POLICY = {
    "autonomous": ("Never ask questions: nobody can answer them. When something is unclear, make the most likely "
                   "assumption, record it under `## Assumptions` in your final message, and continue."),
    "interactive": ("If something is genuinely unclear, list it under `## Open questions` with your best assumption; "
                    "a human reviews the spec and the plan before implementation. Never stop to wait for an answer."),
}
ASSUMPTIONS_HEADING = {"autonomous": "Assumptions", "interactive": "Open questions"}


def cap(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n…[truncated: {len(text) - limit} more characters]\n"


def cap_diff(diff: str, stat: str, limit: int = CAPS["diff"]) -> str:
    """A --stat header, then each file's hunks, the largest files truncated first."""
    files = re.split(r"(?m)^(?=diff --git )", diff)
    files = [f for f in files if f.strip()]
    head = f"# git diff --stat\n{stat.strip()}\n\n"
    budget = limit - len(head)
    if sum(len(f) for f in files) <= budget:
        return head + "".join(files)
    per = max(800, budget // max(1, len(files)))
    out = []
    for f in files:
        out.append(f if len(f) <= per else f[:per] + f"\n…[file diff truncated: {len(f) - per} more characters]\n")
    return cap(head + "".join(out), limit)


def _norm_title(line: str) -> str:
    t = re.sub(r"^[#\s]+", "", line)
    t = re.sub(r"^\d+[.)]\s*", "", t)
    return re.sub(r"[*_`:]", "", t).strip().lower()


def sections(md: str) -> list[tuple[str, str]]:
    """(normalized title, body incl. heading) for every Markdown heading section."""
    out: list[tuple[str, str]] = []
    cur_title: str = ""
    cur: list[str] = []
    for line in md.splitlines(keepends=True):
        if re.match(r"^#{1,4}\s", line):
            if cur:
                out.append((cur_title, "".join(cur)))
            cur_title, cur = _norm_title(line), [line]
        else:
            cur.append(line)
    if cur:
        out.append((cur_title, "".join(cur)))
    return out


def extract(md: str, titles: list[str]) -> str:
    """The sections whose title starts with one of `titles` (case-insensitive); the whole text if none matches."""
    want = [t.lower() for t in titles]
    got = [body for title, body in sections(md) if any(title.startswith(w) for w in want)]
    return "".join(got) if got else md


def map_views(map_md: str) -> dict[str, str]:
    return {"map": cap(map_md, CAPS["map"]),
            "map_commands": cap(extract(map_md, ["commands", "test infrastructure"]), DEFAULT_CAP),
            "map_conventions": cap(extract(map_md, ["conventions", "pitfalls"]), DEFAULT_CAP)}


def render(template: str, values: dict[str, str], *, caps: dict[str, int] | None = None) -> tuple[str, list[str]]:
    """Fill every {{name}}; values are capped (per-name caps, else 12 kB). Returns (text, missing names)."""
    caps = {**CAPS, **(caps or {})}
    missing: list[str] = []

    def sub(m: re.Match) -> str:
        k = m.group(1)
        if k not in values:
            missing.append(k)
            return ""
        v = values[k] if values[k] is not None else ""
        return v if k in ("diff",) else cap(str(v), caps.get(k, DEFAULT_CAP))

    return PLACEHOLDER.sub(sub, template), missing


def mode_values(mode: str) -> dict[str, str]:
    return {"question_policy": QUESTION_POLICY[mode], "assumptions_or_questions_heading": ASSUMPTIONS_HEADING[mode]}
