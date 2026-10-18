"""Build tests/fixtures/grading/<task>/*.patch: the seven sanity-matrix inputs (specs/grading-protocol.md).

    uv run python scripts/make_grading_fixtures.py

Works in a scratch snapshot of the task's base commit (git archive + git init), applies gold.patch,
makes each variant's edit, and records `git diff --binary base` as the fixture.
"""
from __future__ import annotations

import re
from pathlib import Path

from abb import paths
from abb.config import load_repo, load_task
from abb.harness.workspace import Workspace
from abb.util import stamp

OUT = paths.fixtures_dir() / "grading"


def _ws(task_id: str) -> Workspace:
    t = load_task(task_id)
    ws = Workspace(load_repo(t.repo), paths.work_dir() / "fixtures" / f"{stamp()}-{task_id}", "none")
    ws.snapshot(t.base_commit)
    return ws


def _diff(ws: Workspace) -> str:
    ws.git("add", "-A")
    return ws.git("diff", "--binary", "--cached", "base").stdout()


def _reset(ws: Workspace) -> None:
    ws.git("reset", "-q", "--hard", "base")
    ws.git("clean", "-fdq")


def _edit(ws: Workspace, rel: str, old: str, new: str, count: int = 1) -> None:
    p = ws.dirs.work / rel
    s = p.read_text(encoding="utf-8")
    assert old in s, (rel, old[:60])
    p.write_text(s.replace(old, new, count), encoding="utf-8", newline="\n")


def build(task_id: str, variants: dict) -> None:
    t = load_task(task_id)
    gold = paths.tasks_dir() / task_id / t.gold_patch
    ws = _ws(task_id)
    out = OUT / task_id
    out.mkdir(parents=True, exist_ok=True)
    try:
        for name, fn in variants.items():
            _reset(ws)
            if name != "empty" and fn is not None and name != "interface_mismatch":
                assert ws.apply_patch(gold), "gold does not apply"
            if fn:
                fn(ws)
            (out / f"{name}.patch").write_bytes(_diff(ws).encode("utf-8"))
            print(task_id, name, (out / f"{name}.patch").stat().st_size, "bytes")
    finally:
        ws.cleanup()


def gradlew_edit(ws: Workspace) -> None:
    p = ws.dirs.work / "gradlew"
    p.write_bytes(p.read_bytes() + b"\n# edited by the agent\n")


# ---------------------------------------------------------------------------- antennapod-0000
DP = "parser/feed/src/main/java/de/danoeh/antennapod/parser/feed/util/DurationParser.java"
DPT = "parser/feed/src/test/java/de/danoeh/antennapod/parser/feed/element/util/DurationParserTest.java"
ITUNES = "parser/feed/src/main/java/de/danoeh/antennapod/parser/feed/namespace/Itunes.java"


def seed_regression(ws: Workspace) -> None:
    """F2P (decimal comma) passes, but a P2P test (fractional seconds with '.') breaks."""
    s = (ws.dirs.work / DP).read_text(encoding="utf-8")
    start = s.index("    private static long toMillis(String seconds) {")
    end = s.index("\n    }\n", start) + len("\n    }\n")
    s = s[:start] + '''    private static long toMillis(String seconds) {
        if (seconds.contains(",")) {
            float value = Float.parseFloat(seconds.replace(',', '.'));
            return SECONDS.toMillis((long) value) + (long) ((value % 1) * 1000);
        }
        if (seconds.contains(".")) {
            return SECONDS.toMillis((long) Float.parseFloat(seconds));
        }
        return SECONDS.toMillis(Long.parseLong(seconds));
    }
''' + s[end:]
    (ws.dirs.work / DP).write_text(s, encoding="utf-8", newline="\n")


def seed_interface_mismatch(ws: Workspace) -> None:
    """A correct fix that also renames the public entry point the hidden test calls."""
    _edit(ws, DP, "    private static long toMillis(String seconds) {\n",
          "    private static long toMillis(String seconds) {\n        seconds = seconds.replace(',', '.');\n")
    _edit(ws, DP, "public static long inMillis(String durationStr)", "public static long parseMillis(String durationStr)")
    _edit(ws, ITUNES, "DurationParser.inMillis(", "DurationParser.parseMillis(")


SEED = {
    "gold": lambda ws: None,
    "empty": None,
    "gold_plus_delete_test": lambda ws: (ws.dirs.work / DPT).unlink(),
    "compile_break": lambda ws: _edit(ws, DP, "public class DurationParser {", "public class DurationParser {\n    int broken = ;"),
    "regression": None,  # replaced below (needs the base file, not gold)
    "gradlew_edit": gradlew_edit,
    "interface_mismatch": seed_interface_mismatch,
}

# ---------------------------------------------------------------------------- antennapod-0005
FP = "storage/database/src/main/java/de/danoeh/antennapod/storage/database/FeedItemPermutors.java"
FPT = "storage/database/src/test/java/de/danoeh/antennapod/storage/database/FeedItemPermutorsTest.java"


def refactor_regression(ws: Workspace) -> None:
    """getComparator exists and agrees with getPermutor (F2P passes), but title A-Z is now reversed (P2P breaks)."""
    _edit(ws, FP, "            case EPISODE_TITLE_A_Z:\n                return (f1, f2) -> itemTitle(f1).compareTo(itemTitle(f2));",
          "            case EPISODE_TITLE_A_Z:\n                return (f1, f2) -> itemTitle(f2).compareTo(itemTitle(f1));")


def refactor_interface_mismatch(ws: Workspace) -> None:
    gold = paths.tasks_dir() / "antennapod-0005" / "gold.patch"
    assert ws.apply_patch(gold)
    s = (ws.dirs.work / FP).read_text(encoding="utf-8")
    s = re.sub(r"\bgetComparator\b", "comparatorFor", s)
    (ws.dirs.work / FP).write_text(s, encoding="utf-8", newline="\n")


REFACTOR = {
    "gold": lambda ws: None,
    "empty": None,
    "gold_plus_delete_test": lambda ws: (ws.dirs.work / FPT).unlink(),
    "compile_break": lambda ws: _edit(ws, FP, "public class FeedItemPermutors {",
                                      "public class FeedItemPermutors {\n    int broken = ;"),
    "regression": refactor_regression,
    "gradlew_edit": gradlew_edit,
    "interface_mismatch": refactor_interface_mismatch,
}


def main() -> None:
    seed = dict(SEED)

    def seed_regression_from_base(ws: Workspace) -> None:
        seed_regression(ws)
    seed["regression"] = seed_regression_from_base
    # the seed's regression variant replaces the fix itself, so it starts from base, not from gold
    build("antennapod-0000", {k: v for k, v in seed.items() if k != "regression"})
    ws = _ws("antennapod-0000")
    try:
        seed_regression(ws)
        (OUT / "antennapod-0000" / "regression.patch").write_bytes(_diff(ws).encode("utf-8"))
        print("antennapod-0000 regression (from base)")
    finally:
        ws.cleanup()
    build("antennapod-0005", REFACTOR)


if __name__ == "__main__":
    main()
