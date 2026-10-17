# Spec: Driving Claude Code headlessly

Verified against the Claude Code docs on 2026-10-16 (see `reference/sources.md`). **Re-verify
with the pinned `claude.exe --help` before Phase 4's gate** and record in
`reference/verified.md`.

Two implementations exist and must stay identical in behaviour:
`benchmark/abb/harness/agent_driver.py` (plain, control and Spec Kit arms) and
`s2a/s2a/driver.py` (the orchestrator). Both parse the same transcript fixtures in their tests
(`benchmark/tests/fixtures/transcripts/`, copied into `s2a/tests/fixtures/transcripts/`).

## Flags and environment that matter

| Need | Flag / behaviour |
|---|---|
| Non-interactive single prompt | `claude -p "<prompt>"` (or prompt on stdin, ≤ 10 MB) |
| Full transcript + cost | `--output-format stream-json --verbose` |
| Cap agentic turns | `--max-turns N` → on hit: non-zero exit, result `subtype: "error_max_turns"` |
| Cap spend | `--max-budget-usd X` → `subtype: "error_max_budget_usd"` (caps Claude Code's client-side estimate at list price — the only cost figure that exists under a subscription; may overshoot one response) |
| Continue a session | `claude -p --resume <session_id> "<prompt>"` (sessions made by `-p` are resumable; never pass `--no-session-persistence`) |
| Skip permission prompts | `--permission-mode bypassPermissions` (= `--dangerously-skip-permissions`). Refused as root/sudo on Linux and macOS only; on Windows just never run the harness as Administrator. Always pass it explicitly (the `-p` default mode varies by version and feature flags). |
| Deny tools | `--disallowedTools "WebFetch,WebSearch"` (deny rules apply in every mode); arms may deny more in their own calls |
| Pin model | `--model claude-opus-5-5` — the full model id (Phase 0 proves the owner's plan accepts it, else D-001 falls back to `claude-sonnet-5-5`); never an alias like `opus`. If the CLI reports a dated snapshot (`claude-opus-5-5-2026…`) in `init.model`/`modelUsage`, the driver matches by prefix and records the resolved id in `run.json` |
| System prompt | `--append-system-prompt "<text>"` (keeps Claude Code's defaults; recorded on the first request and reused on `--resume`) |
| Slash commands | Put `/name args` in the prompt string; Claude Code expands the first one. The `init` event lists `slash_commands`; Phase 5's gate checks it contains `speckit-specify`. |
| Auth | `CLAUDE_CODE_OAUTH_TOKEN` in the environment block, mapped by the harness from the user variable `ABB_OAUTH_TOKEN` (one-year token from `claude setup-token`); **no** `ANTHROPIC_API_KEY`/`ANTHROPIC_AUTH_TOKEN`/cloud flags (an API key would take precedence and "is always used when present" with `-p`); the harness refuses to start if its own environment has `CLAUDE_CODE_OAUTH_TOKEN` or `ANTHROPIC_API_KEY`; `abb auth check` (`claude.exe auth status` through the launcher → `authMethod: oauth_token`) once per run (`specs/auth-and-usage.md`) |
| No self-update, no telemetry | Agent env (`config/sandbox.yaml`): `DISABLE_AUTOUPDATER=1 DISABLE_UPDATES=1 CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1` (a native install otherwise updates itself in the background and would move off the pinned version; feature-flag/telemetry hosts would also be blocked by the firewall and retried). Version floors: `DISABLE_UPDATES` ≥ 2.1.118, `CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS` ≥ 2.1.182, stdin fix on Windows ≥ 2.1.211, Opus 5.5 ≥ 2.1.280 (docs/en/model-config) → **pin ≥ 2.1.280** (D-026) |
| Credential scrub | `CLAUDE_CODE_SUBPROCESS_ENV_SCRUB=1` in the agent env: Claude Code strips credentials (matched "by name or value shape") from the environments of its subprocesses — Bash, PowerShell, hooks, MCP — so an agent running `env` cannot print `CLAUDE_CODE_OAUTH_TOKEN` into the verbatim transcript. The docs' example names `ANTHROPIC_API_KEY`, so Phase 0 step 5 proves the OAuth token is covered too. It also removes `CLAUDE_CONFIG_DIR` from subprocesses (nothing in a trial needs it there). Backstop: `abb audit` fails on any file under the run that contains the token (below) (D-026) |
| Proxy DNS | `CLAUDE_CODE_PROXY_RESOLVES_HOSTS=1` so the CLI lets the proxy resolve `api.anthropic.com` (a per-user firewall rule does not block DNS — Windows resolves through the `Dnscache` service — but with the proxy doing the lookup nothing else needs name resolution) |
| Windows specifics | Call the pinned binary by absolute path (`ABB_HOME\tools\claude\<version>\claude.exe`; Claude Desktop can shadow `claude` on PATH). The Bash tool runs Git Bash; `CLAUDE_CODE_USE_POWERSHELL_TOOL=1` is set explicitly so every arm has the same shell set; never deny `Bash` (that would also remove PowerShell). Settings and sessions live in a per-trial `CLAUDE_CONFIG_DIR` (`<trial>\claude-config`, seeded from `ABB_HOME\sandbox\claude-config.template`, `settings.json` deny-write). Credentials are file-based on Windows; the token is passed only via the environment block. |
| Background work after final turn | `CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS=60000` so a trial cannot hang 10 min after finishing |
| Model-switch guard | The certain guard is the `modelUsage` assertion below. No `fallbackModel` setting and no `ANTHROPIC_MODEL` env are set. `~/.claude/settings.json: {"switchModelsOnFlag": false}` is baked in **only if the pinned version documents the key**. It is documented as of 2026-10-17 (docs/en/model-config: `false` = "Ask each time"; in `-p` "a flagged request ends the turn with a refusal instead"), so the default is to keep it; Phase 0 step 5 re-checks on the pinned version and records |
| Do NOT use | `--bare` (skips CLAUDE.md, commands, skills — breaks Spec Kit and repo instructions; docs say it "will become the default for `-p` in a future release", which is why `CLAUDE_CODE_VERSION` is pinned; it also never reads the OAuth token) and `--restricted` (refuses bypassPermissions) |

## `run_headless(...)`

```python
def run_headless(
    ws: Workspace,                # the trial workspace (benchmark) — or a local subprocess runner (s2a)
    prompt: str,
    *,
    call_name: str,
    limits_left: Limits,          # remaining budget for this trial
    session_id: str | None = None,
    append_system_prompt: str | None = None,   # environment.md first, arm text after
    extra_disallowed_tools: list[str] = (),
    turn_cap: int | None = None,  # arm-supplied per-call cap; None = whole remaining total
    nudge_policy: NudgePolicy = NudgePolicy.default(),
    is_implementing_call: bool = False,        # enables nudge trigger (c)
) -> PhaseCall
```

Behaviour:

1. Compose argv:
   ```
   claude -p --output-format stream-json --verbose
          --model <limits.model>
          --max-turns <min(turn_cap or limits_left.max_turns_total, limits_left.max_turns_total)>
          --max-budget-usd <limits_left.max_usd>
          --permission-mode bypassPermissions
          --disallowedTools "WebFetch,WebSearch[,<extra>]"
          [--resume <session_id>]
          --append-system-prompt "<environment.md + arm text>"
          "<prompt>"
   ```
   There is no global per-call turn cap (fairness-protocol.md, "Turn budget"). Both drivers start
   the process through their platform layer (`specs/platform-layer.md`): the benchmark as the
   sandbox user in the workspace, s2a as the current user; a Job Object (Windows) limits memory
   and kills the tree. At the deadline the platform layer stops the process gracefully
   (on Windows the launcher sends `CTRL_BREAK_EVENT` to the child's own process group — the one
   console signal that can be targeted —, SIGINT elsewhere; `sandbox.yaml: process.interrupt`
   holds the choice and **both drivers use the same one**), waits 30 s for the `result` line, then
   kills the job. **Whether Claude Code writes its `result` line after Ctrl+Break (or Ctrl+C) on
   Windows is not documented**; Phase 0 measures both (`smoke-interrupt`) and, if only one works,
   the interrupt is switched for both drivers together. The driver therefore maps outcomes
   itself: a harness-initiated stop → `timeout` (cost from the result line if present, else
   `null` + imputed); a process that ends without a result line for any other reason →
   `agent_error`. POSIX exit codes are never interpreted.
   Save the prompt to `prompts/<call_name>.md` and its sha256 (and the sha256 of the combined
   system prompt) in the `PhaseCall`.
2. Stream stdout to `transcript/<call_name>.jsonl` **verbatim**. Parse as it arrives:
   - `system` / `init`: assert `model.startswith(limits.model)` (a dated snapshot of the pinned
     id is accepted and recorded as `resolved_model`), record `claude_code_version` (assert it
     equals the pinned version), `permissionMode`, `slash_commands`; mismatch → abort the call
     as `harness_error`.
   - `system` / `api_retry`: count `error == "rate_limit"` (or `error_status == 429`) into
     `rate_limit_retries`; everything else (`overloaded`, `server_error`, …) into
     `other_retries`. Claude Code retries these internally.
   - `assistant` messages: count `tool_use` blocks → `tool_calls`; count `tool_result` blocks
     with `is_error` → `tool_errors`; remember the last text block; set `asked_question=True`
     if a `tool_use` block is named `AskUserQuestion`.
   - final `result` message: read `subtype`, `session_id`, `num_turns`, `duration_ms`,
     `duration_api_ms`, `total_cost_usd`, `usage.{input_tokens,output_tokens,
     cache_read_input_tokens,cache_creation_input_tokens}`, `permission_denials` (an entry
     naming `AskUserQuestion` also sets `asked_question`), and **`modelUsage`** (camelCase in
     stream-json; `model_usage` exists only inside the SDK's usage report). Sum sub-agent
     spend into the totals. **Assert every `modelUsage` key starts with `limits.model`**; a
     `claude-haiku-*` key is background usage — record it as `background_models` — any other
     model means a fallback happened: flag `model_drift=True` and treat the call as
     `harness_error` (the pinned-model rule was violated).
   - **Usage limit** (subscription): the call is `usage_limited` — not an agent failure; the
     attempt is kept under `<run>/usage_limited/`, the trial re-queued, and it is not counted in
     the primary metric (the sensitivity check uses it, D-028); the scheduler pauses and probes
     (`specs/auth-and-usage.md` §3) — when the result/error text matches `hit your (session|
     weekly|Opus|Sonnet) limit` (a `rate_limit_event`/`error: rate_limit` line naming the plan
     quota counts too), **or** when the call ends without a `success` result, without an
     explaining subtype, and the **probe** says the service is unavailable. The probe is skipped
     for `success`, `error_max_turns` and `error_max_budget_usd` (already explained) and runs
     right after any other ending (no `result` line, `is_error`, other error subtypes):
     `claude.exe -p "ping" --tools "" --max-turns 1 --model <the call's model>` through the
     same launch path, transcript kept **outside the trial** at
     `<run>/probes/<ts>-<arm>-<task>-t<k>-<n>.jsonl` (never wiped; `abb audit` recounts pauses
     from these). Outcomes: limit text or 429 → `usage_limited` and the scheduler pause loop;
     401/403 → the **run** aborts at once with `aborted_reason: auth` (trial directory kept;
     message points at `abb auth check`); model id rejected or `init.model` mismatch → the run
     aborts with `aborted_reason: model`; any other probe failure (proxy, launcher) →
     `harness_error` (re-queued once); probe succeeds → the call's own classification stands.
     The exact `-p` output on a limit is undocumented — Phase 4 records the first real
     occurrence verbatim in `reference/verified.md` before any matrix run.
   - A call with **no `assistant` message at all** is never `agent_error`: `usage_limited` when
     the probe fails, `harness_error` (re-queued once) when it succeeds.
   - A call that ends with **no** `result` line after at least one `assistant` message (killed,
     hung, retries exhausted) and a succeeding probe is `agent_error` with `cost_usd = None`. The driver also computes `cost_usd_imputed` from the
     per-message `usage` blocks seen so far and the model's list price, so means are not biased
     downward for the arm that is killed more often; reports show both.
3. **Nudge protocol** (the measurable stand-in for "human interventions"):
   - The call *needs a nudge* if `subtype == "success"` and any of:
     a. `asked_question` is true (AskUserQuestion was invoked — in `-p` with no permission host
        the call is denied, the model is told nobody can approve it, and the run continues; the
        denial appears in `permission_denials`), or
     b. the last assistant text matches the question heuristic (ends with `?`, or contains one
        of: "should I", "do you want", "which option", "let me know", "please confirm",
        "would you like", "clarify") — **disabled for calls that return a structured artifact**
        (S2A read-only stages, whose formats legitimately contain "Unknowns"), or
     c. `is_implementing_call` and the workspace diff is empty.
     Which calls are "implementing" is an arm property: plain → its one call; Spec Kit →
     `speckit-implement`/`speckit-bug-fix`; S2A → `implement` tasks and `fix`.
   - If needed and both caps allow (`max_interventions` = 2 per call, `max_interventions_per_trial`
     = 4 per trial, identical for every arm): resume the same session with the fixed text
     > "No human is available. Make reasonable assumptions, state them briefly, and proceed to
     > complete the task end to end without asking further questions."
     and increment both counters; repeat the check on the new result.
   - Nudges count against the same turn/USD/time budgets.
   - Each nudge is a separate `claude -p --resume` process. Its stream-json goes to
     `transcript/<call_name>.nudge<k>.jsonl`, listed in `PhaseCall.nudge_transcript_paths`; its
     turns, tool calls, tokens and cost are **added into the same `PhaseCall`** (same
     `session_id`); the trigger and text go into `PhaseCall.interventions_log`.
   - Decision D-005: `AskUserQuestion` stays available — do **not** pass
     `--permission-prompts none` — so the question signal stays observable.
4. Map `subtype`/exit code → `PhaseCall.subtype`; the adapter maps to `ExitReason`.
5. Return `PhaseCall`. Never raise on agent failure; raise only on harness errors (platform failure,
   transcript unparsable).

**Source of truth.** The verbatim transcripts are the record; `run.json` is derived. Phase 4
ships `abb audit <run_id>`, which recomputes turns, cost, tool calls, the `init` model and
version, `modelUsage` keys and Σ turns ≤ `max_turns_total` from the transcripts of **every**
arm (including the orchestrator's) and fails on any mismatch with `run.json`/`calls.jsonl`.
It also **fails if any file under the run directory** (transcripts, probes, prompts, artifacts,
diffs, logs) contains the value of `ABB_OAUTH_TOKEN` or matches `sk-ant-[a-z]+\d{2}-` (OAuth `oat`, API `api`, `admin` keys); the
failure names the file, never the match (D-026). Nothing leaves the machine before audit passes.

## Assisted mode (optional, dev tasks only)

`abb run --assisted` replaces the fixed nudge with a human: at every nudge point the harness
prints the agent's last message, reads one reply from stdin, sends it with `--resume`, and
records `{source: "human", type: clarification|correction|environment, text}` in
`PhaseCall.interventions_log` (the counters still increment). Assisted trials are stored under
a run labelled `assisted-*` and reported in their own table; they never mix with autonomous runs
and are never run on `split: test` tasks. If this is not built, list it under non-goals in the
README.

## Default limits (`benchmark/config/limits.yaml` is the source of truth)

```yaml
default:
  timeout_minutes: 45
  max_turns_total: 200
  max_usd: 15.0
  max_interventions: 2             # nudges per headless call
  max_interventions_per_trial: 4   # nudges per trial, all calls together (comparable across arms)
  # no global per-call turn cap: arms split max_turns_total in abb/arms/<arm>/config.yaml
  grade_timeout_minutes: 30        # used by the grader only
profiles:
  dev:                             # cheaper while developing the harness
    model: claude-sonnet-5-5
    max_usd: 5.0
  final:
    model: claude-opus-5-5
```

The `Limits` dataclass in `abb/arms/base.py` has the same fields. **Binding limits across arms
are wall-clock and USD**; the turn budget is also identical but turns are *reported*, not
treated as comparable work units (an orchestrator-run Gradle gate costs no turn; a plain-arm
Gradle run does — see fairness-protocol.md).

The plain arm gets the whole total in one call (`--max-turns 200`). Multi-call arms split it
(Spec Kit: 15/15/15/120/20/remaining; S2A: per `pipeline.yaml`). A call that ends in
`error_max_turns` gets no continuation.

## Smoke test (Phase 0 gate)

Through the harness launch path (`abb ws smoke`, which builds the agent environment block exactly
as a trial would and runs the pinned `claude.exe`), with the block carrying
`CLAUDE_CODE_OAUTH_TOKEN` (mapped from `ABB_OAUTH_TOKEN`) and **no** `ANTHROPIC_API_KEY`; the
equivalent PowerShell by hand (set the variable for that shell only). Run it only in a **fresh
PowerShell 7 window**, never from inside a chat: a desktop-app chat's shell carries ~29
`CLAUDE_CODE_*`/`ANTHROPIC_*` variables (e.g. `CLAUDE_CODE_ENTRYPOINT=claude-desktop`,
`ANTHROPIC_BASE_URL`, `CLAUDE_CODE_CHILD_SESSION`) that a child `claude.exe` would inherit, so the
fixture would not match a trial. `abb ws smoke` builds the block from scratch and is unaffected.

```powershell
$env:CLAUDE_CODE_OAUTH_TOKEN = $env:ABB_OAUTH_TOKEN      # this shell only; never set it at user level
& "$env:USERPROFILE\.local\bin\claude.exe" -p --output-format stream-json --verbose --model claude-sonnet-5-5 `
  --max-turns 3 --permission-mode bypassPermissions "Print the current directory and exit." `
  | Tee-Object benchmark\tests\fixtures\transcripts\smoke-success.jsonl | Select-Object -Last 1 `
  | ConvertFrom-Json | Select-Object subtype, total_cost_usd, num_turns, session_id, usage, modelUsage
```

Must print a `result` with `subtype: "success"` whose `modelUsage` keys start with the
configured id, and whose `total_cost_usd`/`usage` fields are present under subscription auth
(record this; if absent, the driver estimates from per-message usage and `config/prices.yaml`).
Run it once with `--model claude-opus-5-5` and once with `claude-sonnet-5-5`: whichever the plan
accepts decides D-001. Also run `claude.exe auth status` through the same launch path and
record `authMethod`. Repeat with `--max-turns 1` and a prompt that needs two tool calls → save as
`smoke-maxturns1.jsonl` (`subtype: "error_max_turns"`). Third: `abb ws smoke --deadline 20
"Count slowly to 100 using the shell"` → at 20 s the launcher sends Ctrl+Break (and, in a second run,
Ctrl+C) → save as `smoke-interrupt.jsonl` and record in `reference/verified.md` whether a
`result` line was written and what the exit code was for each signal (this decides whether timed-out trials carry a measured or an imputed
cost; either way it is applied identically to every arm). These three files are the parser
fixtures Phases 4 and 6 use. Fourth, the **scrub check** (not saved as a fixture): an `abb ws smoke` prompt that asks the
agent to run, in Bash, `[ -n "$CLAUDE_CODE_OAUTH_TOKEN" ] && echo SET || echo UNSET` and, in
PowerShell, `if ($env:CLAUDE_CODE_OAUTH_TOKEN) {'SET'} else {'UNSET'}`, and to print both outputs.
Both must print `UNSET`. The commands print a word, never the value, so a failed scrub cannot
leak the token into the transcript; grep that transcript for the token value as well. If either prints `SET`, stop: the trial env needs another way to keep the token out of
subprocesses before any agent run. If a model id is rejected, try the current ids from the model docs with `claude.exe --model <id> -p "ping"`
(there is no API key to query `/v1/models`), update D-001 and `config/limits.yaml`, and continue. Record `claude --version` in `reference/verified.md`.
