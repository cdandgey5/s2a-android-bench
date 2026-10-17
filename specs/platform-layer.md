# Spec: Platform layer (`abb/harness/platform/`, mirrored in `s2a/s2a/platform/`)

All OS-specific behaviour lives behind one small interface. Windows is implemented in v1; macOS
(and Linux) get `posix.py` later without touching the rest of the code. Both packages carry a
copy (they must not import each other); the shared contract is this file and a common test
suite in `tests/platform/`.

```python
class Platform(Protocol):
    id: str                                   # "windows" | "macos" | "linux"
    def gradlew(self, repo_dir: Path) -> list[str]     # ["gradlew.bat"] on Windows, ["./gradlew"] elsewhere
    def python(self) -> Path                           # the shared tools interpreter (ABB_HOME/tools/python/...)
    def claude_exe(self) -> Path                       # ABB_HOME/tools/claude/<version>/claude.exe (absolute)
    def run(self, spec: ProcSpec) -> Proc              # start (optionally as the sandbox user), limit, redirect
    def wait(self, proc: Proc, timeout_s: int) -> ProcResult
    def stop_gracefully(self, proc: Proc, grace_s: int = 30) -> None   # Ctrl+Break to the child's group (SIGINT elsewhere), then kill the job/tree
    def grant(self, path: Path, principal: str, rights: Literal["rx","modify","deny"], *, inherit=True) -> None
    def deny_write(self, path: Path, principal: str) -> None          # file/dir-level deny-write ACE (settings.json, C:\Users\abb-agent)
    def reset_inheritance(self, root: Path, owners: list[str]) -> None  # icacls /inheritance:r + full control for the harness user/SYSTEM/Administrators
    def check_access(self, path: Path, *, as_user: str, op: Literal["read","create"]) -> Literal["ok","denied"]   # REAL attempt as that user
    def as_user_available(self) -> bool
    def env_fingerprint_parts(self) -> dict            # os release, arch
    def enable_long_paths(self) -> None                # admin; no-op elsewhere
    def rmtree_robust(self, path: Path) -> list[Path]  # returns leftovers it could not delete
```

```python
@dataclass
class ProcSpec:
    argv: list[str]                  # the real command (claude.exe …, gradlew.bat …, git …)
    cwd: Path
    env: dict[str, str]              # the FULL environment block (never inherit the harness env)
    stdin_text: str | None           # prompts go in on stdin (Claude Code >= 2.1.211)
    timeout_s: int
    memory_mb: int | None            # Job Object JOB memory limit (whole tree)
    as_user: str | None              # "abb-agent" or None
    out_dir: Path                    # stdout.txt / stderr.txt land here (agent-writable when as_user)
    hidden: bool = True

@dataclass
class ProcResult:
    exit_code: int | None            # None if killed by the harness
    stopped_by_harness: bool         # True when the deadline hit -> exit_reason "timeout" regardless of code
    duration_s: float
    peak_memory_mb: int | None       # from the Job Object
    job_memory_hit: bool             # a process inside the job hit the job limit (JVM OOM) -> agent_error, never harness_error
```

## Windows implementation (`windows.py` + `tools/abb_launch.py`)

| Concern | Mechanism |
|---|---|
| Launch as the sandbox user | `advapi32.CreateProcessWithLogonW` (the API behind `runas`; no special privilege) via `ctypes`, **`dwLogonFlags=0`** (no profile loaded — `HKCU` maps to the read-only `HKU\.DEFAULT`, nothing persists between trials), password from Credential Manager (`keyring`), **command line = the tiny launcher only** (`<tools python> <tools>\abb_launch.py <trial>\launch.json`, well under the API's 1024-char limit), `CREATE_SUSPENDED \| CREATE_NEW_CONSOLE \| CREATE_UNICODE_ENVIRONMENT`, `STARTF_USESHOWWINDOW` + `SW_HIDE` (Phase 0 confirms no Windows Terminal flash; fallback `CREATE_NO_WINDOW`). The harness then assigns the process to the Job Object and calls `ResumeThread`, so no child can escape the job. The launcher runs under the shared tools Python (stdlib + `ctypes` only), reads `launch.json`, starts the real command with `subprocess.Popen(creationflags=CREATE_NEW_PROCESS_GROUP)` (32 K argv limit), writes stdout/stderr to `out_dir`, and polls for `<trial>\STOP` |
| Launch as the harness user | the same launcher started with `subprocess.Popen(creationflags=CREATE_NEW_CONSOLE \| CREATE_SUSPENDED)` + job + resume (one code path for both) |
| Resource limits and tree kill | `win32job`: `CreateJobObject` → `SetInformationJobObject(ExtendedLimitInformation: JOB_OBJECT_LIMIT_JOB_MEMORY, KILL_ON_JOB_CLOSE, no breakaway)` → `AssignProcessToJobObject` before resume; `QueryInformationJobObject` for peak job memory; a job-limit hit kills the offending process only (reported as `job_memory_hit`) |
| Graceful stop | the harness writes `<trial>\STOP`; the launcher calls `GenerateConsoleCtrlEvent(CTRL_BREAK_EVENT, <child pid>)` — Ctrl+Break can be targeted at one process group, Ctrl+C cannot — so nothing else in the console is hit. **s2a's driver uses exactly the same call on its own child**, so every arm's timed-out calls are stopped the same way. After `grace_s` the harness `TerminateJobObject`s. Phase 0 measures whether a `result` line follows Ctrl+Break and, separately, Ctrl+C; if only Ctrl+C works, both drivers switch together (recorded in D-024 and the manifest) |
| ACLs | `icacls <path> /grant:r abb-agent:(OI)(CI)M` (modify) / `/grant:r abb-agent:(OI)(CI)RX` (read **and execute** — plain `R` cannot start an exe) / `/deny abb-agent:(OI)(CI)F` / `/inheritance:r`; file-level `/deny abb-agent:(W,WA,WD,DC)` for `settings.json`; `C:\Users\abb-agent` gets `/deny abb-agent:(OI)(CI)(W,WA,WD,AD,DC)`; root inheritance reset at `ABB_HOME` and `abb-src` before any grant; verification = `check_access`, a real `open()`/create performed through the launcher as the sandbox user (never `Test-Path`, which returns False on access-denied) |
| Firewall | `New-NetFirewallRule -DisplayName abb-agent-block-out -Direction Outbound -Action Block -Profile Any -LocalUser "O:LSD:(A;;CC;;;<SID>)"` (admin, once, in `sandbox-setup.ps1`; `A` = the principal the rule applies to); loopback is not filtered, so `127.0.0.1:8888` stays reachable; DNS is resolved by the `Dnscache` service and is not affected, hence `CLAUDE_CODE_PROXY_RESOLVES_HOSTS=1`; `abb sandbox check` proves `curl.exe https://github.com` fails as that user **and** still succeeds as the harness user |
| Account creation | `sandbox-setup.ps1` (elevated) uses `net user abb-agent <pw> /add /expires:never /passwordchg:no` (the `LocalAccounts` cmdlets are Windows-PowerShell-only); no extra logon right is needed (`CreateProcessWithLogonW` performs an interactive logon, granted to all users on a workstation) |
| Long paths | registry `HKLM\SYSTEM\CurrentControlSet\Control\FileSystem\LongPathsEnabled=1` (admin) + `core.longpaths=true` |
| Robust delete | stop the trial's Gradle daemons, then `rmtree` with retries (0.5 s × 10) and `FILE_ATTRIBUTE_READONLY` clearing; leftovers reported, never silently ignored |
| Shell for docs and scripts | PowerShell 7 (`pwsh`) for humans; the elevated account step shells out to `net`/`icacls`/`New-NetFirewallRule`; no `.sh` scripts anywhere; helper scripts are Python or `.ps1`; gate commands in the phase files are PowerShell |
| Paths | `pathlib` everywhere; never string-concatenate paths; no `/tmp`; temp dirs under the trial's `home/` |

## POSIX implementation (`posix.py`, later)

Same contract: `./gradlew`; the same launcher started with `subprocess` under `start_new_session=True`
(and `sudo -u <sandbox user>` where a sandbox user exists); `SIGINT` then `SIGKILL` to the
process group; `resource`/`ulimit` or cgroups for memory; `chmod`/ACLs; `pf` (macOS) or
`nftables` rules per user for egress. Nothing else in the harness changes.

## Rules

1. No code outside `platform/` may import `pywin32`, `ctypes` for Win32, `icacls`, `netsh`,
   `New-NetFirewallRule`, `/bin/sh`, `timeout(1)` or any other OS-specific tool.
2. Every subprocess the harness or `s2a` starts goes through `Platform.run` (so limits, stops
   and logging are uniform), including Gradle and git.
3. `platform.id` is part of the environment fingerprint and the manifest.
4. The driver maps outcomes itself: `stopped_by_harness → timeout`; exit 0 with a result line →
   per subtype; no result line → `agent_error`; `job_memory_hit` → `agent_error`; never by
   interpreting POSIX exit codes.
5. The common test suite (`tests/platform/`) runs on every supported OS: start/stop a sleeping
   process through the launcher, job memory limit trips (reported, not `harness_error`),
   deny/grant round trip with a real read and a real create attempt, tree kill, robust delete
   with a locked file, graceful stop delivers Ctrl+Break/SIGINT to a child that prints on it,
   before/after hash of the sandbox user's profile directory is identical.
