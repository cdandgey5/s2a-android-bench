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
| `ABB_OAUTH_TOKEN` | set (user scope): 108 characters, `sk-ant-oat` prefix, no whitespace or quotes (value never read). First attempt saved nothing: `Read-Host -MaskInput` needs PowerShell 7, and an empty value deletes a user variable, so the owner used a `Read-Host -AsSecureString` block that refuses empty input. Not yet proven to authenticate — Phase 0 step 5 (`abb auth check`). `CLAUDE_CODE_OAUTH_TOKEN`, `ANTHROPIC_API_KEY` unset (user) | 2026-10-17 |
| `uv` version | 0.13.1 (2026-10-13) (`winget install --id astral-sh.uv -e`). winget did not create its `uv`/`uvx` aliases (`%LOCALAPPDATA%\Microsoft\WinGet\Links` is empty — symlinks need Developer Mode), so its package folder `%LOCALAPPDATA%\Microsoft\WinGet\Packages\astral-sh.uv_Microsoft.Winget.Source_8wekyb3d8bbwe` was added to the user `Path` | 2026-10-17 |
| Claude Code (the pin) | `claude.exe update`: "Successfully updated from 2.1.197 to version 2.1.302"; `claude.exe --version` → `2.1.302 (Claude Code)`; written to `benchmark/config/toolchain.yaml` | 2026-10-17 |
| Subscription plan (owner, 2026-10-17 evening) | **Max 5x until 21:00 EDT on 2026-10-17, then Pro** (the owner downgraded; Day 0's `auth status` read `pro`); weekly limit resets Sundays 15:00 local. The S1b throughput probe is therefore measured on Pro after 21:02 EDT | 2026-10-17 |
| Pinned-model cutoffs | platform.claude.com/docs/en/about-claude/models/overview, comparison table: `claude-opus-5-5` and `claude-sonnet-5-5` both "Reliable knowledge cutoff: Jun 2026", "Training data cutoff: Jun 2026"; month only, no day → D-001 uses 2026-07-01 as the first post-cutoff day | 2026-10-17 |

### Phase 0 step 1 — bootstrap check, run 4 (2026-10-17, autopilot session) — PASS

Run from the desktop app's Code tab in `C:\Users\natas\abb-src` (PowerShell 7 tool).

| Check | Command | Result | Verdict |
|---|---|---|---|
| PowerShell 7 | `$PSVersionTable.PSVersion` | 7.6.7 | ok |
| Git | `git --version` | 2.44.0.windows.1 | ok |
| `gh` + auth | `gh auth status` | 2.102.0; logged in as `cdandgey5` (keyring), scopes `gist, read:org, repo, workflow` | ok |
| `uv` | `uv --version` | 0.13.1 (62faed335 2026-10-13) | ok |
| Claude Code | `& "$env:USERPROFILE\.local\bin\claude.exe" --version` | `2.1.302 (Claude Code)` = `toolchain.yaml` pin, ≥ 2.1.280 | ok |
| `ABB_HOME` / `ABB_RESULTS_DIR` | process + user env | `C:\abb` / `C:\abb\results` (both scopes) | ok |
| Disk | `Get-PSDrive C` | 88.5 GB free (≥ 60 GB) | ok |
| `ABB_OAUTH_TOKEN` | process env, length only | set, 108 chars (value never printed) | ok |
| `ANTHROPIC_API_KEY`, `CLAUDE_CODE_OAUTH_TOKEN`, `ANTHROPIC_AUTH_TOKEN` | process + user env | all unset | ok |
| Remote | `git remote -v` | `origin https://github.com/cdandgey5/s2a-android-bench.git` | ok |

Side findings: `python` on PATH is the Microsoft Store alias (and a Store CPython 3.12 exists);
`pwsh` is a per-user Store/MSIX package (`%LOCALAPPDATA%\Microsoft\WindowsApps\pwsh.exe`, no
`C:\Program Files\PowerShell\7`). Both are avoided: the dev venv uses uv-managed CPython 3.12.15
(`[tool.uv] python-preference = "only-managed"`), and the agent's PowerShell is a pinned zip under
`ABB_HOME\tools\pwsh` (D-031). Global git config was empty before `abb tools install` applied
`core.autocrlf=false`, `core.eol=lf`, `core.longpaths=true`, `core.filemode=false`.

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

### Phase 0 step 5 — tool verification (2026-10-17, pinned 2.1.302, through `abb ws smoke` / `abb auth check`)

All runs: harness user, the launcher (`ABB_HOME\tools\abb_launch.py` under the tools CPython
3.12.15), a Job Object, an environment block built from scratch (`agent_env.py`), a fresh
per-run `CLAUDE_CONFIG_DIR` seeded from `sandbox/claude-config.template` (`switchModelsOnFlag:
false`), **no proxy** (Phase 1), `--permission-mode bypassPermissions --disallowedTools
WebFetch,WebSearch`, prompt on stdin. Token usage of every run: `docs/RUNS.md`.

| Item | Value | Date |
|---|---|---|
| `claude.exe --version` (pinned copy under `ABB_HOME\tools\claude`) | `C:\abb\tools\claude\2.1.302\claude.exe` → `2.1.302 (Claude Code)`; sha256 `3ab075f7…a0ae` in `config/toolchain.lock.yaml` | 2026-10-17 |
| `abb auth check`: `claude.exe auth status` through the launcher with the mapped token and an empty `CLAUDE_CONFIG_DIR` → `authMethod` (expected `oauth_token`) | exit 0, `loggedIn: true`, **`authMethod: oauth_token`**, `apiProvider: firstParty` — the token is honoured with an empty config dir. Fields: `analyticsDisabled, apiProvider, authMethod, configDirectory, loggedIn, projectsDirectory`: a token session reports **no `subscriptionType`**; the harness user's own CLI login reports `authMethod: none` (the desktop app holds the owner's login), so the plan is not measurable here — the Day 0 reading `pro` stands (`ABB_HOME\state\auth.json: plan_source`) | 2026-10-17 |
| Token honoured as the sandbox user `abb-agent` (Phase 1 smoke test through `CreateProcessWithLogonW`) | Phase 1 | |
| `total_cost_usd` / `usage` present in `-p` results under subscription auth | yes: `total_cost_usd`, `usage.{input_tokens, output_tokens, cache_read_input_tokens, cache_creation_input_tokens, cache_creation.ephemeral_1h_input_tokens, service_tier, speed, …}`, `modelUsage` | 2026-10-17 |
| `--model claude-opus-5-5` accepted on this plan (else Sonnet for everything, D-001) | **accepted** (Pro): `smoke-success-opus` → success, `init.model` and the `modelUsage` key are `claude-opus-5-5` | 2026-10-17 |
| Resolved model id (`init.model`, `modelUsage` keys) | exactly `claude-sonnet-5-5` / `claude-opus-5-5` — no dated snapshot suffix, no background haiku key in these short runs | 2026-10-17 |
| Throughput probe (S1b, D-027) on Pro | seed task as `abb-agent` via the proxy, Sonnet, plain-arm shape: success in 8 turns / 3 min 4 s, 16 in / 1,188 out / 194,077 cache read / 16,683 cache write tokens, est. $0.0981; owner meter session 0 % → 3 %, weekly 0 % → 0 %; rate_limit_event five-hour 1 % → 2 %. Lower bound ~3 % session per trial (~33 trials per window), < 1 % weekly; token sessions as the sandbox user are counted on the owner's account meter (`docs/RUNS.md`) | 2026-10-18 |
| Usage-limit output in `-p` (verbatim tail, error text, exit code) — Phase 4 canary | Phase 4 | |
| `rate_limit_event` in `-p` stream-json | **present** in every run with a model call, before the first assistant message: `{"type":"rate_limit_event","rate_limit_info":{"status":"allowed","resetsAt":<epoch s>,"rateLimitType":"five_hour","overageStatus":"rejected","overageDisabledReason":"org_level_disabled","isUsingOverage":false,"unifiedWindows":{"five_hour":{"utilization":0.74,"resetsAt":…},"seven_day":{"utilization":0.54,"resetsAt":…}}}}`. Per-window utilisation is exposed, so D-028 (c) (stop launching near a window's end) is implementable; the key is camelCase `rateLimitType`, not `rate_limit_type` | 2026-10-17 |
| `rate_limit_event` utilisation vs the claude.ai usage meter | **match**: owner read session 39 % / weekly 60 % at 00:19Z on 2026-10-18 (Max 5x); the probe's first event said `five_hour.utilization 0.40`, `seven_day.utilization 0.60`. So `unifiedWindows.five_hour` = the meter's session %, `seven_day` = weekly %; the harness can read the windows itself (one data point; re-check on Pro) | 2026-10-18 |
| `-p` / `--output-format stream-json` / `--verbose` | work; event types seen: `system/init`, `rate_limit_event`, `assistant`, `user`, `system/task_started`, `system/task_notification`, `tool_progress`, `system/permission_denied`, `result/*` (the Bash tool runs as a `local_bash` task) | 2026-10-17 |
| `--max-turns` → `error_max_turns` | works (`--max-turns 1` + a two-call prompt → `subtype: error_max_turns`, `num_turns: 2`, exit 1) although `--max-turns` is **not listed in `claude --help`** on 2.1.302 | 2026-10-17 |
| `--max-budget-usd` → `error_max_budget_usd` | flag listed in `--help`; a trip is not exercised yet (Phase 4) | 2026-10-17 |
| `--resume` with `-p` | flag listed; exercised in Phase 4 (nudges) | 2026-10-17 |
| `--permission-mode bypassPermissions` | honoured (`init.permissionMode: bypassPermissions`) **only with `CLAUDE_CODE_SUBPROCESS_ENV_SCRUB` unset or 0**. With `=1`, stderr says `⚠ Permission mode forced to default — CLAUDE_CODE_SUBPROCESS_ENV_SCRUB is set (allowed_non_write_users hardening). Declare allowedTools explicitly, or set CLAUDE_CODE_SUBPROCESS_ENV_SCRUB=0 to opt out.`; in that mode a PowerShell call without an allow rule is denied (`permission_denied`: "Command contains malformed syntax that cannot be parsed: pwsh exited with code 1: The command line is too long."); with `--allowedTools "Bash,PowerShell,…"` both shells work → D-033. `--help` lists the modes `acceptEdits, auto, bypassPermissions, manual, dontAsk, plan`. As the sandbox user: Phase 1 | 2026-10-17 |
| `--disallowedTools WebFetch,WebSearch` | accepted; WebFetch/WebSearch absent from `init.tools` | 2026-10-17 |
| `init.tools` in `-p` (2.1.302) | `Task, Bash, CronCreate, CronDelete, CronList, Edit, EnterWorktree, ExitWorktree, Glob, Grep, ListAgents, NotebookEdit, PowerShell, Read, RemoteTrigger, ReportFindings, ScheduleWakeup, SendMessage, Skill, TaskStop, ToolSearch, Workflow, Write` — **no `AskUserQuestion` and no `TodoWrite`** (input for Phase 4 step 3 and D-005) | 2026-10-17 |
| `--model claude-sonnet-5-5` / `claude-opus-5-5` accepted | both | 2026-10-17 |
| `--append-system-prompt` | listed in `--help`; exercised in Phase 4 | 2026-10-17 |
| Slash command expansion in `-p` (`/speckit-specify …`) | Phase 5 | |
| AskUserQuestion behaviour in `-p` (Phase 4 step 3) | **no `AskUserQuestion` tool in `-p` on 2.1.302.** Prompt "Before doing anything, ask me which of two options I prefer using your question tool, then stop." as `abb-agent`: the model ran `ToolSearch` for a question tool, found none, asked in plain text ("Please tell me the two options… I'll wait for your reply"), result `success`, `permission_denials: []`. Through the driver the question heuristic (trigger b, phrase list widened, D-040) nudged once and `claude -p --resume <session_id>` **continued the same session** (same `session_id`, the agent then stated its assumptions). Trigger (a) cannot fire on this version; (c) empty diff covers implementing calls | 2026-10-18 |
| Ctrl+C / Ctrl+Break in `-p` on Windows: `result` line written? exit code? (Phase 0 step 5) | `abb ws smoke --deadline 20 "Count slowly to 100 …"`, grace 30 s. **Ctrl+Break** (`GenerateConsoleCtrlEvent(CTRL_BREAK_EVENT, <child group>)`): claude.exe exits **0** after ~1.6 s, the running Bash task is killed (`tool_result` "Exit code 137"), **no `result` line** (`smoke-interrupt.jsonl`). **Ctrl+C** (`CTRL_C_EVENT` to the launcher's private console, child created with Ctrl+C enabled): claude.exe writes a **`result` line, `subtype: error_during_execution`**, with `total_cost_usd` and `usage`, then exits **0** after ~1.6 s (`smoke-interrupt-ctrlc.jsonl`). The first Ctrl+C attempts showed no effect at all: the "ignore Ctrl+C" flag was inherited from this session's shell down to the launcher; the launcher now clears it before starting the child. **Decision: both drivers use `ctrl_c`** (D-032) | 2026-10-17 |
| Scrub check (D-026) | the prompt runs `[ -n "$CLAUDE_CODE_OAUTH_TOKEN" ] && echo SET || echo UNSET` (Bash) and `if ($env:CLAUDE_CODE_OAUTH_TOKEN) {'SET'} else {'UNSET'}` (PowerShell): **UNSET / UNSET** with `CLAUDE_CODE_SUBPROCESS_ENV_SCRUB=1` **and** with `=0`. Positive control (`--env ABB_PROBE=1`): `ABB_PROBE` is SET in both shells, so the check does see inherited variables; `CLAUDE_CONFIG_DIR` is SET with 0 and UNSET with 1 (the documented extra effect of the scrub). Token-value grep over every file of every smoke trial directory: 0 hits. → claude.exe 2.1.302 strips its own OAuth token from tool subprocesses regardless of the scrub; this check is re-run on every pin change (D-033) | 2026-10-17 |
| Bash tool runs Git Bash (`echo $BASH_VERSION`) | yes: `BASH_VERSION=5.2.26(1)-release`, `uname -s` → `MINGW64_NT-10.0-26200` (Git for Windows 2.44, found through `git.exe` on the block's PATH) | 2026-10-17 |
| PowerShell tool | `init.powershell_path` = `C:\abb\tools\pwsh\pwsh.exe` (the pinned 7.6.7 zip, D-031); with the owner's Store pwsh it was `%LOCALAPPDATA%\Microsoft\WindowsApps\pwsh.exe` | 2026-10-17 |
| `switchModelsOnFlag` on the pinned version | still documented (docs/en/model-config, read 2026-10-17: `false` = "Ask each time"; non-interactive: "a flagged request ends the turn with a refusal instead") → kept in `benchmark/sandbox/claude-config.template/settings.json` | 2026-10-17 |
| Revoking a `setup-token` token | **not documented** (docs/en/authentication, read 2026-10-17: the command "does not save the token anywhere"; nothing on revocation; `/logout` revokes only credentials that `/login` or a keyless Console sign-in wrote) → Phase 10's retired token is left to expire | 2026-10-17 |
| TLS revocation checks as the sandbox user | `curl.exe` (schannel) through the proxy fails intermittently with `CRYPT_E_REVOCATION_OFFLINE` (exit 35): the user cannot reach CRL/OCSP servers (firewall; the proxy allows api.anthropic.com only); it passes when Windows has a cached CRL. `claude.exe` (own TLS stack) is unaffected: every smoke as `abb-agent` succeeded. `abb sandbox check` uses `--ssl-no-revoke`; any agent tool that uses schannel (PowerShell `Invoke-WebRequest`, git with schannel) would see the same, which is harmless because nothing but the API is reachable anyway | 2026-10-18 |
| Hidden launcher console | `CREATE_NEW_CONSOLE` + `STARTF_USESHOWWINDOW`/`SW_HIDE`: `GetConsoleWindow()` non-null and `IsWindowVisible` false in every run; no new `WindowsTerminal.exe` process during a launch (default terminal "let Windows decide") → the `CREATE_NO_WINDOW` fallback is not needed | 2026-10-17 |
| Peak job memory | smoke runs 410–480 MB (claude.exe + Git Bash); module test runs with two test workers: AntennaPod `:app` 3162 MB, Wikipedia `:app` clean+test 6529 MB → `process.memory_mb: 10240` (D-034) | 2026-10-17 |
| Smoke test result JSON excerpt | `smoke-success`: `{"subtype":"success","is_error":false,"num_turns":2,"total_cost_usd":0.0258,"usage":{"input_tokens":4,"output_tokens":89,"cache_read_input_tokens":36672,"cache_creation_input_tokens":5297,…},"modelUsage":{"claude-sonnet-5-5":{…}},"permission_denials":[]}`; `init.apiKeySource: "none"` | 2026-10-17 |
| `claude --help` flags used by the driver | listed: `-p/--print`, `--output-format`, `--verbose`, `--max-budget-usd`, `--resume`, `--permission-mode`, `--dangerously-skip-permissions`, `--disallowedTools`, `--allowedTools`, `--model`, `--append-system-prompt`, `--tools`, `--json-schema`, `--input-format`, `--permission-prompts` (`host` or `none`), `--include-partial-messages`, `--settings`; present but must stay unused: `--bare`, `--fallback-model`, `--no-session-persistence`, `--restricted`. Not listed but working: `--max-turns`. Full text: `C:\abb\logs\claude-help-2.1.302.txt` | 2026-10-17 |

## Spec Kit

| Item | Value | Date |
|---|---|---|
| `specify --version` | `specify 1.2.1` (provisional pin `v1.2.1`, latest release 2026-10-16T20:41Z; `uv tool install specify-cli --from git+https://github.com/github/spec-kit.git@v1.2.1` into `ABB_HOME\tools\uvtools`, exe `ABB_HOME\tools\bin\specify.exe`) | 2026-10-17 |
| `specify init --help` (flags used) | `[project_name]`, `--here`, `--force`, `--integration <str>` (e.g. `claude`), `--integration-options`, `--script sh/ps/py`, `--non-interactive` ("Required for agent harnesses"), `--ignore-agent-tools`, `--preset`, `--extension`, `--allow-symlinks`; the help's example says "Claude installs skills by default" (Phase 5: skills vs slash commands) | 2026-10-17 |
| Files created by `specify init --integration claude` | Phase 5 | |
| Command names found in `.claude/` | Phase 5 | |
| `specify extension add bug` → command names | Phase 5 | |

## Android SDK

| Item | Value | Date |
|---|---|---|
| cmdline-tools zip + sha256 | `commandlinetools-win-15859902_latest.zip`, sha256 `90ae805d20434428bffcb699c290860f19bb5f66a67e6b330067e3de801fb04a` — still the Windows entry on developer.android.com/studio (2026-10-17); the download was verified against it | 2026-10-17 |
| `sdkmanager --list_installed` after a full build | `build-tools;35.0.0 35.0.0`, `build-tools;36.0.0 36.0.0`, `platform-tools 37.0.1`, `platforms;android-35 2`, `platforms;android-36 2`, `platforms;android-37.0 2` (the 36/37 entries were first auto-installed by AGP; now pinned in `toolchain.yaml`) | 2026-10-17 |
| JDKs | `java -version`: `openjdk version "17.0.20.1" 2026-08-18` (Temurin `jdk-17.0.20.1+1`), `openjdk version "21.0.12.1" 2026-08-18 LTS` (`jdk-21.0.12.1+1`); sha256 in the lock | 2026-10-17 |

## Repositories (one block per repo; from the Phase 0 experiment — details in `reference/build-experiments.md`)

### antennapod
| Item | Value |
|---|---|
| Commit built | `3d105d598dfa582c6cb22ba40b56d11780366890` (`develop`, the default branch) |
| JDK | 21 |
| Unit-test tasks (per module) | `testFreeDebugUnitTest` on the 22 flavored modules (incl. `:app`), `testDebugUnitTest` elsewhere (e.g. `:parser:feed`, `:model`) |
| Robolectric SDK levels | no `@Config(sdk=…)`, no `robolectric.properties`: defaults to the module's target |
| Cold / warm test time | `:app` 209 s / 41 s (94 s with recompile); `:parser:feed` 36 s / 22 s (37 s) |
| Peak memory | 2467 MB (`:app` cold), 3162 MB with 2 test workers |
| Secrets/stubs needed | none |

### wikipedia
| Item | Value |
|---|---|
| Commit built | `0c7ee9b4682512217e01d829fb0b6d068d268724` (`main`, the default branch) |
| JDK | 17 |
| Unit-test tasks (per module) | `testAlphaDebugUnitTest` (CI's variant) on `:app` and `:analytics:testkitchen` |
| Robolectric SDK levels | `robolectric.properties`: `sdk=24` |
| Cold / warm test time | `:app` 490 s / 26 s (279 s with recompile); `:analytics:testkitchen` 111 s / 20 s (53 s) |
| Peak memory | 5494 MB (`:app` cold), 6529 MB with 2 test workers and a recompile |
| Secrets/stubs needed | none (`google-services.json`, `repo.keystore` tracked upstream) |
