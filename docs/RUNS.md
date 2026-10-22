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

Valid Phase 5 gate run (D-050 fixed; no nudge on any call; code edits only in `bug-fix` / `implement` / `implement-2`). The constitution setup is reused from `20261018-2151` (produced at est. $0.2144, no nudge).

| Time (UTC) | Run / activity | Model | Result | in | out | cr | cw | est. USD | Pauses | Note |
|---|---|---|---|---|---|---|---|---|---|---|
| 01:12 | `20261019-0112-dev5-speckit-2` speckit/antennapod-0000/t1 | claude-sonnet-5-5 | completed, 15 turns, 234 s | 24 | 4,984 | 426,427 | 53,840 | 0.3079 | 0 | resolved=True; nudges 0; five-hour 0 → 0.02, seven-day 0.12 |
| 01:17 | `20261019-0112-dev5-speckit-2` speckit/antennapod-0001/t1 | claude-sonnet-5-5 | completed, 20 turns, 250 s | 28 | 7,096 | 549,298 | 37,813 | 0.2772 | 0 | resolved=True; nudges 0; five-hour 0.02 → 0.04, seven-day 0.12 |
| 01:23 | `20261019-0112-dev5-speckit-2` speckit/antennapod-0002/t1 | claude-sonnet-5-5 | completed, 18 turns, 280 s | 30 | 6,722 | 585,280 | 34,481 | 0.2637 | 0 | resolved=True; nudges 0; five-hour 0.04 → 0.06, seven-day 0.12 |
| 01:29 | `20261019-0112-dev5-speckit-2` speckit/antennapod-0003/t1 | claude-sonnet-5-5 | completed, 80 turns, 1161 s | 84 | 46,240 | 4,341,996 | 143,779 | 1.4719 | 0 | resolved=True; nudges 0; five-hour 0.06 → 0.16, seven-day 0.13 |
| 01:50 | `20261019-0112-dev5-speckit-2` speckit/antennapod-0004/t1 | claude-sonnet-5-5 | completed, 53 turns, 1006 s | 94 | 32,938 | 4,057,721 | 117,019 | 1.2034 | 0 | resolved=True; nudges 0; five-hour 0.16 → 0.24, seven-day 0.14 |
| 02:09 | `20261019-0112-dev5-speckit-2` speckit/antennapod-0005/t1 | claude-sonnet-5-5 | completed, 41 turns, 703 s | 64 | 21,530 | 2,190,466 | 86,591 | 0.7808 | 0 | resolved=True; nudges 0; five-hour 0.25 → 0.3, seven-day 0.14 |
| | **`20261019-0112-dev5-speckit-2` total (6 trials, 6 resolved)** | | mean 606 s | **324** | **119,510** | **12,151,188** | **473,523** | **4.3050** | 0 | incl. one-time setup |

## 2026-10-19 — Phase 6 bring-up (s2a end-to-end on antennapod-0001, `scripts/s2a_e2e.py`)

Bring-up runs (D-051): `0224` stopped in the map setup (max_turns before the gate; fixed), `0238` stopped at the plan gate (no retry for read-only stages; fixed), `0310` ran every stage, was interrupted in implement, resumed, ACCEPT, resolved. The map setup cached for later runs is the one from `0238` (est. $0.4454).

| Time (UTC) | Run / activity | Model | Result | in | out | cr | cw | est. USD | Pauses | Note |
|---|---|---|---|---|---|---|---|---|---|---|
| 02:35 | `20261019-0224-s2a-e2e` setup s2a-map/antennapod | claude-sonnet-5-5 | max_turns, 27 turns | 46 | 24,520 | 1,193,934 | 62,895 | 0.6163 | 0 | one-time setup (reported separately); five-hour 0.38 → 0.44, seven-day 0.16 |
| 02:24 | `20261019-0224-s2a-e2e` s2a e2e antennapod-0001 | claude-sonnet-5-5 | first None, resume None, 0 turns, 0 calls | 0 | 0 | 0 | 0 | 0.0000 | 0 | resolved=None; verdict None; five-hour —, seven-day — |
| | **`20261019-0224-s2a-e2e` total (1 trials, 0 resolved)** | | mean 0 s | **46** | **24,520** | **1,193,934** | **62,895** | **0.6163** | 0 | incl. one-time setup |
| 02:55 | `20261019-0238-s2a-e2e` setup s2a-map/antennapod | claude-sonnet-5-5 | success, 22 turns | 38 | 15,195 | 877,529 | 51,414 | 0.4454 | 0 | one-time setup (reported separately); five-hour 0.46 → 0.49, seven-day 0.16 |
| 02:38 | `20261019-0238-s2a-e2e` s2a e2e antennapod-0001 | claude-sonnet-5-5 | first [3, 'gate_failed'], resume None, 29 turns, 6 calls | 44 | 13,488 | 655,015 | 127,043 | 0.7086 | 0 | resolved=False; verdict None; five-hour 0.49 → 0.53, seven-day 0.17 |
| | **`20261019-0238-s2a-e2e` total (1 trials, 0 resolved)** | | mean 0 s | **82** | **28,683** | **1,532,544** | **178,457** | **1.1541** | 0 | incl. one-time setup |
| 03:10 | `20261019-0310-s2a-e2e` s2a e2e antennapod-0001 | claude-sonnet-5-5 | first [4, 'timeout'], resume [0, 'completed'], 53 turns, 12 calls | 82 | 22,443 | 1,196,413 | 203,631 | 1.1588 | 0 | resolved=True; verdict ACCEPT; five-hour 0.66 → 0.68, seven-day 0.18 |
| | **`20261019-0310-s2a-e2e` total (1 trials, 1 resolved)** | | mean 0 s | **82** | **22,443** | **1,196,413** | **203,631** | **1.1588** | 0 | incl. one-time setup |

## 2026-10-19 — Phase 6 dev5 bring-up run (s2a, s2a-nomap, s2a-noverify)

`20261019-0337-dev5-s2a-1`: 18 trials through `scripts/run_paced.py` (one usage-limit pause, resumed after the 06:10 reset); audit PASS. **Bring-up, not a measurement (D-052):** 6 trials stopped at a faulty locate gate and every `s2a-nomap` compile gate failed on a null task name. Resolved: s2a 3/6, s2a-noverify 5/6, s2a-nomap 0/6.

| Time (UTC) | Run / activity | Model | Result | in | out | cr | cw | est. USD | Pauses | Note |
|---|---|---|---|---|---|---|---|---|---|---|
| 03:37 | `20261019-0337-dev5-s2a-1` s2a/antennapod-0000/t1 | claude-sonnet-5-5 | completed, 26 turns, 362 s | 40 | 11,904 | 497,369 | 124,980 | 0.6688 | 0 | resolved=True; nudges 0; five-hour 0.77 → 0.78, seven-day 0.19; bring-up (D-052) |
| 04:19 | `20261019-0337-dev5-s2a-1` s2a/antennapod-0001/t1 | claude-sonnet-5-5 | completed, 37 turns, 377 s | 48 | 14,833 | 696,114 | 133,546 | 0.7522 | 0 | resolved=True; nudges 0; five-hour 0.91 → 0.93, seven-day 0.21; bring-up (D-052) |
| 06:28 | `20261019-0337-dev5-s2a-1` s2a/antennapod-0002/t1 | claude-sonnet-5-5 | agent_error, 13 turns, 123 s | 18 | 6,099 | 258,302 | 49,758 | 0.2859 | 0 | resolved=False; nudges 0; five-hour 0.07 → 0.08, seven-day 0.22; bring-up (D-052) |
| 07:08 | `20261019-0337-dev5-s2a-1` s2a/antennapod-0003/t1 | claude-sonnet-5-5 | agent_error, 12 turns, 89 s | 12 | 6,499 | 186,728 | 41,843 | 0.2511 | 0 | resolved=False; nudges 0; five-hour 0.24 → 0.25, seven-day 0.23; bring-up (D-052) |
| 08:11 | `20261019-0337-dev5-s2a-1` s2a/antennapod-0004/t1 | claude-sonnet-5-5 | agent_error, 17 turns, 136 s | 22 | 8,981 | 374,000 | 75,264 | 0.4283 | 0 | resolved=False; nudges 0; five-hour 0.5 → 0.52, seven-day 0.26; bring-up (D-052) |
| 08:22 | `20261019-0337-dev5-s2a-1` s2a/antennapod-0005/t1 | claude-sonnet-5-5 | completed, 34 turns, 524 s | 48 | 27,147 | 751,015 | 170,651 | 1.0293 | 0 | resolved=True; nudges 0; five-hour 0.62 → 0.65, seven-day 0.27; bring-up (D-052) |
| 03:50 | `20261019-0337-dev5-s2a-1` s2a-nomap/antennapod-0000/t1 | claude-sonnet-5-5 | completed, 56 turns, 590 s | 84 | 18,598 | 1,026,746 | 139,052 | 0.8450 | 0 | resolved=False; nudges 0; five-hour 0.83 → 0.82, seven-day 0.2; bring-up (D-052) |
| 06:12 | `20261019-0337-dev5-s2a-1` s2a-nomap/antennapod-0001/t1 | claude-sonnet-5-5 | agent_error, 13 turns, 96 s | 16 | 4,790 | 195,802 | 42,655 | 0.2381 | 0 | resolved=False; nudges 0; five-hour 0 → 0.02, seven-day 0.21; bring-up (D-052) |
| 06:32 | `20261019-0337-dev5-s2a-1` s2a-nomap/antennapod-0002/t1 | claude-sonnet-5-5 | completed, 79 turns, 866 s | 114 | 28,606 | 1,491,212 | 191,573 | 1.2017 | 0 | resolved=False; nudges 0; five-hour 0.17 → 0.16, seven-day 0.23; bring-up (D-052) |
| 07:11 | `20261019-0337-dev5-s2a-1` s2a-nomap/antennapod-0003/t1 | claude-sonnet-5-5 | completed, 114 turns, 1269 s | 132 | 72,407 | 2,515,203 | 296,287 | 2.1610 | 0 | resolved=False; nudges 0; five-hour 0.38 → 0.34, seven-day 0.24; bring-up (D-052) |
| 08:15 | `20261019-0337-dev5-s2a-1` s2a-nomap/antennapod-0004/t1 | claude-sonnet-5-5 | agent_error, 21 turns, 143 s | 24 | 9,744 | 340,494 | 61,173 | 0.3762 | 0 | resolved=False; nudges 0; five-hour 0.53 → 0.54, seven-day 0.26; bring-up (D-052) |
| 08:39 | `20261019-0337-dev5-s2a-1` s2a-nomap/antennapod-0005/t1 | claude-sonnet-5-5 | completed, 82 turns, 897 s | 114 | 55,391 | 1,856,915 | 242,401 | 1.7094 | 0 | resolved=False; nudges 0; five-hour 0.76 → 0.74, seven-day 0.27; bring-up (D-052) |
| 04:07 | `20261019-0337-dev5-s2a-1` s2a-noverify/antennapod-0000/t1 | claude-sonnet-5-5 | completed, 23 turns, 318 s | 34 | 10,937 | 412,936 | 105,413 | 0.5724 | 0 | resolved=True; nudges 0; five-hour 0.87 → 0.86, seven-day 0.2; bring-up (D-052) |
| 06:15 | `20261019-0337-dev5-s2a-1` s2a-noverify/antennapod-0001/t1 | claude-sonnet-5-5 | completed, 31 turns, 423 s | 46 | 14,930 | 629,409 | 152,180 | 0.8211 | 0 | resolved=True; nudges 0; five-hour 0.06 → 0.05, seven-day 0.22; bring-up (D-052) |
| 06:53 | `20261019-0337-dev5-s2a-1` s2a-noverify/antennapod-0002/t1 | claude-sonnet-5-5 | completed, 38 turns, 477 s | 56 | 18,704 | 790,699 | 147,868 | 0.8577 | 0 | resolved=True; nudges 0; five-hour 0.23 → 0.22, seven-day 0.23; bring-up (D-052) |
| 07:44 | `20261019-0337-dev5-s2a-1` s2a-noverify/antennapod-0003/t1 | claude-sonnet-5-5 | completed, 62 turns, 656 s | 72 | 34,773 | 1,192,806 | 196,902 | 1.2548 | 0 | resolved=True; nudges 0; five-hour 0.46 → 0.45, seven-day 0.25; bring-up (D-052) |
| 08:19 | `20261019-0337-dev5-s2a-1` s2a-noverify/antennapod-0004/t1 | claude-sonnet-5-5 | agent_error, 15 turns, 97 s | 12 | 6,450 | 196,553 | 44,963 | 0.2640 | 0 | resolved=False; nudges 0; five-hour 0.56 → 0.58, seven-day 0.26; bring-up (D-052) |
| 09:00 | `20261019-0337-dev5-s2a-1` s2a-noverify/antennapod-0005/t1 | claude-sonnet-5-5 | completed, 31 turns, 535 s | 48 | 26,839 | 699,542 | 166,225 | 1.0033 | 0 | resolved=True; nudges 0; five-hour 0.83 → 0.81, seven-day 0.28; bring-up (D-052) |
| | **`20261019-0337-dev5-s2a-1` total (18 trials, 8 resolved)** | | mean 443 s | **940** | **377,632** | **14,111,845** | **2,382,734** | **14.7203** | 0 | incl. one-time setup; bring-up (D-052) |

## 2026-10-19 — Phase 6 gate run (s2a, s2a-nomap, s2a-noverify on dev5)

`20261019-1112-dev5-s2a-2` (s2a `ed8f6f9`, D-052 fixes), 18 trials through `scripts/run_paced.py`; one usage-limit pause (s2a-noverify/antennapod-0003 attempt 1 kept under `usage_limited/`), resumed after the 16:10 reset; audit PASS. Resolved: **s2a 6/6, s2a-nomap 5/6, s2a-noverify 4/6**. The three failures are s2a stopping on its own gates (exit 3): nomap/0004 plan named new files without `(new)` after its retry; noverify/0002 locate read a host name as a path and noverify/0003 locate's retry was misreported (both parser/reporting bugs, fixed after the run, D-053). The map setup is reused (produced at est. $0.4454 in `20261019-0238-s2a-e2e`). Bring-up results (one trial per task), not the tuned framework.

| Time (UTC) | Run / activity | Model | Result | in | out | cr | cw | est. USD | Pauses | Note |
|---|---|---|---|---|---|---|---|---|---|---|
| 11:12 | `20261019-1112-dev5-s2a-2` s2a/antennapod-0000/t1 | claude-sonnet-5-5 | completed, 27 turns, 404 s | 40 | 11,336 | 461,333 | 150,685 | 0.7623 | 0 | resolved=True; nudges 0; five-hour 0.04 → 0.05, seven-day 0.3 |
| 11:53 | `20261019-1112-dev5-s2a-2` s2a/antennapod-0001/t1 | claude-sonnet-5-5 | completed, 42 turns, 461 s | 60 | 15,798 | 843,590 | 156,643 | 0.8690 | 0 | resolved=True; nudges 0; five-hour 0.18 → 0.18, seven-day 0.31 |
| 12:42 | `20261019-1112-dev5-s2a-2` s2a/antennapod-0002/t1 | claude-sonnet-5-5 | completed, 37 turns, 456 s | 58 | 14,191 | 816,545 | 136,506 | 0.7697 | 0 | resolved=True; nudges 0; five-hour 0.42 → 0.43, seven-day 0.33 |
| 13:19 | `20261019-1112-dev5-s2a-2` s2a/antennapod-0003/t1 | claude-sonnet-5-5 | timeout, 93 turns, 1118 s | 120 | 48,836 | 2,052,602 | 340,478 | 2.0558 | 0 | resolved=True; nudges 0; five-hour 0.73 → 0.73, seven-day 0.35 |
| 16:16 | `20261019-1112-dev5-s2a-2` s2a/antennapod-0004/t1 | claude-sonnet-5-5 | completed, 61 turns, 957 s | 88 | 36,386 | 1,417,566 | 271,270 | 1.5909 | 0 | resolved=True; nudges 0; five-hour 0.23 → 0.29, seven-day 0.39 |
| 17:29 | `20261019-1112-dev5-s2a-2` s2a/antennapod-0005/t1 | claude-sonnet-5-5 | completed, 34 turns, 542 s | 54 | 26,139 | 806,721 | 167,767 | 1.0132 | 0 | resolved=True; nudges 0; five-hour 0.6 → 0.64, seven-day 0.41 |
| 11:26 | `20261019-1112-dev5-s2a-2` s2a-nomap/antennapod-0000/t1 | claude-sonnet-5-5 | completed, 35 turns, 399 s | 50 | 12,868 | 593,147 | 97,937 | 0.5798 | 0 | resolved=True; nudges 0; five-hour 0.08 → 0.09, seven-day 0.31 |
| 12:09 | `20261019-1112-dev5-s2a-2` s2a-nomap/antennapod-0001/t1 | claude-sonnet-5-5 | completed, 46 turns, 551 s | 64 | 19,060 | 829,434 | 148,413 | 0.8673 | 0 | resolved=True; nudges 0; five-hour 0.27 → 0.27, seven-day 0.32 |
| 12:57 | `20261019-1112-dev5-s2a-2` s2a-nomap/antennapod-0002/t1 | claude-sonnet-5-5 | completed, 45 turns, 657 s | 70 | 18,106 | 902,065 | 138,739 | 0.8264 | 0 | resolved=True; nudges 0; five-hour 0.5 → 0.51, seven-day 0.33 |
| 14:06 | `20261019-1112-dev5-s2a-2` s2a-nomap/antennapod-0003/t1 | claude-sonnet-5-5 | completed, 60 turns, 753 s | 70 | 35,678 | 1,001,535 | 201,044 | 1.2612 | 0 | resolved=True; nudges 0; five-hour 0.91 → 0.96, seven-day 0.37 |
| 16:46 | `20261019-1112-dev5-s2a-2` s2a-nomap/antennapod-0004/t1 | claude-sonnet-5-5 | agent_error, 21 turns, 334 s | 36 | 19,422 | 473,109 | 114,854 | 0.7010 | 0 | resolved=False; nudges 0; five-hour 0.3 → 0.35, seven-day 0.39 |
| 17:48 | `20261019-1112-dev5-s2a-2` s2a-nomap/antennapod-0005/t1 | claude-sonnet-5-5 | completed, 38 turns, 702 s | 58 | 23,823 | 845,839 | 135,148 | 0.8635 | 0 | resolved=True; nudges 0; five-hour 0.7 → 0.72, seven-day 0.42 |
| 11:40 | `20261019-1112-dev5-s2a-2` s2a-noverify/antennapod-0000/t1 | claude-sonnet-5-5 | completed, 23 turns, 343 s | 36 | 10,547 | 445,576 | 105,538 | 0.5723 | 0 | resolved=True; nudges 0; five-hour 0.12 → 0.11, seven-day 0.31 |
| 12:28 | `20261019-1112-dev5-s2a-2` s2a-noverify/antennapod-0001/t1 | claude-sonnet-5-5 | completed, 37 turns, 408 s | 50 | 17,102 | 714,458 | 131,825 | 0.7699 | 0 | resolved=True; nudges 0; five-hour 0.35 → 0.33, seven-day 0.32 |
| 13:16 | `20261019-1112-dev5-s2a-2` s2a-noverify/antennapod-0002/t1 | claude-sonnet-5-5 | agent_error, 14 turns, 123 s | 22 | 6,272 | 341,585 | 54,241 | 0.3139 | 0 | resolved=False; nudges 0; five-hour 0.52 → 0.54, seven-day 0.33 |
| 16:12 | `20261019-1112-dev5-s2a-2` s2a-noverify/antennapod-0003/t1 | claude-sonnet-5-5 | agent_error, 18 turns, 137 s | 22 | 11,149 | 374,409 | 96,144 | 0.5336 | 0 | resolved=False; nudges 0; five-hour 0 → 0.03, seven-day 0.37 |
| 16:56 | `20261019-1112-dev5-s2a-2` s2a-noverify/antennapod-0004/t1 | claude-sonnet-5-5 | completed, 72 turns, 985 s | 102 | 39,612 | 1,625,851 | 279,731 | 1.6778 | 0 | resolved=True; nudges 0; five-hour 0.48 → 0.45, seven-day 0.4 |
| 18:09 | `20261019-1112-dev5-s2a-2` s2a-noverify/antennapod-0005/t1 | claude-sonnet-5-5 | completed, 35 turns, 480 s | 56 | 24,688 | 909,597 | 158,006 | 0.9700 | 0 | resolved=True; nudges 0; five-hour 0.78 → 0.77, seven-day 0.42 |
| | **`20261019-1112-dev5-s2a-2` total (18 trials, 15 resolved)** | | mean 545 s | **1,056** | **391,013** | **15,454,962** | **2,884,969** | **16.9976** | 0 | incl. one-time setup |

Stage costs (mean per trial; turns · est. USD; `fix` includes trials where it did not run):

| arm | intake | locate | reproduce | spec | plan | implement | verify | fix | report | total |
|---|---|---|---|---|---|---|---|---|---|---|
| s2a (mean of 6) | 1.0 t · $0.058 | 8.8 t · $0.156 | 10.0 t · $0.208 | 1.0 t · $0.074 | 2.0 t · $0.146 | 17.8 t · $0.304 | 6.0 t · $0.162 | 1.5 t · $0.029 | 0.8 t · $0.040 | 49.0 t · $1.177 |
| s2a-nomap (mean of 6) | 1.0 t · $0.048 | 9.5 t · $0.143 | 11.5 t · $0.197 | 1.3 t · $0.068 | 3.0 t · $0.118 | 9.5 t · $0.134 | 3.5 t · $0.090 | 0.7 t · $0.010 | 0.8 t · $0.041 | 40.8 t · $0.850 |
| s2a-noverify (mean of 6) | 1.0 t · $0.058 | 11.7 t · $0.245 | 8.5 t · $0.174 | 0.7 t · $0.048 | 1.5 t · $0.085 | 9.2 t · $0.162 | — | — | 0.7 t · $0.033 | 33.2 t · $0.806 |

## 2026-10-19/20 — Phase 8 (runner: parallel slots, budget stop, resume, pause before the limit)

- `20261019-2337-p8-smoke`: one plain trial through the new scheduler (slot 1, audit in the loop OK).
- `20261019-2341-p8-budget-test`: `--max-usd 0.50` on plain/dev5; antennapod-0003 crossed the cap ($0.36 -> $0.79) and nothing more was launched: `aborted_reason: budget`.
- `abb sandbox setup --slots 2` (owner's UAC, 2026-10-20 00:30 UTC): `abb-agent2` created; `abb sandbox check --no-smoke` 63 OK, 0 FAIL (every boundary row repeated for slot 2).
- `20261020-0036-p8-resume-test`: plain + s2a, dev5 x 2, `--parallel 2`. With both slots live, each slot user was denied read and create on the other slot's trial (`cross_slot_check.json`). Killed (`taskkill /T /F` on the harness) at 00:50:35 after 3 trials were complete; no agent process survived. `--resume` swept the two stale workspaces (0 leftovers), skipped exactly the 3 complete trials and re-ran the interrupted s2a/antennapod-0001 from scratch. At 01:58 a trial reported five-hour utilisation 0.91: the scheduler stopped launching (running trials finished), waited for the 04:30 reset, probed (ok) at 04:32 and resumed: **no usage-limited attempt**. Finished 05:49; audit PASS (in the loop). plain 12/12, s2a 10/12 resolved. Peak Job Object memory per trial 5,846 MB (slot 1) / 3,795 MB (slot 2) against the 10,240 MB limit; no memory-limit kill. Active time ~2.4 h for 21 trials on 2 slots.

| Time (UTC) | Run / activity | Model | Result | in | out | cr | cw | est. USD | Pauses | Note |
|---|---|---|---|---|---|---|---|---|---|---|
| 23:37 | `20261019-2337-p8-smoke` plain/antennapod-0000/t1 | claude-sonnet-5-5 | completed, 8 turns, 124 s | 12 | 1,477 | 123,831 | 27,410 | 0.1368 | 0 | resolved=True; nudges 0; five-hour 0.13 → 0.14, seven-day 0.47 |
| | **`20261019-2337-p8-smoke` total (1 trials, 1 resolved)** | | mean 124 s | **12** | **1,477** | **123,831** | **27,410** | **0.1368** | 0 | incl. one-time setup |
| 23:41 | `20261019-2341-p8-budget-test` plain/antennapod-0000/t1 | claude-sonnet-5-5 | completed, 8 turns, 141 s | 12 | 1,441 | 139,320 | 11,541 | 0.0745 | 0 | resolved=True; nudges 0; five-hour 0.14 → 0.15, seven-day 0.47 |
| 23:44 | `20261019-2341-p8-budget-test` plain/antennapod-0001/t1 | claude-sonnet-5-5 | completed, 17 turns, 169 s | 26 | 3,266 | 359,210 | 17,157 | 0.1373 | 0 | resolved=True; nudges 0; five-hour 0.15 → 0.16, seven-day 0.47 |
| 23:48 | `20261019-2341-p8-budget-test` plain/antennapod-0002/t1 | claude-sonnet-5-5 | completed, 10 turns, 203 s | 16 | 2,355 | 204,038 | 26,262 | 0.1490 | 0 | resolved=True; nudges 0; five-hour 0.16 → 0.17, seven-day 0.47 |
| 23:53 | `20261019-2341-p8-budget-test` plain/antennapod-0003/t1 | claude-sonnet-5-5 | completed, 30 turns, 396 s | 30 | 14,351 | 743,093 | 54,009 | 0.4339 | 0 | resolved=True; nudges 0; five-hour 0.17 → 0.2, seven-day 0.47 |
| | **`20261019-2341-p8-budget-test` total (4 trials, 4 resolved)** | | mean 227 s | **84** | **21,413** | **1,445,661** | **108,969** | **0.7947** | 0 | incl. one-time setup |
| 00:36 | `20261020-0036-p8-resume-test` plain/antennapod-0000/t1 | claude-sonnet-5-5 | completed, 7 turns, 131 s | 8 | 1,217 | 88,187 | 15,757 | 0.0840 | 0 | resolved=True; nudges 0; five-hour 0.29 → 0.31, seven-day 0.49 |
| 01:44 | `20261020-0036-p8-resume-test` plain/antennapod-0000/t2 | claude-sonnet-5-5 | completed, 7 turns, 114 s | 10 | 1,207 | 114,334 | 11,019 | 0.0676 | 0 | resolved=True; nudges 0; five-hour 0.82 → 0.84, seven-day 0.53 |
| 00:40 | `20261020-0036-p8-resume-test` plain/antennapod-0001/t1 | claude-sonnet-5-5 | completed, 16 turns, 152 s | 18 | 3,071 | 239,143 | 17,979 | 0.1266 | 0 | resolved=True; nudges 0; five-hour 0.31 → 0.35, seven-day 0.49 |
| 01:55 | `20261020-0036-p8-resume-test` plain/antennapod-0001/t2 | claude-sonnet-5-5 | completed, 15 turns, 133 s | 18 | 2,834 | 242,582 | 17,994 | 0.1246 | 0 | resolved=True; nudges 0; five-hour 0.9 → 0.91, seven-day 0.54 |
| 00:52 | `20261020-0036-p8-resume-test` plain/antennapod-0002/t1 | claude-sonnet-5-5 | completed, 8 turns, 184 s | 12 | 1,807 | 148,106 | 25,638 | 0.1355 | 0 | resolved=True; nudges 0; five-hour 0.43 → 0.46, seven-day 0.5 |
| 04:32 | `20261020-0036-p8-resume-test` plain/antennapod-0002/t2 | claude-sonnet-5-5 | completed, 10 turns, 125 s | 16 | 2,048 | 189,854 | 34,033 | 0.1756 | 0 | resolved=True; nudges 0; five-hour 0 → 0.04, seven-day 0.54 |
| 01:08 | `20261020-0036-p8-resume-test` plain/antennapod-0003/t1 | claude-sonnet-5-5 | completed, 17 turns, 296 s | 24 | 10,827 | 488,251 | 44,886 | 0.3367 | 0 | resolved=True; nudges 0; five-hour 0.55 → 0.59, seven-day 0.51 |
| 04:50 | `20261020-0036-p8-resume-test` plain/antennapod-0003/t2 | claude-sonnet-5-5 | completed, 26 turns, 370 s | 30 | 13,775 | 640,017 | 42,232 | 0.3707 | 0 | resolved=True; nudges 0; five-hour 0.2 → 0.25, seven-day 0.56 |
| 01:14 | `20261020-0036-p8-resume-test` plain/antennapod-0004/t1 | claude-sonnet-5-5 | completed, 13 turns, 177 s | 20 | 6,635 | 308,412 | 25,004 | 0.1972 | 0 | resolved=True; nudges 0; five-hour 0.61 → 0.63, seven-day 0.52 |
| 04:58 | `20261020-0036-p8-resume-test` plain/antennapod-0004/t2 | claude-sonnet-5-5 | completed, 16 turns, 199 s | 22 | 7,701 | 370,159 | 27,494 | 0.2240 | 0 | resolved=True; nudges 0; five-hour 0.27 → 0.3, seven-day 0.56 |
| 01:22 | `20261020-0036-p8-resume-test` plain/antennapod-0005/t1 | claude-sonnet-5-5 | completed, 11 turns, 157 s | 16 | 6,558 | 229,622 | 22,839 | 0.1799 | 0 | resolved=True; nudges 0; five-hour 0.69 → 0.7, seven-day 0.52 |
| 05:29 | `20261020-0036-p8-resume-test` plain/antennapod-0005/t2 | claude-sonnet-5-5 | completed, 15 turns, 146 s | 20 | 5,331 | 287,536 | 21,313 | 0.1674 | 0 | resolved=True; nudges 0; five-hour 0.51 → 0.53, seven-day 0.58 |
| 00:37 | `20261020-0036-p8-resume-test` s2a/antennapod-0000/t1 | claude-sonnet-5-5 | completed, 28 turns, 370 s | 42 | 12,922 | 519,375 | 146,404 | 0.7669 | 0 | resolved=True; nudges 0; five-hour 0.35 → 0.39, seven-day 0.5 |
| 01:47 | `20261020-0036-p8-resume-test` s2a/antennapod-0000/t2 | claude-sonnet-5-5 | completed, 30 turns, 289 s | 42 | 12,418 | 527,873 | 124,580 | 0.6754 | 0 | resolved=True; nudges 0; five-hour 0.89 → 0.91, seven-day 0.54 |
| 00:52 | `20261020-0036-p8-resume-test` s2a/antennapod-0001/t1 | claude-sonnet-5-5 | completed, 43 turns, 442 s | 60 | 18,074 | 906,771 | 144,476 | 0.8494 | 0 | resolved=True; nudges 0; five-hour 0.51 → 0.55, seven-day 0.51 |
| 04:32 | `20261020-0036-p8-resume-test` s2a/antennapod-0001/t2 | claude-sonnet-5-5 | completed, 144 turns, 1264 s | 244 | 48,805 | 4,608,737 | 321,763 | 2.2365 | 0 | resolved=False; nudges 0; five-hour 0.23 → 0.19, seven-day 0.56 |
| 00:57 | `20261020-0036-p8-resume-test` s2a/antennapod-0002/t1 | claude-sonnet-5-5 | completed, 41 turns, 381 s | 58 | 17,965 | 825,829 | 145,382 | 0.8439 | 0 | resolved=True; nudges 0; five-hour 0.53 → 0.58, seven-day 0.51 |
| 04:36 | `20261020-0036-p8-resume-test` s2a/antennapod-0002/t2 | claude-sonnet-5-5 | completed, 40 turns, 439 s | 62 | 18,018 | 891,684 | 145,369 | 0.8509 | 0 | resolved=True; nudges 0; five-hour 0.15 → 0.19, seven-day 0.56 |
| 01:13 | `20261020-0036-p8-resume-test` s2a/antennapod-0003/t1 | claude-sonnet-5-5 | completed, 107 turns, 951 s | 126 | 49,671 | 2,152,452 | 332,003 | 2.0402 | 0 | resolved=True; nudges 2; five-hour 0.84 → 0.84, seven-day 0.53 |
| 04:57 | `20261020-0036-p8-resume-test` s2a/antennapod-0003/t2 | claude-sonnet-5-5 | completed, 102 turns, 884 s | 116 | 56,097 | 2,136,216 | 299,917 | 1.9745 | 0 | resolved=True; nudges 0; five-hour 0.35 → 0.53, seven-day 0.58 |
| 01:19 | `20261020-0036-p8-resume-test` s2a/antennapod-0004/t1 | claude-sonnet-5-5 | agent_error, 20 turns, 74 s | 18 | 9,807 | 279,038 | 70,920 | 0.4097 | 0 | resolved=False; nudges 0; five-hour 0.65 → 0.66, seven-day 0.52 |
| 05:04 | `20261020-0036-p8-resume-test` s2a/antennapod-0004/t2 | claude-sonnet-5-5 | completed, 75 turns, 722 s | 102 | 41,750 | 2,169,935 | 266,857 | 1.7021 | 0 | resolved=True; nudges 0; five-hour 0.41 → 0.51, seven-day 0.58 |
| 01:27 | `20261020-0036-p8-resume-test` s2a/antennapod-0005/t1 | claude-sonnet-5-5 | completed, 37 turns, 370 s | 52 | 23,300 | 811,854 | 176,613 | 1.0207 | 0 | resolved=True; nudges 0; five-hour 0.77 → 0.82, seven-day 0.53 |
| 05:33 | `20261020-0036-p8-resume-test` s2a/antennapod-0005/t2 | claude-sonnet-5-5 | completed, 43 turns, 579 s | 66 | 34,788 | 1,106,556 | 186,424 | 1.2044 | 0 | resolved=True; nudges 0; five-hour 0.6 → 0.62, seven-day 0.59 |
| | **`20261020-0036-p8-resume-test` total (24 trials, 22 resolved)** | | mean 373 s | **1,202** | **406,626** | **20,282,523** | **2,666,896** | **16.7645** | 0 | incl. one-time setup |

## 2026-10-20/21 — dev-set baseline (5 arms × 10 dev tasks × 2, Sonnet 5.5, `ABB_TUNING=1`)

`20261020-2049-dev-baseline-1`: 100 trials on 2 slots, 20 h 23 min wall clock incl. four pre-emptive pauses at five-hour utilisation 0.90-0.92 (each resumed after the reset and a good probe) and one usage-limited attempt (s2a/wikipedia-0009/t2, kept and re-run); first Wikipedia setups (Spec Kit constitution, s2a map) built here; audit PASS. After the wikipedia-0007 task fix (tasks/CHANGELOG.md, 2026-10-21) its 10 trials were re-graded (`scripts/regrade.py`, 9 flipped to resolved). **pass@1: plain 0.90, plain-guided 0.90, plain-gate 0.90, speckit 0.90, s2a 0.75.** Every arm fails wikipedia-0006 (hard, valid); s2a also loses antennapod-0003/t1 (verifier accepted), antennapod-0004/t1 (locate gate) and wikipedia-0007/t2. Peak Job Object memory 9,651 MB (s2a on Wikipedia; limit 10,240). Plan: Pro until 2026-10-21, then Max (`abb auth set-plan`).

Verifier calibration `20261021-1722-verify-calibration` (6 re-verifications, est. $0.93): 4/6 before, 5/6 after tuning 1 (s2a/CHANGELOG.md).

| Time (UTC) | Run / activity | Model | Result | in | out | cr | cw | est. USD | Pauses | Note |
|---|---|---|---|---|---|---|---|---|---|---|
| 02:41 | `20261020-2049-dev-baseline-1` setup s2a-map/wikipedia | claude-sonnet-5-5 | success, 16 turns | 26 | 13,071 | 469,132 | 36,241 | 0.3226 | 0 | one-time setup (reported separately); five-hour 0.23 → 0.27, seven-day 0.75 |
| 02:24 | `20261020-2049-dev-baseline-1` setup speckit-constitution/wikipedia | claude-sonnet-5-5 | success, 5 turns | 8 | 2,841 | 103,883 | 17,097 | 0.1072 | 0 | one-time setup (reported separately); five-hour 0.2 → 0.21, seven-day 0.74 |
| 20:50 | `20261020-2049-dev-baseline-1` plain/antennapod-0000/t1 | claude-sonnet-5-5 | completed, 11 turns, 160 s | 20 | 1,646 | 232,921 | 29,761 | 0.1588 | 0 | resolved=True; nudges 0; five-hour 0.15 → 0.18, seven-day 0.66 |
| 04:55 | `20261020-2049-dev-baseline-1` plain/antennapod-0000/t2 | claude-sonnet-5-5 | completed, 15 turns, 136 s | 20 | 2,214 | 249,872 | 19,452 | 0.1250 | 0 | resolved=True; nudges 0; five-hour 0.81 → 0.83, seven-day 0.79 |
| 21:00 | `20261020-2049-dev-baseline-1` plain/antennapod-0001/t1 | claude-sonnet-5-5 | completed, 13 turns, 140 s | 18 | 2,728 | 238,807 | 23,021 | 0.1433 | 0 | resolved=True; nudges 0; five-hour 0.23 → 0.25, seven-day 0.66 |
| 06:42 | `20261020-2049-dev-baseline-1` plain/antennapod-0001/t2 | claude-sonnet-5-5 | completed, 15 turns, 159 s | 22 | 3,298 | 287,718 | 33,420 | 0.1955 | 0 | resolved=True; nudges 0; five-hour 0 → 0.04, seven-day 0.8 |
| 21:16 | `20261020-2049-dev-baseline-1` plain/antennapod-0002/t1 | claude-sonnet-5-5 | completed, 10 turns, 123 s | 16 | 2,158 | 207,031 | 18,616 | 0.1168 | 0 | resolved=True; nudges 0; five-hour 0.34 → 0.36, seven-day 0.67 |
| 06:59 | `20261020-2049-dev-baseline-1` plain/antennapod-0002/t2 | claude-sonnet-5-5 | completed, 8 turns, 172 s | 12 | 1,754 | 147,551 | 25,834 | 0.1357 | 0 | resolved=True; nudges 0; five-hour 0.14 → 0.15, seven-day 0.81 |
| 21:36 | `20261020-2049-dev-baseline-1` plain/antennapod-0003/t1 | claude-sonnet-5-5 | completed, 35 turns, 306 s | 30 | 15,819 | 721,884 | 52,646 | 0.4410 | 0 | resolved=True; nudges 0; five-hour 0.46 → 0.5, seven-day 0.68 |
| 07:14 | `20261020-2049-dev-baseline-1` plain/antennapod-0003/t2 | claude-sonnet-5-5 | completed, 39 turns, 368 s | 30 | 14,951 | 734,124 | 53,721 | 0.4379 | 0 | resolved=True; nudges 0; five-hour 0.23 → 0.29, seven-day 0.82 |
| 22:13 | `20261020-2049-dev-baseline-1` plain/antennapod-0004/t1 | claude-sonnet-5-5 | completed, 20 turns, 310 s | 30 | 7,885 | 530,787 | 27,104 | 0.2404 | 0 | resolved=True; nudges 0; five-hour 0.8 → 0.84, seven-day 0.71 |
| 07:53 | `20261020-2049-dev-baseline-1` plain/antennapod-0004/t2 | claude-sonnet-5-5 | completed, 8 turns, 188 s | 16 | 5,948 | 242,456 | 25,202 | 0.1846 | 0 | resolved=True; nudges 0; five-hour 0.57 → 0.59, seven-day 0.85 |
| 01:42 | `20261020-2049-dev-baseline-1` plain/antennapod-0005/t1 | claude-sonnet-5-5 | completed, 13 turns, 145 s | 14 | 5,289 | 177,712 | 37,393 | 0.2203 | 0 | resolved=True; nudges 0; five-hour 0 → 0.03, seven-day 0.73 |
| 08:36 | `20261020-2049-dev-baseline-1` plain/antennapod-0005/t2 | claude-sonnet-5-5 | completed, 11 turns, 174 s | 20 | 5,657 | 291,865 | 23,429 | 0.1795 | 0 | resolved=True; nudges 0; five-hour 0.88 → 0.9, seven-day 0.87 |
| 02:00 | `20261020-2049-dev-baseline-1` plain/wikipedia-0002/t1 | claude-sonnet-5-5 | completed, 10 turns, 334 s | 18 | 3,899 | 249,728 | 19,449 | 0.1418 | 0 | resolved=True; nudges 0; five-hour 0.15 → 0.16, seven-day 0.74 |
| 11:54 | `20261020-2049-dev-baseline-1` plain/wikipedia-0002/t2 | claude-sonnet-5-5 | completed, 11 turns, 356 s | 16 | 4,450 | 220,289 | 18,633 | 0.1411 | 0 | resolved=True; nudges 0; five-hour 0.12 → 0.14, seven-day 0.89 |
| 02:39 | `20261020-2049-dev-baseline-1` plain/wikipedia-0006/t1 | claude-sonnet-5-5 | completed, 12 turns, 333 s | 14 | 4,361 | 198,831 | 24,212 | 0.1604 | 0 | resolved=False; nudges 0; five-hour 0.25 → 0.29, seven-day 0.75 |
| 12:31 | `20261020-2049-dev-baseline-1` plain/wikipedia-0006/t2 | claude-sonnet-5-5 | completed, 13 turns, 334 s | 16 | 4,406 | 227,950 | 21,423 | 0.1526 | 0 | resolved=False; nudges 0; five-hour 0.25 → 0.31, seven-day 0.9 |
| 03:32 | `20261020-2049-dev-baseline-1` plain/wikipedia-0007/t1 | claude-sonnet-5-5 | completed, 13 turns, 321 s | 16 | 2,934 | 224,915 | 18,958 | 0.1277 | 0 | resolved=True; nudges 0; five-hour 0.51 → 0.54, seven-day 0.77 |
| 13:15 | `20261020-2049-dev-baseline-1` plain/wikipedia-0007/t2 | claude-sonnet-5-5 | completed, 17 turns, 353 s | 24 | 3,940 | 374,110 | 24,170 | 0.1735 | 0 | resolved=True; nudges 0; five-hour 0.56 → 0.62, seven-day 0.92 |
| 04:12 | `20261020-2049-dev-baseline-1` plain/wikipedia-0009/t1 | claude-sonnet-5-5 | completed, 13 turns, 398 s | 16 | 5,907 | 258,615 | 25,847 | 0.1884 | 0 | resolved=True; nudges 0; five-hour 0.65 → 0.68, seven-day 0.78 |
| 13:54 | `20261020-2049-dev-baseline-1` plain/wikipedia-0009/t2 | claude-sonnet-5-5 | completed, 12 turns, 398 s | 14 | 7,193 | 229,620 | 26,105 | 0.1993 | 0 | resolved=True; nudges 0; five-hour 0.73 → 0.77, seven-day 0.92 |
| 20:54 | `20261020-2049-dev-baseline-1` plain-gate/antennapod-0000/t1 | claude-sonnet-5-5 | completed, 8 turns, 137 s | 12 | 1,446 | 139,394 | 11,332 | 0.0738 | 0 | resolved=True; nudges 0; five-hour 0.18 → 0.2, seven-day 0.66 |
| 05:02 | `20261020-2049-dev-baseline-1` plain-gate/antennapod-0000/t2 | claude-sonnet-5-5 | completed, 8 turns, 113 s | 12 | 1,422 | 139,514 | 16,458 | 0.0940 | 0 | resolved=True; nudges 0; five-hour 0.85 → 0.87, seven-day 0.8 |
| 21:07 | `20261020-2049-dev-baseline-1` plain-gate/antennapod-0001/t1 | claude-sonnet-5-5 | completed, 14 turns, 135 s | 20 | 2,695 | 270,359 | 22,718 | 0.1449 | 0 | resolved=True; nudges 0; five-hour 0.27 → 0.29, seven-day 0.67 |
| 06:50 | `20261020-2049-dev-baseline-1` plain-gate/antennapod-0001/t2 | claude-sonnet-5-5 | completed, 17 turns, 161 s | 24 | 3,138 | 344,258 | 22,027 | 0.1540 | 0 | resolved=True; nudges 0; five-hour 0.07 → 0.08, seven-day 0.81 |
| 21:24 | `20261020-2049-dev-baseline-1` plain-gate/antennapod-0002/t1 | claude-sonnet-5-5 | completed, 9 turns, 169 s | 14 | 1,997 | 176,512 | 26,361 | 0.1431 | 0 | resolved=True; nudges 0; five-hour 0.39 → 0.39, seven-day 0.67 |
| 07:06 | `20261020-2049-dev-baseline-1` plain-gate/antennapod-0002/t2 | claude-sonnet-5-5 | completed, 9 turns, 175 s | 14 | 2,078 | 175,221 | 25,814 | 0.1416 | 0 | resolved=True; nudges 0; five-hour 0.18 → 0.2, seven-day 0.82 |
| 21:43 | `20261020-2049-dev-baseline-1` plain-gate/antennapod-0003/t1 | claude-sonnet-5-5 | completed, 36 turns, 391 s | 30 | 13,569 | 681,556 | 46,907 | 0.3915 | 0 | resolved=True; nudges 0; five-hour 0.52 → 0.57, seven-day 0.69 |
| 07:27 | `20261020-2049-dev-baseline-1` plain-gate/antennapod-0003/t2 | claude-sonnet-5-5 | completed, 36 turns, 379 s | 26 | 16,987 | 600,133 | 55,171 | 0.4506 | 0 | resolved=True; nudges 0; five-hour 0.33 → 0.43, seven-day 0.84 |
| 22:31 | `20261020-2049-dev-baseline-1` plain-gate/antennapod-0004/t1 | claude-sonnet-5-5 | completed, 20 turns, 189 s | 18 | 7,719 | 291,878 | 29,120 | 0.2229 | 0 | resolved=True; nudges 0; five-hour 0.89 → 0.92, seven-day 0.72 |
| 08:04 | `20261020-2049-dev-baseline-1` plain-gate/antennapod-0004/t2 | claude-sonnet-5-5 | completed, 13 turns, 257 s | 22 | 7,508 | 370,619 | 29,823 | 0.2315 | 0 | resolved=True; nudges 0; five-hour 0.61 → 0.64, seven-day 0.85 |
| 01:46 | `20261020-2049-dev-baseline-1` plain-gate/antennapod-0005/t1 | claude-sonnet-5-5 | completed, 11 turns, 196 s | 18 | 5,393 | 251,439 | 19,501 | 0.1571 | 0 | resolved=True; nudges 0; five-hour 0.03 → 0.06, seven-day 0.73 |
| 11:42 | `20261020-2049-dev-baseline-1` plain-gate/antennapod-0005/t2 | claude-sonnet-5-5 | completed, 9 turns, 195 s | 12 | 5,916 | 137,326 | 35,267 | 0.2140 | 0 | resolved=True; nudges 0; five-hour 0 → 0.05, seven-day 0.88 |
| 02:11 | `20261020-2049-dev-baseline-1` plain-gate/wikipedia-0002/t1 | claude-sonnet-5-5 | completed, 14 turns, 362 s | 20 | 4,579 | 288,565 | 21,110 | 0.1591 | 0 | resolved=True; nudges 0; five-hour 0.19 → 0.2, seven-day 0.74 |
| 12:06 | `20261020-2049-dev-baseline-1` plain-gate/wikipedia-0002/t2 | claude-sonnet-5-5 | completed, 12 turns, 362 s | 20 | 4,408 | 287,820 | 19,700 | 0.1517 | 0 | resolved=True; nudges 0; five-hour 0.17 → 0.18, seven-day 0.89 |
| 03:02 | `20261020-2049-dev-baseline-1` plain-gate/wikipedia-0006/t1 | claude-sonnet-5-5 | completed, 12 turns, 326 s | 12 | 4,280 | 168,654 | 23,081 | 0.1520 | 0 | resolved=False; nudges 0; five-hour 0.34 → 0.37, seven-day 0.75 |
| 12:54 | `20261020-2049-dev-baseline-1` plain-gate/wikipedia-0006/t2 | claude-sonnet-5-5 | completed, 12 turns, 349 s | 14 | 4,524 | 197,632 | 20,829 | 0.1483 | 0 | resolved=False; nudges 0; five-hour 0.37 → 0.47, seven-day 0.91 |
| 03:54 | `20261020-2049-dev-baseline-1` plain-gate/wikipedia-0007/t1 | claude-sonnet-5-5 | completed, 22 turns, 386 s | 24 | 5,619 | 476,371 | 38,516 | 0.2579 | 0 | resolved=True; nudges 0; five-hour 0.6 → 0.64, seven-day 0.78 |
| 13:27 | `20261020-2049-dev-baseline-1` plain-gate/wikipedia-0007/t2 | claude-sonnet-5-5 | completed, 13 turns, 368 s | 16 | 3,118 | 237,385 | 22,905 | 0.1466 | 0 | resolved=True; nudges 0; five-hour 0.64 → 0.65, seven-day 0.92 |
| 04:37 | `20261020-2049-dev-baseline-1` plain-gate/wikipedia-0009/t1 | claude-sonnet-5-5 | completed, 10 turns, 318 s | 12 | 5,754 | 187,290 | 24,501 | 0.1743 | 0 | resolved=True; nudges 0; five-hour 0.73 → 0.78, seven-day 0.79 |
| 14:16 | `20261020-2049-dev-baseline-1` plain-gate/wikipedia-0009/t2 | claude-sonnet-5-5 | completed, 13 turns, 413 s | 18 | 6,693 | 313,110 | 28,990 | 0.2142 | 0 | resolved=True; nudges 0; five-hour 0.82 → 0.84, seven-day 0.93 |
| 20:50 | `20261020-2049-dev-baseline-1` plain-guided/antennapod-0000/t1 | claude-sonnet-5-5 | completed, 11 turns, 161 s | 16 | 1,970 | 198,452 | 18,552 | 0.1138 | 0 | resolved=True; nudges 0; five-hour 0.16 → 0.18, seven-day 0.66 |
| 04:59 | `20261020-2049-dev-baseline-1` plain-guided/antennapod-0000/t2 | claude-sonnet-5-5 | completed, 13 turns, 135 s | 18 | 2,116 | 226,681 | 19,545 | 0.1220 | 0 | resolved=True; nudges 0; five-hour 0.83 → 0.85, seven-day 0.79 |
| 21:04 | `20261020-2049-dev-baseline-1` plain-guided/antennapod-0001/t1 | claude-sonnet-5-5 | completed, 15 turns, 141 s | 18 | 2,943 | 247,845 | 18,777 | 0.1294 | 0 | resolved=True; nudges 0; five-hour 0.26 → 0.27, seven-day 0.67 |
| 06:46 | `20261020-2049-dev-baseline-1` plain-guided/antennapod-0001/t2 | claude-sonnet-5-5 | completed, 16 turns, 188 s | 24 | 3,520 | 353,791 | 19,480 | 0.1485 | 0 | resolved=True; nudges 0; five-hour 0.04 → 0.07, seven-day 0.81 |
| 21:19 | `20261020-2049-dev-baseline-1` plain-guided/antennapod-0002/t1 | claude-sonnet-5-5 | completed, 9 turns, 177 s | 14 | 2,030 | 182,903 | 27,812 | 0.1499 | 0 | resolved=True; nudges 0; five-hour 0.37 → 0.38, seven-day 0.67 |
| 07:03 | `20261020-2049-dev-baseline-1` plain-guided/antennapod-0002/t2 | claude-sonnet-5-5 | completed, 10 turns, 187 s | 16 | 2,376 | 213,838 | 28,585 | 0.1595 | 0 | resolved=True; nudges 0; five-hour 0.16 → 0.17, seven-day 0.82 |
| 21:43 | `20261020-2049-dev-baseline-1` plain-guided/antennapod-0003/t1 | claude-sonnet-5-5 | completed, 39 turns, 425 s | 30 | 15,134 | 721,907 | 54,014 | 0.4396 | 0 | resolved=True; nudges 0; five-hour 0.51 → 0.57, seven-day 0.69 |
| 07:22 | `20261020-2049-dev-baseline-1` plain-guided/antennapod-0003/t2 | claude-sonnet-5-5 | completed, 42 turns, 248 s | 30 | 16,197 | 747,390 | 55,240 | 0.4577 | 0 | resolved=True; nudges 0; five-hour 0.29 → 0.33, seven-day 0.83 |
| 22:21 | `20261020-2049-dev-baseline-1` plain-guided/antennapod-0004/t1 | claude-sonnet-5-5 | completed, 26 turns, 488 s | 42 | 10,869 | 963,684 | 43,326 | 0.3784 | 0 | resolved=True; nudges 0; five-hour 0.84 → 0.88, seven-day 0.71 |
| 07:59 | `20261020-2049-dev-baseline-1` plain-guided/antennapod-0004/t2 | claude-sonnet-5-5 | completed, 12 turns, 172 s | 16 | 7,292 | 248,391 | 27,442 | 0.2076 | 0 | resolved=True; nudges 0; five-hour 0.59 → 0.61, seven-day 0.85 |
| 01:44 | `20261020-2049-dev-baseline-1` plain-guided/antennapod-0005/t1 | claude-sonnet-5-5 | completed, 12 turns, 139 s | 12 | 4,451 | 170,101 | 22,965 | 0.1534 | 0 | resolved=True; nudges 0; five-hour 0.02 → 0.03, seven-day 0.73 |
| 08:40 | `20261020-2049-dev-baseline-1` plain-guided/antennapod-0005/t2 | claude-sonnet-5-5 | completed, 11 turns, 159 s | 16 | 7,025 | 249,355 | 25,344 | 0.1966 | 0 | resolved=True; nudges 0; five-hour 0.9 → 0.91, seven-day 0.88 |
| 02:10 | `20261020-2049-dev-baseline-1` plain-guided/wikipedia-0002/t1 | claude-sonnet-5-5 | completed, 16 turns, 433 s | 26 | 5,500 | 416,341 | 24,108 | 0.1931 | 0 | resolved=True; nudges 0; five-hour 0.18 → 0.2, seven-day 0.74 |
| 12:03 | `20261020-2049-dev-baseline-1` plain-guided/wikipedia-0002/t2 | claude-sonnet-5-5 | completed, 12 turns, 433 s | 16 | 5,565 | 231,235 | 22,288 | 0.1680 | 0 | resolved=True; nudges 0; five-hour 0.15 → 0.18, seven-day 0.89 |
| 02:51 | `20261020-2049-dev-baseline-1` plain-guided/wikipedia-0006/t1 | claude-sonnet-5-5 | completed, 11 turns, 360 s | 12 | 4,424 | 176,034 | 27,195 | 0.1706 | 0 | resolved=False; nudges 0; five-hour 0.3 → 0.33, seven-day 0.75 |
| 12:42 | `20261020-2049-dev-baseline-1` plain-guided/wikipedia-0006/t2 | claude-sonnet-5-5 | completed, 12 turns, 345 s | 18 | 4,854 | 294,424 | 27,779 | 0.1891 | 0 | resolved=False; nudges 0; five-hour 0.33 → 0.37, seven-day 0.9 |
| 03:43 | `20261020-2049-dev-baseline-1` plain-guided/wikipedia-0007/t1 | claude-sonnet-5-5 | completed, 14 turns, 332 s | 18 | 3,554 | 269,319 | 24,906 | 0.1621 | 0 | resolved=True; nudges 0; five-hour 0.57 → 0.59, seven-day 0.77 |
| 13:26 | `20261020-2049-dev-baseline-1` plain-guided/wikipedia-0007/t2 | claude-sonnet-5-5 | completed, 12 turns, 368 s | 18 | 3,078 | 265,622 | 21,578 | 0.1437 | 0 | resolved=True; nudges 0; five-hour 0.62 → 0.65, seven-day 0.92 |
| 04:25 | `20261020-2049-dev-baseline-1` plain-guided/wikipedia-0009/t1 | claude-sonnet-5-5 | completed, 15 turns, 375 s | 20 | 7,622 | 358,962 | 30,525 | 0.2343 | 0 | resolved=True; nudges 0; five-hour 0.7 → 0.72, seven-day 0.78 |
| 14:07 | `20261020-2049-dev-baseline-1` plain-guided/wikipedia-0009/t2 | claude-sonnet-5-5 | completed, 7 turns, 613 s | 14 | 5,630 | 232,966 | 30,715 | 0.2025 | 0 | resolved=True; nudges 0; five-hour 0.79 → 0.84, seven-day 0.93 |
| 20:58 | `20261020-2049-dev-baseline-1` s2a/antennapod-0000/t1 | claude-sonnet-5-5 | completed, 27 turns, 317 s | 40 | 11,920 | 480,766 | 137,696 | 0.7181 | 0 | resolved=True; nudges 0; five-hour 0.27 → 0.29, seven-day 0.67 |
| 06:42 | `20261020-2049-dev-baseline-1` s2a/antennapod-0000/t2 | claude-sonnet-5-5 | completed, 30 turns, 324 s | 44 | 14,634 | 555,601 | 146,189 | 0.7867 | 0 | resolved=True; nudges 0; five-hour 0.06 → 0.09, seven-day 0.81 |
| 21:12 | `20261020-2049-dev-baseline-1` s2a/antennapod-0001/t1 | claude-sonnet-5-5 | completed, 45 turns, 472 s | 66 | 19,926 | 950,118 | 165,416 | 0.9561 | 0 | resolved=True; nudges 0; five-hour 0.36 → 0.41, seven-day 0.68 |
| 06:55 | `20261020-2049-dev-baseline-1` s2a/antennapod-0001/t2 | claude-sonnet-5-5 | completed, 29 turns, 270 s | 44 | 12,694 | 604,095 | 123,651 | 0.6820 | 0 | resolved=True; nudges 0; five-hour 0.15 → 0.17, seven-day 0.81 |
| 21:31 | `20261020-2049-dev-baseline-1` s2a/antennapod-0002/t1 | claude-sonnet-5-5 | completed, 30 turns, 290 s | 48 | 14,724 | 648,676 | 136,119 | 0.7567 | 0 | resolved=True; nudges 0; five-hour 0.48 → 0.51, seven-day 0.68 |
| 07:11 | `20261020-2049-dev-baseline-1` s2a/antennapod-0002/t2 | claude-sonnet-5-5 | completed, 34 turns, 353 s | 54 | 16,945 | 743,847 | 138,719 | 0.7988 | 0 | resolved=True; nudges 0; five-hour 0.28 → 0.32, seven-day 0.83 |
| 21:53 | `20261020-2049-dev-baseline-1` s2a/antennapod-0003/t1 | claude-sonnet-5-5 | completed, 107 turns, 1048 s | 130 | 62,626 | 2,311,940 | 344,711 | 2.2366 | 0 | resolved=False; nudges 0; five-hour 0.71 → 0.89, seven-day 0.72 |
| 07:36 | `20261020-2049-dev-baseline-1` s2a/antennapod-0003/t2 | claude-sonnet-5-5 | completed, 83 turns, 1006 s | 108 | 49,670 | 1,831,560 | 283,461 | 1.8139 | 0 | resolved=True; nudges 0; five-hour 0.51 → 0.64, seven-day 0.85 |
| 01:42 | `20261020-2049-dev-baseline-1` s2a/antennapod-0004/t1 | claude-sonnet-5-5 | agent_error, 0 turns, 0 s | 0 | 0 | 0 | 0 | 0.0000 | 0 | resolved=False; nudges 0; five-hour —, seven-day — |
| 08:12 | `20261020-2049-dev-baseline-1` s2a/antennapod-0004/t2 | claude-sonnet-5-5 | completed, 80 turns, 768 s | 100 | 41,447 | 1,679,532 | 299,739 | 1.7816 | 0 | resolved=True; nudges 0; five-hour 0.78 → 0.89, seven-day 0.87 |
| 01:52 | `20261020-2049-dev-baseline-1` s2a/antennapod-0005/t1 | claude-sonnet-5-5 | completed, 45 turns, 595 s | 60 | 26,078 | 988,935 | 186,352 | 1.1052 | 0 | resolved=True; nudges 0; five-hour 0.13 → 0.17, seven-day 0.74 |
| 11:48 | `20261020-2049-dev-baseline-1` s2a/antennapod-0005/t2 | claude-sonnet-5-5 | completed, 36 turns, 389 s | 50 | 24,086 | 796,120 | 173,193 | 1.0133 | 0 | resolved=True; nudges 0; five-hour 0.11 → 0.15, seven-day 0.89 |
| 02:42 | `20261020-2049-dev-baseline-1` s2a/wikipedia-0002/t1 | claude-sonnet-5-5 | completed, 43 turns, 707 s | 54 | 28,745 | 792,736 | 161,351 | 1.0122 | 0 | resolved=True; nudges 0; five-hour 0.33 → 0.36, seven-day 0.75 |
| 12:23 | `20261020-2049-dev-baseline-1` s2a/wikipedia-0002/t2 | claude-sonnet-5-5 | completed, 46 turns, 796 s | 62 | 33,578 | 951,201 | 169,390 | 1.1086 | 0 | resolved=True; nudges 0; five-hour 0.32 → 0.36, seven-day 0.9 |
| 03:18 | `20261020-2049-dev-baseline-1` s2a/wikipedia-0006/t1 | claude-sonnet-5-5 | completed, 74 turns, 885 s | 110 | 45,426 | 1,948,204 | 282,847 | 1.7807 | 0 | resolved=False; nudges 0; five-hour 0.55 → 0.55, seven-day 0.77 |
| 13:11 | `20261020-2049-dev-baseline-1` s2a/wikipedia-0006/t2 | claude-sonnet-5-5 | agent_error, 36 turns, 533 s | 44 | 30,728 | 642,264 | 153,135 | 0.9841 | 0 | resolved=False; nudges 0; five-hour 0.5 → 0.58, seven-day 0.91 |
| 04:11 | `20261020-2049-dev-baseline-1` s2a/wikipedia-0007/t1 | claude-sonnet-5-5 | completed, 40 turns, 656 s | 56 | 17,702 | 805,219 | 146,438 | 0.8434 | 0 | resolved=True; nudges 0; five-hour 0.71 → 0.73, seven-day 0.78 |
| 13:45 | `20261020-2049-dev-baseline-1` s2a/wikipedia-0007/t2 | claude-sonnet-5-5 | completed, 41 turns, 681 s | 60 | 17,799 | 809,346 | 149,460 | 0.8569 | 0 | resolved=False; nudges 0; five-hour 0.77 → 0.81, seven-day 0.93 |
| 04:54 | `20261020-2049-dev-baseline-1` s2a/wikipedia-0009/t1 | claude-sonnet-5-5 | completed, 41 turns, 565 s | 62 | 30,236 | 925,869 | 212,068 | 1.2433 | 0 | resolved=True; nudges 0; five-hour 0.89 → 0.92, seven-day 0.8 |
| 16:42 | `20261020-2049-dev-baseline-1` s2a/wikipedia-0009/t2 | claude-sonnet-5-5 | completed, 41 turns, 528 s | 62 | 33,404 | 931,461 | 249,681 | 1.4260 | 0 | resolved=True; nudges 0; five-hour 0.1 → 0.14, seven-day 0.95 |
| 20:54 | `20261020-2049-dev-baseline-1` speckit/antennapod-0000/t1 | claude-sonnet-5-5 | completed, 16 turns, 296 s | 26 | 5,902 | 479,574 | 33,354 | 0.2404 | 0 | resolved=True; nudges 0; five-hour 0.18 → 0.23, seven-day 0.66 |
| 05:06 | `20261020-2049-dev-baseline-1` speckit/antennapod-0000/t2 | claude-sonnet-5-5 | completed, 20 turns, 237 s | 32 | 6,393 | 614,433 | 35,629 | 0.2680 | 0 | resolved=True; nudges 0; five-hour 0.88 → 0.9, seven-day 0.8 |
| 21:11 | `20261020-2049-dev-baseline-1` speckit/antennapod-0001/t1 | claude-sonnet-5-5 | completed, 18 turns, 247 s | 32 | 6,507 | 644,350 | 36,812 | 0.2768 | 0 | resolved=True; nudges 0; five-hour 0.29 → 0.33, seven-day 0.67 |
| 06:55 | `20261020-2049-dev-baseline-1` speckit/antennapod-0001/t2 | claude-sonnet-5-5 | completed, 25 turns, 177 s | 38 | 8,151 | 799,091 | 40,344 | 0.3229 | 0 | resolved=True; nudges 0; five-hour 0.09 → 0.13, seven-day 0.81 |
| 21:29 | `20261020-2049-dev-baseline-1` speckit/antennapod-0002/t1 | claude-sonnet-5-5 | completed, 18 turns, 354 s | 28 | 7,832 | 583,821 | 47,261 | 0.3258 | 0 | resolved=True; nudges 0; five-hour 0.4 → 0.45, seven-day 0.68 |
| 07:08 | `20261020-2049-dev-baseline-1` speckit/antennapod-0002/t2 | claude-sonnet-5-5 | completed, 17 turns, 284 s | 30 | 6,847 | 649,678 | 47,605 | 0.3239 | 0 | resolved=True; nudges 0; five-hour 0.18 → 0.23, seven-day 0.82 |
| 21:53 | `20261020-2049-dev-baseline-1` speckit/antennapod-0003/t1 | claude-sonnet-5-5 | completed, 88 turns, 1096 s | 100 | 51,835 | 5,585,932 | 153,959 | 1.6930 | 0 | resolved=True; nudges 0; five-hour 0.57 → 0.79, seven-day 0.71 |
| 07:28 | `20261020-2049-dev-baseline-1` speckit/antennapod-0003/t2 | claude-sonnet-5-5 | completed, 81 turns, 1390 s | 106 | 44,923 | 5,727,483 | 141,250 | 1.5872 | 0 | resolved=True; nudges 0; five-hour 0.35 → 0.55, seven-day 0.85 |
| 22:34 | `20261020-2049-dev-baseline-1` speckit/antennapod-0004/t1 | claude-sonnet-5-5 | completed, 53 turns, 851 s | 92 | 33,424 | 4,023,750 | 114,102 | 1.1932 | 0 | resolved=True; nudges 0; five-hour 0.91 → 0.99, seven-day 0.72 |
| 08:12 | `20261020-2049-dev-baseline-1` speckit/antennapod-0004/t2 | claude-sonnet-5-5 | completed, 84 turns, 1315 s | 138 | 42,824 | 7,236,426 | 135,016 | 1.6922 | 0 | resolved=True; nudges 0; five-hour 0.65 → 0.87, seven-day 0.87 |
| 01:48 | `20261020-2049-dev-baseline-1` speckit/antennapod-0005/t1 | claude-sonnet-5-5 | completed, 34 turns, 613 s | 64 | 18,346 | 2,025,155 | 75,141 | 0.6867 | 0 | resolved=True; nudges 0; five-hour 0.04 → 0.14, seven-day 0.74 |
| 11:42 | `20261020-2049-dev-baseline-1` speckit/antennapod-0005/t2 | claude-sonnet-5-5 | completed, 31 turns, 610 s | 58 | 18,435 | 1,900,480 | 79,956 | 0.6943 | 0 | resolved=True; nudges 0; five-hour 0.01 → 0.11, seven-day 0.89 |
| 02:25 | `20261020-2049-dev-baseline-1` speckit/wikipedia-0002/t1 | claude-sonnet-5-5 | completed, 21 turns, 523 s | 32 | 12,445 | 685,280 | 43,928 | 0.3688 | 0 | resolved=True; nudges 0; five-hour 0.21 → 0.24, seven-day 0.74 |
| 12:16 | `20261020-2049-dev-baseline-1` speckit/wikipedia-0002/t2 | claude-sonnet-5-5 | completed, 17 turns, 504 s | 26 | 10,610 | 538,281 | 40,295 | 0.3212 | 0 | resolved=True; nudges 0; five-hour 0.19 → 0.25, seven-day 0.89 |
| 03:12 | `20261020-2049-dev-baseline-1` speckit/wikipedia-0006/t1 | claude-sonnet-5-5 | completed, 64 turns, 862 s | 84 | 39,513 | 3,777,395 | 121,404 | 1.2587 | 0 | resolved=False; nudges 0; five-hour 0.37 → 0.5, seven-day 0.77 |
| 12:54 | `20261020-2049-dev-baseline-1` speckit/wikipedia-0006/t2 | claude-sonnet-5-5 | completed, 52 turns, 945 s | 70 | 37,858 | 3,047,608 | 120,795 | 1.1667 | 0 | resolved=False; nudges 0; five-hour 0.38 → 0.5, seven-day 0.91 |
| 03:55 | `20261020-2049-dev-baseline-1` speckit/wikipedia-0007/t1 | claude-sonnet-5-5 | completed, 20 turns, 595 s | 34 | 9,758 | 788,378 | 47,744 | 0.3675 | 0 | resolved=True; nudges 0; five-hour 0.62 → 0.64, seven-day 0.78 |
| 13:38 | `20261020-2049-dev-baseline-1` speckit/wikipedia-0007/t2 | claude-sonnet-5-5 | completed, 33 turns, 580 s | 40 | 11,673 | 993,798 | 53,319 | 0.4295 | 0 | resolved=True; nudges 0; five-hour 0.65 → 0.72, seven-day 0.92 |
| 04:39 | `20261020-2049-dev-baseline-1` speckit/wikipedia-0009/t1 | claude-sonnet-5-5 | completed, 27 turns, 581 s | 54 | 19,073 | 1,742,650 | 80,522 | 0.6872 | 0 | resolved=True; nudges 0; five-hour 0.75 → 0.79, seven-day 0.79 |
| 14:24 | `20261020-2049-dev-baseline-1` speckit/wikipedia-0009/t2 | claude-sonnet-5-5 | completed, 24 turns, 593 s | 48 | 21,208 | 1,605,037 | 82,203 | 0.7015 | 0 | resolved=True; nudges 0; five-hour 0.84 → 0.91, seven-day 0.93 |
| | **`20261020-2049-dev-baseline-1` total (100 trials, 87 resolved)** | | mean 403 s | **3,554** | **1,293,267** | **81,970,168** | **6,902,296** | **48.7460** | 0 | incl. one-time setup |

## 2026-10-21 — tuning 1 after-run (s2a, dev × 2, Sonnet 5.5, `ABB_TUNING=1`)

`20261021-1802-dev-s2a-tune1` (s2a `1ee1ad9`): stopped with `abb run abort` after 6 trials when D-055 recurred, s2a/antennapod-0000/t1 invalidated (D-056) and the run resumed with the ACL fix; the baseline's speckit/antennapod-0001/t2 was invalidated and re-run the same way (resolved). audit PASS. s2a pass@1 0.75 (baseline 0.75), pass^2 0.70 (0.60). Plan: Max from 2026-10-21 18:02 UTC.

| Time (UTC) | Run / activity | Model | Result | in | out | cr | cw | est. USD | Pauses | Note |
|---|---|---|---|---|---|---|---|---|---|---|
| 19:01 | `20261021-1802-dev-s2a-tune1` s2a/antennapod-0000/t1 | claude-sonnet-5-5 | completed, 30 turns, 300 s | 44 | 13,039 | 576,205 | 115,898 | 0.6517 | 0 | resolved=True; nudges 0; five-hour 0.26 → 0.29, seven-day 0.04 |
| 19:56 | `20261021-1802-dev-s2a-tune1` s2a/antennapod-0000/t2 | claude-sonnet-5-5 | completed, 31 turns, 314 s | 46 | 13,335 | 604,002 | 131,909 | 0.7215 | 0 | resolved=True; nudges 0; five-hour 0.4 → 0.41, seven-day 0.05 |
| 18:02 | `20261021-1802-dev-s2a-tune1` s2a/antennapod-0001/t1 | claude-sonnet-5-5 | completed, 56 turns, 533 s | 78 | 23,318 | 1,147,771 | 211,076 | 1.1924 | 0 | resolved=True; nudges 0; five-hour 0.04 → 0.04, seven-day 0 |
| 20:08 | `20261021-1802-dev-s2a-tune1` s2a/antennapod-0001/t2 | claude-sonnet-5-5 | completed, 47 turns, 450 s | 62 | 21,946 | 905,928 | 180,852 | 1.0336 | 0 | resolved=True; nudges 0; five-hour 0.43 → 0.43, seven-day 0.05 |
| 18:18 | `20261021-1802-dev-s2a-tune1` s2a/antennapod-0002/t1 | claude-sonnet-5-5 | completed, 34 turns, 386 s | 52 | 16,277 | 715,757 | 142,325 | 0.8037 | 0 | resolved=True; nudges 0; five-hour 0.08 → 0.09, seven-day 0.01 |
| 20:09 | `20261021-1802-dev-s2a-tune1` s2a/antennapod-0002/t2 | claude-sonnet-5-5 | completed, 38 turns, 378 s | 60 | 16,734 | 860,942 | 145,746 | 0.8365 | 0 | resolved=True; nudges 0; five-hour 0.42 → 0.44, seven-day 0.05 |
| 18:20 | `20261021-1802-dev-s2a-tune1` s2a/antennapod-0003/t1 | claude-sonnet-5-5 | completed, 67 turns, 718 s | 86 | 40,001 | 1,433,489 | 244,448 | 1.5213 | 0 | resolved=True; nudges 0; five-hour 0.08 → 0.18, seven-day 0.02 |
| 20:23 | `20261021-1802-dev-s2a-tune1` s2a/antennapod-0003/t2 | claude-sonnet-5-5 | completed, 69 turns, 691 s | 94 | 35,902 | 1,628,877 | 242,615 | 1.4926 | 0 | resolved=True; nudges 0; five-hour 0.45 → 0.47, seven-day 0.06 |
| 18:36 | `20261021-1802-dev-s2a-tune1` s2a/antennapod-0004/t1 | claude-sonnet-5-5 | agent_error, 18 turns, 77 s | 20 | 9,288 | 319,970 | 65,180 | 0.3856 | 0 | resolved=False; nudges 0; five-hour 0.1 → 0.1, seven-day 0.01 |
| 20:25 | `20261021-1802-dev-s2a-tune1` s2a/antennapod-0004/t2 | claude-sonnet-5-5 | completed, 78 turns, 827 s | 110 | 42,455 | 1,832,499 | 289,543 | 1.7662 | 0 | resolved=True; nudges 1; five-hour 0.46 → 0.48, seven-day 0.06 |
| 18:39 | `20261021-1802-dev-s2a-tune1` s2a/antennapod-0005/t1 | claude-sonnet-5-5 | completed, 36 turns, 515 s | 50 | 23,666 | 814,843 | 159,741 | 0.9572 | 0 | resolved=True; nudges 0; five-hour 0.14 → 0.21, seven-day 0.03 |
| 20:53 | `20261021-1802-dev-s2a-tune1` s2a/antennapod-0005/t2 | claude-sonnet-5-5 | completed, 39 turns, 411 s | 54 | 24,329 | 809,602 | 169,324 | 1.0017 | 0 | resolved=True; nudges 0; five-hour 0.49 → 0.53, seven-day 0.06 |
| 19:02 | `20261021-1802-dev-s2a-tune1` s2a/wikipedia-0002/t1 | claude-sonnet-5-5 | completed, 47 turns, 862 s | 72 | 33,340 | 1,080,597 | 184,102 | 1.1780 | 0 | resolved=True; nudges 2; five-hour 0.32 → 0.36, seven-day 0.05 |
| 20:55 | `20261021-1802-dev-s2a-tune1` s2a/wikipedia-0002/t2 | claude-sonnet-5-5 | completed, 41 turns, 662 s | 58 | 26,226 | 801,637 | 172,528 | 1.0327 | 0 | resolved=True; nudges 2; five-hour 0.53 → 0.54, seven-day 0.06 |
| 19:15 | `20261021-1802-dev-s2a-tune1` s2a/wikipedia-0006/t1 | claude-sonnet-5-5 | agent_error, 37 turns, 506 s | 42 | 29,642 | 603,404 | 146,412 | 0.9425 | 0 | resolved=False; nudges 0; five-hour 0.3 → 0.33, seven-day 0.04 |
| 21:12 | `20261021-1802-dev-s2a-tune1` s2a/wikipedia-0006/t2 | claude-sonnet-5-5 | completed, 82 turns, 1004 s | 98 | 43,144 | 1,606,558 | 298,740 | 1.7873 | 0 | resolved=False; nudges 0; five-hour 0.57 → 0.56, seven-day 0.07 |
| 19:28 | `20261021-1802-dev-s2a-tune1` s2a/wikipedia-0007/t1 | claude-sonnet-5-5 | completed, 49 turns, 655 s | 66 | 22,496 | 926,716 | 163,776 | 0.9729 | 0 | resolved=False; nudges 0; five-hour 0.38 → 0.39, seven-day 0.05 |
| 21:26 | `20261021-1802-dev-s2a-tune1` s2a/wikipedia-0007/t2 | claude-sonnet-5-5 | completed, 38 turns, 692 s | 54 | 17,627 | 757,355 | 141,795 | 0.8193 | 0 | resolved=False; nudges 0; five-hour 0.57 → 0.57, seven-day 0.07 |
| 19:35 | `20261021-1802-dev-s2a-tune1` s2a/wikipedia-0009/t1 | claude-sonnet-5-5 | completed, 42 turns, 655 s | 62 | 34,212 | 948,653 | 226,777 | 1.3442 | 0 | resolved=True; nudges 0; five-hour 0.39 → 0.4, seven-day 0.05 |
| 21:54 | `20261021-1802-dev-s2a-tune1` s2a/wikipedia-0009/t2 | claude-sonnet-5-5 | completed, 62 turns, 1074 s | 86 | 46,724 | 1,325,293 | 297,267 | 1.7890 | 0 | resolved=True; nudges 0; five-hour 0.6 → 0.6, seven-day 0.07 |
| | **`20261021-1802-dev-s2a-tune1` total (20 trials, 15 resolved)** | | mean 586 s | **1,294** | **533,701** | **19,700,098** | **3,730,054** | **22.2298** | 0 | incl. one-time setup |

## 2026-10-21/22 — tuning 2 after-run (s2a, dev × 2, Sonnet 5.5, `ABB_TUNING=1`)

`20261021-2234-dev-s2a-tune2` (s2a `8a06aa2`): paused for the five-hour window after 7 trials, stopped with `abb run abort` and resumed at 00:28 UTC after the owner reset the quota; audit PASS; s2a pass@1 0.75, pass^2 0.60.

| Time (UTC) | Run / activity | Model | Result | in | out | cr | cw | est. USD | Pauses | Note |
|---|---|---|---|---|---|---|---|---|---|---|
| 22:35 | `20261021-2234-dev-s2a-tune2` s2a/antennapod-0000/t1 | claude-sonnet-5-5 | completed, 27 turns, 318 s | 42 | 12,421 | 529,660 | 122,583 | 0.6676 | 0 | resolved=True; nudges 0; five-hour 0.65 → 0.66, seven-day 0.07 |
| 01:19 | `20261021-2234-dev-s2a-tune2` s2a/antennapod-0000/t2 | claude-sonnet-5-5 | completed, 24 turns, 281 s | 38 | 11,445 | 464,009 | 123,199 | 0.6537 | 0 | resolved=True; nudges 0; five-hour 0.26 → 0.28, seven-day 0.03 |
| 22:35 | `20261021-2234-dev-s2a-tune2` s2a/antennapod-0001/t1 | claude-sonnet-5-5 | completed, 35 turns, 302 s | 48 | 14,765 | 682,794 | 133,125 | 0.7485 | 0 | resolved=True; nudges 0; five-hour 0.65 → 0.66, seven-day 0.07 |
| 01:33 | `20261021-2234-dev-s2a-tune2` s2a/antennapod-0001/t2 | claude-sonnet-5-5 | completed, 32 turns, 275 s | 46 | 13,219 | 658,372 | 129,927 | 0.7178 | 0 | resolved=True; nudges 0; five-hour 0.3 → 0.31, seven-day 0.04 |
| 22:47 | `20261021-2234-dev-s2a-tune2` s2a/antennapod-0002/t1 | claude-sonnet-5-5 | completed, 33 turns, 322 s | 52 | 15,607 | 718,003 | 141,052 | 0.7922 | 0 | resolved=True; nudges 0; five-hour 0.68 → 0.69, seven-day 0.08 |
| 01:34 | `20261021-2234-dev-s2a-tune2` s2a/antennapod-0002/t2 | claude-sonnet-5-5 | completed, 35 turns, 319 s | 50 | 17,118 | 684,028 | 143,666 | 0.8143 | 0 | resolved=True; nudges 0; five-hour 0.3 → 0.31, seven-day 0.04 |
| 22:48 | `20261021-2234-dev-s2a-tune2` s2a/antennapod-0003/t1 | claude-sonnet-5-5 | agent_error, 23 turns, 296 s | 32 | 24,334 | 504,383 | 141,830 | 0.8612 | 0 | resolved=False; nudges 0; five-hour 0.66 → 0.67, seven-day 0.08 |
| 01:45 | `20261021-2234-dev-s2a-tune2` s2a/antennapod-0003/t2 | claude-sonnet-5-5 | completed, 90 turns, 935 s | 126 | 46,577 | 2,268,417 | 286,472 | 1.8388 | 0 | resolved=True; nudges 0; five-hour 0.33 → 0.36, seven-day 0.04 |
| 22:55 | `20261021-2234-dev-s2a-tune2` s2a/antennapod-0004/t1 | claude-sonnet-5-5 | agent_error, 105 turns, 1125 s | 142 | 49,464 | 2,498,004 | 362,267 | 2.1938 | 0 | resolved=True; nudges 0; five-hour 0.66 → 0.36, seven-day 0.12 |
| 01:47 | `20261021-2234-dev-s2a-tune2` s2a/antennapod-0004/t2 | claude-sonnet-5-5 | completed, 84 turns, 912 s | 116 | 47,497 | 2,151,003 | 299,962 | 1.8902 | 0 | resolved=True; nudges 0; five-hour 0.33 → 0.36, seven-day 0.04 |
| 22:59 | `20261021-2234-dev-s2a-tune2` s2a/antennapod-0005/t1 | claude-sonnet-5-5 | completed, 33 turns, 516 s | 44 | 22,022 | 676,761 | 154,433 | 0.9057 | 0 | resolved=True; nudges 0; five-hour 0.07 → 0.35, seven-day 0.12 |
| 02:19 | `20261021-2234-dev-s2a-tune2` s2a/antennapod-0005/t2 | claude-sonnet-5-5 | completed, 40 turns, 378 s | 56 | 23,401 | 854,492 | 182,906 | 1.0512 | 0 | resolved=True; nudges 0; five-hour 0.43 → 0.44, seven-day 0.05 |
| 23:16 | `20261021-2234-dev-s2a-tune2` s2a/wikipedia-0002/t1 | claude-sonnet-5-5 | agent_error, 17 turns, 77 s | 22 | 9,057 | 313,760 | 49,964 | 0.3218 | 0 | resolved=False; nudges 0; five-hour 0.42 → 0.44, seven-day 0.13 |
| 02:23 | `20261021-2234-dev-s2a-tune2` s2a/wikipedia-0002/t2 | claude-sonnet-5-5 | completed, 40 turns, 672 s | 56 | 27,841 | 811,158 | 156,565 | 0.9859 | 0 | resolved=True; nudges 0; five-hour 0.44 → 0.45, seven-day 0.05 |
| 00:29 | `20261021-2234-dev-s2a-tune2` s2a/wikipedia-0006/t1 | claude-sonnet-5-5 | timeout, 109 turns, 1322 s | 142 | 58,457 | 2,400,975 | 314,701 | 2.0838 | 0 | resolved=False; nudges 0; five-hour 0.06 → 0.02, seven-day 0 |
| 02:37 | `20261021-2234-dev-s2a-tune2` s2a/wikipedia-0006/t2 | claude-sonnet-5-5 | completed, 113 turns, 1339 s | 152 | 62,363 | 2,917,426 | 328,402 | 2.2293 | 0 | resolved=False; nudges 0; five-hour 0.47 → 0.47, seven-day 0.05 |
| 00:29 | `20261021-2234-dev-s2a-tune2` s2a/wikipedia-0007/t1 | claude-sonnet-5-5 | completed, 41 turns, 676 s | 56 | 19,266 | 830,021 | 139,585 | 0.8341 | 0 | resolved=False; nudges 0; five-hour 0.05 → 0.06, seven-day 0.01 |
| 02:52 | `20261021-2234-dev-s2a-tune2` s2a/wikipedia-0007/t2 | claude-sonnet-5-5 | completed, 38 turns, 698 s | 52 | 18,590 | 725,260 | 145,157 | 0.8392 | 0 | resolved=True; nudges 0; five-hour 0.47 → 0.48, seven-day 0.05 |
| 00:58 | `20261021-2234-dev-s2a-tune2` s2a/wikipedia-0009/t1 | claude-sonnet-5-5 | completed, 37 turns, 579 s | 56 | 37,931 | 784,993 | 230,376 | 1.3794 | 0 | resolved=True; nudges 0; five-hour 0.19 → 0.26, seven-day 0.03 |
| 03:20 | `20261021-2234-dev-s2a-tune2` s2a/wikipedia-0009/t2 | claude-sonnet-5-5 | completed, 42 turns, 779 s | 66 | 31,215 | 992,371 | 216,743 | 1.2785 | 0 | resolved=True; nudges 0; five-hour 0.5 → 0.5, seven-day 0.05 |
| | **`20261021-2234-dev-s2a-tune2` total (20 trials, 15 resolved)** | | mean 606 s | **1,394** | **562,590** | **22,465,890** | **3,802,915** | **23.0869** | 0 | incl. one-time setup |
