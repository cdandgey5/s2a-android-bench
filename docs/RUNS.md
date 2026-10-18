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
| 01:12 (18th) | Phase 1 gate `abb sandbox check` smoke `20261018-011201-sbcheck` | claude-sonnet-5-5 | success | — | — | — | — | ~0.03 | 0 | as `abb-agent` via the proxy; part of the gate |

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

## 2026-10-18 — Phase 4 (plain arm through `abb run`: sandbox user, proxy, driver, grading, audit)

From here on every row comes from `<results>/<run_id>/` (`run.json`, `grade.json`, transcripts);
"five-hour"/"seven-day" are the `rate_limit_event` utilisations (`unifiedWindows`) at the first and
last API call of the trial. The five-hour window ran 01:00–06:00 UTC.

**Runs before 04:10 UTC are invalid (D-043):** the sandbox user could not read the read-only
Gradle and Robolectric caches (Phase 2's warm had replaced them without the grants), so every agent
Gradle run failed and the agents fixed tasks without running a test. They are kept for the cost log.

| Time (UTC) | Run / activity | Model | Result | in | out | cr | cw | est. USD | Pauses | Note |
|---|---|---|---|---|---|---|---|---|---|---|
| 03:14 | AskUserQuestion check, smoke `20261018-031351-smoke` | claude-sonnet-5-5 | success, 2 turns | 4 | 267 | 36,684 | 11,704 | 0.0532 | 0 | as `abb-agent` via the proxy; no question tool in `-p`: one `ToolSearch`, then a plain-text question ("…I'll wait for your reply…"); no permission denial (D-040); five-hour 35 %, seven-day 5 % |
| 03:15 | driver check `_driver-check/20261018-031524` (`run_headless`, question prompt) | claude-sonnet-5-5 | success, 2 + 1 turns | 6 | 560 | 52,098 | 29,538 | 0.1290 | 0 | trigger (b) nudged once; `--resume` continued the same session. The nudge's `total_cost_usd` (0.1290) was the session total, not its own 0.0064 (D-041); five-hour 38 % |
| 03:17 | `20261018-0317-shakedown` plain/antennapod-0000/t1 | claude-sonnet-5-5 | completed, 11 turns, 69 s | 18 | 1,967 | 215,491 | 12,596 | 0.0916 | 0 | **invalid (D-043)**: agent Gradle runs failed; resolved=True; nudges 0; five-hour 0.39 → 0.40, seven-day 0.05 |
| | **`20261018-0317-shakedown` total (1 trials, 1 resolved)** | | mean 69 s | **18** | **1,967** | **215,491** | **12,596** | **0.0916** (mean 0.0916) | 0 | **invalid (D-043)** |
| 03:23 | `20261018-0322-dev5-plain-1` plain/antennapod-0000/t1 | claude-sonnet-5-5 | completed, 11 turns, 65 s | 16 | 1,845 | 195,899 | 13,904 | 0.0937 | 0 | **invalid (D-043)**: agent Gradle runs failed; resolved=True; nudges 0; five-hour 0.43 → 0.44, seven-day 0.06 |
| 03:25 | `20261018-0322-dev5-plain-1` plain/antennapod-0001/t1 | claude-sonnet-5-5 | completed, 14 turns, 80 s | 20 | 3,121 | 276,438 | 17,966 | 0.1308 | 0 | **invalid (D-043)**: agent Gradle runs failed; resolved=True; nudges 0; five-hour 0.45 → 0.46, seven-day 0.06 |
| 03:27 | `20261018-0322-dev5-plain-1` plain/antennapod-0002/t1 | claude-sonnet-5-5 | completed, 9 turns, 66 s | 14 | 2,018 | 174,801 | 13,761 | 0.0927 | 0 | **invalid (D-043)**: agent Gradle runs failed; resolved=True; nudges 0; five-hour 0.48 → 0.49, seven-day 0.06 |
| 03:29 | `20261018-0322-dev5-plain-1` plain/antennapod-0003/t1 | claude-sonnet-5-5 | completed, 40 turns, 163 s | 36 | 15,169 | 841,496 | 48,420 | 0.4296 | 0 | **invalid (D-043)**: agent Gradle runs failed; resolved=True; nudges 0; five-hour 0.50 → 0.54, seven-day 0.07 |
| 03:34 | `20261018-0322-dev5-plain-1` plain/antennapod-0004/t1 | claude-sonnet-5-5 | completed, 8 turns, 88 s | 16 | 5,987 | 250,647 | 24,211 | 0.1818 | 0 | **invalid (D-043)**: agent Gradle runs failed; resolved=True; nudges 0; five-hour 0.55 → 0.56, seven-day 0.07 |
| 03:37 | `20261018-0322-dev5-plain-1` plain/antennapod-0005/t1 | claude-sonnet-5-5 | completed, 12 turns, 75 s | 18 | 5,577 | 256,263 | 19,812 | 0.1607 | 0 | **invalid (D-043)**: agent Gradle runs failed; resolved=True; nudges 0; five-hour 0.56 → 0.57, seven-day 0.07 |
| | **`20261018-0322-dev5-plain-1` total (6 trials, 6 resolved)** | | mean 89 s | **120** | **33,717** | **1,995,544** | **138,074** | **1.0893** (mean 0.1815) | 0 | **invalid (D-043)** |
| 03:40 | `20261018-0340-dev5-guided-1` plain-guided/antennapod-0000/t1 | claude-sonnet-5-5 | completed, 15 turns, 84 s | 22 | 2,790 | 321,200 | 20,891 | 0.1436 | 0 | **invalid (D-043)**: agent Gradle runs failed; resolved=True; nudges 0; five-hour 0.58 → 0.59, seven-day 0.07 |
| 03:42 | `20261018-0340-dev5-guided-1` plain-guided/antennapod-0001/t1 | claude-sonnet-5-5 | completed, 27 turns (two results, D-042), 701 s | 42 | 5,313 | 712,170 | 26,200 | 0.2292 | 0 | **invalid (D-043)**: agent Gradle runs failed; resolved=True; nudges 0; five-hour 0.6 → 0.61, seven-day 0.07 |
| 03:55 | `20261018-0340-dev5-guided-1` plain-guided/antennapod-0002/t1 | claude-sonnet-5-5 | completed, 11 turns, 66 s | 16 | 2,549 | 214,878 | 16,013 | 0.1111 | 0 | **invalid (D-043)**: agent Gradle runs failed; resolved=True; nudges 0; five-hour 0.61 → 0.62, seven-day 0.07 |
| 03:57 | `20261018-0340-dev5-guided-1` plain-guided/antennapod-0003/t1 | claude-sonnet-5-5 | completed, 31 turns, 154 s | 28 | 16,841 | 699,675 | 52,677 | 0.4491 | 0 | **invalid (D-043)**: agent Gradle runs failed; resolved=True; nudges 0; five-hour 0.62 → 0.65, seven-day 0.08 |
| | **`20261018-0340-dev5-guided-1` total (4 trials, 4 resolved)** | | mean 251 s | **108** | **27,493** | **1,947,923** | **115,781** | **0.9330** (mean 0.2333) | 0 | **invalid (D-043)**; stopped after 4 trials when the cause was found |
| 04:00 | `20261018-0340-dev5-guided-1` plain-guided/antennapod-0004/t1 | claude-sonnet-5-5 | stopped by the operator (harness killed) | — | — | — | — | unknown (< 0.5) | 0 | **invalid (D-043)**; the stream lived only in the workspace's `agent-out/` and was deleted with the workspace before it was copied: **transcript lost**. `abb run` now salvages `agent-out` streams into the run before it deletes stale workspaces |

Valid runs (after D-043; agent Gradle works):

| Time (UTC) | Run / activity | Model | Result | in | out | cr | cw | est. USD | Pauses | Note |
|---|---|---|---|---|---|---|---|---|---|---|
| 04:29 | `20261018-0429-dev5-plain-1` plain/antennapod-0000/t1 | claude-sonnet-5-5 | completed, 12 turns, 137 s | 16 | 1,984 | 191,196 | 18,295 | 0.1122 | 0 | resolved=True; nudges 0; five-hour 0.81 → 0.82, seven-day 0.10 |
| 04:33 | `20261018-0429-dev5-plain-1` plain/antennapod-0001/t1 | claude-sonnet-5-5 | completed, 16 turns, 162 s | 20 | 3,012 | 275,298 | 24,587 | 0.1560 | 0 | resolved=True; nudges 0; five-hour 0.83 → 0.84, seven-day 0.10 |
| 04:37 | `20261018-0429-dev5-plain-1` plain/antennapod-0002/t1 | claude-sonnet-5-5 | completed, 9 turns, 126 s | 12 | 2,128 | 146,386 | 17,438 | 0.1057 | 0 | resolved=True; nudges 0; five-hour 0.84 → 0.85, seven-day 0.10 |
| 04:40 | `20261018-0429-dev5-plain-1` plain/antennapod-0003/t1 | claude-sonnet-5-5 | completed, 35 turns, 258 s | 28 | 13,478 | 667,886 | 53,699 | 0.4164 | 0 | harness crashed while grading (a `repos/*.yaml` edited mid-run, my error); graded on `--resume`; resolved=True; nudges 0; five-hour 0.86 → 0.91, seven-day 0.11 |
| 04:47 | `20261018-0429-dev5-plain-1` plain/antennapod-0004/t1 | claude-sonnet-5-5 | completed, 20 turns, 205 s | 32 | 8,543 | 534,667 | 26,397 | 0.2445 | 0 | resolved=True; nudges 0; five-hour 0.93 → 0.94, seven-day 0.11 |
| 04:52 | `20261018-0429-dev5-plain-1` plain/antennapod-0005/t1 | claude-sonnet-5-5 | completed, 11 turns, 177 s | 16 | 6,292 | 221,729 | 20,406 | 0.1667 | 0 | resolved=True; nudges 0; five-hour 0.95 → 0.96, seven-day 0.11 |
| | **`20261018-0429-dev5-plain-1` total (6 trials, 6 resolved)** | | mean 178 s | **124** | **35,437** | **2,037,162** | **160,822** | **1.2015** (mean 0.2003) | 0 | |
| 04:56 | `20261018-0456-dev5-plain-2` plain/antennapod-0000/t1 | claude-sonnet-5-5 | completed, 8 turns, 130 s | 14 | 1,296 | 165,341 | 12,251 | 0.0785 | 0 | resolved=True; nudges 0; five-hour 0.97 → 0.97, seven-day 0.11 |
| 05:00 | `20261018-0456-dev5-plain-2` plain/antennapod-0001/t1 | claude-sonnet-5-5 | completed, 16 turns, 193 s | 24 | 3,407 | 333,681 | 17,531 | 0.1376 | 0 | resolved=True; nudges 0; five-hour 0.97 → 0.98, seven-day 0.12 |
| 05:04 | `20261018-0456-dev5-plain-2` plain/antennapod-0002/t1 | claude-sonnet-5-5 | completed, 9 turns, 140 s | 14 | 1,926 | 188,351 | 21,477 | 0.1240 | 0 | resolved=True; nudges 0; five-hour 0.99 → 0.99, seven-day 0.12 |
| 05:08 | `20261018-0456-dev5-plain-2` plain/antennapod-0003/t1 **attempt 1** (`usage_limited/plain/antennapod-0003/t1-a1`) | claude-sonnet-5-5 | usage_limited, 2 turns, 18 s | 2 | 100 | 15,766 | 9,880 | 0.0421 | 1 | **usage-limit canary** (verified.md): "You've hit your session limit · resets 2am (America/Toronto)"; five-hour 100 %; run stopped, resumed 09:52 UTC |
| 09:52 | `20261018-0456-dev5-plain-2` plain/antennapod-0003/t1 | claude-sonnet-5-5 | completed, 35 turns, 292 s | 34 | 13,867 | 850,926 | 68,333 | 0.4972 | 0 | attempt 2 after the reset (09:52 UTC); resolved=True; nudges 0; five-hour 0.06 → 0.1, seven-day 0.13 |
| 09:59 | `20261018-0456-dev5-plain-2` plain/antennapod-0004/t1 | claude-sonnet-5-5 | completed, 14 turns, 298 s | 24 | 8,113 | 409,754 | 26,422 | 0.2278 | 0 | resolved=True; nudges 0; five-hour 0.1 → 0.12, seven-day 0.13 |
| 10:06 | `20261018-0456-dev5-plain-2` plain/antennapod-0005/t1 | claude-sonnet-5-5 | completed, 11 turns, 167 s | 22 | 5,789 | 321,273 | 21,319 | 0.1753 | 0 | resolved=True; nudges 0; five-hour 0.12 → 0.13, seven-day 0.13 |
| | **`20261018-0456-dev5-plain-2` total (6 trials, 6 resolved)** | | mean 203 s | **132** | **34,398** | **2,269,326** | **167,333** | **1.2404** (mean 0.2067) | 1 | excludes the cut attempt (0.0421) |
| 10:10 | `20261018-1010-dev5-guided-1` plain-guided/antennapod-0000/t1 | claude-sonnet-5-5 | completed, 8 turns, 127 s | 10 | 1,411 | 115,134 | 16,478 | 0.0916 | 0 | resolved=True; nudges 0; five-hour 0.14 → 0.15, seven-day 0.13 |
| 10:13 | `20261018-1010-dev5-guided-1` plain-guided/antennapod-0001/t1 | claude-sonnet-5-5 | completed, 17 turns, 196 s | 24 | 3,770 | 354,272 | 20,433 | 0.1549 | 0 | resolved=True; nudges 0; five-hour 0.16 → 0.16, seven-day 0.14 |
| 10:18 | `20261018-1010-dev5-guided-1` plain-guided/antennapod-0002/t1 | claude-sonnet-5-5 | completed, 14 turns, 226 s | 22 | 3,182 | 318,569 | 18,270 | 0.1368 | 0 | resolved=True; nudges 0; five-hour 0.17 → 0.18, seven-day 0.14 |
| 10:23 | `20261018-1010-dev5-guided-1` plain-guided/antennapod-0003/t1 | claude-sonnet-5-5 | completed, 32 turns, 277 s | 36 | 14,417 | 863,779 | 49,201 | 0.4274 | 0 | resolved=True; nudges 0; five-hour 0.18 → 0.21, seven-day 0.14 |
| 10:29 | `20261018-1010-dev5-guided-1` plain-guided/antennapod-0004/t1 | claude-sonnet-5-5 | completed, 19 turns, 218 s | 22 | 8,702 | 430,649 | 36,358 | 0.2756 | 0 | resolved=True; nudges 0; five-hour 0.22 → 0.24, seven-day 0.14 |
| 10:35 | `20261018-1010-dev5-guided-1` plain-guided/antennapod-0005/t1 | claude-sonnet-5-5 | completed, 13 turns, 181 s | 18 | 6,919 | 292,839 | 26,470 | 0.2044 | 0 | resolved=True; nudges 0; five-hour 0.24 → 0.25, seven-day 0.14 |
| | **`20261018-1010-dev5-guided-1` total (6 trials, 6 resolved)** | | mean 204 s | **132** | **38,401** | **2,375,242** | **167,210** | **1.2907** (mean 0.2151) | 0 | |

### Phase 4 throughput and cost (valid runs, 2026-10-18; numbers from the rows above)

| Quantity | Value | How |
|---|---|---|
| est. USD per plain trial (dev5, Sonnet 5.5) | **mean 0.20** (plain-1 0.2003, plain-2 0.2067; range 0.08–0.50); **1.20–1.24 per 6-task run** | `abb report` totals; drives PLAN §6 |
| est. USD per plain-guided trial | mean 0.2151 (0.09–0.43) | `abb report 20261018-1010-dev5-guided-1` |
| wall clock per trial | plain 178–203 s, guided 204 s (incl. the agent's Gradle runs; grading ~45–80 s more) | report |
| five-hour window per trial | **~1.3–1.8 pp**: between each trial's first and last API call 10 pp / 6 (plain-1), 8 pp / 6 (guided); whole guided run 0.14 → 0.25 (11 pp / 6, 28 min, building session mostly idle) | `rate_limit_event` `unifiedWindows.five_hour` |
| trials per five-hour window | **~55–75** if trials are the only use; far fewer while this building session works in the same window (it moved the counter ~0.7 pp/min while it built, 04:00–04:32) | 100 / pp per trial |
| seven-day per trial | ~0.2 pp (0.10 → 0.14 over 15 trials incl. the building session) | same events |
| usage-limit behaviour | five-hour 90 % → `allowed_warning`; 100 % → `rejected` + a synthetic 429 message; the cut attempt is kept (`usage_limited/`), the run stops, `--resume` re-runs it after the reset | canary in `reference/verified.md` |

Lower bound note: dev5 is easy for plain on Sonnet (12/12 resolved, 6/6 guided), so the Phase 7 tasks
(more files, cross-module) will cost more per trial; re-measure on the first Phase 7 dev runs.

## 2026-10-18 — Phase 5 (Spec Kit arm, dev5)

Rows from `<results>/<run_id>/` (`scripts/runs_rows.py`). **Run `20261018-2151-dev5-speckit-1` is invalid (D-050):** on the three sdd-path tasks trigger (b) nudged `speckit-specify` ("/speckit-clarify" matched "clarify") and the agent implemented the change there. It is kept for the cost log; the whole run is repeated with the fixed arm. The bug-path trials (0000-0002) had no nudge.

| Time (UTC) | Run / activity | Model | Result | in | out | cr | cw | est. USD | Pauses | Note |
|---|---|---|---|---|---|---|---|---|---|---|
| 21:52 | `20261018-2151-dev5-speckit-1` setup speckit-constitution/antennapod | claude-sonnet-5-5 | success, 6 turns | 10 | 4,198 | 134,387 | 39,728 | 0.2144 | 0 | one-time setup (reported separately); five-hour 0.63 → 0.64, seven-day 0.08; **invalid (D-050)** for the sdd path |
| 21:52 | `20261018-2151-dev5-speckit-1` speckit/antennapod-0000/t1 | claude-sonnet-5-5 | completed, 17 turns, 253 s | 24 | 5,952 | 444,162 | 36,602 | 0.2504 | 0 | resolved=True; nudges 0; five-hour 0.64 → 0.66, seven-day 0.09; **invalid (D-050)** for the sdd path |
| 21:58 | `20261018-2151-dev5-speckit-1` speckit/antennapod-0001/t1 | claude-sonnet-5-5 | completed, 20 turns, 270 s | 28 | 6,866 | 603,344 | 42,063 | 0.2973 | 0 | resolved=True; nudges 0; five-hour 0.66 → 0.68, seven-day 0.09; **invalid (D-050)** for the sdd path |
| 22:03 | `20261018-2151-dev5-speckit-1` speckit/antennapod-0002/t1 | claude-sonnet-5-5 | completed, 16 turns, 245 s | 28 | 6,710 | 536,991 | 35,157 | 0.2615 | 0 | resolved=True; nudges 0; five-hour 0.68 → 0.7, seven-day 0.09; **invalid (D-050)** for the sdd path |
| 22:09 | `20261018-2151-dev5-speckit-1` speckit/antennapod-0003/t1 | claude-sonnet-5-5 | completed, 43 turns, 822 s | 66 | 29,773 | 2,684,496 | 110,509 | 1.0083 | 0 | resolved=True; nudges 1; five-hour 0.7 → 0.77, seven-day 0.09; **invalid (D-050)** for the sdd path |
| 22:24 | `20261018-2151-dev5-speckit-1` speckit/antennapod-0004/t1 | claude-sonnet-5-5 | completed, 47 turns, 826 s | 94 | 25,328 | 3,415,501 | 105,578 | 1.0173 | 0 | resolved=True; nudges 1; five-hour 0.77 → 0.84, seven-day 0.1; **invalid (D-050)** for the sdd path |
| 22:40 | `20261018-2151-dev5-speckit-1` speckit/antennapod-0005/t1 | claude-sonnet-5-5 | completed, 52 turns, 759 s | 72 | 26,002 | 2,440,081 | 94,193 | 0.8809 | 0 | resolved=True; nudges 1; five-hour 0.84 → 0.9, seven-day 0.11; **invalid (D-050)** for the sdd path |
| | **`20261018-2151-dev5-speckit-1` total (6 trials, 6 resolved)** | | mean 529 s | **322** | **104,829** | **10,258,962** | **463,830** | **3.9301** | 0 | incl. one-time setup; **invalid (D-050)** for the sdd path |
