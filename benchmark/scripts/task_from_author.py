"""Turn an authoring checkout (C:/abb/work/author/<id>: a git repo whose commit `base` is the upstream
base commit, with the reference fix and hidden tests left in the working tree) into tasks/<id>/.

    uv run python scripts/task_from_author.py <author_dir> --id <task id> --repo <repo> --base <sha>
        --category <cat> --f2p <module>=<TestClass> [...] --p2p <module> [...] [--new-surface]

gold.patch = every changed or new file outside src/test (and outside _task/); test.patch = every
changed or new file under src/test. problem.md and NOTES.md come from <author_dir>/_task/.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import yaml

from abb import paths
from abb.config import load_repo
from abb.harness.platform import get_platform, run_capture
from abb.harness.tasks import task_dir


def git(d: Path, args: list[str]) -> str:
    r = run_capture(get_platform(), ["git", *args], cwd=d, timeout_s=600)
    if r.exit_code != 0:
        raise RuntimeError(f"git {' '.join(args[:3])}: {r.stderr()[-400:]}")
    return r.stdout()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("author_dir")
    ap.add_argument("--id", required=True)
    ap.add_argument("--repo", required=True)
    ap.add_argument("--base", required=True)
    ap.add_argument("--category", required=True)
    ap.add_argument("--f2p", nargs="+", required=True)
    ap.add_argument("--p2p", nargs="+", required=True)
    ap.add_argument("--new-surface", action="store_true")
    a = ap.parse_args()
    d = Path(a.author_dir)
    repo = load_repo(a.repo)
    git(d, ["add", "-N", "--", ".", ":(exclude)_task"])  # untracked new files show up in `git diff`
    gold = git(d, ["diff", "--binary", "HEAD", "--", ".", ":(exclude)_task", ":(exclude)**/src/test/**"])
    test = git(d, ["diff", "--binary", "HEAD", "--", ":(glob)**/src/test/**"])
    if not gold.strip() or not test.strip():
        raise SystemExit(f"empty {'gold' if not gold.strip() else 'test'} patch from {d}")
    out = task_dir(a.id)
    out.mkdir(parents=True, exist_ok=False)
    (out / "gold.patch").write_text(gold, encoding="utf-8", newline="\n")
    (out / "test.patch").write_text(test, encoding="utf-8", newline="\n")
    (out / "problem.md").write_text((d / "_task" / "problem.md").read_text(encoding="utf-8"), encoding="utf-8",
                                    newline="\n")
    notes = (d / "_task" / "NOTES.md").read_text(encoding="utf-8") if (d / "_task" / "NOTES.md").exists() else ""
    (out / "NOTES.md").write_text("# Provenance notes (not shown to agents)\n\n- Source: authored for this benchmark "
                                  f"(drafted by the building agent with claude-opus-5-5 at base {a.base}).\n\n"
                                  + notes.strip() + "\n", encoding="utf-8", newline="\n")
    s2a_sha = git(paths.repo_clone(), ["log", "-1", "--format=%H", "--", "s2a"]).strip()
    f2p = []
    for item in a.f2p:
        mod, _, cls = item.partition("=")
        f2p.append({"module": ":" + mod.lstrip(":"), "test": cls})
    task = {
        "id": a.id, "repo": repo.key, "base_commit": a.base, "source": "authored", "category": a.category,
        "upstream": {"issue_url": None, "pr_url": None, "fix_commit": None, "fix_date": None, "issue_created": None},
        "tags": {"new_surface": True} if a.new_surface else {}, "problem_statement": "problem.md",
        "test_patch": "test.patch", "gold_patch": "gold.patch", "fail_to_pass": f2p,
        "pass_to_pass": [{"module": ":" + m.lstrip(":")} for m in a.p2p], "limits": {"timeout_minutes": 45},
        "needs_emulator": False, "split": "dev", "status": "draft", "created_with_s2a_sha": s2a_sha,
        "drafted_by": "agent", "drafted_with_model": "claude-opus-5-5", "hidden_tests": "authored", "validation": None,
    }
    (out / "task.yaml").write_text(yaml.safe_dump(task, sort_keys=False, allow_unicode=True), encoding="utf-8",
                                   newline="\n")
    (out / "LICENSE-NOTE.md").write_text(
        "# License note\n\n`test.patch` and `gold.patch` in this directory apply to "
        f"{repo.display_name} ({repo.url}), commit {a.base}, which is licensed under {repo.license}; the patches are "
        "distributed under the same license. Both patches and `problem.md` were written for this benchmark.\n\n"
        "Harness code outside `tasks/` is licensed separately (see `benchmark/LICENSE`).\n", encoding="utf-8",
        newline="\n")
    print(out, "gold files:", gold.count("diff --git"), "test files:", test.count("diff --git"))


if __name__ == "__main__":
    main()
