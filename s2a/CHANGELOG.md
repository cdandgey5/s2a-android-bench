# s2a changelog

Bring-up (making the pipeline run at all) and tuning (any change judged by results) are logged
here. Tuning starts only after the task set's hash is committed and runs on development tasks only,
one change at a time, with before/after numbers. The prompt hashes in each run's `calls.jsonl` are
the audit trail.

## Bring-up

### 2026-10-18 — v0
- Stages intake → map → locate → reproduce → spec → plan → implement (one fresh session per task,
  one commit per task) → verify → fix (≤ 2 loops) → report; gates in `pipeline.yaml`, commands
  from `profiles/android.yaml`; state and `progress.md` under `.s2a/runs/<id>/`; `s2a resume`.
- Driver: headless `claude -p` per stage, the nudge protocol, a probe after unexplained endings,
  per-process cost; an interrupted call is recorded as `timeout` before the interrupt propagates.
- CLI: `s2a run "<prompt>" | --prompt-file F`, `resume`, `status`, `map [--refresh | --print-key]`,
  `show`.
- 44 unit tests with fake Claude and fake Gradle (stage order, gates, resume, fix loop,
  reproduction gate failing then passing, weakened-test detection).

### 2026-10-19 — bring-up fixes from the first real runs (D-051)
- A call's work reaches its gate even when the call spent the last turns.
- intake, locate, spec and plan retry once on a gate failure; no retry with fewer than 5 stage turns left.
- The reproduction gate reports the end of the Gradle output when the tests produced no results.
- Interrupted calls are recorded; slash-command names are not questions (D-050).
- Reproduction tests are the @Test methods a file has now and did not have at HEAD (whole-file comparison; the
  diff-line rule picked up an existing passing test in e2e `20261019-0310`); gate log numbering continues after a resume.

### 2026-10-19 — bring-up fixes from the first dev5 run (D-052)
- locate candidates skip URLs, elided paths and files marked new; a retry gets at least 5 turns of the total budget.
- Without a map, task discovery reads tasks that have no description; the compile task follows the test task's name.
- Gate messages quote Gradle's error lines from stdout and stderr; per-task call counters are kept out of `stages`.

### 2026-10-19 — after the Phase 6 gate run (D-053)
- dev5 × 1 (`20261019-1112-dev5-s2a-2`, s2a `ed8f6f9`): s2a 6/6, s2a-nomap 5/6, s2a-noverify 4/6 resolved.
- locate candidates skip host names; a failed read-only artifact is reported from the final answer.

## Tuning (Phase 6 step 18; `split: dev` only, `ABB_TUNING=1`)

### 2026-10-20 — verifier calibration, preliminary (no change made)
- Final verify verdict vs the hidden-test grade on every s2a / s2a-nomap trial with a verdict in
  `20261019-1112-dev5-s2a-2` and `20261020-0036-p8-resume-test` (dev5): 21/22 agree (ACCEPT & resolved 20,
  REJECT & unresolved 1, REJECT & resolved 1: antennapod-0003 t1, the trial that hit its time limit).
- Above the 5/6 bar, but only 2 unresolved trials had a verdict: REJECT is barely tested. Re-check on the
  dev baseline (`dev-baseline-1`, Wikipedia tasks included) before deciding anything about `verify.md`.

### 2026-10-21 — tuning 1: verify checks the original request (s2a `1ee1ad9`)
- **Change:** `prompts/verify.md` adds a "Request requirements" section (one R line per behavioural requirement
  of the original request; R FAIL forces REJECT like AC/UB) and two short scored examples (one REJECT, one
  ACCEPT); `parse.verdict` counts R lines. New `s2a verify <run>` re-runs the stage (no fix loop).
- **Why:** on `20261020-2049-dev-baseline-1` the verifier ACCEPTed 2 unresolved s2a trials whose spec had
  dropped a requirement of the request; the verifier only checked the spec's criteria.
- **Calibration** (`scripts/verify_calibration.py`, run `20261021-1722-verify-calibration`, 3 resolved + 3
  unresolved dev trials, verify re-run on each final diff): **4/6 before -> 5/6 after** (bar: 5/6).
  wikipedia-0006/t1 ACCEPT -> REJECT (R3: completion until June 25 not implemented; R12: the requested field is
  never used); antennapod-0003/t1 still a false ACCEPT; the 3 resolved stay ACCEPT. Cost est. $0.93.
- **After-run** `20261021-1802-dev-s2a-tune1` (s2a, dev x 2, Sonnet 5.5; one trial re-run after D-056): **pass@1 0.75 -> 0.75**, pass^2 0.60 -> 0.70, est. $1.10 -> $1.11 per trial (baseline s2a in `20261020-2049-dev-baseline-1`). Neutral on resolution at this n (10 tasks x 2; detectable delta ~0.38); kept for the calibration gain. The fix loop does not turn the new REJECTs into fixes (wikipedia-0006/t2). s2a fixes wikipedia-0007's URL but not the shared `normalizeLanguageCode` mapping the other arms extend (both trials).

### 2026-10-21 — tuning 2 (prepared, not yet installed): files to create get their own locate section
- **Change:** `prompts/locate.md` adds `## Files to create`; the ranked candidates are existing paths only; the
  `listed_paths_exist` gate message says where a new file belongs.
- **Why:** feature tasks list the file they must create among the candidates and fail the gate even after the
  retry (antennapod-0004: `20261020-2049-dev-baseline-1` s2a/t1 and `20261021-1802-dev-s2a-tune1` s2a/t1).
- **Measured after tuning 1's after-run completes** (one change at a time).
