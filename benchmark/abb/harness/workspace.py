"""Trial workspaces (specs/environments.md §4): history-free snapshot + per-trial dirs + ACLs.

Layout of a trial directory (TrialDirs): work/ (the repo, one commit tagged `base`), home/,
gradle-home/, claude-config/, agent-out/, plus transcript/ prompts/ artifacts/ written by the
harness after the run. With sandbox "user" the sandbox user gets MODIFY on exactly
work/home/gradle-home/claude-config/agent-out and RX on the trial dir itself.
"""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Literal

from abb import paths
from abb.config import RepoConfig, load_sandbox, load_toolchain
from abb.harness import gradle
from abb.harness.agent_env import TrialDirs, build_agent_env, claude_template_dir
from abb.harness.env import gradle_pristine
from abb.harness.platform import ProcResult, ProcSpec, get_platform, run_capture
from abb.harness.repos import extract_commit
from abb.log import get_logger

log = get_logger("abb.workspace")

AUTOMATION = [".claude/settings.json", ".claude/settings.local.json", ".claude/hooks", ".mcp.json"]
AGENT_INSTRUCTIONS = ["CLAUDE.md", "AGENTS.md", ".cursorrules", ".github/copilot-instructions.md"]
GIT_IDENTITY = {
    "GIT_AUTHOR_NAME": "abb", "GIT_AUTHOR_EMAIL": "abb@localhost", "GIT_COMMITTER_NAME": "abb",
    "GIT_COMMITTER_EMAIL": "abb@localhost", "GIT_AUTHOR_DATE": "2026-01-01T00:00:00Z",
    "GIT_COMMITTER_DATE": "2026-01-01T00:00:00Z",
}


class WorkspaceError(RuntimeError):
    pass


def gitconfig_text() -> str:
    tc = load_toolchain()
    sections: dict[str, list[str]] = {}
    for k, v in tc.git.global_config.items():
        sec, key = k.split(".", 1)
        sections.setdefault(sec, []).append(f"\t{key} = {v}")
    sections.setdefault("user", []).extend(["\tname = abb-agent", "\temail = abb-agent@localhost"])
    # the workspace is created by the harness user; git as the sandbox user would refuse it as "dubious ownership"
    sections.setdefault("safe", []).append("\tdirectory = *")
    sections.setdefault("init", []).append("\tdefaultBranch = main")
    return "".join(f"[{s}]\n" + "\n".join(lines) + "\n" for s, lines in sections.items())


def apply_trial_acls(dirs: TrialDirs, user: str) -> None:
    """sandbox.yaml acl for $TRIAL: list+traverse on every ancestor below work/ (D-036), RX on the trial
    dir itself, MODIFY on its five writable dirs, deny-write on claude-config/settings.json."""
    plat = get_platform()
    work = paths.work_dir().resolve()
    anc = dirs.root.resolve().parent
    chain = []
    while anc != work and work in anc.parents:
        chain.append(anc)
        anc = anc.parent
    for a in reversed(chain):
        plat.grant(a, user, "list")
    plat.grant(dirs.root, user, "rx", inherit=False)
    plat.owner_rights_none(dirs.root)
    for d in (dirs.work, dirs.home, dirs.gradle_home, dirs.claude_config, dirs.agent_out):
        plat.grant(d, user, "modify")
    settings = dirs.claude_config / "settings.json"
    if settings.exists():
        plat.deny_write(settings, user)


class Workspace:
    def __init__(self, repo: RepoConfig, trial_dir: Path, sandbox: Literal["user", "none"] = "none",
                 run_as: str | None = None) -> None:
        self.repo = repo
        self.dirs = TrialDirs(Path(trial_dir))
        self.sandbox = sandbox
        # the slot user that runs this trial (D-037: one per parallel slot); default the configured abb-agent
        self.run_as = run_as or load_sandbox().modes["user"].run_as
        self.peak_memory_mb = 0          # highest Job Object peak of any process run as the agent
        self.plat = get_platform()
        self.base: str | None = None

    # ------------------------------------------------------------------ git helpers (harness user)
    def git(self, *args: str, check: bool = True, timeout_s: int = 600, env_extra: dict | None = None) -> ProcResult:
        env = self.plat.harness_env({**GIT_IDENTITY, **(env_extra or {})})
        r = run_capture(self.plat, ["git", *args], cwd=self.dirs.work, env=env, timeout_s=timeout_s)
        if check and r.exit_code != 0:
            raise WorkspaceError(f"git {' '.join(args)} failed ({r.exit_code}): {r.stderr()[-1500:]}")
        return r

    # ------------------------------------------------------------------ snapshot
    def snapshot(self, base_commit: str, *, seed_transforms: bool | None = None) -> str:
        if self.dirs.root.exists() and any(self.dirs.root.iterdir()):
            raise WorkspaceError(f"{self.dirs.root} is not empty")
        self.dirs.root.mkdir(parents=True, exist_ok=True)
        extract_commit(self.repo, base_commit, self.dirs.work, exclude=self.repo.workspace.exclude_from_snapshot)
        for rel in AUTOMATION + (AGENT_INSTRUCTIONS if self.repo.workspace.strip_agent_instructions else []):
            p = self.dirs.work / rel
            if p.is_dir():
                shutil.rmtree(p)
            elif p.exists():
                p.unlink()
        (self.dirs.root / "home").mkdir()
        (self.dirs.home / ".gitconfig").write_text(gitconfig_text(), encoding="utf-8", newline="\n")
        (self.dirs.home / ".android").mkdir()
        cfg = ["-c", "core.autocrlf=false", "-c", "core.eol=lf", "-c", "core.longpaths=true", "-c", "core.filemode=false"]
        self.git("init", "-q", "-b", "main")
        for k in ("core.autocrlf=false", "core.eol=lf", "core.longpaths=true", "core.filemode=false"):
            self.git("config", *k.split("=", 1))
        self.git(*cfg, "add", "-A", timeout_s=1800)
        self.git(*cfg, "commit", "-q", "--no-verify", "-m", "base", timeout_s=1800)
        self.git("tag", "base")
        self.base = self.git("rev-parse", "HEAD").stdout().strip()
        self._seed_gradle_home(seed_transforms)
        self.dirs.claude_config.mkdir()
        for f in claude_template_dir().iterdir():
            if f.is_file():
                shutil.copyfile(f, self.dirs.claude_config / f.name)
        self.dirs.agent_out.mkdir()
        if self.sandbox == "user":
            self._apply_acls()
        return self.base

    def _seed_gradle_home(self, seed_transforms: bool | None) -> None:
        sb = load_sandbox()
        guh = self.dirs.gradle_home
        gradle.write_gradle_home(self.repo, guh, with_init=True)
        pristine = gradle_pristine(self.repo)
        for rel in sb.process.seed_gradle_home:  # wrapper/dists
            src = pristine / rel
            dst = guh / rel
            if rel.replace("\\", "/").rstrip("/") == "wrapper/dists":  # only this checkout's distribution (D-046)
                name = gradle.wrapper_dist_name(self.dirs.work)
                src, dst = src / name, dst / name
            if not src.exists():
                raise WorkspaceError(f"{src} missing: run `abb env warm {self.repo.key}`")
            shutil.copytree(src, dst, ignore=shutil.ignore_patterns("*.lck"))
        if sb.process.seed_transforms if seed_transforms is None else seed_transforms:
            for t in (pristine / "caches").glob("*/transforms"):
                shutil.copytree(t, guh / t.relative_to(pristine), ignore=shutil.ignore_patterns("*.lock"))

    def _apply_acls(self) -> None:
        apply_trial_acls(self.dirs, self.run_as)

    # ------------------------------------------------------------------ running things
    def agent_env(self, token: str | None, *, proxy: bool = True) -> dict[str, str]:
        return build_agent_env(self.dirs, token=token, repo=self.repo, proxy=proxy)

    def exec(self, argv: list[str], *, env: dict[str, str], timeout_s: int, out_dir: Path, cwd: Path | None = None,
             as_agent: bool = False, stdin_text: str | None = None, memory_mb: int | None = None) -> ProcResult:
        sb = load_sandbox()
        user = self.run_as if as_agent else None
        if as_agent and not Path(out_dir).resolve().is_relative_to(self.dirs.agent_out.resolve()):
            raise WorkspaceError(f"out_dir {out_dir} must be under {self.dirs.agent_out} (the only dir the sandbox user may write)")
        spec = ProcSpec(argv=argv, cwd=cwd or self.dirs.work, env=env, stdin_text=stdin_text, timeout_s=timeout_s,
                        memory_mb=memory_mb or sb.process.memory_mb, as_user=user, out_dir=out_dir,
                        interrupt=sb.process.interrupt, stop_file=self.dirs.stop_file, grace_s=sb.process.grace_s)
        r = self.plat.wait(self.plat.run(spec))
        if as_agent and r.peak_memory_mb:
            self.peak_memory_mb = max(self.peak_memory_mb, r.peak_memory_mb)
        return r

    def put(self, src: Path, dst_rel: str) -> None:
        dst = self.dirs.work / dst_rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)

    def get(self, src_rel: str, dst: Path) -> None:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(self.dirs.work / src_rel, dst)

    def apply_patch(self, patch: Path, *, check_only: bool = False) -> bool:
        args = ["apply", "--whitespace=nowarn"] + (["--check"] if check_only else []) + [str(patch)]
        return self.git(*args, check=False).exit_code == 0

    def diff(self, exclude: list[str] | None = None) -> str:
        excl = exclude if exclude is not None else self.repo.workspace.diff_exclude
        self.git("add", "-A", "-N")
        return self.git("diff", "--binary", "base", "--", ".", *[f":(exclude,glob){e}" for e in excl]).stdout()

    def changed_paths(self) -> list[str]:
        self.git("add", "-A", "-N")
        out = self.git("diff", "--name-only", "base").stdout()
        return [ln for ln in out.splitlines() if ln]

    def revoke(self) -> None:
        """End of trial (D-037): remove the sandbox user's grants on this trial before it runs anything else."""
        if self.sandbox != "user":
            return
        user = self.run_as
        for d in (self.dirs.work, self.dirs.home, self.dirs.gradle_home, self.dirs.claude_config, self.dirs.agent_out,
                  self.dirs.claude_config / "settings.json", self.dirs.root):
            if d.exists():
                self.plat.revoke(d, user)

    def cleanup(self) -> list[Path]:
        if (self.dirs.work / "gradlew.bat").exists() and self.dirs.gradle_home.exists():
            env = gradle.harness_gradle_env(self.repo, guh=self.dirs.gradle_home, home=self.dirs.home)
            gradle.run(gradle.expand_cmd("{gradlew} --stop", self.dirs.work), src=self.dirs.work, env=env,
                       out_dir=paths.work_dir() / "_cleanup" / self.dirs.root.name, timeout_s=300)
        self.revoke()
        return self.plat.rmtree_robust(self.dirs.root)
