# Phase 2 — Tasks and validation

**Goal.** The task format implemented end to end: create, lint, mine, and validate tasks 3×.
Five validated tasks for repo #1 (the "dev5" set) that Phases 3–6 use.

**Prerequisites.** Phase 1 gate for repo #1. `gh auth status` OK (mining uses the GitHub API).

**Effort.** ~1–2 weeks. Writing good tasks is the slow part; expect to discard 30–50 % of
mined candidates.

## Deliverables

```
benchmark/abb/harness/tasks.py        # load/save TaskConfig; lint rules; `abb tasks new|list|lint|tag`
benchmark/abb/harness/mine.py         # GitHub mining -> candidate task folders
benchmark/abb/harness/validate.py     # V1/V2 x runs per specs/task-format.md; writes validation block
benchmark/tasks/_template/            # seed provided
benchmark/tasks/README.md             # authoring guide (below)
benchmark/tasks/<repo>-000{1..5}/     # 5 validated tasks (>=3 mined, 1 reverted, 1 authored)
benchmark/tests/test_tasks.py         # lint rules; patch splitting; tag computation
CLI: abb tasks new <id> --repo --base-commit   abb tasks lint [--all]   abb tasks mine <repo> --since YYYY-MM-DD [--max-files 8] [--limit 50]
     abb tasks tag <id>   abb tasks validate <id>|--all [--runs 3] [--keep-going]
```

## Steps

1. **Task model + lint** (`tasks.py`). Rules from `specs/task-format.md` → each a named check:
   id matches dir; patches apply with `git apply --check` against a snapshot (uses Phase 1
   workspace, so lint has a `--offline-only` mode that skips patch checks); `test.patch` only
   touches `test_dirs`; every F2P names a class; P2P covers gold modules; `needs_emulator`
   false; `problem.md` contains no path that exists in the repo and no test class name from
   `test.patch` (regex scan) unless `tags.ticket_mentions_code: true` is set deliberately;
   **hidden-test interface rule** (CamelCase identifiers in `test.patch` must exist at base or in
   `problem.md`, task-format rule 7); **identifier leak** (rule 8); `issue_created` present for
   mined tasks; `created_with_s2a_sha` recorded.
2. **`abb tasks tag <id>`**: compute `tags.files_touched`, `files_bucket`, `modules` (from the
   Gradle project a file belongs to — nearest ancestor dir with `build.gradle(.kts)`), `lang`
   (by extension majority in gold.patch), `ui` (touches `res/layout/**` or `*.xml` layouts →
   xml; files containing `@Composable` → compose), `test_kind` (grep test.patch for
   `RobolectricTestRunner`/`@RunWith(AndroidJUnit4` → robolectric, `createComposeRule` →
   compose, `Roborazzi|Paparazzi` → screenshot, else junit).
3. **Mining** (`mine.py`), via `gh api` or REST with `GITHUB_TOKEN`:
   - list merged PRs on the default branch since `--since` (prefer dates after the pinned
     model's training cutoff; also allow older with a flag);
   - keep PRs whose body/title links an issue (`fixes #N`, `closes #N`) and whose file list has
     ≥ 1 path matching `test_dirs` and ≤ `--max-files` non-test paths;
   - for each: `base_commit` = first parent of the merge commit (or PR base sha); split the PR
     diff into `test.patch` / `gold.patch` by `test_dirs`; `problem.md` = issue title + body
     (strip templates/bot text, keep repro steps); `upstream.*` filled; `status: draft`;
   - write `tasks/<repo>-<NNNN>/` with the next free number and a `NOTES.md` listing the PR's
     test files and any non-test helper the tests need;
   - print a ranked list (fewest non-test files first, tests present, issue quality).
   Mining is a starting point; **every mined task is hand-edited** before validation.
4. **Authoring guide** (`tasks/README.md`): how to write `problem.md` like a real issue; how
   to write hidden tests that pin the behaviour but not the implementation; using Robolectric
   for Android-dependent code; how to turn a feature commit into a `reverted` task; the
   category and tag definitions; the license note template; the validation loop.
5. **Validation** (`validate.py`): per `specs/task-format.md`. Each run = fresh workspace
   (offline (proxy stopped)): V1 apply test.patch → run F2P + P2P → expect F2P fail/error, P2P pass;
   V2 apply gold.patch + test.patch → expect all pass. `--runs 3`; results must agree; write
   `validation:` block, `status: validated|flaky`, `env_fingerprint`. Save logs under
   `tasks/<id>/.validation/<timestamp>/` (git-ignored). `--keep-going` continues past failures
   and prints a summary table.
6. **Build dev5 for repo #1.** Mine ≥ 10 candidates, pick/edit 3 mined; create 1 `reverted`
   (feature commit with tests); write 1 `authored` task (e.g. a small behavioural change in a
   core module with a Robolectric test). Aim for ≥ 2 bugfix, ≥ 1 feature, ≥ 1 refactor.
7. **Warm caches** for the dev5 base commits: `abb env warm antennapod --warm-commits …`
   (Phase 1 step 5) and re-run `abb env verify`. Mining records `upstream.issue_created` as
   well as `fix_date`.
8. **`setup_commit`.** Compute `git merge-base --octopus <dev5 base commits + antennapod-0000>` in
   the upstream clone, write it to `repos/antennapod.yaml: build.setup_commit`, and include it in
   `--warm-commits` (Phases 5 and 6 generate setup artifacts there).
9. Validate all five 3× (plus the seed task). Fix or replace flaky ones. Commit `phase 2: tasks +
   validation (dev5)`.

## Acceptance gate

```
uv run abb tasks lint --all                 # 0 errors
uv run abb tasks validate --all --runs 3    # 6 x "validated" (dev5 = 5 tasks + the seed antennapod-0000)
uv run abb tasks list                       # table: id, repo, category, source, tags, status
uv run pytest -q tests/test_tasks.py
```

Passes when five tasks are `validated` with 3 agreeing runs each, mixed sources and categories,
and lint is clean.

## Pitfalls

- A PR's tests often depend on non-test changes (new constructor params, `@VisibleForTesting`).
  Prefer rewriting the test against the public surface; otherwise put the hook in `gold.patch`
  and tag `needs_test_hook`.
- Mined issues may contain the fix discussion. Strip anything that names the fix location.
- Flaky Robolectric tests: usually ordering, `Looper` idling, or time. Fix in `test.patch`
  (`ShadowLooper.idleMainLooper()`, fixed clocks) rather than dropping the task.
- Keep `.validation/` out of git; keep `NOTES.md` in.
