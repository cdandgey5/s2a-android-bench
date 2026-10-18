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
