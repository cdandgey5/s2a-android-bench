# Sources consulted on 2026-10-16

These informed `specs/` and `reference/`. They go stale; `reference/verified.md` (written by the
building agent in Phase 0) is the live record.

## Claude Code (headless driving, flags, install)

- CLI reference — https://code.claude.com/docs/en/cli-reference.md
- Headless / programmatic use — https://code.claude.com/docs/en/headless.md
- Permission modes — https://code.claude.com/docs/en/permission-modes.md
- Tools reference — https://code.claude.com/docs/en/tools-reference.md
- Skills (slash command expansion in `-p`) — https://code.claude.com/docs/en/skills.md
- Sessions (`--resume`, `--continue`) — https://code.claude.com/docs/en/sessions.md
- Environment variables — https://code.claude.com/docs/en/env-vars.md
- Model configuration — https://code.claude.com/docs/en/model-config.md
- Setup and installation — https://code.claude.com/docs/en/setup.md
- Agent SDK Python reference (ResultMessage fields) — https://code.claude.com/docs/en/agent-sdk/python.md
- Agent SDK cost tracking — https://code.claude.com/docs/en/agent-sdk/cost-tracking.md

Key facts used: `-p`/`--print`; `--output-format stream-json --verbose`; `--max-turns` →
`error_max_turns`; `--max-budget-usd` → `error_max_budget_usd`; `--permission-mode
bypassPermissions` refused as root; `--disallowedTools`; `--model` accepts full ids;
`--append-system-prompt`; slash commands expand from the prompt string; `--bare` skips
CLAUDE.md/commands; `switchModelsOnFlag`; `CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS`; native
installer `curl -fsSL https://claude.ai/install.sh | bash -s <version>`; no official Docker
image.

## Claude Code on Windows (verified 2026-10-17 via the docs above)

Native Windows is supported (no WSL needed): installer `irm https://claude.ai/install.ps1 | iex`
(pin with `& ([scriptblock]::Create((irm https://claude.ai/install.ps1))) <version>`), binary at
`%USERPROFILE%\.local\bin\claude.exe`; Git for Windows provides Git Bash for the Bash tool
(`CLAUDE_CODE_GIT_BASH_PATH`), PowerShell tool toggled by `CLAUDE_CODE_USE_POWERSHELL_TOOL`;
`--disallowedTools Bash` would also remove PowerShell; settings at `%USERPROFILE%\.claude\settings.json`
(`CLAUDE_CONFIG_DIR` moves them); credentials file-based; stdin piping needs ≥ 2.1.211; the
root/sudo refusal of `bypassPermissions` is Linux/macOS only; graceful interruption on Windows
(Ctrl+Break) is **not documented** — measured in Phase 0. Android command-line tools for Windows:
`commandlinetools-win-15859902_latest.zip`, sha256
`90ae805d20434428bffcb699c290860f19bb5f66a67e6b330067e3de801fb04a`.

## Models

- Models overview — https://platform.claude.com/docs/en/about-claude/models/overview.md
- Deprecations — https://platform.claude.com/docs/en/about-claude/model-deprecations.md

Current ids used in this plan: `claude-opus-5-5` (pinned for final runs), `claude-sonnet-5-5`
(development), `claude-haiku-5-5` (not used). `claude-sonnet-4-5-20250929` is deprecated.

## GitHub Spec Kit

- Repository README — https://github.com/github/spec-kit
- Installation — https://github.com/github/spec-kit/blob/main/docs/installation.md
- Quickstart — https://github.com/github/spec-kit/blob/main/docs/quickstart.md

Key facts used: `uv tool install specify-cli --from git+https://github.com/github/spec-kit.git@<tag>`;
`specify init --here --force --non-interactive --integration claude --script ps --ignore-agent-tools` (`ps` on Windows, `sh` elsewhere);
hyphenated commands `/speckit-constitution`, `/speckit-specify`, `/speckit-clarify`,
`/speckit-plan`, `/speckit-checklist`, `/speckit-tasks`, `/speckit-analyze`,
`/speckit-implement`, `/speckit-converge`; bug extension (`specify extension add bug` →
`/speckit-bug-assess`, `/speckit-bug-fix`, `/speckit-bug-test`); artifacts `spec.md`,
`plan.md`, `tasks.md`, `.specify/feature.json`, `.specify/bugs/<slug>/`.

## Android SDK

- Android Studio downloads page, "Command line tools only" —
  https://developer.android.com/studio#command-line-tools-only
  Linux: `commandlinetools-linux-15859902_latest.zip`, SHA-256
  `4e4c464f145a7512b57d088ac6c278c03c9eea610886b35a5e0804e74eedf583`, served from
  `https://dl.google.com/android/repository/`.

## Repositories

- https://github.com/AntennaPod/AntennaPod
- https://github.com/wikimedia/apps-android-wikipedia
- https://github.com/thunderbird/thunderbird-android (+ `.java-version` = 21)
- https://github.com/TeamNewPipe/NewPipe
- https://github.com/tuskyapp/Tusky (archived 2025-05-23)

## Methodology background (not fetched today; well known)

- SWE-bench (Jimenez et al., 2023) — fail-to-pass / pass-to-pass grading, test-file reset.
- SWE-bench Verified — human validation of task quality.
- pass@k / pass^k definitions as used in agent evaluations (e.g. τ-bench's pass^k).
