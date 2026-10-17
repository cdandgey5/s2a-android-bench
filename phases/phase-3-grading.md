# Phase 3 — Grading

**Goal.** Deterministic, anti-gaming grading of an arbitrary diff against a task, exactly per
`specs/grading-protocol.md`, proven with a sanity matrix.

**Prerequisites.** Phase 2 gate (dev5 validated).

**Effort.** ~1 week part-time.

## Deliverables

```
benchmark/abb/harness/diffscope.py    # scoped diff; classify paths (test_dirs, build_config, diff_exclude); suspect-line scan
benchmark/abb/harness/grade.py        # grade(task, diff_path, env_fingerprint) -> GradeResult; writes grade.json, junit/, gradle.log
benchmark/abb/harness/lint.py         # optional lint_delta (step 7)
benchmark/tests/test_diffscope.py
benchmark/tests/fixtures/grading/<task>/{gold,empty,gold_plus_delete_test,compile_break,regression,gradlew_edit,interface_mismatch}.patch
CLI: abb grade-patch <task_id> <patch> [--out dir]     abb grade <run_id> [--arm A] [--task T] [--trial k] [--parallel N]
```

## Steps

1. **Path classification** (`diffscope.py`): `classify(path, repo) -> {"test","protected_build",
   "build_config","excluded","source"}` using the repo globs (fnmatch with `**`). `scoped_diff(ws, repo)`
   returns the diff with `excluded` paths removed and untracked files included.
   `suspect_test_config(diff_text)` applies the regex list from the spec to added lines in
   `build_config` files.
2. **Grader** (`grade.py`): implement the 9-step algorithm. Use `Workspace(sandbox="none")`.
   Reverting touched tests: `git checkout base -- <path>` for paths existing at base, `rm` for
   new ones; record `flags.reverted_test_paths`. Then restore every `protected_build` and
   `build_config` path that `gold.patch` does not touch (`flags.build_config_reverted`). Apply
   `test.patch`. Run F2P and P2P with
   `gradle.run_tests` (group selections by module → one Gradle call per module with repeated
   `--tests`). Parse JUnit. Compute `resolved`, `regressions`, `diff_stats`, `scope_creep`
   (modules of changed source files minus modules in `gold.patch` — the grader may read
   `gold.patch` for this, arms may not). Write `grade.json` atomically.
3. **Build-failure detection.** `build_ok=False` when Gradle exits non-zero **and** no fresh
   `TEST-*.xml` was produced for a requested module, or the log contains `Compilation failed`
   / `e: ` (Kotlin) / `error: ` (javac) in the compile tasks. A test failure alone keeps
   `build_ok=True`. If the **main** sources compiled but the **unit-test** source set did not
   (`compile<Variant>UnitTest*` failed), set `reason="test_compile_failed"`. Run with
   `<module>:cleanTest` and require JUnit files newer than the grading start with `time`
   attributes. On any P2P failure re-run those tests once in a fresh workspace (`flaky_p2p`).
4. **Sanity fixtures** for ≥ 2 tasks (the seed `antennapod-0000` and one dev5 task): craft the
   seven patches from the spec table (gold; empty; gold + deletion of the F2P test file; gold +
   a syntax error in a source file; gold + a change that breaks a P2P test; gold + an edit to
   `gradlew`; a correct fix whose public method name differs from the hidden test's). `tests/test_grading_matrix.py` (integration,
   `ABB_INTEGRATION=1`) runs `grade-patch` on each and asserts the expected `resolved`,
   `build_ok`, `flags`, `regressions`.
5. **CLI** `abb grade-patch` (ad-hoc) and `abb grade <run_id>` (walks `results/<run_id>/<arm>/
   <task>/t<k>/diff.patch` lacking `grade.json`; `--parallel N` workspaces; writes
   `metrics.json` by merging `run.json` + `grade.json` + task metadata per
   `specs/results-layout.md`).
6. **Timeouts.** `limits.grade_timeout_minutes` (default 30) per module call; on timeout:
   `build_ok=False, reason="grade_timeout"`, Gradle process tree killed by the Job Object.
7. **Optional lint delta** (`lint.py`): if `repos.lint` is set, run lint at base (cache the
   count per task in `tasks/<id>/.validation/lint_base.json`) and after the diff; report new
   warnings by id. Skip if lint takes > 5 min for the repo; note in DECISIONS.
8. Commit `phase 3: grading`.

## Acceptance gate

```
$env:ABB_INTEGRATION=1; uv run pytest -q tests\test_grading_matrix.py     # 2 tasks x 7 patches, all expectations met
uv run pytest -q tests/test_diffscope.py
uv run abb grade-patch antennapod-0001 tasks/antennapod-0001/gold.patch   # resolved: true
```

Passes when the sanity matrix is green for two tasks and the grader never needs network.

## Pitfalls

- Gradle `--tests` filter with a class that does not exist fails the task with "No tests found
  for given includes" → treat as `missing` (not build failure) and keep going (`--continue`).
- `git apply` of a diff that creates files already present fails; the scoped diff must include
  untracked files consistently (`git add -A -N` before `git diff`).
- Binary files (PNG screenshots for Roborazzi): keep `--binary` in diff generation and apply.
- Never grade inside the agent's trial directories; always a fresh harness-user workspace with the pristine cache.
