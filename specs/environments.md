# Spec: Environments (Windows-native; no containers)

Everything runs **natively on the host OS** through the platform layer (`specs/platform-layer.md`).
Windows 11 is the first supported host; macOS is the planned second. Nothing in the harness or in
`s2a` depends on Linux, WSL or Docker. What a container used to provide — a pinned toolchain, a
warm dependency cache, a throw-away workspace, a network boundary, resource limits, and
*no state shared between trials* — is provided by the pieces below. Each states the check that
proves it.

## 1. Layout (`ABB_HOME`, default `%USERPROFILE%\abb`; keep it short, e.g. `C:\abb`)

`ABB_HOME` must be on a **local NTFS or ReFS (Dev Drive) volume** that no sync client watches. On
the reference laptop `G:` is Google Drive for desktop (a FAT32 virtual drive that uploads
everything): no ACLs, 4 GB file limit, cloud sync of every cache — never use it. `abb tools
install` refuses an `ABB_HOME` on a file system without ACLs (FAT32/exFAT).

`abb sandbox setup` first **resets inheritance at the root** (`icacls C:\abb /inheritance:r
/grant:r "<harness user>:(OI)(CI)F" "SYSTEM:(OI)(CI)F" "Administrators:(OI)(CI)F"`, and the same
for `%USERPROFILE%\abb-src`) — otherwise a data-drive root gives *Authenticated Users* Modify and
the sandbox user could write anywhere not explicitly denied. Then it applies the grants below
(`RX` = read and execute; plain `R` has no execute bit and could not even start `python.exe`).

```
ABB_HOME/                        # root: harness user F; sandbox user: LIST + traverse on this folder only (D-036), nothing inherited
  tools/                         # installed ONCE by the harness user with `abb tools install`; sandbox user: RX
    jdk17/  jdk21/               # Eclipse Temurin JDK zips, pinned by release name + sha256
    android-sdk/                 # cmdline-tools (commandlinetools-win-15859902_latest.zip) + sdkmanager packages
    python/                      # uv-managed CPython (abb tools install sets UV_PYTHON_INSTALL_DIR for its own uv calls)
    uvtools/  bin/               # UV_TOOL_DIR / UV_TOOL_BIN_DIR: `specify.exe`, `s2a.exe` (installed by the harness user)
    claude/<version>/claude.exe  # copy of the pinned native install (the launcher calls it by absolute path)
    abb_launch.py                # the launcher (stdlib + ctypes only)
  caches/                        # sandbox user: LIST + traverse on this folder only (D-036)
    repos/<repo>.git             # bare mirror of the upstream repo                       [sandbox user: DENIED]
    gradle-ro/<repo>/            # read-only dependency cache (GRADLE_RO_DEP_CACHE), lock files stripped [RX]
    robolectric/<repo>/          # flat dir of android-all-instrumented jars (robolectric.dependency.dir) [RX]
    gradle-pristine/<repo>/      # harness-only GRADLE_USER_HOME for validation and grading [sandbox user: DENIED]
  sandbox/
    claude-config.template/      # settings.json template; copied per trial               [sandbox user: RX]
  work/                          # sandbox user: LIST + traverse on this folder and on every ancestor of a trial dir (D-036)
  work/<run_id>/<arm>/<task>/t<k>/   # the trial dir itself: sandbox user RX (so it cannot create siblings)
    work/                        # the repo snapshot                                      [sandbox user: MODIFY]
    home/                        # per-trial user.home / USERPROFILE / TEMP / APPDATA     [sandbox user: MODIFY]
    gradle-home/                 # per-trial GRADLE_USER_HOME seeded with wrapper dists (+ transforms, optional) [MODIFY]
    claude-config/               # per-trial CLAUDE_CONFIG_DIR (settings.json deny-write)  [MODIFY]
    agent-out/                   # launcher writes stdout/stderr/transcript here           [MODIFY]
    transcript/ prompts/ artifacts/   # copied/written by the harness user after the run  [DENIED]
  results/<run_id>/...           # ABB_RESULTS_DIR                                        [sandbox user: DENIED]
  env.lock.json                  # fingerprints (below)                                   [sandbox user: DENIED]
```

The repository clone (code, `benchmark/tasks/` with the hidden tests) lives in
`%USERPROFILE%\abb-src` and is **denied** to the sandbox user.

**Nothing writable is shared between trials.** Every writable location the agent sees is inside
its own trial directory and is created fresh; every shared location is read-only. Three things
would silently break that on Windows and are handled explicitly:

- **Java ignores `USERPROFILE`**: `user.home` comes from the shell's known-folder API
  (JDK-4787931), so Gradle, AGP, Kotlin and Robolectric would use `C:\Users\abb-agent`. The
  agent env therefore sets `JAVA_TOOL_OPTIONS=-Duser.home=<trial>\home -Dfile.encoding=UTF-8`
  (reaches every JVM, including test workers) and `ANDROID_USER_HOME=<trial>\home\.android`;
  `gradle_user_home_props` sets `kotlin.compiler.execution.strategy=in-process` so no shared
  Kotlin daemon exists at all.
- **The sandbox user's real profile**: the launcher is started with `dwLogonFlags=0` (no profile
  loaded; `HKCU` maps to the read-only `HKU\.DEFAULT`), and `abb sandbox setup` denies writes to
  `C:\Users\abb-agent` (`icacls … /deny abb-agent:(OI)(CI)(W,WA,WD,AD,DC)`) so no `.android`,
  `.m2`, PowerShell profile or `Command Processor\AutoRun` can persist between trials. Phase 1
  measures that `claude.exe`, git, pwsh and `gradlew.bat` work without a loaded profile.
- **Trials of the same sandbox user cannot be told apart by ACLs** (Phase 1 finding, D-037): a
  user that has MODIFY on its own trial has it on every other trial granted to the same user. So
  (a) when a trial ends, the harness **revokes** the sandbox user's grants on that trial directory
  (`Workspace.revoke()`, before the same user runs anything else) and then deletes it; every trial
  directory carries an inheritable `OWNER RIGHTS` (`S-1-3-4`) entry with no rights, so files the
  agent created give it no implicit owner access (`WRITE_DAC`) once revoked; (b) **concurrent
  trials run as different users**: one sandbox user per parallel slot (`abb-agent`, `abb-agent2`,
  …), created by `abb sandbox setup --slots N` (elevated, needed from Phase 8 on; until then every
  run is sequential).
- **Residual channel, stated in the README**: two concurrent trials run as the *same* user and
  could in principle talk over loopback or named pipes. Nothing on disk is shared; the channel
  is noted, not closed.

## 2. Toolchain (`abb tools install`, run by the harness user, once)

| Component | Source | Pin |
|---|---|---|
| JDK 17 / 21 | Adoptium API: first install resolves `assets/latest/<major>/hotspot?os=windows&architecture=x64&image_type=jdk&vendor=eclipse` and records `release_name` + sha256 in `config/toolchain.lock.yaml`; every later install fetches **that release** (`assets/release_name/eclipse/<release_name>?os=windows&architecture=x64&image_type=jdk`) and verifies the locked sha256 | lock file |
| Android command-line tools | `https://dl.google.com/android/repository/commandlinetools-win-15859902_latest.zip`, sha256 `90ae805d20434428bffcb699c290860f19bb5f66a67e6b330067e3de801fb04a` (2026-10-16; re-verify) | `config/toolchain.yaml` |
| SDK packages | `sdkmanager.bat` with the pinned package list; licences accepted by feeding `y` lines on stdin from Python; installed list recorded | `config/toolchain.yaml` + lock |
| Python for tools + launcher | `uv python install 3.12` with `UV_PYTHON_INSTALL_DIR=ABB_HOME\tools\python` set **in `abb tools install`'s own process environment only** (not as a user variable, so the owner's other uv projects are untouched) | lock |
| PowerShell 7 (the agent's PowerShell tool) | `PowerShell-<v>-win-x64.zip` from the GitHub release, sha256 = the release asset digest, unpacked to `ABB_HOME\tools\pwsh`, first on the agent PATH; the owner's `pwsh` may be a per-user Store/MSIX package the sandbox user cannot run (D-031) | `config/toolchain.yaml: powershell` + lock |
| `specify`, `s2a` | `uv tool install` with `UV_TOOL_DIR=ABB_HOME\tools\uvtools`, `UV_TOOL_BIN_DIR=ABB_HOME\tools\bin` (same per-process env); `specify` at `speckit.ref` (a provisional latest tag in Phase 0, re-pinned in Phase 5); `s2a` from `%USERPROFILE%\abb-src\s2a` at `s2a_git_sha` (`abb sandbox install-s2a` re-runs it); the harness calls both by absolute path — adding `tools\bin` to the owner's PATH is optional convenience | `config/toolchain.yaml`, `env.lock.json: s2a_git_sha` |
| Claude Code | pinned native install for the harness user, **≥ 2.1.280** (Opus 5.5 floor, D-026); the versioned binary is copied to `ABB_HOME\tools\claude\<version>\claude.exe`, the only path the launcher ever runs | `config/toolchain.yaml: claude_code.version` |
| Git for Windows | on the host (2.44); provides Git Bash for Claude Code's Bash tool | `git --version` recorded |

Nothing is ever installed *as* the sandbox user (its egress is blocked): it only **reads and
executes** `tools/`. Git settings that matter on Windows, applied with `git config --global` for
the harness user and written into every per-trial `home/.gitconfig`: `core.autocrlf=false`,
**`core.eol=lf`** (an upstream `.gitattributes` with `text=auto` would otherwise still produce
CRLF), `core.longpaths=true`, `core.filemode=false`. `abb repos check` compares a sample of
workspace files byte-for-byte with the mirror blobs. The long-path policy (`LongPathsEnabled`) is
enabled by `abb sandbox setup` (admin).

## 3. Per-repo warm cache (`abb env warm <repo>`) — replaces "the image"

Run by the harness user: clone a bare mirror into `caches/repos/<repo>.git`; scratch checkout at
`cache_commit`; with a scratch `GRADLE_USER_HOME` **and** `JAVA_TOOL_OPTIONS=-Duser.home=<scratch>\home`
(so Robolectric's downloads land in `<scratch>\home\.m2`, not the owner's profile), run every
`build.warm_commands` entry (`gradlew.bat`, `--no-daemon`, `org.gradle.caching=false`), once at
`cache_commit` and once at every task base commit and the `setup_commit`. The warm fails if the
wrapper version in `gradle/wrapper/gradle-wrapper.properties` differs between those commits (the
read-only cache must be seeded by the Gradle version that consumes it). Then:

- `caches/gradle-ro/<repo>/modules-2` ← scratch GUH `caches\modules-2` with every `*.lock` and
  `gc.properties` removed (required by Gradle for a read-only dependency cache);
- `caches/robolectric/<repo>/` ← every `org\robolectric\android-all-instrumented\**\*.jar` from
  `<scratch>\home\.m2\repository` (flat);
- `caches/gradle-pristine/<repo>/` ← the whole scratch GUH, plus the same `init.d\abb.gradle` as
  trials get (below), minus `daemon\`; harness only;
- `env.lock.json` ← the **environment fingerprint**: `sha256(jdk release names, sdk package
  list, cache_commit, sorted warm commits, gradle wrapper version, gradle_user_home_props,
  claude_code_version, platform id, modules-2 content hash, robolectric jar dir hash)`.

Tasks record the fingerprint they were validated against; `abb run` refuses a different one
unless `--allow-env-drift` (recorded in the manifest).

**Per-trial Gradle home.** `snapshot()` creates `gradle-home/` with `gradle.properties` rendered
from `toolchain.gradle_user_home_props`, a harness-written `init.d/abb.gradle` that sets, for every
`Test` task, `systemProperty("robolectric.offline", "true")` and
`systemProperty("robolectric.dependency.dir", "<caches/robolectric/<repo>>")`, and a copy of
`wrapper\dists\<dist>\<hash>\` from the pristine cache (the wrapper takes a lock there, so it
cannot be a read-only share; without it the first `gradlew.bat` would try to download the
distribution and die on the firewall). `sandbox.yaml: seed_transforms` additionally copies
`caches\<version>\transforms` so AAR transforms are not redone per trial; Phase 1 measures the
cold-trial time with and without it and records the choice. The agent may edit anything in
`gradle-home/` — it affects only its own trial; grading never uses it.

## 4. Workspace (`Workspace` class, `abb/harness/workspace.py`)

Snapshot script (Python, platform-independent, run by the harness user): `git archive
<base_commit>` from the mirror → extract into `work/` → remove repo-shipped agent *automation*
(`.claude/settings*.json`, `.claude/hooks/`, `.mcp.json`; keep `CLAUDE.md`/`AGENTS.md`) →
`git init -q; git add -A; git commit -qm base; git tag base` with a fixed identity → create
`home/` (with `.gitconfig`), `gradle-home/` (seeded as above), `claude-config/` (from the
template; `settings.json` with a deny-write ACE), `agent-out/` → grant the sandbox user MODIFY on
exactly those directories and RX on the trial directory itself. Guarantees (checked by the
invariants test, run **as the sandbox user through the launcher** with real `open()`/create
attempts, never `Test-Path`): one commit, no remotes; mirror / results / code checkout / pristine
cache / a sibling trial directory's contents / `C:\Users\abb-agent` → access denied on read or create; `ABB_HOME`, `caches`, `work` and a trial's ancestor folders → names listable, create denied (D-036: Java's `Path.toRealPath()` walks every parent with `FindFirstFile`, so Gradle's compiler and zip file system fail without list rights on the ancestors); `gradle-ro`, `robolectric`, `tools` readable but not writable; no daemon dirs, no
build cache; `claude-config\settings.json` not writable; a hash of the `C:\Users\abb-agent` tree
before and after a smoke trial is identical; `reg add HKCU\Software\abb /f` fails.

Clean-up: `gradlew.bat --stop` with the trial's `GRADLE_USER_HOME`, then delete the trial
directory (file locks are the usual Windows failure; the platform layer retries with a short
backoff and reports leftovers).

## 5. Sandbox (`abb sandbox setup|check|install-s2a`) — replaces the container boundary

`config/sandbox.yaml` has two modes:

| Mode | Who runs the agent | Network | Filesystem | Use |
|---|---|---|---|---|
| `user` (**required for any run that includes `split: test` tasks**) | the local Windows user `abb-agent`, created once by `abb sandbox setup` (elevated; it runs the account part with `net user abb-agent <pw> /add /expires:never /passwordchg:no` — the `LocalAccounts` cmdlets are Windows-PowerShell-only — and stores the random password in Credential Manager via `keyring`; interactive logon is granted to all users on a workstation, and `CreateProcessWithLogonW` always performs an interactive logon, so no extra logon right is needed) | Windows Defender Firewall outbound **block** rule **applied to that principal**: `New-NetFirewallRule -DisplayName abb-agent-block-out -Direction Outbound -Action Block -Profile Any -LocalUser "O:LSD:(A;;CC;;;<SID>)"` (an `A` ACE lists the principals the rule applies to). Loopback is exempt, so the only way out is the harness proxy on `127.0.0.1:8888`. DNS is **not** blocked by a per-user rule (Windows resolves through the `Dnscache` service), which is why the proxy resolves hosts itself and the check does not assert "DNS fails". `abb sandbox check` proves both halves: as `abb-agent`, `curl.exe https://github.com` fails; as the harness user, it still succeeds | NTFS ACLs per §1 | benchmark runs |
| `none` (dev only) | the harness user | proxy env + tool deny list + Gradle offline; nothing enforced | nothing enforced | quick iteration; refused for `split: test`; recorded in the manifest |

**Egress proxy** (`abb/harness/proxy.py`, ~150 lines of asyncio, no dependency): an HTTP CONNECT
proxy on `127.0.0.1:8888` that allows `api.anthropic.com:443` only, resolves DNS itself
(`CLAUDE_CODE_PROXY_RESOLVES_HOSTS=1` in the agent env), logs every CONNECT (allowed/denied) to
`results/<run_id>/proxy.log`, and is started by `abb run` and `abb env verify`. Agent env:
`HTTPS_PROXY=HTTP_PROXY=http://127.0.0.1:8888`, `NO_PROXY=127.0.0.1,localhost`.

**Process launch as the sandbox user** (`specs/platform-layer.md`): the harness never passes the
agent command line through `CreateProcessWithLogonW` (its `lpCommandLine` is capped at 1024
characters and it opens a new console by default). It starts the tiny **launcher**
(`ABB_HOME\tools\python\…\python.exe ABB_HOME\tools\abb_launch.py <trial>\launch.json`) as
`abb-agent` with `dwLogonFlags=0`, `CREATE_SUSPENDED | CREATE_NEW_CONSOLE |
CREATE_UNICODE_ENVIRONMENT`, a hidden window (`STARTF_USESHOWWINDOW`/`SW_HIDE`; Phase 0 checks
that Windows Terminal does not flash a window and falls back to `CREATE_NO_WINDOW`), assigns it
to a **Job Object** (`JOB_OBJECT_LIMIT_JOB_MEMORY` = `sandbox.yaml: memory_mb`, `KILL_ON_JOB_CLOSE`,
breakaway disabled), then resumes it. The launcher reads `launch.json` (argv, cwd, output paths,
the prompt, the STOP path, the interrupt — **no environment**: the block is the launcher's own
process environment, handed unchanged to the child, so the token never touches disk, D-030),
starts `claude.exe` with a normal `CreateProcess` (32 K argv limit), feeds the prompt on stdin
(≥ 2.1.211), redirects stdout/stderr to `agent-out/`, and polls for `<trial>\STOP`. On `STOP` it
sends `sandbox.yaml: process.interrupt` — **`ctrl_c`** since Phase 0 (D-032):
`GenerateConsoleCtrlEvent(CTRL_C_EVENT, 0)` to its own private hidden console, with the child
created Ctrl+C-enabled and the launcher ignoring it; claude.exe then writes a `result` line
(`error_during_execution`, cost + usage) and exits (Ctrl+Break, the alternative, ends it without a
`result` line). **The same mechanism is used by s2a's own driver for its child**, so every arm's
timed-out calls are stopped identically. After `grace_s` the harness terminates the job. The
driver marks a stop it initiated as `timeout` regardless; if no result line follows, cost is
`null` + imputed — identically for every arm. A job-memory hit kills a JVM
inside the trial, not the job: the driver classifies that as `agent_error` (or `timeout` if the
deadline also passed), never `harness_error`. Manual diagnostic for window-station or logon
failures: `runas /user:abb-agent cmd`. Fallback launcher start if `CreateProcessWithLogonW`
misbehaves: `pwsh Start-Process -Credential … -WindowStyle Hidden` (same short command line).

**Per-trial environment block** (built from scratch; the harness environment is never
inherited): `sandbox.yaml: process.env` with the per-trial paths filled in (`USERPROFILE`,
`HOME`, `TEMP`, `TMP`, `APPDATA`, `LOCALAPPDATA` → `<trial>\home`; `JAVA_TOOL_OPTIONS`;
`ANDROID_USER_HOME`; `GRADLE_USER_HOME`; `GRADLE_RO_DEP_CACHE`; `CLAUDE_CONFIG_DIR`) +
`CLAUDE_CODE_OAUTH_TOKEN` (the subscription token, mapped from the harness user's
`ABB_OAUTH_TOKEN`; never an API key — `specs/auth-and-usage.md`) +
`JAVA_HOME=tools\jdk<N>` + `ANDROID_HOME` + `PATH` (toolchain, Git, `tools\bin` only). Two parallel trials therefore share nothing writable even though both run as
`abb-agent`.

**Verification** (`abb env verify <repo> --sandbox user` and `abb sandbox check`, run as the
sandbox user through the launcher with real file reads and real network attempts): denied paths
raise access-denied on read and on create; `git -C <mirror> log` fails; `curl.exe
https://github.com` fails (and succeeds for the harness user); `curl.exe -x
http://127.0.0.1:8888 https://api.anthropic.com/v1/models` returns an HTTP status (401 is
fine — no key, it proves the proxy forwards); the Claude
smoke test through the launcher succeeds; the repo's unit tests run offline from a fresh
workspace **with a freshly seeded `gradle-home`** in < 10 min (no `Could not resolve`, no
`android-all` download, no wrapper download).

## 6. Resource limits and parallelism

Job-wide memory limit per trial (`memory_mb`, **10 GB** — Phase 0 measured 6.5 GB for
Wikipedia's `:app` recompile + tests with two test workers, plus ~0.4 GB for `claude.exe`, so the
planned 8 GB left too little headroom, D-034; raise it if a JVM dies), Gradle `org.gradle.jvmargs=-Xmx3g`, Kotlin in-process; `--no-daemon` everywhere the
harness runs Gradle. 32 GB laptop → 2 trials in parallel (`abb run --parallel 2`). The final run
can stay on the laptop (~504 trials × ~15 min ÷ 2 ≈ 60 h of compute — but under a
subscription the real bound is usage windows, so it is spread over days or weeks of batches,
`specs/auth-and-usage.md` §3) or move to a **Windows** VM set up by `scripts/vm-setup.ps1`
(same `abb tools install`, same fingerprints; it uses the same token, one account).

## 7. Windows-specific pitfalls the harness handles

| Pitfall | Handling |
|---|---|
| CRLF conversion breaks `git apply` | `core.autocrlf=false` + `core.eol=lf` in every git config the harness controls; patches stored and applied as bytes; `abb repos check` byte-compares workspace files with mirror blobs |
| MAX_PATH (260) in deep Android trees | `LongPathsEnabled=1` (admin), `core.longpaths=true`, short `ABB_HOME`, `abb repos check` rejects paths > 200 chars |
| Defender real-time scanning slows Gradle 2–5× | recommend an exclusion for `ABB_HOME` (user decision, `docs/DAY-0.md`) |
| Gradle daemons hold file locks → delete fails | `--no-daemon` for everything the harness runs; `gradlew.bat --stop` on the trial GUH before delete; retry with backoff |
| Java `user.home` ≠ `USERPROFILE` | `JAVA_TOOL_OPTIONS=-Duser.home=<trial>\home` on every JVM; `ANDROID_USER_HOME` |
| Persistent profile of the sandbox user | launcher started without a profile (`dwLogonFlags=0`); profile directory deny-write; before/after hash in the invariants test |
| Fresh Gradle home has no wrapper distribution | `wrapper\dists` seeded from the pristine cache per trial; optional `transforms` seeding |
| Claude Desktop's `Claude.exe` shadows `claude.exe` on PATH | the launcher runs `ABB_HOME\tools\claude\<version>\claude.exe` by absolute path |
| `--disallowedTools Bash` also disables the PowerShell tool | never deny Bash; set `CLAUDE_CODE_USE_POWERSHELL_TOOL=1` explicitly so the shell set is identical for every arm |
| Case-insensitive file system | `abb repos check` fails a repo whose tree has two paths differing only by case |
| Gradle wrapper form | `./gradlew` inside Git Bash (the agent's Bash tool), `gradlew.bat` for the harness; `platform.gradlew()` returns the right form |
| `Test-Path` returns False on access-denied | verification opens files for read/create and expects `PermissionError` |
| `icacls R` has no execute bit | `RX` on everything the sandbox user must run (`tools`, caches) |

## 8. What this does not give you (stated in the README)

A kernel-level boundary. The sandbox user is a normal low-privilege Windows user: it cannot read
denied paths, cannot write anything shared, and cannot reach the network, but it shares the
kernel and the host, and two of its concurrent trials could talk over loopback or named pipes.
That is the same honesty note the container design needed for Bash access; it is not weaker for
the questions this benchmark asks (fix lookup, cross-trial leakage, network egress). An optional
container backend can be added later for Linux hosts without changing any contract above.
