"""Compose and run Gradle (`gradlew.bat`) through the platform layer (specs/task-format.md, "Test selection").

Repo-specific knowledge (task names, JDK, gradle.properties) comes only from repos/<repo>.yaml.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

from abb import paths
from abb.config import RepoConfig
from abb.harness.platform import ProcResult, ProcSpec, get_platform

GRADLE_TIMEOUT_S = 2 * 3600


def render_props(repo: RepoConfig) -> str:
    """`gradle_user_home_props` without the explanatory `#` comments (Java properties would keep them in values)."""
    lines = []
    for ln in repo.toolchain.gradle_user_home_props.splitlines():
        body = ln.split("#", 1)[0].rstrip()
        if body.strip():
            lines.append(body.strip())
    return "\n".join(lines) + "\n"


def robolectric_dir(repo: RepoConfig) -> Path:
    return paths.caches_dir() / "robolectric" / repo.key


def init_script(repo: RepoConfig) -> str:
    """`init.d/abb.gradle` for trial and pristine Gradle homes: Robolectric strictly offline from the flat jar dir."""
    d = robolectric_dir(repo).as_posix()
    return (
        "// written by abb (specs/environments.md §3): Robolectric never downloads inside a trial or at grading\n"
        "allprojects {\n"
        "    tasks.withType(Test).configureEach {\n"
        '        systemProperty("robolectric.offline", "true")\n'
        f'        systemProperty("robolectric.dependency.dir", "{d}")\n'
        "    }\n"
        "}\n"
    )


def write_gradle_home(repo: RepoConfig, guh: Path, *, with_init: bool) -> None:
    guh.mkdir(parents=True, exist_ok=True)
    (guh / "gradle.properties").write_text(render_props(repo), encoding="utf-8", newline="\n")
    if with_init:
        (guh / "init.d").mkdir(exist_ok=True)
        (guh / "init.d" / "abb.gradle").write_text(init_script(repo), encoding="utf-8", newline="\n")


def harness_gradle_env(repo: RepoConfig, *, guh: Path, home: Path) -> dict[str, str]:
    """Environment for Gradle run BY THE HARNESS (warm, validation, grading). Agent blocks: agent_env.py."""
    plat = get_platform()
    jh = paths.tools_dir() / f"jdk{repo.toolchain.jdk}"
    env = plat.harness_env({
        **repo.build.env,
        "JAVA_HOME": str(jh),
        "ANDROID_HOME": str(paths.tools_dir() / "android-sdk"),
        "ANDROID_SDK_ROOT": str(paths.tools_dir() / "android-sdk"),
        "GRADLE_USER_HOME": str(guh),
        "JAVA_TOOL_OPTIONS": f"-Duser.home={home} -Dfile.encoding=UTF-8",
        "ANDROID_USER_HOME": str(home / ".android"),
        "TEMP": str(home / "tmp"),
        "TMP": str(home / "tmp"),
    })
    env["PATH"] = str(jh / "bin") + os.pathsep + plat.harness_env().get("PATH", "")
    (home / ".android").mkdir(parents=True, exist_ok=True)
    (home / "tmp").mkdir(parents=True, exist_ok=True)
    return env


def expand_cmd(cmd: str, src: Path) -> list[str]:
    """A repos/<repo>.yaml command string ("{gradlew} --console=plain ...") -> argv."""
    parts = cmd.split()
    out: list[str] = []
    for p in parts:
        if p == "{gradlew}":
            out += get_platform().gradlew(src)
        else:
            out.append(p)
    return out


def run(argv: list[str], *, src: Path, env: dict[str, str], out_dir: Path, timeout_s: int = GRADLE_TIMEOUT_S,
        memory_mb: int | None = None, as_user: str | None = None) -> ProcResult:
    plat = get_platform()
    spec = ProcSpec(argv=argv, cwd=src, env=env, stdin_text=None, timeout_s=timeout_s, memory_mb=memory_mb,
                    as_user=as_user, out_dir=out_dir)
    return plat.wait(plat.run(spec))


def test_args(repo: RepoConfig, module: str, tests: list[str] | None = None, *, clean: bool = True,
              offline: bool = True) -> list[str]:
    """`<module>:cleanTest <module>:<task> --tests <t>...` with the validation/grading flags."""
    task = repo.tests.task_for(module)
    args = ["--console=plain", "--continue", "--no-daemon", "--no-build-cache"]
    if offline:
        args.insert(0, "--offline")
    if clean:
        args.append(f"{module}:cleanTest")
    args.append(f"{module}:{task}")
    for t in tests or []:
        args += ["--tests", t]
    return args


def module_dir(src: Path, module: str) -> Path:
    return src.joinpath(*[p for p in module.split(":") if p])


def junit_dir(repo: RepoConfig, src: Path, module: str) -> Path:
    return module_dir(src, module) / Path(repo.tests.junit_dir) / repo.tests.task_for(module)


def wrapper_version(src: Path) -> str:
    props = (src / "gradle" / "wrapper" / "gradle-wrapper.properties").read_text(encoding="utf-8")
    m = re.search(r"distributionUrl=.*gradle-([0-9][0-9A-Za-z.\-]*?)-(bin|all)\.zip", props)
    if not m:
        raise ValueError("no Gradle wrapper distributionUrl")
    return m.group(1)


OFFLINE_FAILURE_PATTERNS = [
    r"Could not resolve", r"No cached version", r"android-all.*(download|Downloading)",
    r"Downloading https?://", r"Could not GET", r"Could not HEAD",
]


def offline_failures(text: str) -> list[str]:
    return [p for p in OFFLINE_FAILURE_PATTERNS if re.search(p, text)]
