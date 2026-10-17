# Verified facts (live record)

The building agent fills this in during Phase 0 and updates it whenever a tool is upgraded.
Each entry: date, command run, exact output excerpt, verdict.

## Host

| Item | Value | Date |
|---|---|---|
| WSL2 memory / cpus (`docker info`) | | |
| Docker Desktop version | | |

## Claude Code

| Item | Value | Date |
|---|---|---|
| `claude --version` inside `abb-base` | | |
| `-p` / `--output-format stream-json` / `--verbose` | | |
| `--max-turns` → `error_max_turns` | | |
| `--max-budget-usd` → `error_max_budget_usd` | | |
| `--resume` with `-p` | | |
| `--permission-mode bypassPermissions` (as user `bench`) | | |
| `--disallowedTools WebFetch,WebSearch` | | |
| `--model claude-sonnet-5-5` / `claude-opus-5-5` accepted | | |
| `--append-system-prompt` | | |
| Slash command expansion in `-p` (`/speckit-specify …`) | | |
| AskUserQuestion behaviour in `-p` (Phase 4 step 3) | | |
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
