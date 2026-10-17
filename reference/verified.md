# Verified facts (live record)

The building agent fills this in during Phase 0 and updates it whenever a tool is upgraded.
Each entry: date, command run, exact output excerpt, verdict.

## Host (Windows-native)

| Item | Value | Date |
|---|---|---|
| PowerShell 7 version | not installed (only Windows PowerShell 5.1.26100.9711) | 2026-10-17 |
| `ABB_HOME` drive and free space | `ABB_HOME` unset. C: NTFS, 928.7 GiB, 90.2 GiB free. G: is Google Drive for desktop (`Win32_LogicalDisk`: FAT32, label "Google Drive", `GoogleDriveFS` running), mirrors C:'s size; unusable for `ABB_HOME` | 2026-10-17 |
| Git for Windows version; `core.autocrlf`/`core.eol` | 2.44.0.windows.1; `core.autocrlf=true` (system), `core.eol`/`core.longpaths`/`core.filemode` unset (global); `LongPathsEnabled=1` (HKLM) | 2026-10-17 |
| Defender exclusion / Dev Drive (yes/no) | exclusions not readable without admin; Dev Drive: no (C: is NTFS) | 2026-10-17 |

### Phase 0 step 1 — bootstrap check, run 2 (2026-10-17, Windows-native plan)

Verdict: **FAIL — Day 0 (Windows) not done.** Phase 0 stops here.

| Check | Command | Result | Verdict |
|---|---|---|---|
| PowerShell 7 | `Get-Command pwsh` | missing; this shell is 5.1.26100.9711 | **missing** |
| Git for Windows | `git --version` | 2.44.0.windows.1 | ok |
| `gh` + auth | `Get-Command gh` | not installed | **missing** |
| `uv` | `Get-Command uv` | not installed | **missing** |
| Claude Code | `& "$env:USERPROFILE\.local\bin\claude.exe" --version` | 2.1.197; plan needs ≥ 2.1.211; `toolchain.yaml` `claude_code.version: TODO_PIN` | **too old, not pinned** |
| `ABB_HOME` | process + user env | unset (`ABB_RESULTS_DIR` unset too) | **missing** |
| Disk for `ABB_HOME` | `Win32_LogicalDisk` | C: NTFS 90.2 GiB free ≥ 60 GB; G: is Google Drive (FAT32), not usable | ok on C: |
| `ABB_OAUTH_TOKEN` (subscription auth, D-025; no API key wanted) | user env | not checked yet — `claude setup-token` per `docs/DAY-0.md` §3 | **to do** |
| `ANTHROPIC_API_KEY` and global `CLAUDE_CODE_OAUTH_TOKEN` must be unset | process + user env | not checked (plan changed 2026-10-17) | **to do** |
| Pinned model accepted on the plan | `claude.exe --model claude-opus-5-5 -p ping` | not run (Phase 0 step 5) | **not checked** |
| Working clone `%USERPROFILE%\abb-src` | `Test-Path` | absent; the only repo is the OneDrive folder (commits `2f09972`, `3bd3122`) | **missing** |
| `git remote -v` | — | no remote | **missing** |
| D-001 training-cutoff date | `docs/DECISIONS.md` | still TODO | **missing** |
| `winget` | `Get-Command winget` | present (for the Day 0 installs) | ok |

### Phase 0 step 1 — bootstrap check, run 1 (2026-10-17, from the Windows host; WSL absent) — SUPERSEDED

This run was made against the earlier WSL/Docker version of the plan. The plan is now
Windows-native (D-024): WSL, Docker and `.wslconfig` are no longer required; disk needs are
~60 GB on the `ABB_HOME` drive. Re-run step 1 against `docs/DAY-0.md` (Windows).

Verdict then: **FAIL — Day 0 not done.**

| Check | Command | Result | Verdict |
|---|---|---|---|
| OS | `Win32_OperatingSystem` | Windows 11 Home, build 26200 | ok |
| Hardware | `Win32_ComputerSystem` | 31.7 GiB RAM, 32 logical CPUs (i9-13900HX) | ok for `.wslconfig` 24 GB / 8 CPU |
| Virtualization | `systeminfo` | "A hypervisor has been detected" (VBS/HVCI running), so VT-x is on | ok |
| WSL2 + Ubuntu | `wsl -l -v` | "The Windows Subsystem for Linux is not installed" | **missing** |
| `.wslconfig` | `Test-Path %USERPROFILE%\.wslconfig` | absent | **missing** |
| Docker Desktop | `Get-Command docker`; install dir | not installed | **missing** |
| Free disk (vhdx drive) | `Get-PSDrive C` | C: 84.7 GiB free (G: 80.5 GiB free); plan needs ≥ 120 GB | **short by ~35 GB** |
| `uv` | `Get-Command uv` | not found (and WSL absent) | **missing** |
| `gh` | `Get-Command gh` | not found (and WSL absent) | **missing** |
| `claude` | `claude --version` | 2.1.197 on the Windows host only; needed inside WSL | **missing in WSL** |
| `git` | `git --version` | 2.44.0.windows.1 on the Windows host | ok (host) |
| `ANTHROPIC_API_KEY` | `$env:` / user env | unset | **missing** |
| Pinned model ids (`/v1/models`) | — | not run: no API key | **not checked** |
| `git remote -v` | — | repo initialised in the OneDrive folder (commit `2f09972`), no remote | **missing** |
| `~/abb` WSL clone | — | does not exist (no WSL) | **missing** |

## Claude Code

| Item | Value | Date |
|---|---|---|
| `claude.exe --version` (pinned copy under `ABB_HOME\tools\claude`) | | |
| `abb auth check`: `claude.exe auth status` through the launcher with the mapped token and an empty `CLAUDE_CONFIG_DIR` → `authMethod` (expected `oauth_token`) | | |
| Token honoured as the sandbox user `abb-agent` (Phase 1 smoke test through `CreateProcessWithLogonW`) | | |
| `total_cost_usd` / `usage` present in `-p` results under subscription auth | | |
| `--model claude-opus-5-5` accepted on this plan (else Sonnet for everything, D-001) | | |
| Usage-limit output in `-p` (verbatim tail, error text, exit code) — Phase 4 canary | | |
| `-p` / `--output-format stream-json` / `--verbose` | | |
| `--max-turns` → `error_max_turns` | | |
| `--max-budget-usd` → `error_max_budget_usd` | | |
| `--resume` with `-p` | | |
| `--permission-mode bypassPermissions` (as the sandbox user through the launcher) | | |
| `--disallowedTools WebFetch,WebSearch` | | |
| `--model claude-sonnet-5-5` / `claude-opus-5-5` accepted | | |
| `--append-system-prompt` | | |
| Slash command expansion in `-p` (`/speckit-specify …`) | | |
| AskUserQuestion behaviour in `-p` (Phase 4 step 3) | | |
| Ctrl+C / Ctrl+Break in `-p` on Windows: `result` line written? exit code? (Phase 0 step 5) | | |
| Bash tool runs Git Bash (`echo $BASH_VERSION`) | | |
| Smoke test result JSON excerpt | | |

## Spec Kit

| Item | Value | Date |
|---|---|---|
| `specify --version` | | |
| `specify init --help` (flags used) | | |
| Files created by `specify init --integration claude` | | |
| Command names found in `.claude/` | | |
| `specify extension add bug` → command names | | |

## Android SDK

| Item | Value | Date |
|---|---|---|
| cmdline-tools zip + sha256 | | |
| `sdkmanager --list_installed` after a full build | | |

## Repositories (one block per repo; from the Phase 0 experiment)

### antennapod
| Item | Value |
|---|---|
| Commit built | |
| JDK | |
| Unit-test tasks (per module) | |
| Robolectric SDK levels | |
| Cold / warm test time | |
| Peak memory | |
| Secrets/stubs needed | |
