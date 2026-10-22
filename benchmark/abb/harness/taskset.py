"""Task-set level tools (phases/phase-7 steps 5, 9, 10): coverage vs targets, setup commits,
the task-set hash, the frozen dev/test split and the setup-leak lint.

Targets scale with N from the N = 40 table in phases/phase-7-scale-tasks.md; the MVP cut (D-045)
sets two repos at "no repo > 50 %" (± 1 task) and authored ≥ 6.
"""
from __future__ import annotations

import hashlib
import json
import random
import re
from collections import Counter
from pathlib import Path

import yaml

from abb import paths
from abb.config import load_repo, load_task
from abb.harness.platform import get_platform, run_capture
from abb.harness.repos import ensure_mirror
from abb.harness.tasks import is_post_cutoff, task_dir, task_ids, update_task_yaml
from abb.util import utcnow_iso

CATEGORY_40 = {"bugfix": 16, "feature": 12, "refactor": 8, "cross_module": 4}
FILES_SHARE = {"1": 0.30, "2-5": 0.50, "6+": 0.20}
MAX_REPO_SHARE = 0.50   # MVP cut (D-045); 0.40 in the full plan
MIN_AUTHORED = 6        # MVP cut
HASHED = ("task.yaml", "problem.md", "test.patch", "gold.patch")


def _tasks() -> list:
    return [load_task(t) for t in task_ids()]


# ---------------------------------------------------------------------------- setup commits
def octopus_base(repo_key: str, commits: list[str]) -> str:
    m = ensure_mirror(load_repo(repo_key))
    r = run_capture(get_platform(), ["git", "merge-base", "--octopus", *sorted(set(commits))], cwd=m, timeout_s=300)
    if r.exit_code != 0:
        raise RuntimeError(f"merge-base --octopus failed for {repo_key}: {r.stderr()[-300:]}")
    return r.stdout().strip()


def set_setup_commit(repo_key: str, sha: str) -> bool:
    """Rewrite `build.setup_commit` in repos/<repo>.yaml in place (comment kept). True if it changed."""
    p = paths.repos_config_dir() / f"{repo_key}.yaml"
    s = p.read_text(encoding="utf-8")
    new, n = re.subn(r"(?m)^(\s*setup_commit:\s*)([0-9a-f]{40})", lambda mm: mm.group(1) + sha, s, count=1)
    if n != 1:
        raise RuntimeError(f"{p}: no setup_commit line")
    if new != s:
        p.write_text(new, encoding="utf-8", newline="\n")
        return True
    return False


# ---------------------------------------------------------------------------- coverage
def coverage(*, write: bool = True, set_setup: bool = True) -> dict:
    ts = _tasks()
    n = len(ts)
    by = lambda f: Counter(f(t) for t in ts)  # noqa: E731
    repos, cats, srcs = by(lambda t: t.repo), by(lambda t: t.category), by(lambda t: t.source)
    files, langs, uis, kinds = (by(lambda t: t.tags.files_bucket), by(lambda t: t.tags.lang), by(lambda t: t.tags.ui),
                                by(lambda t: t.tags.test_kind))
    hidden = by(lambda t: t.hidden_tests)
    mr = [t for t in ts if t.source in ("mined", "reverted")]
    post = sum(1 for t in mr if is_post_cutoff(t))
    rows = []

    def row(dim: str, value: str, have, target: str, ok: bool) -> None:
        rows.append({"dimension": dim, "value": value, "have": have, "target": target, "ok": ok})

    cap = int(MAX_REPO_SHARE * n) + 1
    for r, c in sorted(repos.items()):
        row("repo", r, c, f"≤ {MAX_REPO_SHARE:.0%} (+1 task) = ≤ {cap}", c <= cap)
    row("repo", "count", len(repos), "2 (MVP)", len(repos) >= 2)
    for k, v40 in CATEGORY_40.items():
        tgt = round(v40 * n / 40)
        row("category", k, cats.get(k, 0), f"{tgt} ± 2", abs(cats.get(k, 0) - tgt) <= 2)
    row("source", "authored", srcs.get("authored", 0), f"≥ {MIN_AUTHORED}", srcs.get("authored", 0) >= MIN_AUTHORED)
    for k in ("mined", "reverted"):
        row("source", k, srcs.get(k, 0), "rest", True)
    row("post_cutoff", "mined/reverted with both dates after the cutoff", f"{post}/{len(mr)}", "≥ 50 %",
        bool(mr) and post * 2 >= len(mr))
    for k, share in FILES_SHARE.items():
        row("files_bucket", k, files.get(k, 0), f"~{share:.0%} ≈ {round(share * n)}", True)
    row("lang", "java and kotlin present", dict(langs), "both", bool(langs.get("java") or langs.get("mixed"))
        and bool(langs.get("kotlin") or langs.get("mixed")))
    ui_n = n - uis.get("none", 0)
    row("ui", "ui != none", ui_n, f"≥ {round(8 * n / 40)}", ui_n >= round(8 * n / 40))
    row("test_kind", "robolectric", kinds.get("robolectric", 0), f"≥ {round(10 * n / 40)}",
        kinds.get("robolectric", 0) >= round(10 * n / 40))
    cs = kinds.get("compose", 0) + kinds.get("screenshot", 0)
    row("test_kind", "compose or screenshot", cs, f"≥ {max(1, round(2 * n / 40))}", cs >= max(1, round(2 * n / 40)))
    row("hidden_tests", "authored (D-047)", hidden.get("authored", 0), "reported", True)
    setup = {}
    for r in sorted(repos):
        sha = octopus_base(r, [t.base_commit for t in ts if t.repo == r])
        changed = set_setup_commit(r, sha) if set_setup else False
        setup[r] = {"setup_commit": sha, "changed": changed}
    out = {"generated_at": utcnow_iso(), "n": n, "rows": rows, "setup_commits": setup,
           "validated": sum(1 for t in ts if t.status == "validated")}
    if write:
        lines = [f"# Task-set coverage (generated by `abb tasks coverage`, {out['generated_at']})", "",
                 f"N = {n} tasks ({out['validated']} validated). Targets: phases/phase-7-scale-tasks.md scaled to N, "
                 "MVP cut D-045.", "", "| dimension | value | have | target | ok |", "|---|---|---|---|---|"]
        lines += [f"| {r['dimension']} | {r['value']} | {r['have']} | {r['target']} | {'yes' if r['ok'] else '**no**'} |"
                  for r in rows]
        lines += ["", "## setup_commit (octopus merge-base of each repo's task base commits)", ""]
        lines += [f"- {r}: `{v['setup_commit']}`" + (" (updated in repos/*.yaml)" if v["changed"] else "")
                  for r, v in setup.items()]
        lines += ["", "## Tasks", "", "| id | repo | category | source | hidden tests | post-cutoff | files | lang | ui | kind | status |",
                  "|---|---|---|---|---|---|---|---|---|---|---|"]
        for t in ts:
            lines.append(f"| {t.id} | {t.repo} | {t.category} | {t.source} | {t.hidden_tests} | "
                         f"{'yes' if is_post_cutoff(t) else 'no'} | {t.tags.files_bucket} | {t.tags.lang} | {t.tags.ui} | "
                         f"{t.tags.test_kind} | {t.status} |")
        notes = paths.tasks_dir() / "COVERAGE-NOTES.md"  # hand-written "note why not" for dimensions out of tolerance
        if notes.exists():
            lines += ["", notes.read_text(encoding="utf-8").strip()]
        (paths.tasks_dir() / "COVERAGE.md").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return out


# ---------------------------------------------------------------------------- hash
def taskset_hash() -> tuple[str, list[str]]:
    """sha256 over every task's task.yaml, problem.md, test.patch, gold.patch (sorted); per-file lines."""
    h = hashlib.sha256()
    lines = []
    for tid in task_ids():
        for name in HASHED:
            p = task_dir(tid) / name
            data = p.read_bytes() if p.exists() else b""
            fh = hashlib.sha256(data).hexdigest()
            lines.append(f"{fh}  {tid}/{name}")
            h.update(f"{tid}/{name}\0{fh}\n".encode())
    return h.hexdigest(), lines


def write_hash() -> Path:
    total, lines = taskset_hash()
    p = paths.tasks_dir() / "TASKSET.sha256"
    p.write_text(f"{total}  TASKSET ({len(task_ids())} tasks; {utcnow_iso()})\n" + "\n".join(lines) + "\n",
                 encoding="utf-8", newline="\n")
    return p


# ---------------------------------------------------------------------------- split
def pinned_from_results() -> list[str]:
    """Every task id with any trial directory under the results root (valid, invalid or usage-limited)."""
    ids = set(task_ids())
    found = set()
    root = paths.results_dir()
    for d in root.glob("*/*/*") if root.exists() else []:
        if d.is_dir() and d.name in ids:
            found.add(d.name)
    for d in root.glob("*/usage_limited/*/*") if root.exists() else []:
        if d.is_dir() and d.name in ids:
            found.add(d.name)
    return sorted(found)


def make_split(seed: int, dev_frac: float, pin_dev: list[str] | None = None) -> dict:
    ts = _tasks()
    pins = sorted(set(pin_dev if pin_dev is not None else pinned_from_results()))
    strata: dict[tuple[str, str], list[str]] = {}
    for t in ts:
        strata.setdefault((t.repo, t.category), []).append(t.id)
    rng = random.Random(seed)
    dev, test = [], []
    for key in sorted(strata):
        ids = sorted(strata[key])
        want = round(len(ids) * dev_frac)
        pinned = [i for i in ids if i in pins]
        rest = [i for i in ids if i not in pins]
        rng.shuffle(rest)
        extra = max(0, want - len(pinned))
        dev += pinned + rest[:extra]
        test += rest[extra:]
    dev, test = sorted(dev), sorted(test)
    counts = {f"{r}/{c}": {"dev": sum(1 for i in dev if i in strata[(r, c)]),
                           "test": sum(1 for i in test if i in strata[(r, c)])} for (r, c) in sorted(strata)}
    ids_sha = hashlib.sha256("\n".join(sorted(dev + test)).encode()).hexdigest()
    total, _ = taskset_hash()
    doc = {"seed": seed, "dev_frac": dev_frac, "created_at": utcnow_iso(), "stratified_on": "repo x category",
           "pinned_dev": pins, "dev": dev, "test": test, "counts": counts, "task_ids_sha256": ids_sha,
           "taskset_sha256_before_split_fields": total}
    for i in dev:
        update_task_yaml(i, {"split": "dev"})
    for i in test:
        update_task_yaml(i, {"split": "test"})
    doc["taskset_sha256"] = taskset_hash()[0]   # = tasks/TASKSET.sha256 (`abb tasks hash`) while no task changes
    (paths.tasks_dir() / "split.yaml").write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8", newline="\n")
    return doc


def split_sha256() -> str | None:
    p = paths.tasks_dir() / "split.yaml"
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None


# ---------------------------------------------------------------------------- setup-leak lint
def leak_needles(repo_key: str, setup_commit: str) -> tuple[dict[str, str], dict[str, str]]:
    """({needle: task}, {modified path: task}) for the tasks of one repo against its setup_commit
    (fairness-protocol.md): needles are the files a gold.patch adds and the names it declares that do
    not exist at setup_commit; a file the patch only modifies exists there and is merely counted (D-062)."""
    from abb.harness.tasks import added_lines, code_only, identifiers, patch_files, tree

    repo = load_repo(repo_key)
    files_at, names_at = set(tree(repo, setup_commit)), identifiers(repo, setup_commit)
    added: dict[str, str] = {}
    modified: dict[str, str] = {}
    for tid in task_ids():
        if load_task(tid).repo != repo_key:
            continue
        gold = (task_dir(tid) / "gold.patch").read_text(encoding="utf-8", errors="replace")
        for f in patch_files(gold):
            (modified if f in files_at else added)[f] = tid
        for name in set(re.findall(r"\b(?:class|interface|object|enum class|fun)\s+([A-Z][A-Za-z0-9_]{3,})",
                                   code_only("\n".join(added_lines(gold))))):
            if name not in names_at:
                added[name] = tid
    return added, modified


def _mentions(needle: str, text: str) -> int:
    return len(re.findall(rf"(?<![A-Za-z0-9_]){re.escape(needle)}(?![A-Za-z0-9_])", text))


def setup_leaks() -> tuple[list[str], dict[str, int], int]:
    """(hits, modified-file mention counts, files skipped) for the cached one-time setup artifacts
    (results/_setup_cache/<key>/artifacts/**), each checked against the gold.patch of every task of its
    own repo at its own setup_commit (phases/phase-7 step 5). A file byte-identical in the setups of two
    different repos was installed by the tool (Spec Kit's stock skills and scripts), not generated about
    a repo, and is skipped (D-062). ([], {}, 0) when no setup cache exists yet."""
    root = paths.results_dir() / "_setup_cache"
    if not root.exists():
        return [], {}, 0
    caches = []
    repos_of: dict[tuple[str, str, str], set[str]] = {}
    for cdir in sorted(p for p in root.iterdir() if (p / "record.json").exists()):
        rec = json.loads((cdir / "record.json").read_text(encoding="utf-8"))
        files = []
        for f in sorted((cdir / "artifacts").rglob("*")):
            if f.is_file():
                rel = f.relative_to(cdir / "artifacts").as_posix()
                sha = hashlib.sha256(f.read_bytes()).hexdigest()
                repos_of.setdefault((rec["setup_kind"], rel, sha), set()).add(rec["repo"])
                files.append((f, rel, sha))
        caches.append((rec, files))
    hits: list[str] = []
    counts: Counter = Counter()
    skipped = 0
    needles: dict[tuple[str, str], tuple[dict[str, str], dict[str, str]]] = {}
    for rec, files in caches:
        key = (rec["repo"], rec["setup_commit"])
        if key not in needles:
            needles[key] = leak_needles(*key)
        added, modified = needles[key]
        for f, rel, sha in files:
            if len(repos_of[(rec["setup_kind"], rel, sha)]) > 1:
                skipped += 1
                continue
            text = f.read_text(encoding="utf-8", errors="replace")
            for needle, tid in added.items():
                if _mentions(needle, text):
                    hits.append(f"{f.relative_to(root)}: mentions {needle!r} (added by {tid}'s gold.patch)")
            for path, tid in modified.items():
                counts[f"{path} ({tid})"] += _mentions(path, text)
    return hits, {k: v for k, v in sorted(counts.items()) if v}, skipped


def summary_json(d: dict) -> str:
    return json.dumps(d, indent=2, default=str)
