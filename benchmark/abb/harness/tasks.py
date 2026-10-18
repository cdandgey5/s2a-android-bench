"""Tasks: load/save, `abb tasks new|list|lint|tag` (specs/task-format.md, phases/phase-2 steps 1–2).

Lint rules are named checks; each returns findings with level "error" or "warn". Checks that need
the repository read the bare mirror at `base_commit` (tree listing, `git grep` identifier index,
`git apply --check` on an extracted snapshot); `offline_only=True` skips them.
"""
from __future__ import annotations

import re
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

import yaml

from abb import paths
from abb.config import RepoConfig, TaskConfig, load_repo, load_task
from abb.harness.platform import get_platform, run_capture
from abb.harness.repos import ensure_mirror, extract_commit
from abb.util import glob_match

CAMEL = re.compile(r"\b[A-Z][A-Za-z0-9_]*[a-z][A-Za-z0-9_]*\b")
COPYLEFT = ("GPL", "AGPL", "LGPL", "MPL")
CUTOFF = "2026-07-01"  # D-001: first post-cutoff day


@dataclass
class Finding:
    task: str
    rule: str
    level: str  # error | warn | info
    message: str

    def __str__(self) -> str:
        return f"{self.level.upper():5} {self.task} [{self.rule}] {self.message}"


# ---------------------------------------------------------------------------- patches
def patch_files(text: str) -> list[str]:
    """Paths a unified git diff touches (new path for renames, old path for deletions)."""
    out: list[str] = []
    for m in re.finditer(r"^diff --git a/(.+?) b/(.+?)$", text, flags=re.M):
        a, b = m.group(1), m.group(2)
        out.append(b if b != "/dev/null" else a)
    return list(dict.fromkeys(out))


def patch_sections(text: str) -> dict[str, str]:
    """{path: that file's section of the diff}."""
    parts = re.split(r"(?=^diff --git )", text, flags=re.M)
    out = {}
    for p in parts:
        m = re.match(r"diff --git a/(.+?) b/(.+?)$", p, flags=re.M)
        if m:
            out[m.group(2)] = p
    return out


_STRING = re.compile(r'"(?:\\.|[^"\\])*"')
_URL = re.compile(r"\b\w+://\S+")


def code_only(text: str) -> str:
    """Drop string literals, comments and URLs: identifiers there are not interfaces (D-020).
    Works line by line on diff fragments, so a block-comment line is recognised by its shape
    (`/*`, `*`, `*/` first): Javadoc/KDoc lines in a hunk have lost their opening `/**`."""
    out = []
    for ln in text.splitlines():
        if ln.lstrip().startswith(("/*", "*")):
            continue
        ln = _URL.sub("", _STRING.sub('""', ln))
        ln = re.sub(r"/\*.*?\*/", "", ln)
        ln = re.sub(r"`[^`\n]*`", "", ln)  # Kotlin backtick names (`test names with spaces`)
        out.append(re.sub(r"//.*$", "", ln))
    return "\n".join(out)


def added_lines(text: str) -> list[str]:
    return [ln[1:] for ln in text.splitlines() if ln.startswith("+") and not ln.startswith("+++")]


def split_patch(text: str, test_dirs: list[str]) -> tuple[str, str]:
    """(test part, non-test part) of a diff, split by the repo's test_dirs globs."""
    test, gold = [], []
    for path, sec in patch_sections(text).items():
        (test if glob_match(path, test_dirs) else gold).append(sec)
    return "".join(test), "".join(gold)


# ---------------------------------------------------------------------------- the repo at a commit
def _git(repo: RepoConfig, args: list[str], timeout_s: int = 600) -> str:
    m = ensure_mirror(repo)
    r = run_capture(get_platform(), ["git", *args], cwd=m, timeout_s=timeout_s)
    if r.exit_code != 0:
        raise RuntimeError(f"git {' '.join(args[:3])} failed: {r.stderr()[-800:]}")
    return r.stdout()


def tree(repo: RepoConfig, commit: str) -> list[str]:
    return [p for p in _git(repo, ["ls-tree", "-r", "--name-only", "-z", commit]).split("\0") if p]


def identifiers(repo: RepoConfig, commit: str) -> set[str]:
    """Every identifier (>= 3 chars) in the .java/.kt sources at `commit` (cached under ABB_HOME/state):
    classes for the CamelCase check, methods/fields for the member-call check (D-020)."""
    cache = paths.state_dir() / "ident" / f"{repo.key}-{commit}-code.txt"
    if cache.exists():
        return set(cache.read_text(encoding="utf-8").split())
    # every source line, then strings / comments / URLs stripped: a name that only appears in a
    # comment or a string literal is not an interface that exists at base
    out = _git(repo, ["grep", "-h", "-I", "-E", ".", commit, "--", "*.java", "*.kt"], timeout_s=1800)
    lines = [ln for ln in out.splitlines() if not ln.lstrip().startswith(("*", "/*"))]
    ids = set(re.findall(r"\b[A-Za-z_][A-Za-z0-9_]{1,}\b", code_only("\n".join(lines))))
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text("\n".join(sorted(ids)), encoding="utf-8")
    return ids


def project_packages(repo: RepoConfig, commit: str, files: list[str]) -> set[str]:
    """Top-level project package prefixes (first three segments), e.g. de.danoeh.antennapod."""
    pk = set()
    for f in files:
        m = re.search(r"src/(?:main|test)/(?:java|kotlin)/(.+)/[^/]+\.(?:java|kt)$", f)
        if m:
            pk.add(".".join(m.group(1).split("/")[:3]))
    return pk


def module_of(path: str, files: set[str]) -> str:
    """Gradle project path of a file: nearest ancestor dir holding build.gradle(.kts)."""
    parts = path.split("/")[:-1]
    while parts:
        d = "/".join(parts)
        if f"{d}/build.gradle" in files or f"{d}/build.gradle.kts" in files:
            return ":" + ":".join(parts)
        parts.pop()
    return ":"


# ---------------------------------------------------------------------------- task files
def task_dir(task_id: str) -> Path:
    return paths.tasks_dir() / task_id


def task_ids(repo: str | None = None) -> list[str]:
    ids = []
    for p in sorted(paths.tasks_dir().glob("*/task.yaml")):
        if p.parent.name.startswith("_"):
            continue
        if repo and not p.parent.name.startswith(repo + "-"):
            continue
        ids.append(p.parent.name)
    return ids


def save_task_yaml(task_id: str, data: dict) -> None:
    p = task_dir(task_id) / "task.yaml"
    p.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8", newline="\n")


def update_task_yaml(task_id: str, updates: dict) -> None:
    """Merge top-level keys into task.yaml, keeping the file's other keys and order."""
    p = task_dir(task_id) / "task.yaml"
    data = yaml.safe_load(p.read_text(encoding="utf-8"))
    for k, v in updates.items():
        if isinstance(v, dict) and isinstance(data.get(k), dict):
            data[k].update(v)
        else:
            data[k] = v
    TaskConfig.model_validate(data)
    save_task_yaml(task_id, data)


def next_task_id(repo: str) -> str:
    nums = [int(i.rsplit("-", 1)[1]) for i in task_ids(repo)]
    return f"{repo}-{(max(nums) + 1) if nums else 1:04d}"


def new_task(task_id: str, repo: str, base_commit: str, *, source: str = "authored") -> Path:
    d = task_dir(task_id)
    if d.exists():
        raise FileExistsError(d)
    shutil.copytree(paths.tasks_dir() / "_template", d)
    data = yaml.safe_load((d / "task.yaml").read_text(encoding="utf-8"))
    data.update(id=task_id, repo=repo, base_commit=base_commit, source=source)
    save_task_yaml(task_id, data)
    return d


# ---------------------------------------------------------------------------- lint
def lint(task_id: str, *, offline_only: bool = False) -> list[Finding]:
    F: list[Finding] = []

    def err(rule: str, msg: str) -> None:
        F.append(Finding(task_id, rule, "error", msg))

    def warn(rule: str, msg: str) -> None:
        F.append(Finding(task_id, rule, "warn", msg))

    d = task_dir(task_id)
    try:
        t = load_task(task_id)
    except Exception as e:  # noqa: BLE001 - schema errors are findings
        return [Finding(task_id, "schema", "error", str(e).splitlines()[0])]
    if t.id != d.name:
        err("id-matches-dir", f"id {t.id} != directory {d.name}")
    if not re.fullmatch(r"[a-z0-9]+-\d{4}", t.id):
        err("id-format", f"{t.id} is not <repo>-<NNNN>")
    repo = load_repo(t.repo)
    files = {"problem": d / t.problem_statement, "test": d / (t.test_patch or ""), "gold": d / (t.gold_patch or "")}
    for k, p in files.items():
        if not p.is_file():
            err("files-exist", f"{k} file missing: {p.name}")
    if any(x in repo.license.upper() for x in COPYLEFT) and not (d / "LICENSE-NOTE.md").exists():
        err("license-note", f"{repo.license} repo: LICENSE-NOTE.md required")
    if F:
        return F
    test_txt = files["test"].read_bytes().decode("utf-8", errors="replace")
    gold_txt = files["gold"].read_bytes().decode("utf-8", errors="replace")
    problem = files["problem"].read_text(encoding="utf-8")
    for k in ("test", "gold"):
        if b"\r" in files[k].read_bytes():
            err("patch-lf", f"{k}.patch contains CR bytes (store and apply patches as LF bytes)")
    tfiles, gfiles = patch_files(test_txt), patch_files(gold_txt)
    if not tfiles:
        err("test-patch-nonempty", "test.patch touches no file")
    if not gfiles:
        err("gold-patch-nonempty", "gold.patch touches no file")
    bad = [f for f in tfiles if not glob_match(f, repo.tests.test_dirs)]
    if bad:
        err("test-patch-in-test-dirs", f"test.patch touches non-test paths: {bad}")
    bad = [f for f in gfiles if glob_match(f, repo.tests.test_dirs)]
    if bad:
        err("gold-patch-no-tests", f"gold.patch touches test paths: {bad}")
    for e in t.fail_to_pass:
        if not e.test:
            err("f2p-names-class", f"F2P entry for {e.module} names no class (whole-module F2P is not allowed)")
    if t.needs_emulator:
        err("no-emulator", "needs_emulator must be false in v1")
    if t.source in ("mined", "reverted"):
        up = t.upstream
        if not up or not up.fix_commit or not up.fix_date:
            err("upstream", f"{t.source} task needs upstream.fix_commit and fix_date")
        if t.source == "mined" and (not up or not up.issue_created or not up.issue_url):
            err("upstream", "mined task needs upstream.issue_url and issue_created")
    if t.source == "authored" and t.upstream and t.upstream.pr_url:
        err("upstream", "authored task must not carry upstream.pr_url")
    if not t.created_with_s2a_sha:
        err("author-isolation", "created_with_s2a_sha not recorded (D-019)")
    if not t.drafted_by:
        err("drafted-by", "drafted_by missing (agent | human)")
    elif t.drafted_by == "agent" and not t.drafted_with_model:
        err("drafted-by", "drafted_with_model required when drafted_by: agent")
    # test class names from test.patch must not appear in the ticket
    test_classes = set(re.findall(r"\b(?:class|object)\s+([A-Z]\w*Test\w*)\b", test_txt))
    test_classes |= {Path(f).stem for f in tfiles if Path(f).suffix in (".java", ".kt")}
    leaked = sorted(c for c in test_classes if re.search(rf"\b{re.escape(c)}\b", problem))
    if leaked and not t.tags.ticket_mentions_code:
        err("problem-no-test-names", f"problem.md names test classes {leaked}")
    if offline_only:
        return F
    # ---- checks against the repository at base_commit
    if len(t.base_commit) != 40:
        err("base-commit", "base_commit is a placeholder")
        return F
    try:
        tr = tree(repo, t.base_commit)
    except RuntimeError as e:
        err("base-commit", f"not in the mirror: {e}")
        return F
    trs = set(tr)
    # paths of the repo named in the ticket
    path_hits = sorted(p for p in tr if "/" in p and p in problem)
    base_hits = sorted({Path(p).name for p in tr if Path(p).suffix in (".java", ".kt")
                        and re.search(rf"\b{re.escape(Path(p).name)}\b", problem)})
    if (path_hits or base_hits) and not t.tags.ticket_mentions_code:
        err("problem-no-paths", f"problem.md names repository files {path_hits + base_hits}")
    # modules
    gold_mods = sorted({module_of(f, trs) for f in gfiles})
    p2p_mods = {e.module for e in t.pass_to_pass}
    missing = [m for m in gold_mods if m not in p2p_mods]
    if missing:
        err("p2p-covers-gold-modules", f"P2P lacks gold modules {missing}")
    for e in t.fail_to_pass + t.pass_to_pass:
        mdir = "/".join(p for p in e.module.split(":") if p)
        if f"{mdir}/build.gradle" not in trs and f"{mdir}/build.gradle.kts" not in trs:
            err("module-exists", f"{e.module} has no build.gradle at base")
    # hidden-test interface rule (D-020) and identifier leak (rule 8)
    base_ids = identifiers(repo, t.base_commit)
    test_added = code_only("\n".join(added_lines(test_txt)))
    declared = set(re.findall(r"\b(?:class|interface|object|enum|fun|val|var)\s+([A-Z]\w*)", test_added))
    lib_ids = set()
    pk = project_packages(repo, t.base_commit, tr)
    for imp in re.findall(r"^\s*import\s+(?:static\s+)?([\w.]+)", test_added, flags=re.M):
        if not any(imp.startswith(p) for p in pk):
            lib_ids |= {s for s in imp.split(".") if CAMEL.fullmatch(s)}
    problem_ids = set(CAMEL.findall(_URL.sub("", problem))) | set(re.findall(r"\b[a-z]\w*[A-Z]\w*\b", problem))
    for span in re.findall(r"`([^`\n]+)`", problem):  # names written as code in the ticket, any case
        problem_ids |= set(re.findall(r"\b[A-Za-z_]\w*\b", span))
    declared |= set(re.findall(r"\b(?:fun|void|boolean|int|long|String|private|public|static)\s+([a-z]\w*)\s*\(",
                               test_added))
    used = set(CAMEL.findall(test_added)) - declared - lib_ids
    # member calls on project types: `Foo.bar(` / `foo.bar(` -> bar must exist at base too
    used |= {m for m in re.findall(r"\.\s*([a-z]\w{2,})\s*\(", test_added)} - declared
    # constants / enum values on project types: `Format.FLAC`, `SortOrder.RANDOM`
    used |= {c for q, c in re.findall(r"\b([A-Z]\w*)\.([A-Z][A-Z0-9_]+)\b", test_added)
             if q not in lib_ids} - declared - lib_ids  # `XmlPullParser.END_TAG` is a library constant
    not_at_base = used - base_ids
    new_surface = sorted(not_at_base & problem_ids)
    unknown = sorted(not_at_base - problem_ids)
    if unknown:
        err("interface-rule", f"test.patch uses identifiers that exist neither at base nor in problem.md: {unknown}")
    if new_surface and not t.tags.new_surface:
        warn("new-surface", f"test.patch uses new surface named in the ticket {new_surface}: set tags.new_surface: true")
    if not new_surface and t.tags.new_surface:
        warn("new-surface", "tags.new_surface is true but test.patch uses only base identifiers")
    gold_only = set(CAMEL.findall(code_only("\n".join(added_lines(gold_txt))))) - base_ids
    leak = sorted((problem_ids & gold_only) - not_at_base)  # new surface the hidden tests use must be named (D-020)
    if leak and not t.tags.ticket_mentions_code:
        err("identifier-leak", f"problem.md contains identifiers that only gold.patch introduces: {leak}")
    # patches apply to an extracted snapshot (bytes, no 3-way)
    with tempfile.TemporaryDirectory(prefix="abb-lint-", dir=paths.work_dir()) as tmp:
        snap = Path(tmp) / "src"
        extract_commit(repo, t.base_commit, snap, exclude=repo.workspace.exclude_from_snapshot)
        for name, p in (("gold", files["gold"]), ("test", files["test"])):
            r = run_capture(get_platform(), ["git", "apply", "--check", "--whitespace=nowarn", str(p)], cwd=snap, timeout_s=120)
            if r.exit_code != 0:
                err("patch-applies", f"{name}.patch does not apply at base: {r.stderr().strip()[-300:]}")
        run_capture(get_platform(), ["git", "apply", "--whitespace=nowarn", str(files["gold"])], cwd=snap, timeout_s=120)
        r = run_capture(get_platform(), ["git", "apply", "--check", "--whitespace=nowarn", str(files["test"])], cwd=snap, timeout_s=120)
        if r.exit_code != 0:
            err("patch-applies", "test.patch does not apply on top of gold.patch")
    return F


# ---------------------------------------------------------------------------- tag
def compute_tags(task_id: str) -> dict:
    t = load_task(task_id)
    repo = load_repo(t.repo)
    d = task_dir(task_id)
    gold_txt = (d / t.gold_patch).read_text(encoding="utf-8", errors="replace")
    test_txt = (d / t.test_patch).read_text(encoding="utf-8", errors="replace")
    gfiles = patch_files(gold_txt)
    trs = set(tree(repo, t.base_commit))
    n = len(gfiles)
    exts = [Path(f).suffix for f in gfiles]
    java, kt = exts.count(".java"), exts.count(".kt")
    lang = "mixed" if java and kt else ("kotlin" if kt > java else "java")
    compose = "@Composable" in gold_txt
    xml_ui = any(re.search(r"/res/layout[^/]*/", f) for f in gfiles)
    ui = "compose" if compose else ("xml" if xml_ui else "none")
    if re.search(r"Roborazzi|Paparazzi", test_txt):
        kind = "screenshot"
    elif "createComposeRule" in test_txt:
        kind = "compose"
    elif re.search(r"RobolectricTestRunner|AndroidJUnit4|org\.robolectric", test_txt):
        kind = "robolectric"
    else:
        kind = "junit"
    return {
        "files_touched": n,
        "files_bucket": "1" if n <= 1 else ("2-5" if n <= 5 else "6+"),
        "modules": len({module_of(f, trs) for f in gfiles}),
        "lang": lang,
        "ui": ui,
        "test_kind": kind,
    }


def tag(task_id: str) -> dict:
    tags = compute_tags(task_id)
    update_task_yaml(task_id, {"tags": tags})
    return tags


def is_post_cutoff(t: TaskConfig) -> bool:
    u = t.upstream
    return bool(u and u.fix_date and u.issue_created and str(u.fix_date) >= CUTOFF and str(u.issue_created) >= CUTOFF)
