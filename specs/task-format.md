# Spec: Task format

A task is a directory `benchmark/tasks/<task_id>/`:

```
tasks/antennapod-0012/
  task.yaml        # metadata (schema below)
  problem.md       # the ticket the agent sees — the ONLY task text any arm receives
  test.patch       # hidden test changes (unified diff against base_commit)
  gold.patch       # reference fix, non-test changes only; never seen by any arm; read by validate, the grader (scope_creep, protected-path exception) and `lint --setup-leak`
  NOTES.md         # optional: provenance, upstream issue/PR URLs, why tests were adjusted
  LICENSE-NOTE.md  # required when test.patch/gold.patch derive from a copyleft repo
```

## `task.yaml` schema

```yaml
id: antennapod-0012                 # <repo>-<NNNN>, must equal the directory name
repo: antennapod                    # key into repos/<repo>.yaml
base_commit: 3f2a9c1d0e5b...        # full 40-char SHA in the upstream repo
source: mined                       # mined | reverted | authored
category: bugfix                    # bugfix | feature | refactor | cross_module
upstream:                           # optional for authored tasks
  issue_url: https://github.com/AntennaPod/AntennaPod/issues/1234
  pr_url: https://github.com/AntennaPod/AntennaPod/pull/1250
  fix_commit: 9ab8c7...
  fix_date: 2026-03-02              # ISO date of the fix commit
  issue_created: 2026-02-20         # ISO date the issue was opened; post-cutoff = BOTH dates after the model cutoff (D-001)
tags:
  files_touched: 3                  # number of non-test files in gold.patch
  files_bucket: "2-5"               # "1" | "2-5" | "6+"
  modules: 2                        # distinct Gradle modules touched by gold.patch
  lang: java                        # java | kotlin | mixed
  ui: xml                           # none | xml | compose
  test_kind: robolectric            # junit | robolectric | compose | screenshot
  needs_test_hook: false            # true if gold.patch carries a non-test helper the tests need (rule 2); the ticket must then name that surface (rule 7)
  new_surface: false                # set by lint: test.patch references a surface that does not exist at base (named in the ticket)
  ticket_mentions_code: false       # true only when the real upstream ticket named files/classes (rule 1)
problem_statement: problem.md
test_patch: test.patch
gold_patch: gold.patch
fail_to_pass:                       # tests that FAIL at base+test.patch and PASS at base+gold+test.patch
  - module: ":playback"             # Gradle project path
    test: "de.danoeh.antennapod.playback.PlaybackSpeedTest"      # class, or class.method
    method: "speedPersistsAfterRestart"                           # optional
pass_to_pass:                       # must pass at base and still pass after the fix
  - module: ":playback"
    test: "de.danoeh.antennapod.playback.PlaybackSpeedTest"      # whole class
  - module: ":model"                # a whole module's unit tests (test omitted)
limits:                             # per-task overrides of the defaults in config/limits.yaml
  timeout_minutes: 45
needs_emulator: false               # must be false in v1; true tasks are skipped
split: dev                          # dev | test — written by `abb split`, never by hand
status: validated                   # draft | validated | flaky | dropped
created_with_s2a_sha: abc1234       # `s2a/` commit current when the task was created (author-isolation record, D-019)
drafted_by: agent                   # agent | human — who wrote problem.md/gold/test before human review (RUN-ALL.md defaults; reported in the README)
drafted_with_model: claude-sonnet-5-5   # required when drafted_by: agent — the model that drafted it (it may be the model under test; a stated limitation)
hidden_tests: upstream             # upstream | authored — who wrote test.patch: the upstream PR, or the benchmark author (authored tasks, and mined tasks whose PR has no unit test; D-047)
validation:                         # written by `abb tasks validate`
  runs: 3
  last_validated: 2026-11-02T14:03:00Z
  env_fingerprint: sha256:...
  p2p_stable: ["de...PlaybackSpeedTest"]   # P2P tests that passed 3/3; whole-module P2P at grading is restricted to these
  screenshot_tolerance: null                 # Roborazzi/Paparazzi tasks: the comparison threshold the hidden test uses
```

### Rules

1. `problem.md` is a ticket, not a spec. Title, description, steps to reproduce, expected vs
   actual behaviour, optional screenshots described in words. **Never** test names, file paths,
   class names or stack traces unless the real upstream issue had them. Mined tasks reuse the
   upstream issue text, lightly cleaned (remove bot comments, links to the fix PR, version
   bumps). All arms receive this exact text.
2. `test.patch` may only touch files under the repo's `test_dirs` globs (see
   `repo-config.md`). If a mined PR's tests need a non-test helper (e.g. a `@VisibleForTesting`
   accessor), that helper goes in `gold.patch` and the task is tagged `tags.needs_test_hook: true`
   — graders must then expect some F2P failures to be compile failures. Prefer rewriting the
   test to avoid this.
3. `gold.patch` must apply cleanly to `base_commit` with `git apply --3way` disabled
   (`git apply --check`).
4. Every F2P entry must name at least a class. Whole-module F2P entries are not allowed (too
   coarse to prove the fix).
5. P2P must include at least the module(s) that `gold.patch` touches.
6. `needs_emulator: true` tasks are rejected by `abb tasks validate` in v1.
7. **Hidden-test interface rule (D-020).** `test.patch` may reference only classes, methods and
   constructors that either exist at `base_commit` or are named in `problem.md` (a real feature
   request often does name the public surface; a bug report rarely needs to). `abb tasks lint`
   extracts CamelCase identifiers from `test.patch`, subtracts those found in the base tree and
   in `problem.md`, and fails on any remainder. Prefer tests that exercise behaviour through
   pre-existing entry points; when a new surface is unavoidable, the ticket states it. The
   grader records the neutral reason `test_compile_failed` when the main sources compile but
   the test source set does not; it counts toward the "interface" table only when the diff is
   non-empty and touches the F2P module(s) (an empty diff on a `new_surface` task is simply
   "did not do the work"). Whether a given case really is a correct fix with a different shape
   is decided by the blind Phase 9 label `INTERFACE`, never by the grader.
8. **Identifier leak.** `problem.md` may not contain CamelCase identifiers that appear only in
   `gold.patch` (the fix's new names) unless `tags.ticket_mentions_code: true` and the upstream
   ticket had them.

### Test selection → Gradle command

The harness composes the Gradle invocation from `repos/<repo>.yaml`:

```
./gradlew --offline --console=plain --continue \
  <module>:<unit_test_task> --tests '<test>[.<method>]'
```

where `unit_test_task` comes from `repos/<repo>.yaml: test_task_for_module` (module-specific
override, else default). Validation and grading add `--no-build-cache` and `<module>:cleanTest`. JUnit XML is read from
`<module-dir>/build/test-results/<unit_test_task>/TEST-*.xml`.

## Task sources

| Source | How to build it | Tagging |
|---|---|---|
| **mined** | `abb tasks mine <repo> --since <date>` lists merged PRs that (a) close an issue, (b) touch test files, (c) touch ≤ 8 non-test files. For each candidate: `base_commit` = PR merge-base parent; `gold.patch` = non-test diff; `test.patch` = test diff; `problem.md` = the linked issue body. Then hand-edit. | `source: mined`, `upstream.*` filled |
| **reverted** | Pick a merged feature commit with tests. `base_commit` = its parent. `gold.patch` = the feature's non-test diff; `test.patch` = its tests. Write `problem.md` as a feature request in the project's issue style. | `source: reverted` |
| **authored** | Choose a realistic change nobody made upstream. Write `problem.md`, implement a reference fix (`gold.patch`) and tests (`test.patch`) yourself. | `source: authored`, no `upstream.pr_url` |

Target mix: 50 % mined, 15 % reverted, 35 % authored. Report mined/reverted ("historical") vs
authored separately in Phase 9.

## Validation (`abb tasks validate <id> --runs 3`)

For each run, in a fresh workspace as the harness user, offline (proxy stopped):

| Step | State | Expectation |
|---|---|---|
| V0 | base only | build succeeds; every P2P test **passes** (the baseline for modules whose test source set may not compile at V1) |
| V1 | base + `test.patch` | every F2P test **fails or errors**. For tasks with `tags.new_surface: false` the test source set compiles and P2P passes; for `new_surface: true` tasks the F2P module's test source set is **expected not to compile** (the hidden tests use a surface the fix introduces) — recorded as `validation.v1_test_compile: failed_as_expected` — and P2P in other modules still passes |
| V2 | base + `gold.patch` + `test.patch` | build succeeds; every F2P test **passes**; every P2P test **passes** |

A task is `validated` only if all 3 runs agree on V1 and V2. Any disagreement → `status: flaky`
with the differing test names recorded in `validation.flaky_tests`; P2P tests that passed 3/3
are listed in `validation.p2p_stable` (whole-module P2P at grading is restricted to them).
`abb tasks validate` writes the `validation:` block and the environment fingerprint used.

## Template

`benchmark/tasks/_template/` holds a filled-in skeleton to copy with `abb tasks new <id>`.
