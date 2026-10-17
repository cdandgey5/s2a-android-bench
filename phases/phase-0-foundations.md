# Phase 0 — Foundations (Windows-native)

**Goal.** A runnable `abb` CLI skeleton, the pinned toolchain installed under `ABB_HOME`, verified
tool facts (including how Claude Code behaves headlessly on Windows), an evidence-based choice of
the first two repositories, and one seed task so every later harness piece has a fixture.

**Prerequisites (done by the human — `docs/DAY-0.md`).** Windows 11, PowerShell 7, Git for
Windows, `gh` (authenticated), `uv`, Claude Code ≥ 2.1.280 pinned and its version written into
`benchmark/config/toolchain.yaml`; the subscription token from `claude setup-token` as the user
environment variable `ABB_OAUTH_TOKEN`, with **no** `ANTHROPIC_API_KEY` and **no** global
`CLAUDE_CODE_OAUTH_TOKEN`; `ABB_HOME`
on the drive with the most space (≥ 60 GB free); the plan cloned to `%USERPROFILE%\abb-src` with a
private GitHub remote; the pinned model's training-cutoff date in D-001. No admin rights are
needed in this phase.

**Effort.** ~1 week part-time. Most of it is waiting for Gradle.

## Deliverables

```
.gitignore                     # root: .venv/, __pycache__/, *.tmp, .env
benchmark/
  pyproject.toml                 # package `abb`; deps: typer, rich, pydantic, pyyaml, pandas, numpy, matplotlib, keyring; windows: pywin32 (no `anthropic` SDK: every model call goes through `claude.exe`)
  README.md  LICENSE (MIT)  .env.example
  abb/__init__.py
  abb/cli.py                     # Typer app: tools, env, sandbox, auth, tasks, repos, run, grade, grade-patch, report, split, labels, audit, repro, ws
  abb/config.py                  # pydantic models: RepoConfig, TaskConfig, SandboxConfig, ToolchainConfig, LimitsConfig (re-exports arms.base.Limits); 5-line .env loader
  abb/paths.py                   # ABB_HOME, TOOLS, CACHES, WORK, RESULTS (= ABB_RESULTS_DIR), REPO_CLONE; all pathlib
  abb/log.py
  abb/harness/platform/{base,windows}.py   # specs/platform-layer.md (posix.py is a stub raising NotImplementedError)
  abb/harness/platform/abb_launch.py       # the launcher (stdlib + ctypes only); copied to ABB_HOME/tools by `abb tools install`
  abb/harness/smoke.py                     # `abb ws smoke [--deadline N] "<prompt>"`: runs claude.exe through the platform layer as the harness user
  abb/harness/tools.py           # `abb tools install|check`: JDK 17/21 + cmdline-tools + sdk packages, checksummed, lock file
  config/limits.yaml  config/sandbox.yaml  config/toolchain.yaml     # seeds provided
  repos/{antennapod,wikipedia,thunderbird,newpipe}.yaml                # seeds provided; fill in discovered values for the two chosen repos
  scripts/try_build.py           # repo-selection experiment (below); Python, not shell
  tasks/antennapod-0000/         # seed task (step 8)
  tests/test_config.py           # schemas load the seed yaml files
  tests/platform/test_windows.py # start/stop a process, memory limit, tree kill, robust delete with a locked file
  tests/fixtures/transcripts/{smoke-success,smoke-maxturns1,smoke-interrupt}.jsonl   # from step 5
docs/RUNS.md                     # lab notebook from day one: date, run id or activity, model, tokens, est. USD, usage pauses
docs/DECISIONS.md                # confirm D-001…D-005, D-024 (Windows-native); fill D-003 with evidence
reference/verified.md            # dated verification of external facts (Windows section)
reference/build-experiments.md   # results of the repo-selection experiment
```

## Steps

1. **Verify the bootstrap.** In `%USERPROFILE%\abb-src` (PowerShell 7): `$PSVersionTable.PSVersion`
   (7.x), `git --version`, `gh auth status`, `uv --version`, `& "$env:USERPROFILE\.local\bin\claude.exe"
   --version` (≥ 2.1.280 and equal to `toolchain.yaml`), `$env:ABB_HOME` set and on a drive with
   ≥ 60 GB free (`Get-PSDrive`), `$env:ABB_OAUTH_TOKEN` set, `$env:ANTHROPIC_API_KEY` and
   `$env:CLAUDE_CODE_OAUTH_TOKEN` unset (never print the token), `git remote -v` shows the private
   remote. Record everything
   in `reference/verified.md`. If anything
   is missing, stop and tell the human exactly what to do.
2. **Project skeleton.** `uv init --package` style layout with the files above. `uv run abb --help`
   must list every command group (stubs print "not implemented in this phase"). No `.sh` files
   anywhere; helper scripts are Python or `.ps1`.
3. **Config models.** Implement `RepoConfig`, `TaskConfig`, `SandboxConfig`, `ToolchainConfig`,
   `LimitsConfig` (`extra="forbid"`); `Limits` lives in `abb/arms/base.py`. **SHA fields accept 40
   hex characters or the literal `TODO_*`**; the strict check is `abb repos check <repo>`.
   `tests/test_config.py` loads every `repos/*.yaml`, `tasks/_template/task.yaml`, `config/*.yaml`.
4. **Platform layer + toolchain.** Implement `platform/windows.py` and the launcher for the
   harness-user path first (launcher under the shared Python, Job Object with a job-wide memory
   limit, STOP-file → Ctrl+C on the launcher's console, robust delete; the sandbox-user launch via
   `CreateProcessWithLogonW` is Phase 1). `abb ws smoke` is the thin command that exercises it.
   Implement `abb tools install`: resolve JDK 17 and 21 from the Adoptium API (first install
   records `release_name` + sha256 in the lock; later installs fetch exactly that release), download
   zips into `ABB_HOME\tools\jdk17|21`; `uv python install 3.12` into `UV_PYTHON_INSTALL_DIR`; copy the
   harness user's pinned `claude.exe` to `ABB_HOME\tools\claude\<version>\`; download the Windows command-line tools zip,
   verify its sha256, unpack to `ABB_HOME\tools\android-sdk\cmdline-tools\latest`, accept licenses
   by piping `y` lines, install the pinned packages with `sdkmanager.bat`; apply the git global
   config from `toolchain.yaml`; write `config/toolchain.lock.yaml`. `abb tools check` re-verifies.
5. **Tool verification.** Paste outputs into `reference/verified.md`: `java -version` from both
   JDKs, `sdkmanager.bat --list_installed`, `claude.exe --version`, `specify --version`, `specify
   init --help`. Then `abb auth check` (runs `claude.exe auth status` through the launcher with the mapped
   token and an empty `CLAUDE_CONFIG_DIR`; record `authMethod` — expected `oauth_token`). Then
   the Claude smoke tests from `specs/headless-agent-driving.md` **through the harness driver's
   launch path** (`abb ws smoke`), saving fixtures: `smoke-success`,
   `smoke-maxturns1`, and `smoke-interrupt` (deadline hit → the launcher sends Ctrl+Break to the child's process
   group, then in a second run Ctrl+C → does a `result` line appear? exit code? record both and
   set `sandbox.yaml: process.interrupt` to the one that ends the turn cleanly). Then the **scrub
   check** from the same spec section: both shells must report `UNSET` for
   `CLAUDE_CODE_OAUTH_TOKEN` and the transcript must not contain the token (stop if not — D-026).
   Check every flag the driver spec uses against `claude --help`. Check the
   settings reference of the pinned version for `switchModelsOnFlag` (documented as of
   2026-10-17: `false` = "Ask each time"; in `-p` a flagged request ends the turn with a refusal);
   keep it in `sandbox/claude-config.template/settings.json` if the pinned version still documents
   it. Record in `reference/verified.md`: whether any smoke transcript contains a
   `rate_limit_event` line and which fields it carries (`status`, `resetsAt`, `rate_limit_type`,
   anything like utilisation — the Agent SDK documents the event, the `-p` docs do not); and
   whether Anthropic documents a way to revoke a `setup-token` token. Record the resolved model id from
   the `init` event, and whether the Bash tool runs Git Bash (`echo $BASH_VERSION`). Also confirm the
   hidden launcher console does not flash a Windows Terminal window (else switch to
   `CREATE_NO_WINDOW`), and record the peak job memory of a module test run with two Robolectric
   workers — that number sets `sandbox.yaml: process.memory_mb`.
6. **Repo-selection experiment (two repos are enough for the gate).** `uv run python
   scripts/try_build.py <repo_url> <ref> <jdk> [--lib-module :m --lib-task t] [--app-module :app
   --app-task t]` in a scratch dir under `ABB_HOME\work\experiments`, using the installed JDK and
   a scratch `GRADLE_USER_HOME` and `JAVA_TOOL_OPTIONS=-Duser.home=<experiment>\home` (keeps
   Robolectric's downloads out of your profile); a Job Object caps memory at 8 GB and reports the peak. First
   run: `gradlew.bat tasks --all` and print the `*UnitTest` task names; second run with
   module/task arguments: time the library-module and app-module unit tests (cold and warm),
   peak memory from the job, LOC via a small Python counter (Java/Kotlin lines), Robolectric
   presence and SDK levels, test counts, failures, secrets needed, merged-PRs-with-linked-issue
   count (`gh pr list -R <owner/repo> --state merged --search "fixes OR closes OR resolves
   merged:>=<date 2 years ago>" --limit 500 --json number | ConvertFrom-Json | Measure-Object`).
   Do **AntennaPod** and **Wikipedia Android** now; Thunderbird (JDK 21) and NewPipe are deferred
   to Phase 7. Write `reference/build-experiments.md` with the table and the decision: repo #1 and
   #2. Criteria: builds without secrets; unit tests pass offline after one warm run; warm test run
   < 10 min; Robolectric or plain JUnit tests across several modules; roughly 20k–150k LOC
   (deviations into D-003); ≥ 100 linked merged PRs; **no two paths differing only by case**;
   **longest path < 200 characters** from the repo root (Windows).
7. **Fill repo configs** for the two chosen repos (JDK, sdk packages actually resolved, test task
   names, warm commands, test dirs, `tests.verify_modules`, `cache_commit` = the ref you built).
8. **Seed task.** While the AntennaPod checkout is at hand, author `benchmark/tasks/antennapod-0000`
   per `specs/task-format.md`: a trivial change in a pure-Java utility class with a plain JUnit
   hidden test; `problem.md` like an issue; `gold.patch`, `test.patch` (LF line endings, applied
   as bytes), `LICENSE-NOTE.md`, `source: authored`, `status: draft`.
9. **Decisions log.** Confirm D-001…D-005 and D-024; write the training-cutoff date, the current
   model ids and the resolved id into D-001; fill D-003.
10. **Lab notebook.** Start `docs/RUNS.md` (date, run id or activity, model, tokens in/out,
    est. API-equivalent USD from the result line, usage-limit pauses, note). Every run from now
    on gets a row.
11. Commit `phase 0: foundations` and push.

## Acceptance gate

```powershell
uv run abb --help
uv run pytest -q                                   # incl. tests/platform/test_windows.py
uv run abb tools check                             # jdk17, jdk21, android-sdk present and checksums match the lock
& "$env:USERPROFILE\.local\bin\claude.exe" --version   # equals toolchain.yaml, >= 2.1.280
uv run abb auth check                              # exit 0; authMethod oauth_token through the launcher; subscriptionType recorded
Get-ChildItem benchmark\tests\fixtures\transcripts  # smoke-success.jsonl smoke-maxturns1.jsonl smoke-interrupt.jsonl
Get-Content reference\verified.md                  # claude version + flags table, interrupt finding (Ctrl+Break and Ctrl+C), scrub check UNSET/UNSET, rate_limit_event finding, resolved model id, Git Bash check, sdk list, disk
Get-Content reference\build-experiments.md         # >= 2 repos with timings and the choice
uv run abb repos check antennapod                  # strict: SHAs real, task names filled, case/path-length checks
Get-ChildItem benchmark\tasks\antennapod-0000      # task.yaml problem.md test.patch gold.patch LICENSE-NOTE.md
```

Gate passes when: the toolchain is installed and locked; `abb auth check` reports
`oauth_token`; the three smoke fixtures exist with
the expected subtypes (and `reference/verified.md` states what happens on Ctrl+Break and on Ctrl+C, and which one both drivers will use); the scrub check printed `UNSET` in both shells; at least
two candidate repos ran unit tests on Windows with wall time recorded; repo #1 and #2 are named
with evidence; their configs pass `abb repos check`; the seed task exists.

## Pitfalls

- Work only in `%USERPROFILE%\abb-src`; never under OneDrive.
- `claude.exe` must be called by its absolute path — Claude Desktop can register a `Claude.exe`
  that wins on PATH.
- Git line endings: `core.autocrlf=false` before cloning anything; a CRLF-converted checkout makes
  every patch fail to apply.
- Gradle on Windows is slower under Defender real-time scanning; an exclusion for `ABB_HOME` is a
  human decision (`docs/DAY-0.md`).
- `sdkmanager.bat` needs `JAVA_HOME` pointing at a JDK ≥ 17; licenses are accepted by feeding `y`
  lines on stdin from Python (there is no `yes` command).
- Gradle daemons keep files locked; `try_build.py` runs `gradlew.bat --stop` before deleting scratch
  checkouts, and the platform layer's robust delete reports leftovers.
- Thunderbird uses `.java-version` 21; NewPipe has KMP folders — both deferred to Phase 7.
