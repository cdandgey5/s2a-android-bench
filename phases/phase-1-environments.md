# Phase 1 — Per-repo environments and the sandbox (Windows-native)

**Goal.** For each chosen repo, a warm per-repo cache that runs unit tests **offline**, the
history-free workspace abstraction, and the sandbox (agent user + firewall + egress proxy) that
every agent run uses. No containers: see `specs/environments.md` and `specs/platform-layer.md`.

**Prerequisites.** Phase 0 gate. `repos/<repo>.yaml` filled for repo #1 and #2; seed task
`antennapod-0000`. One elevated PowerShell session from the human for step 6.

**Effort.** ~1 week part-time (warming is slow; iterate on one repo first).

## Deliverables

```
benchmark/abb/harness/env.py          # `abb env warm|verify|prune|fingerprint`: bare mirror, warm caches, env.lock.json
benchmark/abb/harness/workspace.py    # Workspace: snapshot, exec via platform.run, put/get, diff, cleanup
benchmark/abb/harness/gradle.py       # compose + run Gradle (gradlew.bat) with timeout and log capture
benchmark/abb/harness/junit.py        # JUnit XML -> {test_id: status}
benchmark/abb/harness/proxy.py        # asyncio CONNECT proxy, allow-list, DNS resolution, logging
benchmark/abb/harness/sandbox.py      # `abb sandbox setup|check|install-s2a`: user, firewall, ACLs, per-user Claude Code + toolchain
benchmark/abb/harness/platform/windows.py   # + launch as the sandbox user (CreateProcessWithLogonW), ACL helpers
benchmark/scripts/sandbox-setup.ps1   # the elevated part, invoked by `abb sandbox setup` via `Start-Process pwsh -Verb RunAs`
benchmark/env.lock.json               # repo -> fingerprint, cache_commit, warm commits, build date
benchmark/tests/test_junit.py         # fixtures: passed/failed/error/skipped/parameterized XML
benchmark/tests/test_proxy.py         # allow/deny CONNECT, DNS, logging
benchmark/tests/test_workspace.py     # integration (ABB_INTEGRATION=1): snapshot invariants AS THE AGENT USER
CLI: abb env warm <repo> [--warm-commits ...]   abb env verify <repo> [--sandbox user|none]   abb env prune   abb ws open <repo> [--commit] [--as-agent]
     abb sandbox setup [--refresh]   abb sandbox check   abb sandbox install-s2a
```

## Steps

1. **Mirror + warm** (`env.py`, harness user): `git clone --mirror <url> ABB_HOME\caches\repos\<repo>.git`;
   scratch checkout at `cache_commit` under `ABB_HOME\work\warm\<repo>` with a scratch
   `GRADLE_USER_HOME` and `JAVA_TOOL_OPTIONS=-Duser.home=<scratch>\home`; write `gradle.properties` from `toolchain.gradle_user_home_props`
   (`org.gradle.caching=false`); run each `warm_commands` entry through `platform.run`
   (`gradlew.bat`, `--no-daemon`; `cmd || true` semantics for `allow_failure: true`, otherwise a
   non-zero exit fails the warm); repeat at every `--warm-commits` commit; `gradlew.bat --stop`.
   Then split the result per `specs/environments.md` §3: `caches\modules-2` → `caches\gradle-ro\<repo>`
   (read-only dependency cache; `*.lock` and `gc.properties` stripped), Robolectric jars from
   `<scratch>\home\.m2\repository\org\robolectric\android-all-instrumented` → `caches\robolectric\<repo>\`
   (flat), the whole scratch GUH plus the trial `init.d\abb.gradle` → `caches\gradle-pristine\<repo>`
   (harness only); fail if the wrapper version differs between the warmed commits; delete the scratch checkout and
   every `daemon\` dir; write the fingerprint to `env.lock.json`. Expect 10–30 min.
2. **Workspace class** (`workspace.py`):
   ```python
   class Workspace:
       def __init__(self, repo: RepoConfig, trial_dir: Path, sandbox: Literal["user","none"]): ...
       def snapshot(self, base_commit: str) -> str     # archive from the mirror -> strip automation -> git init + commit + tag base; ACL grant; returns HEAD
       def exec(self, argv, *, cwd=None, timeout_s, env, stdout_path, as_agent=False) -> ProcResult   # platform.run with the full env block
       def put(self, src: Path, dst_rel: str); def get(self, src_rel: str, dst: Path)
       def apply_patch(self, patch: Path, *, check_only=False) -> bool
       def diff(self, exclude: list[str]) -> str     # git add -A -N && git diff --binary base -- . ':(exclude)...'
       def changed_paths(self) -> list[str]
       def cleanup(self) -> list[Path]               # gradlew --stop, robust delete, returns leftovers
   ```
   The agent's environment block is built from scratch (`config/sandbox.yaml: process.env` with
   the per-trial `home/`, `gradle-home/`, `claude-config/` paths filled in, `GRADLE_RO_DEP_CACHE`,
   `CLAUDE_CODE_OAUTH_TOKEN` (mapped from `ABB_OAUTH_TOKEN`; never an API key), `JAVA_HOME`, `ANDROID_HOME`, `PATH` with the toolchain, Git and `tools\bin`
   only); the harness environment is never inherited. `snapshot()` also creates the per-trial
   dirs, renders `gradle-home\gradle.properties` + `init.d\abb.gradle` (Robolectric offline
   properties), seeds `gradle-home\wrapper\dists` (and `caches\<ver>\transforms` when
   `seed_transforms`) from the pristine cache, writes `home\.gitconfig`, copies the Claude config
   template and sets the ACLs; the env block carries `JAVA_TOOL_OPTIONS=-Duser.home=<trial>\home`
   and `ANDROID_USER_HOME`.
3. **Gradle runner** (`gradle.py`): `test_command(repo, module, tests)` per `specs/task-format.md`
   using `platform.gradlew()`; validation and grading run with `GRADLE_USER_HOME=caches\gradle-pristine\<repo>`
   and add `--no-build-cache`, `--no-daemon`, `<module>:cleanTest`; `run_tests(...)` with the Job
   Object timeout; `collect_junit(...)`.
4. **Offline verification** `abb env verify <repo>`: fresh workspace at `cache_commit`, run
   `tests.verify_modules` unit tests with the proxy **stopped** and the sandbox user (so the
   firewall proves offline), parse JUnit, print counts and wall time; fail on `Could not resolve`
   / `No cached version` / `android-all` download attempts. Then the seed task's hidden test at
   base (must fail) and with `gold.patch` (must pass).
5. **Proxy** (`proxy.py`): asyncio server on `127.0.0.1:8888`; `CONNECT host:443` allowed only for
   hosts in `allow_hosts`; plain `GET` denied; resolves DNS itself; logs allowed/denied with
   timestamps; `abb run` and `abb env verify` start/stop it. Unit tests with a local TLS echo.
6. **Sandbox** (`sandbox.py`, `scripts/sandbox-setup.ps1`). `abb sandbox setup` elevates once
   (`Start-Process pwsh -Verb RunAs`) and: creates local user `abb-agent` (random password →
   Credential Manager via `keyring`; password never expires; member of `Users` only, created with `net user … /add /expires:never /passwordchg:no`; no extra
   logon rights are needed), resets inheritance at `ABB_HOME` and `abb-src`, denies writes to
   `C:\Users\abb-agent`, adds the outbound firewall block rule
   **applied to that principal** (`-LocalUser "O:LSD:(A;;CC;;;<SID>)"`), enables `LongPathsEnabled`,
   sets the static ACLs per `sandbox.yaml` (denies on mirrors, pristine caches, results, the code
   checkout; read on `tools`, `gradle-ro`, `robolectric`, the config template). **Nothing is
   installed as that user** — it has no network; it only reads `ABB_HOME\tools`. Then (non-elevated)
   implement the launch path per `specs/platform-layer.md`: `CreateProcessWithLogonW` via `ctypes`
   starts **only the launcher** (`tools\python … abb_launch.py <trial>\launch.json`, suspended,
   hidden), the harness assigns the Job Object and resumes; the launcher (started without a profile, `dwLogonFlags=0`) starts `claude.exe` in its own process
   group with the prompt on stdin, redirects to `agent-out\`, and sends Ctrl+Break to that group on
   `STOP` (or Ctrl+C if Phase 0 decided so). Fallback: `pwsh
   Start-Process -Credential … -WindowStyle Hidden` for the launcher. `abb sandbox check` runs
   checks **as the sandbox user through the launcher**: real `open()` attempts on every denied path
   (mirror, pristine cache, results, repo clone — expect `PermissionError`), read-only on
   `gradle-ro`, `curl.exe https://github.com` (must fail) while the same command succeeds as the
   harness user, `curl.exe -x http://127.0.0.1:8888 https://api.anthropic.com/v1/models` (any HTTP
   status — a 401 is fine, there is no key; it proves the proxy forwards), and the Claude smoke test through the proxy **as the sandbox user** (must succeed, no retries —
   this is also the proof that the subscription token is honoured under `abb-agent` with no
   profile; record it in `reference/verified.md`); it also confirms that
   `claude.exe`, `git`, `pwsh` and `gradlew.bat` work without a loaded profile.
   `abb sandbox install-s2a` (Phase 6) runs `uv tool install` of `s2a` as the harness user into
   `tools\bin`; `--refresh` re-applies ACLs and re-copies `claude.exe` after a version change.
7. **Workspace invariants test** (`test_workspace.py`, integration, run as the sandbox user through
   the launcher): `git log --all --oneline | Measure-Object` = 1; `git remote -v` empty; real reads of
   `caches\repos`, `caches\gradle-pristine`, `results`, the repo clone, another trial's directory →
   `PermissionError`; writes into `caches\gradle-ro` → `PermissionError`; no `daemon\` dirs; no
   `build-cache-1`; `.claude\settings.json`, `.claude\hooks`, `.mcp.json` absent in the workspace
   while `CLAUDE.md` (if shipped) is present; `claude-config\settings.json` not writable; creating a file under `ABB_HOME`, `work\` or a sibling
   trial dir → `PermissionError`; `reg add HKCU\Software\abb /f` fails; the `C:\Users\abb-agent` tree
   hash is identical before and after a smoke trial; a scan of
   `caches\gradle-ro\<repo>` and `caches\robolectric\<repo>` for class names added by any task's
   `gold.patch` (`abb tasks lint --setup-leak --caches`, seeded with `antennapod-0000`) finds nothing;
   a sample of workspace files is byte-identical to the mirror blobs (no CRLF conversion).
8. **Debug helper** `abb ws open <repo> [--commit] [--as-agent]`: creates a workspace and opens a
   PowerShell there (as the agent user with `--as-agent`, via the same launch path).
9. **Prune** `abb env prune`: deletes workspaces of finished runs (`cleanup()` on each), old warm
   scratch dirs, and reports `caches\` sizes; never touches a running trial.
10. Repeat 1 and 4 for repo #2.
10b. **Throughput probe (D-027).**
   Why: the account is on Claude Pro (`subscriptionType: pro`, the smallest usage windows), the
   building chats share those windows, and Phase 4 is the first place the plan would otherwise
   learn whether the matrix fits — about five weeks in. Here the sandbox exists, so one realistic
   agent session can run safely. Steps: (a) the owner notes the usage meter (claude.ai →
   Settings → Usage: current session % and weekly %) and does not chat during the probe; (b)
   `abb ws smoke --sandbox user --repo antennapod --prompt-file tasks/antennapod-0000/problem.md
   --max-turns 200 --deadline 2700 --model claude-sonnet-5-5` in a fresh workspace (the plain
   arm's shape: one call, the whole budget; this step adds those five options to Phase 0's
   `abb ws smoke`); (c) the owner reads the meter again; (d) record in
   `docs/RUNS.md` and `reference/verified.md`: tokens (in/out/cache), est. USD, turns, wall time,
   session % and weekly % used, model, plan. Optionally repeat once on `claude-opus-5-5` (its
   own limit). Then compute and record `trials_per_window ≈ 100 / session_%` and
   `trials_per_week ≈ 100 / weekly_%`, and the weeks the plan needs:
   `weeks ≈ trials / min(trials_per_window × windows you can run per week, trials_per_week)` for
   the dev runs (~430), the final matrix (504, ×2–5 tokens for the multi-stage arms) and the MVP
   cut. The seed task is trivial, so the result is a **lower bound** on usage per trial. The
   owner then makes the START-HERE §5 decision (stay on Pro, move to Max, or take the MVP cut
   now) before Phase 2. This does not replace Phase 4's trials-per-window measurement.
11. Commit `phase 1: environments + sandbox`.

## Acceptance gate

```powershell
uv run abb env verify antennapod --sandbox user    # fresh gradle-home each time; tests run/passed, wall time < 10 min (reported with and without seed_transforms), "offline: OK", seed task fail->pass
uv run abb env verify wikipedia --sandbox user     # same (seed task step skipped)
uv run abb sandbox check                           # denied paths denied, github.com unreachable, API reachable through the proxy, smoke test OK
$env:ABB_INTEGRATION=1; uv run pytest -q tests\test_workspace.py tests\test_junit.py tests\test_proxy.py tests\platform
Get-Content benchmark\env.lock.json
Get-Content docs\RUNS.md                           # throughput probe row (step 10b): tokens, session %, weekly %, weeks estimate
```

Passes when both repos' unit tests run offline from a history-free workspace as the agent user
in under 10 minutes, the invariants test is green, the sandbox check proves the boundary
(filesystem denies + firewall + allow-list proxy), and the throughput probe is recorded in
`docs/RUNS.md` and `reference/verified.md` with the owner's Pro / Max / MVP-cut decision
(START-HERE §5, D-027).

## Pitfalls

- Robolectric downloads `android-all-instrumented-<api>` jars at first test run into the Maven
  local repo. The warm step must *run* tests, serially, for every API level the repo's tests use
  (`@Config(sdk = …)`); grep the warm log for `android-all` downloads.
- `git archive` ignores files matched by `export-ignore`; check nothing needed for the build is
  excluded.
- File locks: a Gradle daemon or an open Explorer window keeps a workspace from being deleted;
  `cleanup()` stops daemons and retries, then reports leftovers rather than failing silently.
- The sandbox user has no interactive desktop; everything it runs is headless and without a
  loaded profile (`dwLogonFlags=0`). If `CreateProcessWithLogonW` fails with a logon or
  window-station error, reproduce it by hand with `runas /user:abb-agent cmd` (interactive logon
  is granted to all users on a workstation; a policy that removed it is the usual cause) and fall
  back to `pwsh Start-Process -Credential … -WindowStyle Hidden` for the launcher.
- Nothing writable is shared between trials: dependencies come from the read-only cache
  (`GRADLE_RO_DEP_CACHE`), everything Gradle writes goes to the per-trial `gradle-home`, and the
  per-trial `home/` absorbs `~`-relative state (`.gitconfig`, temp files). If Gradle refuses the
  read-only cache (version-specific layout), fall back to copying `modules-2` per trial on a Dev
  Drive (block clone makes it cheap) and say so in `reference/verified.md`.
