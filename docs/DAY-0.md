# Day 0 — human bootstrap on Windows (about one hour, once)

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

Claude Code is already installed (2.1.197) but the plan needs **≥ 2.1.211**. Install the current
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

- Free space: C: has ~85 GB, G: ~80 GB. Without container images the plan needs ~40–60 GB for two
  repos (toolchain ~2 GB, warm Gradle caches 5–10 GB per repo, mirrors, workspaces, results).
  Put the data root on the drive with the most space and keep the path short:

```powershell
[Environment]::SetEnvironmentVariable("ABB_HOME", "G:\abb", "User")
[Environment]::SetEnvironmentVariable("ABB_RESULTS_DIR", "G:\abb\results", "User")
# optional convenience: the shared tool launchers (specify.exe, s2a.exe) on your PATH; the harness uses absolute paths anyway
[Environment]::SetEnvironmentVariable("Path", "$([Environment]::GetEnvironmentVariable('Path','User'));G:\abb\tools\bin", "User")
New-Item -ItemType Directory -Force G:\abb | Out-Null
```

- Optional but recommended for Gradle speed: a **Dev Drive** (ReFS) for `ABB_HOME`, and a Windows
  Defender **exclusion** for `G:\abb` (Settings → Virus & threat protection → Exclusions). Both are
  your call; the plan works without them, slower.

## 3. Key and budget

- A **Console API key** with credit. Store it for your user (never in the repo):

```powershell
[Environment]::SetEnvironmentVariable("ANTHROPIC_API_KEY", "sk-ant-...", "User")
```

- Set a **spend alert** in the Console; decide the dev cap per trial (`benchmark/config/limits.yaml:
  profiles.dev.max_usd`, default 5.0).
- Confirm both pinned model ids exist (new terminal so the variable is loaded):

```powershell
(irm "https://api.anthropic.com/v1/models?limit=1000" -Headers @{ "x-api-key" = $env:ANTHROPIC_API_KEY; "anthropic-version" = "2023-06-01" }).data.id | Select-String -Pattern '^claude-(opus|sonnet)-5-5$'
```

Both must print; otherwise write the current ids into `docs/DECISIONS.md` D-001 and
`benchmark/config/limits.yaml`.

## 4. The working clone (out of OneDrive)

The OneDrive folder already has a git repo initialised in it (commit `2f09972`, no remote) from an
earlier attempt. Move the work out of OneDrive — it syncs `.venv` and every transcript, and a live
`.git` under OneDrive is a known corruption risk:

```powershell
Copy-Item -Recurse "$env:USERPROFILE\OneDrive\Documents\Claude\S2AFramework" "$env:USERPROFILE\abb-src"
Set-Location "$env:USERPROFILE\abb-src"
git config core.autocrlf false
git add -A; git commit -m "plan: windows-native revision" | Out-Null
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
| Dev budget per trial and total for the first six weeks | `benchmark/config/limits.yaml`, `PLAN.md` §6 |
| `ABB_HOME` drive, Dev Drive yes/no, Defender exclusion yes/no | this file; `reference/verified.md` |

## 7. Start

Open a **new** PowerShell 7 window (so the user-level variables are loaded), then:

```powershell
Set-Location "$env:USERPROFILE\abb-src"
& "$env:USERPROFILE\.local\bin\claude.exe"
```

Paste the Phase 0 kickoff prompt from `START-HERE.md`. The agent's first step is to verify
everything above and stop if something is missing.
