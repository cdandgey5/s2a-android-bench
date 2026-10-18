"""`abb tasks mine <repo> --since YYYY-MM-DD` (phases/phase-2 step 3).

Lists merged PRs on the default branch that close an issue and touch tests and <= --max-files
non-test files, splits each PR's diff (first parent of the merge commit .. merge commit) into
test.patch / gold.patch by the repo's test_dirs, and writes a candidate folder per PR under
ABB_HOME/state/candidates/<repo>/pr-<N>/ (same layout as a task) plus a ranked TRIAGE list.
`abb tasks mine --promote <N>` copies a reviewed candidate into tasks/<repo>-<NNNN>. Mining is a
starting point: every promoted task is rewritten (ticket) and reviewed (S2) before validation.
"""
from __future__ import annotations

import json
import re
import shutil
from datetime import date
from pathlib import Path

import yaml

from abb import paths
from abb.config import RepoConfig, load_repo
from abb.harness.platform import get_platform, run_capture
from abb.harness.repos import ensure_mirror
from abb.harness.tasks import CUTOFF, next_task_id, split_patch, task_dir
from abb.log import get_logger

log = get_logger("abb.mine")
LINK = re.compile(r"\b(?:fix(?:es|ed)?|close[sd]?|resolve[sd]?)\s*:?\s*#(\d+)", re.I)
PHAB = re.compile(r"phabricator\.wikimedia\.org/(T\d{4,7})\b")
PHAB_BASE = "https://phabricator.wikimedia.org/"
TEMPLATE_NOISE = [  # (pattern, flags): DOTALL only where a match may span lines
    (r"<!--.*?-->", re.S),
    (r"^#+\s*(?:Checklist|Checklist for reviewers|Before submitting)\s*\n(?:\s*- \[[ xX]\] [^\n]*\n?)*", re.M),
    (r"^\s*- \[[ xX]\] [^\n]*$", re.M),
]


def candidates_dir(repo: RepoConfig) -> Path:
    return paths.state_dir() / "candidates" / repo.key


def _gh(args: list[str], timeout_s: int = 300):
    r = run_capture(get_platform(), ["gh", *args], cwd=paths.abb_home(), timeout_s=timeout_s)
    if r.exit_code != 0:
        raise RuntimeError(f"gh {' '.join(args[:3])} failed: {r.stderr()[-500:]}")
    return json.loads(r.stdout())


def _git(m: Path, args: list[str]) -> str:
    r = run_capture(get_platform(), ["git", *args], cwd=m, timeout_s=600)
    if r.exit_code != 0:
        raise RuntimeError(f"git {' '.join(args[:3])} failed: {r.stderr()[-500:]}")
    return r.stdout()


def _phab_task(tid: str) -> dict:
    """A public Phabricator task page -> {title, body, createdAt, url, labels} (anonymous Conduit
    needs a session, the HTML page does not)."""
    import html
    import urllib.request
    from datetime import datetime

    url = PHAB_BASE + tid
    req = urllib.request.Request(url, headers={"User-Agent": "abb-benchmark-miner (research; one request per task)"})
    with urllib.request.urlopen(req, timeout=30) as r:
        page = r.read().decode("utf-8", errors="replace")
    t = re.search(r"<title>(.*?)</title>", page, re.S)
    title = re.sub(rf"^\W*{tid}\s+", "", html.unescape(t.group(1)).strip()) if t else tid
    i = page.find(">Description<")
    m = re.search(r'class="phabricator-remarkup">(.*?)</div>\s*</div>', page[i:i + 20000], re.S) if i >= 0 else None
    body = ""
    if m:
        body = re.sub(r"<br\s*/?>|</p>|</li>|</h\d>", "\n", m.group(1))
        body = re.sub(r"<li[^>]*>", "- ", body)
        body = html.unescape(re.sub(r"<[^>]+>", "", body))
        body = re.sub(r"[ \t]+", " ", body)
        body = re.sub(r"\n\s*\n+", "\n\n", body).strip()
    # the first timeline date is the creation; Phabricator drops the year for dates in the current year
    d = re.search(r"\b([A-Z][a-z]{2} \d{1,2})(?: (\d{4}))?, \d{1,2}:\d{2} [AP]M", page)
    if not d:
        raise OSError(f"{tid}: no creation date on the task page")
    today = datetime.now().date()
    when = datetime.strptime(f"{d.group(1)} {d.group(2) or today.year}", "%b %d %Y").date()
    if not d.group(2) and when > today:
        when = when.replace(year=when.year - 1)
    created = when.isoformat()
    return {"title": title, "body": body, "createdAt": created, "url": url, "labels": []}


def clean_issue(body: str) -> str:
    s = body or ""
    for pat, flags in TEMPLATE_NOISE:
        s = re.sub(pat, "", s, flags=flags)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def _test_classes(test_files: list[str]) -> list[str]:
    out = []
    for f in test_files:
        m = re.search(r"src/test[^/]*/(?:java|kotlin)/(.+)\.(?:java|kt)$", f)
        if m and re.search(r"Test\w*$", m.group(1)):
            out.append(m.group(1).replace("/", "."))
    return out


def _module_dir(path: str) -> str:
    return path.split("/src/", 1)[0] if "/src/" in path else ""


def mine(key: str, since: str, *, max_files: int = 8, limit: int = 200, allow_pre_cutoff: bool = False) -> list[dict]:
    repo = load_repo(key)
    m = ensure_mirror(repo, fetch=True)
    prs = _gh(["pr", "list", "-R", repo.owner_repo, "--state", "merged", "--base", repo.default_branch, "--search",
               f"merged:>={since}", "--limit", str(limit), "--json",
               "number,title,body,mergedAt,mergeCommit,url,files,closingIssuesReferences,labels"])
    out_root = candidates_dir(repo)
    out_root.mkdir(parents=True, exist_ok=True)
    s2a_sha = _git(paths.repo_clone(), ["log", "-1", "--format=%H", "--", "s2a"]).strip()
    rows = []
    for pr in prs:
        files = [f["path"] for f in pr.get("files") or []]
        tests = [f for f in files if _is_test(repo, f)]
        non_test = [f for f in files if not _is_test(repo, f)]
        if repo.issue_tracker == "phabricator":
            issues = list(dict.fromkeys(PHAB.findall((pr.get("body") or "") + " " + pr["title"])))
        else:
            issues = [i["number"] for i in pr.get("closingIssuesReferences") or []]
            issues += [int(n) for n in LINK.findall((pr.get("body") or "") + " " + pr["title"]) if int(n) not in issues]
        reason = None
        if not issues:
            reason = "no linked issue"
        elif not tests:
            reason = "no test files"
        elif len(non_test) > max_files:
            reason = f"{len(non_test)} non-test files"
        elif not non_test:
            reason = "tests only"
        if reason:
            rows.append({"pr": pr["number"], "title": pr["title"], "skip": reason})
            continue
        merge = (pr.get("mergeCommit") or {}).get("oid")
        try:
            base = _git(m, ["rev-parse", f"{merge}^1"]).strip()
            diff = _git(m, ["diff", "--binary", base, merge])
        except RuntimeError as e:
            rows.append({"pr": pr["number"], "title": pr["title"], "skip": f"git: {e}"[:120]})
            continue
        test_patch, gold_patch = split_patch(diff, repo.tests.test_dirs)
        if repo.issue_tracker == "phabricator":
            try:
                issue = _phab_task(issues[0])
            except OSError as e:
                rows.append({"pr": pr["number"], "title": pr["title"], "skip": f"phabricator {issues[0]}: {e}"[:120]})
                continue
        else:
            issue = _gh(["issue", "view", str(issues[0]), "-R", repo.owner_repo, "--json", "title,body,createdAt,url,labels"])
        fix_date = pr["mergedAt"][:10]
        created = issue["createdAt"][:10]
        post = fix_date >= CUTOFF and created >= CUTOFF
        if not post and not allow_pre_cutoff:
            rows.append({"pr": pr["number"], "title": pr["title"], "skip": f"pre-cutoff issue ({created})"})
            continue
        labels = {lb["name"].lower() for lb in (issue.get("labels") or []) + (pr.get("labels") or [])}
        category = "feature" if any("feature" in lb or "enhancement" in lb for lb in labels) else "bugfix"
        d = out_root / f"pr-{pr['number']}"
        if d.exists():
            shutil.rmtree(d)
        d.mkdir(parents=True)
        (d / "test.patch").write_bytes(test_patch.encode("utf-8"))
        (d / "gold.patch").write_bytes(gold_patch.encode("utf-8"))
        (d / "problem.md").write_text(f"# {issue['title']}\n\n{clean_issue(issue.get('body') or '')}\n", encoding="utf-8",
                                      newline="\n")
        classes = _test_classes(tests)
        tmods = sorted({":" + _module_dir(f).replace("/", ":") for f in tests if _module_dir(f)})
        gmods = sorted({":" + _module_dir(f).replace("/", ":") for f in non_test if _module_dir(f)})
        f2p = [{"module": ":" + _module_dir(f).replace("/", ":"), "test": c} for f, c in zip(
            [f for f in tests if re.search(r"Test\w*\.(java|kt)$", f)], classes)]
        task = {
            "id": "CANDIDATE", "repo": repo.key, "base_commit": base, "source": "mined", "category": category,
            "upstream": {"issue_url": issue["url"], "pr_url": pr["url"], "fix_commit": merge, "fix_date": fix_date,
                         "issue_created": created},
            "tags": {}, "problem_statement": "problem.md", "test_patch": "test.patch", "gold_patch": "gold.patch",
            "fail_to_pass": f2p, "pass_to_pass": [{"module": mm} for mm in sorted(set(tmods) | set(gmods))],
            "limits": {"timeout_minutes": 45}, "needs_emulator": False, "split": "dev", "status": "draft",
            "created_with_s2a_sha": s2a_sha, "drafted_by": "agent", "drafted_with_model": "claude-opus-5-5",
            "validation": None,
        }
        (d / "task.yaml").write_text(yaml.safe_dump(task, sort_keys=False), encoding="utf-8", newline="\n")
        (d / "NOTES.md").write_text(
            f"# Provenance notes (not shown to agents)\n\n- Source: mined from {pr['url']} (merged {fix_date}), "
            f"closing {issue['url']} (opened {created}); post-cutoff: {post}.\n- PR test files: {tests}\n"
            f"- PR non-test files (gold.patch): {non_test}\n- F2P draft: every test class the PR touches; "
            f"narrow it to the methods that fail at base during review.\n- Ticket: issue title + body, templates "
            f"stripped; rewrite before S2 (no file/class names unless the reporter wrote them).\n",
            encoding="utf-8", newline="\n")
        rows.append({"pr": pr["number"], "title": pr["title"], "issue": issues[0], "non_test": len(non_test),
                     "tests": len(tests), "issue_len": len(issue.get("body") or ""), "post_cutoff": post,
                     "category": category, "dir": str(d)})
    keep = [r for r in rows if "dir" in r]
    keep.sort(key=lambda r: (r["non_test"], -min(r["issue_len"], 1500)))
    (out_root / "TRIAGE.json").write_text(json.dumps({"mined_at": date.today().isoformat(), "since": since,
                                                       "candidates": keep, "skipped": [r for r in rows if "skip" in r]},
                                                      indent=2), encoding="utf-8")
    return rows


def reverted_from_pr(key: str, pr_number: int) -> Path:
    """A `reverted` candidate: a merged feature PR with tests (no issue needed). base = first parent of the
    merge commit; gold/test split by test_dirs; problem.md must be WRITTEN as a feature request."""
    repo = load_repo(key)
    m = ensure_mirror(repo, fetch=True)
    pr = _gh(["pr", "view", str(pr_number), "-R", repo.owner_repo, "--json", "number,title,body,mergedAt,mergeCommit,url,files"])
    merge = pr["mergeCommit"]["oid"]
    base = _git(m, ["rev-parse", f"{merge}^1"]).strip()
    test_patch, gold_patch = split_patch(_git(m, ["diff", "--binary", base, merge]), repo.tests.test_dirs)
    files = [f["path"] for f in pr["files"]]
    tests = [f for f in files if _is_test(repo, f)]
    d = candidates_dir(repo) / f"pr-{pr_number}"
    if d.exists():
        shutil.rmtree(d)
    d.mkdir(parents=True)
    (d / "test.patch").write_bytes(test_patch.encode("utf-8"))
    (d / "gold.patch").write_bytes(gold_patch.encode("utf-8"))
    (d / "problem.md").write_text(f"# TODO: write a feature request for: {pr['title']}\n", encoding="utf-8", newline="\n")
    s2a_sha = _git(paths.repo_clone(), ["log", "-1", "--format=%H", "--", "s2a"]).strip()
    f2p = [{"module": ":" + _module_dir(f).replace("/", ":"), "test": c}
           for f, c in zip([f for f in tests if re.search(r"Test\w*\.(java|kt)$", f)], _test_classes(tests))]
    mods = sorted({":" + _module_dir(f).replace("/", ":") for f in files if _module_dir(f)})
    task = {
        "id": "CANDIDATE", "repo": repo.key, "base_commit": base, "source": "reverted", "category": "feature",
        "upstream": {"issue_url": None, "pr_url": pr["url"], "fix_commit": merge, "fix_date": pr["mergedAt"][:10],
                     "issue_created": None},
        "tags": {}, "problem_statement": "problem.md", "test_patch": "test.patch", "gold_patch": "gold.patch",
        "fail_to_pass": f2p, "pass_to_pass": [{"module": mm} for mm in mods], "limits": {"timeout_minutes": 45},
        "needs_emulator": False, "split": "dev", "status": "draft", "created_with_s2a_sha": s2a_sha,
        "drafted_by": "agent", "drafted_with_model": "claude-opus-5-5", "validation": None,
    }
    (d / "task.yaml").write_text(yaml.safe_dump(task, sort_keys=False), encoding="utf-8", newline="\n")
    (d / "NOTES.md").write_text(
        f"# Provenance notes (not shown to agents)\n\n- Source: reverted feature {pr['url']} (merged {pr['mergedAt'][:10]}); "
        f"base = first parent of {merge}.\n- PR files: {files}\n- problem.md is written as a feature request in the "
        f"project's issue style (no upstream issue).\n", encoding="utf-8", newline="\n")
    return d


def _is_test(repo: RepoConfig, path: str) -> bool:
    from abb.util import glob_match

    return glob_match(path, repo.tests.test_dirs)


def promote(key: str, pr: int) -> str:
    repo = load_repo(key)
    src = candidates_dir(repo) / f"pr-{pr}"
    if not src.exists():
        raise FileNotFoundError(src)
    tid = next_task_id(repo.key)
    dst = task_dir(tid)
    shutil.copytree(src, dst)
    data = yaml.safe_load((dst / "task.yaml").read_text(encoding="utf-8"))
    data["id"] = tid
    (dst / "task.yaml").write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8", newline="\n")
    if repo.license:  # every derived task carries its upstream license (phase-7 step 6)
        (dst / "LICENSE-NOTE.md").write_text(
            "# License note\n\n`test.patch` and `gold.patch` in this directory are derived from\n"
            f"{repo.display_name} ({repo.url}), commit {data['base_commit']}, which is licensed under {repo.license}.\n"
            "They are distributed under the same license. `problem.md` reproduces or paraphrases upstream\n"
            f"issue {data['upstream']['issue_url']}.\n\nHarness code outside `tasks/` is licensed separately "
            "(see `benchmark/LICENSE`).\n", encoding="utf-8", newline="\n")
    return tid
