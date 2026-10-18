"""Build a task folder from a fix (upstream commit or authored patch) plus hidden tests written as files.

Used for Phase 7 tasks whose hidden tests are written by the benchmark author: mined tasks whose
upstream PR has no unit test (`hidden_tests: authored`) and fully authored tasks. The hidden test
files are given as (repo path, local file) pairs and become new-file hunks in `test.patch`, or
they replace an existing test file (the hunk is then a diff against the base version).

    uv run python scripts/make_task.py spec.yaml

spec.yaml: id, repo, base_commit, source, category, problem (path), gold (path to a patch, or
`upstream: <merge sha>` for the PR's non-test diff), tests: [{path, file}], f2p: [{module, test}],
p2p: [{module}], upstream: {...} (optional), tags: {...} (optional), notes (text).
"""
from __future__ import annotations

import difflib
import sys
from pathlib import Path

import yaml

from abb import paths
from abb.config import load_repo
from abb.harness.platform import get_platform, run_capture
from abb.harness.repos import ensure_mirror
from abb.harness.tasks import split_patch, task_dir


def git(m: Path, args: list[str]) -> str:
    r = run_capture(get_platform(), ["git", *args], cwd=m, timeout_s=600)
    if r.exit_code != 0:
        raise RuntimeError(f"git {' '.join(args[:3])}: {r.stderr()[-400:]}")
    return r.stdout()


def file_patch(path: str, old: str | None, new: str) -> str:
    """A git-style hunk that creates `path` (old None) or rewrites it from `old` to `new`."""
    new_lines = new.splitlines(keepends=True)
    if old is None:
        head = f"diff --git a/{path} b/{path}\nnew file mode 100644\n--- /dev/null\n+++ b/{path}\n"
        body = f"@@ -0,0 +1,{len(new_lines)} @@\n" + "".join("+" + ln for ln in new_lines)
        return head + (body if body.endswith("\n") else body + "\n")
    diff = difflib.unified_diff(old.splitlines(keepends=True), new_lines, f"a/{path}", f"b/{path}", n=3)
    return f"diff --git a/{path} b/{path}\n" + "".join(diff)


def main(spec_path: str) -> None:
    spec_file = Path(spec_path)
    spec = yaml.safe_load(spec_file.read_text(encoding="utf-8"))
    here = spec_file.parent
    repo = load_repo(spec["repo"])
    m = ensure_mirror(repo)
    base = spec["base_commit"]
    if "upstream_merge" in spec:
        diff = git(m, ["diff", "--binary", f"{spec['upstream_merge']}^1", spec["upstream_merge"]])
        _, gold = split_patch(diff, repo.tests.test_dirs)
    else:
        gold = (here / spec["gold"]).read_text(encoding="utf-8")
    hunks = []
    for t in spec["tests"]:
        new = (here / t["file"]).read_text(encoding="utf-8")
        try:
            old = git(m, ["show", f"{base}:{t['path']}"])
        except RuntimeError:
            old = None
        hunks.append(file_patch(t["path"], old, new))
    d = task_dir(spec["id"])
    d.mkdir(parents=True, exist_ok=False)
    (d / "gold.patch").write_text(gold, encoding="utf-8", newline="\n")
    (d / "test.patch").write_text("".join(hunks), encoding="utf-8", newline="\n")
    (d / "problem.md").write_text((here / spec["problem"]).read_text(encoding="utf-8"), encoding="utf-8", newline="\n")
    s2a_sha = git(paths.repo_clone(), ["log", "-1", "--format=%H", "--", "s2a"]).strip()
    task = {
        "id": spec["id"], "repo": repo.key, "base_commit": base, "source": spec["source"], "category": spec["category"],
        "upstream": spec.get("upstream") or {"issue_url": None, "pr_url": None, "fix_commit": None, "fix_date": None,
                                             "issue_created": None},
        "tags": spec.get("tags") or {}, "problem_statement": "problem.md", "test_patch": "test.patch",
        "gold_patch": "gold.patch", "fail_to_pass": spec["f2p"], "pass_to_pass": spec["p2p"],
        "limits": {"timeout_minutes": 45}, "needs_emulator": False, "split": "dev", "status": "draft",
        "created_with_s2a_sha": s2a_sha, "drafted_by": "agent", "drafted_with_model": "claude-opus-5-5",
        "hidden_tests": spec.get("hidden_tests", "authored"), "validation": None,
    }
    (d / "task.yaml").write_text(yaml.safe_dump(task, sort_keys=False, allow_unicode=True), encoding="utf-8",
                                 newline="\n")
    (d / "NOTES.md").write_text("# Provenance notes (not shown to agents)\n\n" + spec["notes"].strip() + "\n",
                                encoding="utf-8", newline="\n")
    if spec["source"] != "authored" or spec.get("license_note", True):
        (d / "LICENSE-NOTE.md").write_text(
            "# License note\n\n`test.patch` and `gold.patch` in this directory apply to "
            f"{repo.display_name} ({repo.url}), commit {base}, which is licensed under {repo.license}; "
            f"the patches are distributed under the same license.\n"
            + ("`gold.patch` is the upstream fix; `test.patch` was written for this benchmark.\n"
               if spec["source"] == "mined" else "Both patches and `problem.md` were written for this benchmark.\n")
            + "\nHarness code outside `tasks/` is licensed separately (see `benchmark/LICENSE`).\n",
            encoding="utf-8", newline="\n")
    print(d)


if __name__ == "__main__":
    main(sys.argv[1])
