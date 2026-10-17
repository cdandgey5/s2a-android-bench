# Spec: Arm B — GitHub Spec Kit, automated

Facts as of 2026-10-16 (re-verify in Phase 5 step 1 with `specify --version`, `specify init --help`
and by listing the command files `specify init` writes):

- Install: `uv tool install specify-cli --from git+https://github.com/github/spec-kit.git@<tag>`.
- Init in an existing repo: `specify init --here --force --non-interactive --integration claude --script sh --ignore-agent-tools`.
- Commands are **hyphenated**: `/speckit-constitution`, `/speckit-specify`, `/speckit-clarify`
  (optional), `/speckit-plan`, `/speckit-checklist` (optional), `/speckit-tasks`,
  `/speckit-analyze` (optional), `/speckit-implement`, `/speckit-converge` (new; "repeat
  implement → converge until it reports Converged").
- Bug-fix extension: `specify extension add bug` → `/speckit-bug-assess`, `/speckit-bug-fix`,
  `/speckit-bug-test`.
- Artifacts: `spec.md`, `plan.md`, `tasks.md`, `checklists/`, `.specify/feature.json`,
  `.specify/memory/constitution.md` (path to confirm), `.specify/bugs/<slug>/`.

## One-time setup per repo (`one_time_setup`)

In a workspace at the repo's `setup_commit` (the octopus merge-base of the repo's task base
commits — see `repo-config.md` and `fairness-protocol.md`; never at `cache_commit`, which
already contains the fixes), network `api-only`:

1. `specify init --here --force --non-interactive --integration claude --script sh --ignore-agent-tools`
2. `specify extension add bug`
3. Headless call `speckit-constitution`: prompt
   `"/speckit-constitution Derive the constitution from this existing codebase: its languages, architecture, testing conventions, code style and release constraints. Do not invent principles the code does not follow."`
4. Save `.specify/` and `.claude/` (command files) as `setup/speckit/<repo>/artifacts/`. The
   runner copies these into every Spec Kit task workspace for that repo before `run()`.
   (Alternative: bake into a derived image `abb-<repo>-speckit`; choose in Phase 5 and record.)

Setup cost = the constitution call (`setup/speckit/<repo>/run.json`).

## Per-task sequence (`run`)

All calls share one Claude Code session (`--resume`) except where noted. `T` = ticket text.

**Feature / refactor / cross-module path (SDD):**

| # | call_name | prompt | turn cap |
|---|---|---|---|
| 1 | `speckit-specify` | `/speckit-specify <T>` | 15 |
| 2 | `speckit-plan` | `/speckit-plan Use the existing build, module layout and test conventions of this repository. Do not add new frameworks.` | 15 |
| 3 | `speckit-tasks` | `/speckit-tasks` | 15 |
| 4 | `speckit-implement` | `/speckit-implement` | 120 |
| 5 | `speckit-converge` | `/speckit-converge` | 20 |
| 6 | `speckit-implement-2` | only if converge added tasks: `/speckit-implement` | remaining |

**Bugfix path (bug extension):**

| # | call_name | prompt | turn cap |
|---|---|---|---|
| 1 | `speckit-bug-assess` | `/speckit-bug-assess <T>` | 20 |
| 2 | `speckit-bug-fix` | `/speckit-bug-fix` | 120 |
| 3 | `speckit-bug-test` | `/speckit-bug-test` | 40 |

Arm config `speckit.path_by_category: {bugfix: bug, feature: sdd, refactor: sdd, cross_module: sdd}`.
A variant arm `speckit-sdd` forces the SDD path for everything (optional ablation of the
tool's own routing).

`/speckit-clarify`, `/speckit-checklist`, `/speckit-analyze` are **skipped** (they expect a
human). Decision recorded in `docs/DECISIONS.md` (D-006) and stated in the README so nobody can
call the arm a strawman unknowingly; the `speckit-sdd` variant is kept, and a `speckit-full`
variant (clarify auto-answered with the nudge text) is an optional exploratory arm. The nudge
protocol handles any question the remaining commands ask.

## Slash command invocation check (Phase 5 step 2)

Run `claude -p "/speckit-specify Add a button"` in a scratch workspace and confirm the transcript
shows the command's template being expanded. If expansion does not happen (name form changed,
`--bare` default, etc.), fall back to **template inlining**: read the command file
(`.claude/commands/speckit-specify.md` or `.claude/skills/speckit-specify/SKILL.md`), substitute
`$ARGUMENTS`, and send the resulting text as the prompt. Record which mechanism was used in
`run.json.notes`.

## Artifacts captured

Copy `specs/**`, `.specify/**` (minus templates), and `.specify/bugs/**` to `artifacts/`. These
paths are in `repos.workspace.diff_exclude`, so they never reach the grader. Spec Kit's plan
step also rewrites the repo's agent-context file (`CLAUDE.md`); that path is in `diff_exclude`
for every repo so it does not inflate arm B's diff size or scope-creep metrics.

## Environment preamble

Every Spec Kit call receives `abb/arms/common/environment.md` via `--append-system-prompt`,
exactly like the other arms (fairness-protocol.md). The Spec Kit command templates themselves
are untouched.

## Turn budget split

Total 200 turns: SDD path 15+15+15+120+20+remaining; bug path 20+120+40+remaining. If an
earlier call ends in `error_max_turns`, continue to the next call anyway (the artifacts may be
partial) and note it.
