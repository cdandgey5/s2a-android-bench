"""Path classification and scoped diffs (specs/grading-protocol.md, phases/phase-3 step 1).

classify(path, repo) -> "excluded" | "test" | "protected_build" | "build_config" | "source", in that
precedence: workflow folders an arm writes (diff_exclude) never reach grading; test dirs are
reverted; protected build paths and build files are restored unless gold.patch touches them.
"""
from __future__ import annotations

import re

from abb.config import RepoConfig
from abb.harness.tasks import added_lines, patch_sections
from abb.util import glob_match

SUSPECT = re.compile(r"testOptions|unitTests|exclude\(|enabled\s*=\s*false|ignoreFailures|allWarningsAsErrors")


def classify(path: str, repo: RepoConfig) -> str:
    if glob_match(path, repo.workspace.diff_exclude):
        return "excluded"
    if glob_match(path, repo.tests.test_dirs):
        return "test"
    if glob_match(path, repo.tests.protected_build_paths):
        return "protected_build"
    if glob_match(path, repo.tests.build_config_files):
        return "build_config"
    return "source"


def scoped_diff(ws, repo: RepoConfig) -> str:
    """The graded diff: everything changed vs the `base` tag, untracked files included, excluded paths dropped."""
    return ws.diff(repo.workspace.diff_exclude)


def drop_excluded(diff_text: str, repo: RepoConfig) -> str:
    return "".join(sec for path, sec in patch_sections(diff_text).items() if classify(path, repo) != "excluded")


def suspect_test_config(diff_text: str, repo: RepoConfig, only_paths: set[str] | None = None) -> list[str]:
    """Added lines in build_config files that look like they disable or weaken tests."""
    hits = []
    for path, sec in patch_sections(diff_text).items():
        if classify(path, repo) not in ("build_config", "protected_build"):
            continue
        if only_paths is not None and path not in only_paths:
            continue
        for ln in added_lines(sec):
            if SUSPECT.search(ln):
                hits.append(f"{path}: {ln.strip()[:120]}")
    return hits


def diff_stats(diff_text: str) -> dict:
    files = list(patch_sections(diff_text))
    ins = sum(1 for ln in diff_text.splitlines() if ln.startswith("+") and not ln.startswith("+++"))
    dels = sum(1 for ln in diff_text.splitlines() if ln.startswith("-") and not ln.startswith("---"))
    return {"files": len(files), "insertions": ins, "deletions": dels, "paths": files}
