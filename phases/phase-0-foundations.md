# Phase 0 — Foundations

**Goal.** A runnable `abb` CLI skeleton, the shared `abb-base` Docker image, verified tool facts,
an evidence-based choice of the first two repositories, and one seed task so every later
harness piece has a fixture from day one.

**Prerequisites (done by the human, before the first agent session — see `docs/DAY-0.md`).**
WSL2 Ubuntu with Docker Desktop's **WSL integration enabled for that distro**; `claude`, `gh`
(authenticated) and `uv` installed **inside WSL**; a Console API key with credit exported as
`ANTHROPIC_API_KEY` (or in `benchmark/.env`); `.wslconfig` set (24 GB / 8 CPU / 8 GB swap) and
WSL restarted; **≥ 120 GB free** on the drive holding the WSL vhdx; the plan cloned to `~/abb`
with a private GitHub remote; the pinned model's training-cutoff date written into D-001; a
dev budget agreed (`profiles.dev.max_usd` in `config/limits.yaml`). The agent runs **in
`~/abb`**, never under `/mnt/c/...`.

**Effort.** ~1 week part-time. Most of it is waiting for Gradle.

## Deliverables

```
.gitignore                     # root: .venv/, results/, *.tmp, __pycache__/, .env  (benchmark/.gitignore stays)
benchmark/
  pyproject.toml                 # uv project; package `abb`; console script `abb`
  README.md                      # how to run the harness (short; grows per phase)
  LICENSE                        # MIT
  .env.example                   # ANTHROPIC_API_KEY=, GITHUB_TOKEN=
  abb/__init__.py
  abb/cli.py                     # Typer app: images, tasks, repos, run, grade, grade-patch, report, split, labels, audit, repro, ws
  abb/config.py                  # pydantic models: RepoConfig, TaskConfig, NetworkConfig, LimitsConfig (re-exports arms.base.Limits); 5-line .env loader (no dotenv dependency)
  abb/paths.py                   # BENCH_ROOT, REPOS_DIR, TASKS_DIR, RESULTS_DIR (= $ABB_RESULTS_DIR, default ~/abb-results), DOCKER_DIR
  abb/log.py                     # rich logging; every long command echoes its argv
  abb/harness/images.py          # build-base only in this phase (per-repo images are Phase 1)
  config/limits.yaml             # seed provided (source of truth for limits)
  config/network.yaml            # seed provided
  docker/base/Dockerfile         # seed provided; adjust only via build-args
  repos/{antennapod,wikipedia,thunderbird,newpipe}.yaml   # seeds provided; fill in discovered values for the two chosen repos
  scripts/try_build.sh           # repo-selection experiment (below)
  tasks/antennapod-0000/         # seed task (step 8)
  tests/test_config.py           # schemas load the seed yaml files
  tests/fixtures/transcripts/{smoke-success,smoke-maxturns1}.jsonl   # from step 5
docs/RUNS.md                     # lab notebook from day one: run id, what, model, cost
docs/DECISIONS.md                # confirm D-001…D-005 (already drafted), fill D-003 with evidence
reference/verified.md            # dated verification of external facts
reference/build-experiments.md   # results of the repo-selection experiment
```

## Steps

1. **Verify the bootstrap.** In `~/abb`: `docker info | grep -iE 'operating system|total memory|cpus'`
   (≥ 20 GB, ≥ 6 CPUs), `df -h /mnt/c` (the Windows drive that holds both vhdx files: ≥ 120 GB
   free; `df -h ~` reports the vhdx's virtual size and proves nothing), `docker system df`,
   `curl -s 'https://api.anthropic.com/v1/models?limit=1000' … | jq -r '.data[].id'` lists both pinned ids (the endpoint pages at 20 by default), `claude --version`,
   `gh auth status`, `uv --version`, `git remote -v` (the private GitHub remote), `echo
   ${ANTHROPIC_API_KEY:+set}`. Record the numbers in `reference/verified.md`. If anything is
   missing, stop and ask the human to finish `docs/DAY-0.md`.
2. **Project skeleton.** `uv init --package` style layout with the files above (root
   `.gitignore` included). Dependencies: `typer`, `rich`, `pydantic>=2`, `pyyaml`, `docker>=7`,
   `pandas`, `numpy`, `matplotlib`, `anthropic`; dev: `pytest`, `ruff`. `uv run abb --help`
   must list every command group (commands may be stubs that print "not implemented in this
   phase"). The `.env` loader is a five-line parser in `abb/config.py`.
3. **Config models.** Implement `RepoConfig`, `TaskConfig`, `NetworkConfig` and `LimitsConfig`
   per `specs/repo-config.md`, `specs/task-format.md`, `specs/headless-agent-driving.md`;
   `Limits` itself lives in `abb/arms/base.py` (seed) and `config.py` re-exports it. Unknown
   keys are errors (`extra="forbid"`). **SHA fields accept either 40 hex characters or the
   literal `TODO_*`**; the strict check lives in `abb repos check <repo>` so the seeds still
   load. `tests/test_config.py` loads every `repos/*.yaml`, `tasks/_template/task.yaml` and
   `config/*.yaml`.
4. **Base image.** Implement `abb images build-base --jdk 17|21` (Docker SDK, streams build
   logs, tags `abb-base:jdk<N>`; build context `benchmark/docker/base/`). Re-verify the
   command-line-tools filename/sha256 on https://developer.android.com/studio and update the
   build-arg defaults if changed. Build both JDK variants. Record the resolved base-image digest
   (`docker inspect --format '{{index .RepoDigests 0}}' eclipse-temurin:17-jdk-noble`) in
   `images.lock.json` under `base_digests` (Phase 4 pins it in the `FROM` line).
5. **Tool verification inside the image.** Run and paste outputs into `reference/verified.md`:
   ```
   docker run --rm abb-base:jdk17 bash -lc 'id; java -version; sdkmanager --list_installed; claude --version; specify --version; specify init --help; cloc --version'
   ```
   Then the three Claude smoke tests from `specs/headless-agent-driving.md` (with `-e
   ANTHROPIC_API_KEY`), saving the stream-json files as the parser fixtures (`smoke-success`,
   `smoke-maxturns1`, `smoke-sigint` — the last proves SIGINT yields a `result` line and exit 124). Check every flag
   the driver spec uses against `claude --help` and mark each CONFIRMED/CHANGED. Pin the exact
   Claude Code version via `CLAUDE_CODE_VERSION` (rebuild). If the model id is rejected, look
   up the current ids, update D-001, continue. Also run one prompt likely to trip a safety
   flag inside `-p` and confirm the call *ends* (no model switch, no hang); check the pinned
   version's settings reference for `switchModelsOnFlag` — keep the image setting if documented,
   remove it otherwise — and confirm no `fallbackModel`/`ANTHROPIC_MODEL` is set; record the
   behaviour and the resolved model id the `init` event reports.
6. **Repo-selection experiment (two repos are enough for the gate).** `scripts/try_build.sh
   <repo_url> <ref> <jdk> [<lib-module> <lib-test-task>] [<app-module> <app-test-task>]` runs
   in a plain `abb-base:jdk<N>` container with 8 GB memory. Run it once with the first three
   arguments to discover the test tasks, then again with module/task arguments:
   ```
   git clone --filter=blob:none <url> /home/bench/x && cd /home/bench/x && git checkout <ref>   # blobless clone works for any ref
   ./gradlew --console=plain tasks --all | grep -oE '^[A-Za-z0-9:_-]*UnitTest' | sort -u   # discover test tasks (lines are `name - description`)
   time ./gradlew --console=plain <lib-module>:<lib-test-task>                   # e.g. :model:testDebugUnitTest
   time ./gradlew --console=plain <app-module>:<app-test-task>                   # e.g. :app:testFreeDebugUnitTest
   cloc --include-lang=Java,Kotlin .                                             # size
   du -sh ~/.gradle ~/.m2
   ```
   Do **AntennaPod** and **Wikipedia Android** now (expect half a day of waiting each);
   Thunderbird (JDK 21) and NewPipe may run in the background but are otherwise deferred to
   Phase 7, which repeats this step and Phase 1 for repos 3/4. Record per repo: clone size,
   discovered unit-test task names, build+test wall time (cold and warm), peak memory (`docker
   stats`), failures, whether any secret/stub was needed, Robolectric presence and SDK levels,
   test counts, LOC, merged-PRs-with-linked-issue count in the last two years (`gh pr list -R
   <owner/repo> --state merged --search "fixes OR closes OR resolves merged:>=$(date -d '2 years
   ago' +%F)" --limit 500 --json number | jq length`). Write `reference/build-experiments.md` with a table and a decision: repo #1 and
   repo #2. Criteria: builds without secrets; unit tests pass offline after one warm run; warm
   test run < 10 min; Robolectric or plain JUnit tests across several modules; roughly
   20k–150k LOC (deviations go into D-003 with how tasks are scoped); ≥ 100 linked merged PRs.
7. **Fill repo configs** for the two chosen repos from the experiment (JDK, sdk packages the
   build actually resolved — `sdkmanager --list_installed` after the build —, test task names,
   warm commands, test dirs, `tests.verify_modules`, `cache_commit` = the ref you built).
8. **Seed task.** While the AntennaPod clone is at hand, author `benchmark/tasks/antennapod-0000`
   per `specs/task-format.md`: a trivial, self-contained change in a pure-Java utility class
   (`:model` or `:parser`) with a plain JUnit hidden test, `problem.md` written like an issue,
   `gold.patch`, `test.patch`, `LICENSE-NOTE.md`, `source: authored`, `status: draft`. It is the
   fixture for Phase 1 verification, Phase 2 validation and Phase 3 grading before real tasks
   exist; it is pinned to `dev` by the split rule.
9. **Decisions log.** Confirm D-001…D-005 in `docs/DECISIONS.md` (write the training-cutoff
   date and the current model ids into D-001), fill D-003 with the experiment evidence.
10. **Lab notebook.** Start `docs/RUNS.md` with a table (date, run id or activity, model,
    cost USD from the Console, note). Every API-spending activity from now on gets a row.
11. Commit `phase 0: foundations` and push.

## Acceptance gate

```
uv run abb --help
uv run pytest -q
docker images | grep abb-base                      # jdk17 and jdk21 present
docker run --rm abb-base:jdk17 bash -lc 'id -u; claude --version; specify --version'   # 1000, pinned versions
ls benchmark/tests/fixtures/transcripts/           # smoke-success.jsonl smoke-maxturns1.jsonl smoke-sigint.jsonl
cat reference/verified.md                          # date, claude version+flags table, specify version+init flags, cmdline-tools filename/sha, WSL memory, disk, safety-flag behaviour
cat reference/build-experiments.md                 # >=2 repos with timings and the choice
uv run abb repos check antennapod                  # strict: SHAs real, task names filled
ls benchmark/tasks/antennapod-0000/                # task.yaml problem.md test.patch gold.patch LICENSE-NOTE.md
```

Gate passes when: both base images build; both smoke tests produced fixtures with the expected
subtypes; at least two candidate repos ran unit tests inside the container with wall time
recorded; repo #1 and #2 are named with evidence; their `repos/<repo>.yaml` pass `abb repos
check`; the seed task exists.

## Pitfalls

- Work only in the WSL clone (`~/abb`); OneDrive holds the original import, not the working
  tree. Docker Desktop file sharing of `/mnt/c` is slow and OneDrive syncs everything it sees.
- `useradd -u 1000` fails on the noble base unless the default `ubuntu` user is removed first
  (the seed Dockerfile does this).
- `sdkmanager` needs `yes | sdkmanager --licenses`; Gradle's Android plugin may demand a newer
  `build-tools` than you pinned — read the error, pin that version.
- Claude Code refuses `bypassPermissions` as root. The Dockerfile sets `USER bench`. The image
  also disables autoupdate and non-essential traffic; keep those env vars.
- The `uv tool install specify-cli` step needs Python ≥ 3.11 in the image (Ubuntu 24.04 has 3.12).
- Thunderbird uses `mise.toml`/`.java-version` (JDK 21). Build with `abb-base:jdk21`.
- NewPipe now has KMP (`shared/`, `desktopApp/`, `iosApp/`); if `./gradlew tasks` tries to
  configure iOS targets and fails, pass `-Pkotlin.native.ignoreDisabledTargets=true` or drop
  the repo.
- Keep an eye on disk: `docker system df` after each image build; `abb images prune` arrives in
  Phase 1.
