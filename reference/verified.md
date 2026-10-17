# Verified facts (live record)

The building agent fills this in during Phase 0 and updates it whenever a tool is upgraded.
Each entry: date, command run, exact output excerpt, verdict.

## Host (Windows-native)

| Item | Value | Date |
|---|---|---|
| PowerShell 7 version | | |
| `ABB_HOME` drive and free space | | |
| Git for Windows version; `core.autocrlf`/`core.eol` | | |
| Defender exclusion / Dev Drive (yes/no) | | |

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
