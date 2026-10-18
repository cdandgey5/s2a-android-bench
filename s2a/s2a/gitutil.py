"""git in the target repository. The orchestrator makes every commit (local identity s2a); `.s2a/` is
excluded through .git/info/exclude (never .gitignore, which would change the repository)."""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

IDENTITY = ["-c", "user.name=s2a", "-c", "user.email=s2a@local", "-c", "commit.gpgsign=false"]


class GitError(RuntimeError):
    pass


def git(repo: Path, *args: str, check: bool = True, timeout_s: float = 300, env: dict | None = None) -> str:
    r = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, encoding="utf-8", errors="replace",
                       timeout=timeout_s, env=env)
    if check and r.returncode != 0:
        raise GitError(f"git {' '.join(args[:4])} failed ({r.returncode}): {r.stderr.strip()[-400:]}")
    return r.stdout


def head(repo: Path) -> str:
    return git(repo, "rev-parse", "HEAD").strip()


def exclude_s2a(repo: Path) -> None:
    info = repo / ".git" / "info"
    info.mkdir(parents=True, exist_ok=True)
    ex = info / "exclude"
    text = ex.read_text(encoding="utf-8") if ex.exists() else ""
    if ".s2a/" not in text.splitlines():
        ex.write_text(text + ("" if text.endswith("\n") or not text else "\n") + ".s2a/\n", encoding="utf-8")


def status_porcelain(repo: Path) -> list[str]:
    return [ln for ln in git(repo, "status", "--porcelain", "--untracked-files=all").splitlines() if ln.strip()]


def _scratch_index(repo: Path) -> dict:
    """An env whose GIT_INDEX_FILE is a copy of the index with untracked files added as intent-to-add:
    `git diff <rev>` then sees new files, and the repository's real index is never touched (an
    intent-to-add entry there would make `git checkout -- .` empty the file)."""
    real = repo / ".git" / "index"
    tmp = repo / ".s2a" / "scratch-index"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    if real.exists():
        shutil.copyfile(real, tmp)
    else:
        tmp.unlink(missing_ok=True)
    env = {**os.environ, "GIT_INDEX_FILE": str(tmp)}
    git(repo, "add", "-A", "-N", env=env)
    return env


def changed_since(repo: Path, rev: str) -> list[str]:
    """Paths changed between `rev` and the working tree (committed, staged, unstaged and untracked)."""
    out = git(repo, "diff", "--name-only", rev, env=_scratch_index(repo))
    return [ln for ln in out.splitlines() if ln and not ln.startswith(".s2a/")]


def diff(repo: Path, rev: str, *, paths: list[str] | None = None, stat: bool = False) -> str:
    args = ["diff", "--stat" if stat else "--no-color", rev, "--", "."] + [":(exclude).s2a"]
    if paths:
        args = ["diff", "--stat" if stat else "--no-color", rev, "--", *paths]
    return git(repo, *args, env=_scratch_index(repo))


def reset_hard_clean(repo: Path, rev: str | None = None) -> None:
    """Back to `rev` (default HEAD), untracked files removed, .s2a kept."""
    git(repo, "reset", "-q", "--hard", rev or "HEAD")
    git(repo, "clean", "-fdq", "-e", ".s2a")


def checkout_clean(repo: Path) -> None:
    git(repo, "checkout", "-q", "--", ".")
    git(repo, "clean", "-fdq", "-e", ".s2a")


def commit_all(repo: Path, message: str) -> str | None:
    """`git add -A && git commit` with the s2a identity; None when there is nothing to commit."""
    git(repo, "add", "-A")
    if not git(repo, "diff", "--cached", "--name-only").strip():
        return None
    git(repo, *IDENTITY, "commit", "-q", "--no-verify", "-m", message)
    return head(repo)


def commit_paths(repo: Path, paths: list[str], message: str) -> str | None:
    if not paths:
        return None
    git(repo, "reset", "-q")
    git(repo, "add", "--", *paths)
    if not git(repo, "diff", "--cached", "--name-only").strip():
        return None
    git(repo, *IDENTITY, "commit", "-q", "--no-verify", "-m", message)
    return head(repo)


def ensure_branch(repo: Path, branch: str) -> None:
    cur = git(repo, "rev-parse", "--abbrev-ref", "HEAD").strip()
    if cur == branch:
        return
    exists = subprocess.run(["git", "rev-parse", "--verify", "--quiet", branch], cwd=repo, capture_output=True).returncode == 0
    git(repo, "checkout", "-q", branch) if exists else git(repo, "checkout", "-q", "-b", branch)
