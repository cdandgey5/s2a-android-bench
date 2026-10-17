# RUN-ALL — one Claude Code session builds everything (autopilot)

This is the default way to run the plan: **one Claude Code session** (the desktop app's Code tab
or `claude.exe` in a terminal, opened on `%USERPROFILE%\abb-src`) executes Phases 0 → 10 in
order, by itself, stopping only where a human is genuinely required. A "chat"/"session" here is
always a Claude Code session, never claude.ai. Nothing needs an API key (`specs/auth-and-usage.md`).

**Kickoff prompt** (the only thing you type):

```
Read AGENTS.md, then phases/RUN-ALL.md, and run the plan in autopilot: execute every phase in
the order RUN-ALL.md gives, from the phase docs/HANDOFF.md names (Phase 0 if it is still the
template). Apply the autopilot defaults for every decision; stop only at the hard stop points,
tell me exactly what you need, and wait. At every gate rewrite docs/HANDOFF.md and commit.
```

If the session is interrupted for any reason (usage limit, restart, you closed it), continue it
(`claude --continue`, or pick the session in the app's sidebar) — or open a new session and paste
the same prompt: `docs/HANDOFF.md` + `git log` carry the state, nothing in the old session is
needed. A long session auto-compacts its context (type `/compact` yourself when it feels heavy);
that is why every gate rewrites the handoff file and commits (`AGENTS.md` rule 12) — nothing
important lives only in the conversation.

## 1. Order (single session, branch `main`, no parallel branches)

| # | Phase | File | Hard stop points inside it |
|---|---|---|---|
| 1 | 0 Foundations | `phase-0-foundations.md` | S0 bootstrap missing (step 1) |
| 2 | 1 Environments + sandbox | `phase-1-environments.md` | S1 UAC prompt for `abb sandbox setup` (step 6); S1b usage-meter readings around the throughput probe (step 10b) |
| 3 | 2 Tasks & validation | `phase-2-tasks-and-validation.md` | S2 task review before validation (step 6) |
| 4 | 3 Grading | `phase-3-grading.md` | — |
| 5 | 4 Arm A + controls | `phase-4-arm-plain.md` | — (first results table → **report it**; MVP default applies, §3) |
| 6 | 7 Scale tasks + freeze split | `phase-7-scale-tasks.md` | S2 task review (steps 2–4); S3 validation nights (step 8) |
| 7 | 5 Spec Kit | `phase-5-arm-speckit.md` | — |
| 8 | 6 S2A orchestrator — bring-up only (steps 1–17) | `phase-6-s2a-orchestrator.md` | — |
| 9 | 8 Runner | `phase-8-runner.md` | — |
| 10 | 6 step 18 tuning (after `TASKSET.sha256`, `ABB_TUNING=1`) + 9 Analysis | `phase-6…` §18, `phase-9-analysis.md` | S4 manual labels (Phase 9 step 8) |
| 11 | 10 Release | `phase-10-release.md` | **S5 PREREG + freeze + `auth_mode` + fresh token** (steps 1, 3); S6 the held-out run batches (steps 2–4); S4 again (step 5) |

Why Phase 7 comes **before** Phases 5/6 here: it needs only Phase 2's tooling, and drafting every
test-split task (ticket, reference fix, hidden tests) *before any `s2a/` code exists* is the
strongest author-isolation this single-session mode can offer (`created_with_s2a_sha` stays at
the seed commit); its overnight validation runs (S3) also overlap the Phase 5/6 building. The
sparse worktree without `s2a/` and the `phase-N` branches exist only for the parallel-session
variant (`START-HERE.md` §3). Author isolation here is **ordering-only**: tasks drafted before
S2A, `tasks/TASKSET.sha256` committed (Phase 7 step 10) before any S2A tuning (Phase 6 step 18),
tuning under `ABB_TUNING=1`, and `abb tasks lint --setup-leak` re-run in Phase 10 step 1 after
S2A's one-time setup exists. Record `author_isolation: ordering-only (single session)` in
`docs/PREREG.md` sign-off and in the README limitations (D-019 says this is hygiene, not a
boundary, in either mode).

## 2. Autopilot rules

1. **Every session start** (first or replacement): `git status`, `git log --oneline -20`, read
   `docs/HANDOFF.md`; if the tree holds uncommitted work the handoff does not mention, inspect
   it before continuing; re-run the last passed gate's commands; then continue from the step the
   handoff names (a template handoff means Phase 0 step 1).
2. **Gate → handoff → commit → next phase.** When a phase's acceptance gate passes: paste the
   gate output into the conversation, rewrite `docs/HANDOFF.md` (set `Mode: autopilot`),
   update the README status table, `git commit -m "phase N: <gate summary>"`, `git push`, and
   start the next phase at once. Do not ask "shall I continue?". If there is no remote or the
   push fails, commit anyway, note it in the handoff, and report it at the next stop point.
   **Also rewrite the handoff (with the exact step) before every long run or dev run and at
   every stop point**, so a session cut mid-phase loses at most the current step.
3. **A failing gate is worked, not skipped.** Fix and re-run. If the same gate fails three
   times for the same reason, or the fix needs something only the human has (admin, account,
   hardware), stop: write the handoff with the exact blocker and wait. Gates adjusted by a
   default (§3) are judged against the adjusted wording.
4. **Decisions use the defaults in §3** and are logged in `docs/DECISIONS.md` as
   `D-xxx (autopilot default)`; the human can overturn any of them later by editing the row and
   saying so. Never invent a different default.
5. **Hard stop points (§4)** are the only places to wait for the human. State what is needed in
   one short block (command to run, file to review, decision to make) and stop. When the human
   replies, re-check (`abb auth check`, `abb sandbox check`, `git status`, …) before continuing.
6. **Usage limits.** When the session itself hits a subscription limit, Claude Code stops; the
   human continues the session after the reset (`claude --continue`, or just type `continue`).
   Headless trials handle their own limits (`specs/auth-and-usage.md` §3). Dev runs and the
   canary go at the end of a work block, as the last thing before a natural pause. The account
   is on **Pro** (verified in Phase 1 step 10b's rationale): expect to hit limits; that is
   normal, not an error.
7. **Long runs** (`abb tasks validate --all --runs 3`, dev-set matrices, the held-out run) are
   started in the background and polled with `abb run status`; the laptop must not sleep
   (`docs/DAY-0.md` §2 `powercfg`). If the session goes idle while such a run is still going,
   the human comes back when it has finished (`abb run status` says so) and types `continue`.
8. **Never** work from the OneDrive folder, never print the token, never set
   `CLAUDE_CODE_OAUTH_TOKEN` or `ANTHROPIC_API_KEY` globally, never read test-split tasks while
   `ABB_TUNING=1`, never start the held-out run without S5.

## 3. Autopilot defaults (each logged as a decision when first applied) and the gates they adjust

| Decision | Default | Gate wording it changes |
|---|---|---|
| Repos | AntennaPod + Wikipedia Android (Phase 0 step 6 picks from the experiment; these two unless one fails the criteria) | — |
| Model | `claude-opus-5-5` pinned if the Phase 0 smoke test accepts it, else `claude-sonnet-5-5` for everything (D-001); dev on Sonnet | — |
| After the throughput probe (S1b) | Stay on the current plan; take the MVP cut **now** if the probe's weeks estimate says the dev runs alone exceed 8 weeks, else decide at the first results table (next row). Moving to Max is the human's call (say so, do not wait). | — |
| MVP cut (`PLAN.md` §9) | **Taken by default when the first results table exists** (end of Phase 4) unless S1b took it already. It takes §9 items 1 and 2 as written (2 repos; 24–30 tasks, authored 14 → 6) and item 6 (laptop only); it **replaces** item 3 (optional arms kept at 1 trial instead of dropped) and does **not** take item 4 (Spec Kit kept, at 1 trial) or item 5 (see the S4 row). The human can restore the full plan, or cut deeper per §9, by saying so. | Phase 7: skip step 1 (no repos 3/4); targets N = 24–30, "no repo > 50 %", authored 6, other rows scaled; gate "≥ 24 validated". Phase 8/10: optional arms at 1 trial. |
| Task drafting | Mined tasks are triaged and tickets rewritten by the agent; authored tasks are drafted by the agent (problem, reference fix, tests). Every task records `drafted_by: agent` and `drafted_with_model: <id>` in `task.yaml` and is **reviewed by the human at stop point S2** before validation; the README, PREREG and `specs/fairness-protocol.md` state that tasks were model-drafted and human-reviewed. | — |
| Manual failure labels (S4) | If the human replies `skip`, labels are LLM-only and the report marks the labeller **uncalibrated** (`agreement: not measured`). This is the *inverse* of `PLAN.md` §9 item 5 (which drops the labeller and keeps a hand-labelled sample); the report says so. | Phase 9 gate "labeller calibrated against ≥ 20 manual labels" and Phase 10 step 5 "≥ 80 %" become "labels generated; agreement reported as not measured". |
| Defender exclusion, Dev Drive, Windows VM | Not used unless the human says so. | — |
| Held-out run `auth_mode` | **No default.** S5 is a hard stop. | — |
| Rerun after a harness bug | PREREG rules; never on autopilot's own initiative beyond what PREREG permits. | — |

## 4. Hard stop points (the human must act)

| Id | Where | What the agent says | What you do |
|---|---|---|---|
| S0 | Phase 0 step 1 | which Day-0 item is missing and the exact command | fix it (`docs/DAY-0.md`), reply `done` |
| S1 | Phase 1 step 6 | "about to run `abb sandbox setup`; a UAC prompt will appear — accept it" | be at the keyboard, accept the prompt, reply `done` |
| S1b | Phase 1 step 10b | "read the usage meter (claude.ai → Settings → Usage) and reply with session % and weekly %; do not chat until I report the probe finished" — twice, before and after | reply with the two readings; the agent computes the estimates and applies the S1b default |
| S2 | Phase 2 step 6; Phase 7 steps 2–4 | "N drafted tasks are listed in `tasks/TRIAGE.md`; review `problem.md`, `gold.patch` and `test.patch` of each" | read every one (this is the benchmark; ~2–4 h for dev5, a day for the full set), edit or reject in place, reply `approved` (or `approved, dropped: <ids>`) |
| S3 | Phase 7 step 8 | "starting `abb tasks validate --all --runs 3` (~N h); keep the laptop on AC with sleep off" | reply `go`; come back when it has finished and type `continue` if the session is idle |
| S4 | Phase 9 step 8; Phase 10 step 5 | "20–30 failure bundles are ready in `labels/`; label them blind, or reply `skip`" | label (≈1–2 h) or `skip` (labeller stays uncalibrated) |
| S5 | Phase 10 steps 1 and 3 | PREREG draft filled with the defaults, plus the open fields: `auth_mode`, plan name, expected windows, final arm list; then "create a fresh `claude setup-token` and store it as `ABB_OAUTH_TOKEN`" (D-026) | fill the fields, approve the freeze tag, make the fresh token, reply `done` |
| S6 | Phase 10 steps 2–4 | the usage-window schedule for the held-out run and the `abb run …` command | reply `go` per batch; the run spans days of windows; type `continue` when a batch has finished if the session is idle |

Everything else — installs under `ABB_HOME`, Gradle builds, mining, drafting, validation, dev
runs, writing code, tests, reports — is the agent's. Your own time: S2 (reading every task),
S4 (labels, optional), the decisions at S1b/S5, and being at the keyboard for S1 — plus
continuing the session after each usage-limit stop and each long run.

**Time.** Serial, one session: 15–18 weeks of calendar for the full plan, roughly 12–14 with
the MVP default (`PLAN.md` §5); most of it is Gradle, validation nights and usage windows, not
your attention.

## 5. If you prefer phase-by-phase sessions

`START-HERE.md` §2 keeps the per-phase prompts (one session per phase, parallel branches for
Phases 5/6/7, a merge session before Phase 8; ~11 weeks because the branches run in parallel).
They are the fallback when a single session becomes unwieldy or when you want to review each
gate before the next phase starts. Both modes share the same files and the same handoff; you can
switch at any gate.
