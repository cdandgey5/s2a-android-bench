"""s2a is a product: its code, prompts and configuration never mention how someone might be measuring it."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN = re.compile(r"hidden[ _-]?tests?|grading|graded|grader|gold[ _-]?patch|test[._]patch|"
                       r"\b(?:antennapod|wikipedia)-\d{4}\b|\bABB_[A-Z]", re.I)


def test_no_measurement_concepts_in_the_product() -> None:
    files = [p for p in (ROOT / "s2a").rglob("*") if p.is_file() and p.suffix in (".py", ".md", ".yaml", ".yml")]
    files += [p for p in (ROOT / "tests").glob("*.py") if p.name != Path(__file__).name]
    hits = [f"{p.relative_to(ROOT)}:{i}: {ln.strip()[:100]}" for p in files
            for i, ln in enumerate(p.read_text(encoding="utf-8").splitlines(), 1) if FORBIDDEN.search(ln)]
    assert len(files) > 20 and hits == []
