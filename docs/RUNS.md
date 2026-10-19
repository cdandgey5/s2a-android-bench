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
