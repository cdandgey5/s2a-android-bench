# Day 0 — human bootstrap on Windows (about two hours, once)

Everything below is done by you, not by the agent, because it needs installers, an account, or an
elevated PowerShell. No WSL, no Docker. When it is done, open Claude Code in `%USERPROFILE%\abb-src`
and paste the kickoff prompt from `START-HERE.md`.

## 1. Tools (regular PowerShell 7; install it first if you only have 5.1)

```powershell
winget install --id Microsoft.PowerShell -e          # PowerShell 7 (pwsh); reopen the terminal afterwards
winget install --id Git.Git -e                       # already present (2.44); also provides Git Bash for Claude Code's Bash tool
winget install --id GitHub.cli -e                    # gh
winget install --id astral-sh.uv -e                  # uv (Python 3.12 is installed by uv on demand)
gh auth login                                        # browser flow; needs repo scope
```

Claude Code is already installed (2.1.197) but the plan needs **≥ 2.1.280** (the docs: "Opus 5.5
requires v2.1.280 or later"; the latest release on 2026-10-16 was 2.1.302). Install the current
release once, then treat the version it prints as **the pin**: write it into
`benchmark/config/toolchain.yaml` (`claude_code.version`); `abb tools install` later reinstalls
exactly that number and copies the binary to `ABB_HOME\tools\claude\<version>\`.

```powershell
& ([scriptblock]::Create((irm https://claude.ai/install.ps1))) latest
& "$env:USERPROFILE\.local\bin\claude.exe" --version   # -> the pin
```

JDKs and the Android SDK are **not** installed here — `abb tools install` (Phase 0) downloads pinned,
checksummed zips into `ABB_HOME\tools`.

## 2. Disk and location

- Free space: C: (NTFS) has ~90 GB free. Without container images the plan needs ~40–60 GB for
  two repos (toolchain ~2 GB, warm Gradle caches 5–10 GB per repo, mirrors, workspaces, results).
- **Not G:.** `G:` on this laptop is Google Drive for desktop — a FAT32 virtual drive that mirrors
  C:'s free space and uploads everything written to it. No ACLs (the Phase 1 sandbox depends on
  them), a 4 GB file limit, and every Gradle cache would sync to the cloud. Use C: with a short path:

```powershell
[Environment]::SetEnvironmentVariable("ABB_HOME", "C:\abb", "User")
[Environment]::SetEnvironmentVariable("ABB_RESULTS_DIR", "C:\abb\results", "User")
# optional convenience: the shared tool launchers (specify.exe, s2a.exe) on your PATH; the harness uses absolute paths anyway
[Environment]::SetEnvironmentVariable("Path", "$([Environment]::GetEnvironmentVariable('Path','User'));C:\abb\tools\bin", "User")
New-Item -ItemType Directory -Force C:\abb | Out-Null
```

- Optional but recommended for Gradle speed: a **Dev Drive** (ReFS) for `ABB_HOME`, and a Windows
  Defender **exclusion** for `C:\abb` (Settings → Virus & threat protection → Exclusions). Both are
  your call; the plan works without them, slower.
- **Power.** Runs last hours and usage-limit pauses can last longer. While a run is active keep
  the laptop on AC with sleep off — sleep suspends every trial and their wall-clock deadlines
  fire on wake:

```powershell
powercfg /change standby-timeout-ac 0
powercfg /change hibernate-timeout-ac 0
```

  Restore your usual values afterwards (`powercfg /q` shows them).

## 3. Subscription token (no API key)

The benchmark's headless runs use your subscription through a one-year token — no API key, no
Console account. In PowerShell 7, logged in to Claude Code as usual:

```powershell
& "$env:USERPROFILE\.local\bin\claude.exe" setup-token      # prints a token; it is not saved anywhere
$t = Read-Host -MaskInput "ABB_OAUTH_TOKEN"                 # paste it here, masked: never as a literal on a command line (shell history)
[Environment]::SetEnvironmentVariable("ABB_OAUTH_TOKEN", $t, "User"); Remove-Variable t
[Environment]::SetEnvironmentVariable("ANTHROPIC_API_KEY", $null, "User")        # no API key anywhere: it would win over the token
[Environment]::SetEnvironmentVariable("CLAUDE_CODE_OAUTH_TOKEN", $null, "User")  # must NOT be set globally (next paragraph)
```

The token expires after a year: repeat these lines then (`abb auth check` tells you when it
has stopped working).

The variable is deliberately **not** named `CLAUDE_CODE_OAUTH_TOKEN`: that name is read by every
Claude Code session on this machine, outranks your login, and a token session cannot use Remote
Control or claude.ai connectors — set globally it would silently turn every building chat into a
CI session. Only the harness maps `ABB_OAUTH_TOKEN` to `CLAUDE_CODE_OAUTH_TOKEN`, inside each
trial's environment block (`specs/auth-and-usage.md` §1). Phase 0 verifies it (`abb auth check`).
Know your plan's usage limits (session and weekly; Opus has its own): the runner pauses and
probes automatically when a limit is hit, and `PLAN.md` §6 plans the runs around the windows.
Read `specs/auth-and-usage.md` §5 once — it explains why the final matrix is a decision you make
before the freeze.

## 4. The working clone (out of OneDrive)

The OneDrive folder already has a git repo in it (no remote), and every plan revision so far is
committed there (`git log` shows them). Move the work out of OneDrive — it syncs `.venv` and every
transcript, and a live `.git` under OneDrive is a known corruption risk:

```powershell
Copy-Item -Recurse "$env:USERPROFILE\OneDrive\Documents\Claude\S2AFramework" "$env:USERPROFILE\abb-src"
Set-Location "$env:USERPROFILE\abb-src"
git config core.autocrlf false
git status --short                             # expect nothing; if it lists files, commit them: git add -A; git commit -m "plan: local edits"
gh repo create <your-github-user>/s2a-android-bench --private --source . --push
```

From now on `%USERPROFILE%\abb-src` is the working tree; the OneDrive folder is the original
import (read it on GitHub instead).

## 5. One elevated step (Administrator PowerShell), later

The sandbox user, its firewall rule and the long-path policy need admin rights **once**. The
agent cannot do this; you run it after Phase 0 has built the CLI, when Phase 1 step 6 asks:
`uv run abb sandbox setup`. It creates the local user `abb-agent` with a random password (stored
in Credential Manager), the outbound firewall block for that user, enables long paths, and
sets the NTFS denies. Nothing is installed as that user (it has no network); it only reads
`ABB_HOME\tools`. Nothing else in the plan needs admin.

## 6. Decisions to write down before the first session

| Decision | Where |
|---|---|
| Pinned model and its **training-cutoff date** (from the model docs) | `docs/DECISIONS.md` D-001 |
| Claude Code version pinned (from step 1) | `benchmark/config/toolchain.yaml` |
| First two repos (default: AntennaPod, Wikipedia Android) | `docs/DECISIONS.md` D-003 (the agent fills in evidence) |
| Your plan (Pro / Max 5x / Max 20x — `claude auth status` showed `pro` on 2026-10-17; `abb auth check` records it in every run) and whether `--model claude-opus-5-5` is allowed on it (Phase 0 smoke test decides the pin) | `docs/DECISIONS.md` D-001 |
| `ABB_HOME` drive, Dev Drive yes/no, Defender exclusion yes/no | this file; `reference/verified.md` |

## 7. Start

Open Claude Code on `%USERPROFILE%\abb-src` — either the desktop app's Code tab pointed at that
folder, or a **new** PowerShell 7 window. Both must start *after* §2 and §3 set the user-level
variables, or they will not see `ABB_HOME` and `ABB_OAUTH_TOKEN` and Phase 0 step 1 fails. For
the desktop app that means **quit it completely** (tray icon → Quit; closing the window is not
enough) and start it again — a Code-tab chat's shell inherits the app's environment from when
the app started:

```powershell
Set-Location "$env:USERPROFILE\abb-src"
& "$env:USERPROFILE\.local\bin\claude.exe"
```

Either way it runs on your normal login (the token is under a name Claude Code never reads).
Paste the Phase 0 kickoff prompt from `START-HERE.md` §2. The agent's first step is to verify
everything above and stop if something is missing.
