# Lab notebook — every agent run

One row per run or activity that called the model. Tokens are the primary cost unit; "est. USD" is
Claude Code's client-side `total_cost_usd` at list price (est. API-equivalent; there is no bill
under the subscription). "in" = uncached input tokens, "cr"/"cw" = cache read/write. Usage-limit
pauses are counted per run. Raw records: `C:\abb\work\smoke\<dir>\summary.json` (Phase 0) and
`<results>/<run_id>/` (Phase 4 on).

## 2026-10-17 — Phase 0 (harness user, no sandbox, no proxy; pinned claude.exe 2.1.302 through the launcher)

| Time (UTC) | Run / activity | Model | Result | in | out | cr | cw | est. USD | Pauses | Note |
|---|---|---|---|---|---|---|---|---|---|---|
| 20:13 | `abb auth check` ×2 | — | `oauth_token` | 0 | 0 | 0 | 0 | 0 | 0 | `auth status` makes no model call |
| 20:15 | smoke `20261017-201539-smoke-success` | claude-sonnet-5-5 | success | 6 | 209 | 41,979 | 21,197 | 0.0911 | 0 | SCRUB=1 (then default): permission mode forced to `default`, PowerShell call denied (D-033) |
| 20:16 | smoke `…-201655-smoke` | claude-sonnet-5-5 | success | 4 | 198 | 36,692 | 5,441 | 0.0274 | 0 | SCRUB=1 + `--allowedTools`: PowerShell + Bash work, mode still `default` |
| 20:17 | smoke `…-201716-smoke` (scrub check) | claude-sonnet-5-5 | success | 4 | 202 | 36,791 | 5,570 | 0.0280 | 0 | SCRUB=1: token UNSET in Bash and PowerShell |
| 20:17 | smoke `…-201723-smoke` (scrub check) | claude-sonnet-5-5 | success | 4 | 192 | 36,791 | 5,570 | 0.0279 | 0 | SCRUB=0, bypassPermissions: token UNSET in both |
| 20:18 | smoke `…-201819-smoke` (scrub check + control) | claude-sonnet-5-5 | success | 4 | 416 | 36,891 | 5,877 | 0.0314 | 0 | SCRUB=0: token UNSET, ABB_PROBE SET, CLAUDE_CONFIG_DIR SET |
| 20:18 | smoke `…-201827-smoke` (scrub check + control) | claude-sonnet-5-5 | success | 4 | 474 | 36,891 | 5,932 | 0.0322 | 0 | SCRUB=1: token UNSET, ABB_PROBE SET, CLAUDE_CONFIG_DIR UNSET |
| 20:21 | smoke `…-202112-smoke-success` | claude-sonnet-5-5 | success | 4 | 114 | 36,672 | 5,322 | 0.0261 | 0 | superseded fixture (pre-pwsh pin) |
| 20:21 | smoke `…-202119-smoke-maxturns1` | claude-sonnet-5-5 | error_max_turns | 2 | 49 | 15,757 | 5,214 | 0.0229 | 0 | superseded fixture |
| 20:21 | smoke `…-202133-smoke-interrupt` (Ctrl+Break) | claude-sonnet-5-5 | no result line | — | — | — | — | — | 0 | stopped at 20 s; superseded fixture |
| 20:21 | smoke `…-202156-smoke-interrupt-ctrlc` | claude-sonnet-5-5 | no result line | — | — | — | — | — | 0 | invalid: Ctrl+C was disabled by an inherited flag (launcher fixed) |
| 20:23 | smoke `…-202307-smoke-success-opus` | claude-opus-5-5 | success | 4 | 117 | 20,962 | 21,135 | 0.1756 | 0 | Opus accepted on the plan (D-001) |
| 20:26 | smoke `…-202630-smoke-success` → **fixture** | claude-sonnet-5-5 | success | 4 | 89 | 36,672 | 5,297 | 0.0258 | 0 | `smoke-success.jsonl` |
| 20:26 | smoke `…-202650-smoke-maxturns1` → **fixture** | claude-sonnet-5-5 | error_max_turns | 2 | 49 | 15,757 | 5,214 | 0.0229 | 0 | `smoke-maxturns1.jsonl` |
| 20:27 | smoke `…-202709-smoke-interrupt` → **fixture** | claude-sonnet-5-5 | no result line | — | — | — | — | — | 0 | `smoke-interrupt.jsonl` (Ctrl+Break) |
| 20:27 | smoke `…-202732-smoke-interrupt-ctrlc` | claude-sonnet-5-5 | no result line | — | — | — | — | — | 0 | invalid (inherited Ctrl+C-disabled flag); replaced at 20:40 |
| 20:28 | smoke `…-202823-smoke-success-opus` → **fixture** | claude-opus-5-5 | success | 4 | 116 | 36,594 | 5,497 | 0.0536 | 0 | `smoke-success-opus.jsonl` |
| 20:40 | smoke `…-204039-smoke-interrupt-ctrlc` → **fixture** | claude-sonnet-5-5 | error_during_execution | 2 | 124 | 15,757 | 5,202 | 0.0236 | 0 | `smoke-interrupt-ctrlc.jsonl`: Ctrl+C writes a result line (D-032) |
| 20:50 | smoke `…-205048-smoke` (Git Bash check) | claude-sonnet-5-5 | success | 4 | 114 | 36,705 | 5,357 | 0.0262 | 0 | `BASH_VERSION=5.2.26(1)-release`, `MINGW64_NT-10.0-26200` |
| | **Phase 0 total (runs with a result line)** | | | **52** | **2,463** | **440,911** | **107,825** | **0.6148** | **0** | 4 Ctrl+Break/invalid runs have no result line (tokens not reported) |

Usage meter (from the `rate_limit_event` in the 20:15 transcript): five-hour window 74 % used,
seven-day 54 % — almost all of it this building session, not the smoke tests.

## 2026-10-17 — Phase 1 (sandbox user `abb-agent` through the launcher, egress proxy on 127.0.0.1:8888)

| Time (UTC) | Run / activity | Model | Result | in | out | cr | cw | est. USD | Pauses | Note |
|---|---|---|---|---|---|---|---|---|---|---|
| 23:05 | `abb sandbox check` smoke `20261017-230526-sbcheck` | claude-sonnet-5-5 | success | 4 | 163 | 36,672 | 5,336 | 0.0266 | 0 | as `abb-agent`, no profile, via the proxy: token honoured, `bypassPermissions`, 0 retries; rate_limit_event: five-hour 11 %, seven-day 56 % |
| 00:19 (18th) | S1b probe `20261018-001946-s1b-probe-tmp` — **aborted** | claude-sonnet-5-5 | error_during_execution (Ctrl+C via STOP) | 8 | 538 | 71,361 | 24,872 | 0.1120 | 0 | owner asked to measure after the Max 5x → Pro switch (21:02 EDT); stopped after 1.5 min, 6 turns; owner meter before: session 39 %, weekly 60 %; rate_limit_event at start: five-hour 40 %, seven-day 60 % (Max 5x) |
| 00:21 (18th) | ping `20261018-002130-smoke` | claude-sonnet-5-5 | success | 2 | 21 | 0 | 2,268 | 0.0093 | 0 | rate_limit_event: five-hour 42 %, seven-day 60 % |
| 01:05 (18th) | **S1b throughput probe** `20261018-010536-smoke` (Pro) | claude-sonnet-5-5 | success, 8 turns, 3 min 4 s | 16 | 1,188 | 194,077 | 16,683 | 0.0981 | 0 | as `abb-agent` via the proxy, seed task antennapod-0000 at its base, plain-arm shape (one call, 200 turns, 45 min, $5 cap); the agent fixed it (1-line diff in the duration parser); peak job memory 4.3 GB. **Owner meter: session 0 % → 3 %, weekly 0 % → 0 %**; rate_limit_event five-hour 1 % at start → 2 % after |
| 01:09 (18th) | ping `20261018-010907-smoke` | claude-sonnet-5-5 | success | 2 | 21 | 0 | 2,268 | 0.0093 | 0 | after-probe cross-check: rate_limit_event five-hour 2 %, seven-day 0 % |

### S1b throughput estimate (2026-10-18, Pro; D-027, D-038)

Lower bound: the seed task is trivial (8 turns, ~213k tokens incl. cache reads, 1.2k output).

| Quantity | Value | How |
|---|---|---|
| session % per trial | ~3 % (meter, incl. the ping); ~1 pp by the API counter | owner meter 0 → 3 %; rate_limit_event 1 → 2 % |
| weekly % per trial | < 1 % (below the meter's resolution) | owner meter 0 → 0 % |
| trials per session window | ~33 | 100 / 3 |
| trials per week | ≥ 100 (lower bound only) | 100 / (< 1) |
| dev runs (~430 trials) | ≤ ~4.3 weeks at the weekly bound; ~0.6 weeks if only session windows bind (21 windows/week assumed) | `weeks ≈ trials / min(trials_per_window × windows_per_week, trials_per_week)` |
| final matrix (504 trials, multi-stage arms 2–5× tokens → ~1,000–2,500 trial-equivalents) | ≤ ~10–25 weeks at the weekly lower bound | same formula; planned from the Opus dev-set confirmation run (Phase 10) |

Decision (autopilot default, D-038): the dev runs fit in < 8 weeks, so **stay on Pro**; the MVP cut
is decided when the first results table exists (end of Phase 4), which also measures trials per
window on realistic tasks. Moving to Max remains the owner's call.
| 01:12 (18th) | Phase 1 gate `abb sandbox check` smoke `20261018-011201-sbcheck` | claude-sonnet-5-5 | success | — | — | — | — | ~0.03 | 0 | as `abb-agent` via the proxy; part of the gate |
