# Verified facts (live record)

The building agent fills this in during Phase 0 and updates it whenever a tool is upgraded.
Each entry: date, command run, exact output excerpt, verdict.

## Host (Windows-native)

| Item | Value | Date |
|---|---|---|
| PowerShell 7 version | 7.6.7 (`winget install --id Microsoft.PowerShell -e`); Windows PowerShell 5.1.26100.9711 also present | 2026-10-17 |
| `ABB_HOME` drive and free space | `ABB_HOME=C:\abb`, `ABB_RESULTS_DIR=C:\abb\results` (user scope), `C:\abb` created, `C:\abb\tools\bin` on user `Path`. C: NTFS, 928.7 GiB, 89.9 GiB free. G: is Google Drive for desktop (`Win32_LogicalDisk`: FAT32, label "Google Drive", `GoogleDriveFS` running), mirrors C:'s size; unusable for `ABB_HOME` | 2026-10-17 |
| Git for Windows version; `core.autocrlf`/`core.eol` | 2.44.0.windows.1; `core.autocrlf=true` (system), `core.eol`/`core.longpaths`/`core.filemode` unset (global); `LongPathsEnabled=1` (HKLM) | 2026-10-17 |
| Defender exclusion / Dev Drive (yes/no) | exclusions not readable without admin; Dev Drive: no (C: is NTFS) | 2026-10-17 |
| `gh` version | 2.102.0 (2026-09-30) (`winget install --id GitHub.cli -e`) | 2026-10-17 |
| `gh auth status` | logged in to github.com as `cdandgey5` (keyring), protocol https, scopes `gist, read:org, repo, workflow`. Git's own credential helper is still `manager` (GCM); `gh auth setup-git` not run | 2026-10-17 |
| Working clone + remote | `%USERPROFILE%\abb-src` copied from OneDrive, `core.autocrlf=false` (local), `git fsck`: one dangling blob, no errors; `gh repo create s2a-android-bench --private --source . --remote origin` → https://github.com/cdandgey5/s2a-android-bench (PRIVATE, default `main`), `main` pushed | 2026-10-17 |
| `ABB_OAUTH_TOKEN` | **not set** (user and machine scope, no `benchmark/.env`) after the owner ran the Day 0 §3 lines; `CLAUDE_CODE_OAUTH_TOKEN`, `ANTHROPIC_API_KEY` unset (user) | 2026-10-17 |
| `uv` version | 0.13.1 (2026-10-13) (`winget install --id astral-sh.uv -e`). winget did not create its `uv`/`uvx` aliases (`%LOCALAPPDATA%\Microsoft\WinGet\Links` is empty — symlinks need Developer Mode), so its package folder `%LOCALAPPDATA%\Microsoft\WinGet\Packages\astral-sh.uv_Microsoft.Winget.Source_8wekyb3d8bbwe` was added to the user `Path` | 2026-10-17 |
| Claude Code (the pin) | `claude.exe update`: "Successfully updated from 2.1.197 to version 2.1.302"; `claude.exe --version` → `2.1.302 (Claude Code)`; written to `benchmark/config/toolchain.yaml` | 2026-10-17 |
| Pinned-model cutoffs | platform.claude.com/docs/en/about-claude/models/overview, comparison table: `claude-opus-5-5` and `claude-sonnet-5-5` both "Reliable knowledge cutoff: Jun 2026", "Training data cutoff: Jun 2026"; month only, no day → D-001 uses 2026-07-01 as the first post-cutoff day | 2026-10-17 |

### Phase 0 step 1 — bootstrap check, run 3 (2026-10-17, subscription-auth plan, D-025)

Verdict: **FAIL — Day 0 (Windows) still not done.** Nothing changed since run 2: `pwsh`, `gh`, `uv`
missing; Claude Code 2.1.197 (needs ≥ 2.1.211); `ABB_HOME`, `ABB_RESULTS_DIR`, `ABB_OAUTH_TOKEN`
unset (process and user); `%USERPROFILE%\abb-src` and `C:\abb` absent; C: 90.2 GiB free.

| Check | Command | Result | Verdict |
|---|---|---|---|
| `ANTHROPIC_API_KEY`, `ANTHROPIC_AUTH_TOKEN`, `CLAUDE_CODE_OAUTH_TOKEN` | process + user env (names only) | all unset | ok |
| Subscription plan | `claude.exe auth status --json` → `subscriptionType` | `pro` | **Pro: smallest usage windows; see the plan review** |
| Auth of the building chat | same → `authMethod`, `apiProvider` | `claude.ai`, `firstParty` | ok (normal login) |
| `auth status` fields | same, keys only | `apiProvider, authMethod, email, loggedIn, orgId, orgName, subscriptionType`; JSON is the default (`--text` for human) | `abb auth check` can record `subscriptionType` instead of a free-text plan |
| Env inherited by a desktop-app chat's shell | `Get-ChildItem env:` names matching CLAUDE/ANTHROPIC | ~29 vars, e.g. `ANTHROPIC_BASE_URL=https://api.anthropic.com/`, `CLAUDE_CODE_ENTRYPOINT=claude-desktop`, `CLAUDE_CODE_SIMPLE=0`, `CLAUDE_CODE_CHILD_SESSION`, `CLAUDE_CODE_MESSAGING_TOKEN`; no OAuth token or API key | the trial env block must stay built from scratch; the by-hand smoke recipe must not run from a chat |

Pre-pin CLI facts (`claude.exe --help`, 2.1.197; re-check on the pinned version in step 5):
`--bare` "Sets CLAUDE_CODE_SIMPLE=1. Anthropic auth is strictly ANTHROPIC_API_KEY or apiKeyHelper
… (OAuth and keychain are never read)" — confirms D-025's "never `--bare`". `--tools ""` disables
all tools. `--json-schema <schema>` exists. `--max-budget-usd` "only works with --print".
`setup-token`: "Set up a long-lived authentication token (requires Claude subscription)".
`--fallback-model` exists (must stay unset).

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

### Docs check (2026-10-17, code.claude.com; re-check against the pinned version)

| Claim in the plan | Verdict | Source / note |
|---|---|---|
| `claude setup-token`: one-year OAuth token, Pro/Max/Team/Enterprise, not saved | confirmed | docs/en/authentication ("generate a one-year OAuth token"; "It does not save the token anywhere.") |
| Precedence: cloud flags, `ANTHROPIC_AUTH_TOKEN`, `ANTHROPIC_API_KEY`, `apiKeyHelper`, `CLAUDE_CODE_OAUTH_TOKEN`, `/login` | confirmed | docs/en/authentication ("the key is always used when present") |
| Token session "can only make model requests" | confirmed | docs/en/authentication |
| `--bare` never reads the OAuth token | confirmed (also in local `--help`) | docs say `--bare` **"will"** become the `-p` default in a future release (plan says "may") |
| `claude auth status` `authMethod` values; exit code | confirmed | docs/en/cli-reference: "Exits with code 0 if logged in, 1 if not."; JSON is the default (`--text` for humans) |
| `total_cost_usd` is a client-side estimate at list price | confirmed for `-p`; "under any auth" not documented | docs/en/headless, docs/en/agent-sdk/cost-tracking |
| Plan-limit behaviour of `-p` | **not documented**; no result subtype for it | SDK types document `rate_limit_event` with `rate_limit_info.status`, `resetsAt`; Python adds `rate_limit_type` ∈ `five_hour, seven_day, seven_day_opus, seven_day_sonnet, overage`. Whether `-p` stream-json emits it is undocumented — Phase 0 smoke records it |
| `CLAUDE_CODE_SUBPROCESS_ENV_SCRUB=1` strips credentials from Bash/hook/MCP subprocess envs | exists | docs/en/env-vars; matches "by name or value shape"; the example names `ANTHROPIC_API_KEY`, not `CLAUDE_CODE_OAUTH_TOKEN` — prove it in Phase 0; it also removes `CLAUDE_CONFIG_DIR` from subprocesses |
| `DISABLE_AUTOUPDATER`, `DISABLE_UPDATES`, `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC`, `CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS` (≥ 2.1.182), `CLAUDE_CODE_PROXY_RESOLVES_HOSTS`, `CLAUDE_CODE_USE_POWERSHELL_TOOL`, `CLAUDE_CONFIG_DIR` | confirmed | docs/en/env-vars |
| `--tools ""`, `--json-schema` → `structured_output`, subtypes `error_max_turns`, `error_max_budget_usd`, `error_max_structured_output_retries` | confirmed | docs/en/cli-reference, docs/en/headless, docs/en/agent-sdk/python |
| `switchModelsOnFlag` documented | **yes** | docs/en/model-config: `false` = "Ask each time"; in `-p` "a flagged request ends the turn with a refusal instead" → keep it in the template |
| Full model id `claude-opus-5-5` on `--model`; Pro/Max default to Opus 5.5 | confirmed; per-plan availability not documented | docs/en/model-config: **"Opus 5.5 requires v2.1.280 or later."** — the plan's floor of 2.1.211 is too low |
| Legal page wording (OAuth for ordinary individual use) | mostly confirmed | docs/en/legal-and-compliance: "assume ordinary, individual usage of Claude Code and the Agent SDK"; "should use API key authentication"; enforcement sentence reads "may do so without prior notice"; use-case questions go to sales |
| Latest Claude Code release | 2.1.302 (2026-10-16) | docs/en/changelog |

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
