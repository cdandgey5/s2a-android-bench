# Spec: Grading protocol

Grading is deterministic, runs in a **fresh** container with `--network none`, and never sees
the agent's transcript — only its diff.

## Inputs

- `task.yaml`, `test.patch`, `gold.patch` (the grader reads `gold.patch` only to compute
  `scope_creep` and the protected-path exception below; no arm ever sees it).
- `diff.patch` — the agent's changes, produced by the arm as
  `git -C /work add -A -N && git -C /work diff --binary base -- . ':(exclude)<diff_exclude globs>'`,
  i.e. everything the agent changed relative to the `base` tag (new files included), minus the
  workflow folders listed in `repos.workspace.diff_exclude`.

## Algorithm (`abb/harness/grade.py: grade(task, diff_path) -> GradeResult`)

```
1. ws = workspace.create(task)                      # fresh snapshot at base, 1 commit
2. apply_result = git apply --index --whitespace=nowarn diff.patch     # plain apply, no 3-way merge
     if it fails to apply: GradeResult(resolved=False, build_ok=False, reason="patch_apply_failed")
3. # Anti-gaming resets (paths from repos/<repo>.yaml)
   a. touched_tests = paths in diff.patch matching tests.test_dirs
      for p in touched_tests: restore from base (checkout) or delete if new
      flags.agent_touched_tests = len(touched_tests) > 0
   b. protected = paths matching tests.protected_build_paths
        (gradlew, gradlew.bat, gradle/**, buildSrc/**, build-logic/**, settings.gradle*,
         gradle.properties, **/build.gradle*, gradle/libs.versions.toml, init scripts)
      for p in protected not touched by gold.patch: restore from base
      flags.build_config_changed = any protected path in the diff
      flags.build_config_reverted = the paths restored
      flags.test_config_suspect  = any surviving build-file change (gold touches it) whose added
                                   lines match /testOptions|unitTests|exclude\(|enabled\s*=\s*false|ignoreFailures|allWarningsAsErrors/
      -> build-time code (wrapper scripts, buildSrc, init scripts) can forge results, so it is
         reverted, not merely flagged. The only exception is a file gold.patch itself changes.
4. git apply --check test.patch && git apply test.patch
     if it fails: GradeResult(resolved=False, reason="test_patch_apply_failed")   # should never happen after validation
5. Build + run F2P tests, per module:
     ./gradlew --offline --console=plain --continue --no-build-cache \
        <module>:cleanTest <module>:<unit_test_task> --tests '<class>[.<method>]' [--tests ...]
     parse JUnit XML written AFTER grading started (file mtime) -> status per test id
     build_ok: false when the Gradle run exits non-zero AND no TEST-*.xml was produced for a
       requested module, OR the log shows compile-task failure markers
       (`Compilation failed`, `e: ` for Kotlin, `error: ` for javac). A test failure alone keeps
       build_ok true.
     test_compile_failed: the MAIN sources compile but the TEST source set does not
       (`compile<Variant>UnitTest*` fails) -> reason="test_compile_failed", unresolved. It is
       counted in the "interface" table (per arm/category) only when the diff is non-empty and
       touches the F2P module(s); whether it is a correct fix with a different shape is the
       blind Phase 9 label `INTERFACE`, not a grader decision (task-format.md rule 7).
6. Run P2P tests similarly (whole classes or whole modules).
   Flakiness guard: any P2P test that failed is re-run ONCE in a fresh container; if it passes,
   it is recorded in flaky_p2p and excluded from regressions.
7. resolved = build_ok and all(F2P == passed) and all(P2P == passed, after the flakiness guard)
   regressions = [t for t in P2P if status != passed and t not in flaky_p2p]
8. Secondary metrics (do not affect `resolved`):
     diff_stats       = files changed, insertions, deletions (non-test, non-excluded, non-reverted)
     scope_creep      = files changed outside the set of modules touched by gold.patch
     lint_delta       = (optional, Phase 3 step 7) new lint warnings vs base
9. Write grade.json; copy JUnit XML and gradle.log into the trial dir.
```

### Gradle invocation notes

- `--continue` so one failing module does not hide others; `--no-build-cache` so nothing is
  served from a cache (images are built with `org.gradle.caching=false` as well).
- `cleanTest` forces the tests to execute in this run; the parser additionally requires each
  F2P `<testcase>` to carry a `time` attribute and the XML to be newer than the grading start.
- Timeout: `limits.grade_timeout_minutes` (default 30) per module call. Timeout →
  `build_ok=False, reason="grade_timeout"`.
- Multiple F2P entries in the same module are passed as repeated `--tests` filters in one call.
- "No tests found for given includes" → those tests are `missing` (count as failed), not a
  build failure.

### JUnit parsing (`abb/harness/junit.py`)

Read every `TEST-*.xml` under `<module>/build/test-results/<task>/`. For each `<testcase>`:
`classname`, `name`, status from child elements (`failure` → failed, `error` → error,
`skipped` → skipped, else passed). A test listed in the task but absent from the XML is
`missing` (counts as failure). Robolectric parameterized tests produce names like
`method[param]`; match by prefix when the task omits the parameter. Roborazzi/Paparazzi
screenshot tests: the task's `validation` block records the comparison tolerance the test
uses; the grader does not alter it.

## `grade.json`

```json
{
  "task_id": "antennapod-0012",
  "resolved": false,
  "build_ok": true,
  "reason": null,
  "f2p": {"de...PlaybackSpeedTest.speedPersistsAfterRestart": "failed"},
  "p2p": {"de...PlaybackSpeedTest": "passed", ":model": "passed"},
  "regressions": [],
  "flaky_p2p": [],
  "flags": {"agent_touched_tests": true, "build_config_changed": false, "build_config_reverted": [],
            "test_config_suspect": false,
            "reverted_test_paths": ["playback/src/test/.../PlaybackSpeedTest.java"]},
  "diff_stats": {"files": 3, "insertions": 41, "deletions": 7, "modules": [":playback"]},
  "scope_creep": {"files_outside_gold_modules": 0, "paths": []},
  "lint_delta": null,
  "grade_duration_s": 412.3,
  "image_digest": "sha256:...",
  "graded_at": "2026-11-05T10:12:44Z"
}
```

## Sanity checks the grader must pass (Phase 3 gate)

| Input diff | Expected |
|---|---|
| `gold.patch` | `resolved: true` |
| empty diff | `resolved: false`; bugfix/no-new-surface task: `build_ok: true`, all F2P failed; `new_surface` task: `reason: test_compile_failed`, not counted in the interface table |
| `gold.patch` + a change that deletes the F2P test | test reverted, `flags.agent_touched_tests: true`, still `resolved: true` |
| a diff that breaks compilation | `build_ok: false`, `resolved: false` |
| a diff that makes F2P pass but breaks a P2P test | `resolved: false`, `regressions` non-empty |
| `gold.patch` + an edit to `gradlew` or `buildSrc/` | path reverted, `flags.build_config_reverted` non-empty, `resolved: true` |
| a correct fix with a different public method name than the hidden test uses (hand-made) | `reason: test_compile_failed`, `resolved: false`, counted in the interface table |

## What grading deliberately does not do

- It does not run the agent's own new tests (they are reverted). Their existence is recorded
  (`flags.agent_touched_tests`) for the "wrote tests" secondary metric.
- It does not judge code quality. That is Phase 9's LLM convention grader, a secondary metric.
- It does not compare with `gold.patch` beyond the module set. Different valid fixes are fine —
  as long as they expose the interface the hidden tests use (task-format rule 7); when they do
  not, the outcome is visible as `test_compile_failed` rather than silently merged into failures.
