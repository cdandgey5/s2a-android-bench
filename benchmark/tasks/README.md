# Authoring guide — benchmark tasks

A task is a folder `tasks/<repo>-<NNNN>/` (`specs/task-format.md`): `task.yaml`, `problem.md`
(the only text any arm sees), `test.patch` (hidden tests), `gold.patch` (reference fix),
`NOTES.md` (provenance, never shown to agents) and, for GPL repos, `LICENSE-NOTE.md`.

In autopilot mode (`phases/RUN-ALL.md`) the building agent drafts every task
(`drafted_by: agent`, `drafted_with_model`) and the human reviews each one at stop point **S2**
before validation. Every task records `created_with_s2a_sha` (author isolation, D-019).

## The loop

```powershell
uv run abb tasks mine antennapod --since 2026-07-01          # candidates -> C:\abb\state\candidates\antennapod\pr-<N>\ (+ TRIAGE.json)
uv run abb tasks mine antennapod --promote 8773              # copy a candidate to tasks/antennapod-<NNNN>
uv run abb tasks new antennapod-0005 --repo antennapod --base-commit <sha>   # authored or reverted task from the template
# edit problem.md / test.patch / gold.patch / task.yaml
uv run abb tasks tag antennapod-0005                         # files, modules, lang, ui, test kind
uv run abb tasks lint antennapod-0005                        # named rules; 0 errors before S2
# S2: human review
uv run abb tasks validate antennapod-0005 --runs 3           # V0/V1/V2 x 3 in fresh offline workspaces
```

## Writing `problem.md` like a real issue

- Title + description in the voice of a user or maintainer: what happens, what should happen,
  steps to reproduce, environment. For features: why it is wanted and what "done" looks like
  from the user's side.
- **No file paths, class or test names, stack traces** unless the real upstream issue had them
  (then set `tags.ticket_mentions_code: true` and say so in `NOTES.md`). Lint enforces this:
  `problem-no-paths`, `problem-no-test-names`, `identifier-leak`.
- Mined tickets start as the issue text with templates stripped. Remove links to the fix PR,
  discussion of where the fix goes, bot comments and version bumps.
- A feature request may name the public surface the hidden tests use (a new method or setting
  name); then lint marks the task `new_surface` (D-020). A bug report rarely needs to.

## Hidden tests that pin behaviour, not implementation

- `test.patch` only touches the repo's `test_dirs` (lint `test-patch-in-test-dirs`) and only uses
  identifiers that exist at `base_commit` or are named in `problem.md` (lint `interface-rule`).
  Prefer driving behaviour through existing entry points (a parser's public method, a database
  query, a ViewModel) over asserting on new helpers.
- If a mined PR's tests need a non-test hook (a `@VisibleForTesting` accessor, a new constructor
  parameter), rewrite the test against the public surface; only if that is impossible, put the
  hook in `gold.patch` and set `tags.needs_test_hook: true`.
- F2P entries name at least a class, ideally the method(s) that fail at base. P2P must include
  every module `gold.patch` touches (lint `p2p-covers-gold-modules`); a whole-module P2P entry
  (`- module: ":x"` without `test`) is fine and is restricted at grading to `validation.p2p_stable`.
- Robolectric for Android-dependent code: `@RunWith(RobolectricTestRunner.class)`; keep tests
  deterministic (`ShadowLooper.idleMainLooper()`, fixed clocks, no network: Robolectric runs
  offline from `caches\robolectric\<repo>` in every trial and at grading).
- Values that look exact must be exact (e.g. binary-exact decimals in duration parsing).

## Task sources

| Source | How | `upstream` |
|---|---|---|
| **mined** | `abb tasks mine`: merged PR that closes an issue, touches tests, ≤ 8 non-test files; base = first parent of the merge commit; diff split by `test_dirs` | `issue_url`, `issue_created`, `pr_url`, `fix_commit`, `fix_date` |
| **reverted** | a merged feature commit with tests: base = its parent, `gold.patch` = its non-test diff, `test.patch` = its tests; write `problem.md` as a feature request in the project's issue style | `pr_url` (if any), `fix_commit`, `fix_date` |
| **authored** | a realistic change nobody made upstream: write the ticket, the reference fix and the tests yourself | none (no `pr_url`) |

Post-cutoff (D-001): a task is post-cutoff only if `issue_created` **and** `fix_date` are on or
after 2026-07-01; `abb tasks mine` keeps only those unless `--allow-pre-cutoff`.

## Categories and tags

- `category`: `bugfix` | `feature` | `refactor` (behaviour-preserving restructuring, tests pin the
  behaviour) | `cross_module` (the fix must change ≥ 2 Gradle modules).
- `tags` are computed by `abb tasks tag` except `needs_test_hook`, `ticket_mentions_code`
  (set deliberately) and `new_surface` (suggested by lint).

## License note (GPL repos)

`LICENSE-NOTE.md` states the upstream repository, commit and license of the derived patches and
which issue `problem.md` paraphrases (template in `_template/`); `abb tasks mine --promote`
writes it.

## Validation

`abb tasks validate <id> --runs 3`: each run is a fresh history-free workspace, offline, with the
harness-only pristine Gradle home; V0 base → P2P passes; V1 + `test.patch` → F2P fails (or, for
`new_surface`, the F2P module's test sources fail to compile as expected), P2P passes; V2 +
`gold.patch` → everything passes. Three agreeing runs → `status: validated` and the
`validation:` block (`p2p_stable`, `env_fingerprint`); disagreement → `flaky` with the differing
tests. Logs: `tasks/<id>/.validation/<timestamp>/` (git-ignored). Fix flaky tests in
`test.patch` rather than dropping the task.
