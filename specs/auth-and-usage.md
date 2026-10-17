# Spec: Authentication, usage limits and cost accounting (subscription, no API key)

The owner has a Claude subscription (Pro or Max) and no API key. Everything in this plan — the
building chats in Claude Code **and** the benchmark's headless runs — uses that subscription.
This file says how, what it changes, and where the one real decision is.

## 1. Authentication

| Where | Mechanism |
|---|---|
| Building phases (you, in Claude Code: the desktop app's Code tab or `claude.exe` in PowerShell 7) | your normal Claude Code login — untouched by anything below |
| Headless runs (`claude.exe -p` started by the harness, or by `s2a` inside a trial) | a **one-year OAuth token** from `claude setup-token` (documented for "CI pipelines and scripts"; requires Pro, Max, Team or Enterprise). You store it once as the user environment variable **`ABB_OAUTH_TOKEN`** (or in the git-ignored `benchmark/.env`); the harness reads it and places it in the per-trial environment block under the name Claude Code reads, `CLAUDE_CODE_OAUTH_TOKEN`. It is never written under the repo or `ABB_HOME`, never logged, never in argv. |

Why the different name: `CLAUDE_CODE_OAUTH_TOKEN` is read by **every** Claude Code session on
the machine and outranks your login, and a token session "can only make model requests" (no
Remote Control, no claude.ai connectors). Setting it globally would silently turn every building
chat into a CI session. `ABB_OAUTH_TOKEN` is read by `abb` alone.

Rules the driver enforces:

- The per-trial environment block **contains no** `ANTHROPIC_API_KEY`, `ANTHROPIC_AUTH_TOKEN`,
  `CLAUDE_CODE_USE_BEDROCK/VERTEX/FOUNDRY`, and the trial's `settings.json` has no
  `apiKeyHelper`: the docs' precedence order puts an API key *above* the OAuth token, and with
  `-p` "the key is always used when present". The harness refuses to start if its own
  environment has `CLAUDE_CODE_OAUTH_TOKEN` or `ANTHROPIC_API_KEY` set (so a stray global
  variable is caught, not inherited).
- Never `--bare`: bare mode "does not read `CLAUDE_CODE_OAUTH_TOKEN`". (The docs say `--bare`
  "will become the default for `-p` in a future release", with no date — one more reason the
  Claude Code version is pinned, and why every pin upgrade re-runs `abb auth check` and the
  smoke tests.)
- Preflight once per run: `abb auth check` runs `claude.exe auth status` through the launcher
  with the mapped block and requires exit 0 and `authMethod: oauth_token` (the CLI reference
  documents the values `none`, `claude.ai`, `oauth_token`, `api_key`, `api_key_helper`,
  `third_party`; exit 0 if logged in, 1 if not). It also records `subscriptionType` (e.g. `pro`,
  `max`) into the manifest's `plan` field, so the plan is measured, not typed. **Phase 0 finding
  (D-035):** a token session's `auth status` has no `subscriptionType` field, so `abb auth check`
  also reads the harness user's own CLI login; when that is not logged in either (the owner works
  in the desktop app), `plan` is `null` with `plan_source` saying why, and the Day 0 reading stands. Whether the token is honoured with an **empty** per-trial `CLAUDE_CONFIG_DIR`
  is not documented — Phase 0 step 5 proves it and records the answer in `reference/verified.md`.
  Whether it is honoured when the process runs **as the sandbox user** (`abb-agent`, no profile)
  is proven by Phase 1's smoke test through the sandbox path, before any trial runs there.
- **The token never reaches a transcript** (D-026). The agent has a shell, and transcripts are
  verbatim and published in Phase 10, so "never logged" must be enforced, not assumed: the agent
  env originally set `CLAUDE_CODE_SUBPROCESS_ENV_SCRUB=1` — now `0`, D-033: `1` forces permission
  mode `default`, and the token is stripped from tool subprocesses either way (Claude Code strips credentials from its Bash,
  PowerShell, hook and MCP subprocesses; Phase 0 step 5 proves it covers the OAuth token), and
  `abb audit` fails on any file under the run that contains the token value or an `sk-ant-…`
  key pattern (`specs/headless-agent-driving.md`, "Source of truth"). Residual channel, stated in
  the README: a process of the sandbox user could still read `claude.exe`'s own environment.
- **A fresh token for the held-out run.** Phase 10 creates a new `setup-token` token for the
  held-out matrix and retires it afterwards (revoked if Anthropic documents a way — Phase 0 step
  5 records whether it does — otherwise left to expire, never reused for publishing or sharing).
- One token, one account, every arm: identical by construction (fairness-protocol.md).
- `s2a` run by you in a terminal, outside the benchmark, simply uses whatever auth that
  `claude.exe` has — your login. Inside a trial it inherits the block.

## 2. Cost accounting without a bill

`total_cost_usd` in a `-p` result is computed "locally from token counts at list price" — a
client-side estimate, not billing, under any auth. With a subscription there is no per-token
charge at all. Therefore:

- **Tokens are the primary cost unit** in every table (`input_tokens`, `output_tokens`,
  cache read/write, totals per task and per arm).
- `cost_usd` keeps its field name for compatibility but every table header and the README call
  it **"est. API-equivalent USD"** (what the same traffic would cost at list price). It is
  still useful as a comparable, plan-independent number.
- `--max-budget-usd` caps that estimate and keeps working as a runaway guard; `limits.yaml:
  max_usd` means the same thing.
- Phase 0 confirms `total_cost_usd` and `usage` appear under OAuth; if either is missing, the
  driver computes the estimate from the per-message `usage` blocks and
  `benchmark/config/prices.yaml` (list prices, dated; a Phase 4 deliverable, also used for
  `cost_usd_imputed`).

## 3. Usage limits (the real constraint)

A subscription has a rolling **session limit** and a **weekly limit**, with separate Opus and
Sonnet limits on some plans; the interactive app shows "You've hit your session limit · resets
3:45pm" and can auto-continue, but **a `-p` run neither waits nor exposes a documented
limit-specific result subtype** — it ends with a non-zero exit and an error. The harness treats
this as an environmental pause, never as an agent failure, and errs on the side of *not
counting* a trial:

| Step | Behaviour |
|---|---|
| Detect | (a) the result/error text matches `hit your (session\|weekly\|Opus\|Sonnet) limit` (and, if present, a `resets <time>` fragment), or (b) a call ends without a `success` result and without an explaining subtype (`error_max_turns`, `error_max_budget_usd` are explained — no probe) and **the probe says the service is unavailable**. The probe: right after such a call the driver runs `claude.exe -p "ping" --tools "" --max-turns 1 --model <the call's model>` through the same launch path and keeps its transcript at `<run>/probes/<ts>-<arm>-<task>-t<k>-<n>.jsonl`, outside the trial directory. Limit text or 429 → `usage_limited`; 401/403 → the run aborts at once (`aborted_reason: auth` → `abb auth check`); model rejected → run aborts (`model`); other probe failure → `harness_error`; probe succeeds → the call's own classification stands. A call with **no `assistant` message at all** is never `agent_error`: `usage_limited`, `harness_error` or an abort, by the probe. The S2A arm applies the same rule inside the orchestrator (`exit_reason: usage_limited`, exit 6; `specs/s2a-orchestrator.md` §7). |
| Classify | the trial gets outcome `usage_limited`: not resolved, not unresolved, **not counted** in the primary metric; the cut attempt's directory is moved to `<run>/usage_limited/<arm>/<task>/t<k>-a<n>/` (kept, never graded; it feeds the sensitivity check, D-028) and the trial re-queued in a fresh `t<k>`; the probe transcript under `<run>/probes/` stays, so `abb audit` can recount `usage_limited_pauses` per arm from transcripts (rule 11) |
| Pause | `abb run --pause-on-usage-limit` (default on): all workers stop launching. First wake-up = the parsed reset time + 2 min when a `resets <time>` fragment parsed (bare clock time, local zone, next occurrence), else 30 min; from then on the scheduler **probes every 15 min** until a probe succeeds, then resumes. The parsed time is only a hint; the probe is the mechanism. Scheduler probes use the run's `limits.model`, run through the launcher as the sandbox user in a scratch `ABB_HOME\work\probe\<ts>` with the trial env block minus workspace, and are kept as `<run>/probes/<ts>-scheduler-<n>.jsonl`; a 401/403 during the loop aborts the run (`auth`) instead of waiting. Total pause is capped by `--max-pause-h` (default 48 h, a weekly limit can be days) → `aborted_reason = "usage_limit"`, resumable with `--resume`. `abb run status` shows `paused until …`/`probing`; probes are logged in `events.jsonl` and summarised in `docs/RUNS.md`. |
| Fairness | every arm is subject to the same pauses; a paused trial is re-run from scratch so no arm's wall-clock budget is consumed by waiting; interleaved scheduling (Phase 8) keeps a window's close from falling on one arm. **Known bias of re-running from scratch:** a longer trial is more likely to be cut when a window closes, so the trials that get counted over-represent short runs. Failures tend to be the long runs (flailing until max turns or the deadline), and the multi-stage arms run longer and get cut more often. Discarding cut attempts therefore favours success, and favours the arms that are cut most. **Handling (D-028):** (a) keep every cut attempt instead of wiping it — move it to `<run>/usage_limited/<arm>/<task>/t<k>-a<n>/` (transcript, `run.json` with tokens, turns and elapsed time at the cut; never graded); (b) a pre-registered sensitivity check: the primary comparison recomputed with each trial slot's **first** attempt, a cut attempt scored unresolved, reported next to the headline; plus cut count, cut rate and mean elapsed/tokens at cut per arm; (c) fewer cuts: if Phase 0 finds `-p` emits `rate_limit_event` with a warning status or utilisation, the scheduler stops *launching* trials once the window is nearly spent, lets running trials finish, then pauses as usual. |
| Canary | the exact `-p` output on a limit is undocumented. Phase 4 captures the first real occurrence verbatim (transcript tail, stderr, exit code) into `reference/verified.md` and tunes the detector. If dev runs never hit a limit, run `abb ws smoke --until-limit --max-calls 200` once when the window is nearly spent (end of a work session, or when the app's usage indicator says so): it loops the probe prompt through the launcher until the limit answers or `--max-calls` is reached, records the output, and costs the remainder of that window — and locks your own chats out until it resets. A **matrix run** — `--tasks test`, or more than 30 trials — refuses to start without the canary unless `--allow-no-canary` is passed, which is recorded in the manifest. |
| Plan | **Throughput probe (D-027):** Phase 1 step 10b first runs one realistic sandboxed session on the seed task with the usage meter read before and after, and records session % and weekly % per trial, giving a lower-bound estimate of the weeks the plan needs and an early Pro / Max / MVP-cut decision. Then Phase 4's gate records **trials per session window** for the plain arm on Sonnet in `docs/RUNS.md` — the number for scheduling dev work. The held-out run is planned from the **Opus dev-set confirmation run** (Phase 10 prerequisite), per arm, because Opus has its own limit and multi-stage arms use 2–5× the tokens. `PLAN.md` §6 turns those into a calendar. |

Opus has its own limit on the plans that separate it, and dev work on `claude-sonnet-5-5`
keeps that window free for the pinned final runs.

**Same account, same windows.** The building chats and the headless trials draw on the same
subscription: a dev run, the canary, or a paused matrix share the window with the chat you are
working in. Practical rules: run dev runs and the canary at the end of a work session; while an
Opus run is scheduled, build on Sonnet (`/model claude-sonnet-5-5` in the chat — Pro/Max chats
default to Opus 5.5); expect Phase 4's trials-per-window number to be lower on days you also
build.

**Power.** A paused or long run on a laptop must not sleep: sleep suspends every trial and
their wall-clock deadlines fire on wake. `docs/DAY-0.md` §2 has the `powercfg` lines; the runner
prints a warning at start if the AC standby timeout is not 0.

## 4. Model availability

The docs say Pro, Max, Team and Enterprise default to Opus 5.5 and accept full model ids on
`--model`. The pin stays `claude-opus-5-5` **if** the Phase 0 smoke test succeeds with it on
your plan; otherwise `claude-sonnet-5-5` for everything (dev and final), recorded in D-001.
Differences between Pro, Max 5x and Max 20x beyond the limits themselves are not documented.

## 5. The policy decision (read before the held-out run)

Anthropic's legal page says OAuth subscription auth "is intended exclusively for purchasers of
… subscription plans and is designed to support ordinary use of Claude Code", that advertised
limits "assume ordinary, individual usage of Claude Code and the Agent SDK", that "developers
building products or services … should use API key authentication", and that Anthropic may
enforce these restrictions and "may do so without prior notice" (docs/en/legal-and-compliance,
checked 2026-10-17; the same page directs use-case questions to Anthropic's sales team). No
document permits or forbids a personal
benchmark batch of hundreds of headless runs; it is not an obviously prohibited case, and it is
hard to call it ordinary individual usage either.

How the plan handles that, honestly:

- **Building the framework, dev-scale runs (dev5 × a few trials, one or two arms at a time, run
  by you) and `s2a` as your own daily tool** are ordinary use of your subscription on your own
  machine. The plan proceeds on that basis.
- **The held-out matrix (hundreds of unattended trials)** is a decision recorded in
  `docs/PREREG.md: auth_mode` before the freeze:
  1. run it under the subscription in small batches across usage windows and days (slow; the
     MVP cut in `PLAN.md` §9 makes it tractable), accepting that this stretches "ordinary";
  2. ask first — describe the batch to Anthropic (the legal page sends use-case questions to
     sales; https://support.claude.com is the other channel) and keep the answer in `docs/`; or
  3. use an API key for that run only — which the owner has ruled out for now.
  The plan does not choose for you; it makes the choice visible and reversible.
- Nothing in this plan ever shares the token with anyone else or serves other users: the
  sandbox user is you under another local account on the same PC, and the token reaches it only
  through the environment block.

## 6. What changes elsewhere

- No `anthropic` SDK dependency: the Phase 9 labeller and convention grader call
  `claude.exe -p --output-format json --json-schema … --tools "" --max-turns 1` through the
  same driver and read `structured_output`.
- `docs/RUNS.md` logs tokens and est. USD per run, plus usage-limit pauses and probes.
- The run manifest records `auth_mode` (`subscription` | `api_key`), the plan (`subscriptionType`
  from `claude auth status`, recorded by `abb auth check`), `allow_no_canary`, and the count of `usage_limited` pauses per arm.
- `docs/PREREG.md` lists `usage_limited` among the not-counted outcomes.
