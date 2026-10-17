# Phase 5 — Arm B (GitHub Spec Kit)

**Goal.** Spec Kit driven headlessly per `specs/speckit-automation.md`, with one-time per-repo
setup accounted separately, completing dev5 end to end.

**Prerequisites.** Phase 4 gate. Spec Kit CLI present in the image (Phase 0).

**Effort.** ~1 week part-time. Can run in parallel with Phase 6 (separate folders).

## Deliverables

```
benchmark/abb/arms/speckit/arm.py
benchmark/abb/arms/speckit/config.yaml          # path_by_category, turn caps, prompts for each call
benchmark/abb/arms/speckit/prompts/*.md         # constitution.md, plan-suffix.md, …
benchmark/tests/test_speckit_arm.py             # unit: call sequence per category; template inlining fallback
reference/verified.md                           # + Spec Kit version, init flags, command names, command file location
docs/DECISIONS.md                               # + D-006 skip clarify/checklist/analyze; D-007 bug path for bugfix tasks
```

## Steps

1. **Verify Spec Kit** inside the image: `specify --version`, `specify init --help`,
   `specify extension --help`. In a scratch workspace run
   `specify init --here --force --non-interactive --integration claude --script sh --ignore-agent-tools`
   and `specify extension add bug`; list what was created (`find .specify .claude -maxdepth 3`).
   Record exact command names and file locations. Pin `SPEC_KIT_REF` to the tag you verified
   and rebuild images.
2. **Slash-command expansion check** (spec step "Slash command invocation check"). Record the
   mechanism (native expansion vs template inlining) and implement both in the arm with a
   config switch; default to whichever worked. Gate: the `init` event's `slash_commands` lists
   `speckit-specify` (this is also the canary for a future `--bare`-by-default CLI).
3. **One-time setup** (`one_time_setup`), in a workspace at `repos.<repo>.build.setup_commit`
   (not `cache_commit`; see `specs/fairness-protocol.md`, "One-time setup artifacts"): init +
   bug extension + constitution call. Store the produced `.specify/` + command files under
   `results/<run>/setup/speckit-constitution/<repo>/artifacts/` through Phase 4's `setup.py`
   (cache key: setup kind, repo, setup_commit, image digest, prompt hash); the cost is recorded
   in the run that first produced it.
4. **Per-task `run`**: copy setup artifacts into `/work`, choose the path by category, execute
   the call table with `--resume` across calls, nudge protocol per call, stop when limits are
   exhausted, implement/converge loop ≤ 1 extra implement. Copy `specs/**` and `.specify/**`
   to `artifacts/`. Produce the scoped diff (these folders are in `diff_exclude`).
5. **Partial-artifact robustness.** If `speckit-specify` ends with `error_max_turns`, continue
   to `speckit-plan` anyway; if `/speckit-implement` finds no `tasks.md`, the transcript will
   show it — that is a legitimate failure of the arm, not of the harness. Note it in
   `run.json.notes`.
6. **Unit tests**: given category → expected call names and prompts; fallback inlining produces
   the right text with `$ARGUMENTS` substituted.
7. Run dev5 × 1 on Sonnet 5.5; grade; report. Compare cost/turns per call to the plain arm in
   `docs/RUNS.md`.
8. Commit `phase 5: speckit arm`.

## Acceptance gate

```
uv run pytest -q tests/test_speckit_arm.py
uv run abb run --arm speckit --tasks dev5 --trials 1 --model claude-sonnet-5-5 --label dev5-speckit-1 --grade
uv run abb report <run_id>            # 6 rows (dev5) + a "setup" section with the constitution cost per repo
ls results/<run_id>/speckit/*/t1/artifacts/     # spec.md / plan.md / tasks.md or .specify/bugs/* present
```

Passes when all five tasks complete (any grade), artifacts are captured, setup cost is listed
separately, and `reference/verified.md` documents the exact Spec Kit commands used.

## Pitfalls

- Spec Kit may create a git branch or commit (`feature.json`, branch naming). The scoped diff
  is computed against the `base` tag, so branches don't matter; but if it commits, `git diff
  base` must use the working tree **and** commits: use `git add -A -N && git diff --binary base`
  (working tree vs base tag) — this already includes committed changes.
- Spec Kit scripts assume `bash` and may call `git` — available in the image.
- The constitution should describe the *existing* codebase; check the first one by hand and
  tune `prompts/constitution.md` (allowed: it is one-time setup, not task-specific).
